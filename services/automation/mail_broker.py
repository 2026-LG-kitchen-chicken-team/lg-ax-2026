"""Private Gmail gateway. Model/Worker code receives no mail credentials.

Official references checked 2026-10-05:
https://developers.google.com/workspace/gmail/api/auth/scopes
https://developers.google.com/workspace/gmail/api/guides/sending
https://developers.google.com/identity/protocols/oauth2/native-app

No chat/browser token is exported. An operator supplies independently authorized
external OAuth credentials, or a separately verified fixed connector transport.
Replies are correlated reports, never authenticated GitHub approvals or commands.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import sqlite3
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses
from pathlib import Path

from services.automation.artifacts import secret_check
from services.automation.github_bridge import exclusive_bridge_lock
from services.automation.isolation import _plain_directory, regular_file
from services.automation.pm import canonical, protected_path
from services.automation.state import MEMBER_NAMES, PM, REPO

SCOPES = {"https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"}
ACTION = re.compile(r"pm-[0-9a-f]{40}")
MESSAGE = re.compile(r"[A-Za-z0-9_-]{1,100}")
ADDRESS = re.compile(r"[^\s@<>\r\n,;]+@[^\s@<>\r\n,;]+\.[^\s@<>\r\n,;]+")
SHA = re.compile(r"[0-9a-f]{40}")


class MailError(ValueError):
    """Sanitized gateway failure; never expose API response bodies or secrets."""


def _private(path):
    value = protected_path(Path(path))
    _plain_directory(value.parent, "mail private parent")
    if value.exists():
        observed = value.lstat()
        if stat.S_ISREG(observed.st_mode) and observed.st_nlink != 1:
            raise MailError("mail private files cannot be hard-linked")
    return value


def _json(path, maximum=2 * 1024 * 1024):
    return json.loads(regular_file(_private(path), maximum=maximum))


def _identifier(value):
    if not isinstance(value, str) or not MESSAGE.fullmatch(value):
        raise MailError("invalid immutable Gmail identifier")
    return value


def _address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value) or "noreply" in value.lower():
        raise MailError("invalid private mail address")
    return value.lower()


def _headers(message):
    result = {}
    for row in message.get("payload", {}).get("headers", []):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not isinstance(row.get("value"), str):
            raise MailError("invalid Gmail message headers")
        result.setdefault(row["name"].lower(), []).append(row["value"])
    return result


def _one(headers, name):
    values = headers.get(name, [])
    if len(values) != 1:
        raise MailError("required single mail header missing or ambiguous")
    return values[0]


def _mailboxes(value):
    return [_address(address) for _, address in getaddresses([value])]


class GmailREST:
    """Bounded stdlib REST client with no ambient ADC/chat/browser auth fallback."""

    supports_custom_message_id = True

    def __init__(self, token_file, *, opener=None, clock=time.time):
        self.token_file = _private(token_file)
        self.opener, self.clock = opener or urllib.request.urlopen, clock
        self.access_token, self.expiry = None, 0

    def _access(self):
        if self.access_token and self.expiry > self.clock() + 30:
            return self.access_token
        credentials = _json(self.token_file, 32768)
        if (credentials.get("type") != "authorized_user" or
                set(credentials.get("scopes", [])) != SCOPES or
                credentials.get("token_uri", "https://oauth2.googleapis.com/token") != "https://oauth2.googleapis.com/token"):
            raise MailError("separately authorized narrow Gmail OAuth credentials required")
        fields = {key: credentials.get(key) for key in ("client_id", "client_secret", "refresh_token")}
        if any(not isinstance(value, str) or not value or len(value) > 8192 for value in fields.values()):
            raise MailError("operator Gmail OAuth setup is incomplete")
        raw = urllib.parse.urlencode({**fields, "grant_type": "refresh_token"}).encode()
        request = urllib.request.Request("https://oauth2.googleapis.com/token", data=raw,
                                         headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        result = self._open(request)
        if (not isinstance(result.get("access_token"), str) or not result["access_token"] or
                type(result.get("expires_in")) is not int or not 60 <= result["expires_in"] <= 86400):
            raise MailError("Gmail OAuth refresh result was not verified")
        if "scope" in result and set(result["scope"].split()) != SCOPES:
            raise MailError("Gmail OAuth grant scopes differ from approved narrow setup")
        self.access_token, self.expiry = result["access_token"], self.clock() + result["expires_in"]
        return self.access_token

    def _open(self, request):
        try:
            with self.opener(request, timeout=10) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise MailError("bounded Gmail response exceeded")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise MailError("invalid Gmail response")
                return result
        except (OSError, urllib.error.URLError, ValueError):
            # No automatic HTTP retry, especially after messages.send.
            raise MailError("Gmail request failed; reconcile before any repeated send") from None

    def request(self, method, route, body=None, params=None):
        if (method not in {"GET", "POST"} or not re.fullmatch(r"(?:profile|messages(?:/[A-Za-z0-9_-]+)?|messages/send|threads/[A-Za-z0-9_-]+)", route) or
                (method == "POST" and route != "messages/send")):
            raise MailError("Gmail gateway route is outside its fixed read/send allowlist")
        url = "https://gmail.googleapis.com/gmail/v1/users/me/" + route
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = canonical(body).encode() if body is not None else None
        return self._open(urllib.request.Request(url, data=data, method=method,
                          headers={"Authorization": "Bearer " + self._access(), "Content-Type": "application/json"}))


class MailBroker:
    """Persistent delivery and immutable, deduplicated report-only inbox events."""

    def __init__(self, config, *, gmail=None, clock=time.time):
        if config.get("schema_version") != 1 or config.get("repo") != REPO or config.get("pm_account") != PM:
            raise MailError("fixed LG PM mail configuration required")
        self.config, self.clock = config, clock
        self.root = _private(config["state_dir"])
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "mail.sqlite3"
        self.outbox_dir = _private(config["outbox_dir"])
        self.broker_state = _private(config["broker_state_file"])
        contact_raw = regular_file(_private(config["contacts_file"]), maximum=65536)
        if hashlib.sha256(contact_raw).hexdigest() != config.get("contacts_sha256"):
            raise MailError("private approved contacts changed")
        contacts = json.loads(contact_raw)
        sender = contacts.get("sender", {})
        self.sender = _address(config.get("sender_email"))
        if _address(sender.get("email")) != self.sender:
            raise MailError("private PM sender differs from approved mail account")
        self.contacts = {}
        for account, contact in contacts.get("contacts", {}).items():
            if (account not in MEMBER_NAMES or account == PM or contact.get("name") != MEMBER_NAMES[account] or
                    not contact.get("source") or not contact.get("verified_at")):
                raise MailError("named team contact needs independent private verification")
            self.contacts[account] = _address(contact.get("email"))
        if len(set(self.contacts.values())) != len(self.contacts):
            raise MailError("team mail addresses must identify distinct contacts")
        self.gmail = gmail or GmailREST(config["oauth_token_file"], clock=clock)
        self.custom_message_id = getattr(self.gmail, "supports_custom_message_id", True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deliveries(
                    action_id TEXT PRIMARY KEY, assignment_id TEXT, owner TEXT, task_id TEXT,
                    fingerprint TEXT, mime BLOB, rfc_id TEXT, status TEXT,
                    gmail_id TEXT, thread_id TEXT, receipt TEXT);
                CREATE TABLE IF NOT EXISTS inbox(message_id TEXT PRIMARY KEY, body_digest TEXT,
                    disposition TEXT, event TEXT);
                CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    previous_digest TEXT, digest TEXT, payload TEXT);
            """)

    @contextmanager
    def connect(self):
        _private(self.database)
        connection = sqlite3.connect(self.database, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _journal(self, db, event):
        last = db.execute("SELECT digest FROM journal ORDER BY seq DESC LIMIT 1").fetchone()
        previous = last[0] if last else "0" * 64
        payload = canonical(event)
        digest = hashlib.sha256((previous + payload).encode()).hexdigest()
        db.execute("INSERT INTO journal(previous_digest,digest,payload) VALUES(?,?,?)", (previous, digest, payload))

    def _verify_journal(self, db):
        previous = "0" * 64
        deliveries, inbox = {}, {}
        for prior, digest, payload in db.execute("SELECT previous_digest,digest,payload FROM journal ORDER BY seq"):
            if prior != previous or digest != hashlib.sha256((previous + payload).encode()).hexdigest():
                raise MailError("mail journal integrity failed; operator reconciliation required")
            previous = digest
            event = json.loads(payload)
            if event["kind"] == "mail_prepared":
                if event["action_id"] in deliveries:
                    raise MailError("mail preparation journal identity was repeated")
                deliveries[event["action_id"]] = {**event, "status": "prepared"}
            elif event["kind"] == "mail_sending":
                row = deliveries[event["action_id"]]
                if row["status"] != "prepared":
                    raise MailError("mail journal attempted to resend an uncertain/sent delivery")
                row["status"] = "sending"
            elif event["kind"] == "delivery_receipt":
                deliveries[event["action_id"]].update(status=event["status"], rfc_id=event.get("rfc_message_id"))
            elif event["kind"] == "mail_reply":
                inbox[event["event_id"][6:]] = event
        actual_deliveries, actual_inbox = set(), set()
        for row in db.execute("SELECT action_id,status,fingerprint,mime,rfc_id FROM deliveries"):
            actual_deliveries.add(row[0])
            event = deliveries.get(row[0])
            if (not event or event["status"] != row[1] or event["fingerprint"] != row[2] or
                    event["mime_sha256"] != hashlib.sha256(row[3]).hexdigest() or
                    (event.get("rfc_id") and event["rfc_id"] != row[4])):
                raise MailError("mail durable state differs from its append-only journal")
        for mid, digest, disposition, event_json in db.execute("SELECT * FROM inbox"):
            actual_inbox.add(mid)
            event = inbox.get(mid)
            if (not event or event["digest"] != digest or event["disposition"] != disposition or
                    event["event_sha256"] != hashlib.sha256(event_json.encode()).hexdigest()):
                raise MailError("mail inbox event differs from its immutable journal")
        if actual_deliveries != set(deliveries) or actual_inbox != set(inbox):
            raise MailError("mail durable state lost immutable journal records")

    def preflight(self):
        profile = self.gmail.request("GET", "profile")
        if _address(profile.get("emailAddress")) != self.sender:
            raise MailError("actual authenticated Gmail account is not the exact PM sender")
        return {"authenticated_pm_sender": True, "mail_sent": False,
                "contacts_verified": len(self.contacts), "reply_authority": "report_only"}

    def _source(self, outbox):
        path = _private(outbox)
        if path.parent != self.outbox_dir or path.suffix != ".json" or not ACTION.fullmatch(path.stem):
            raise MailError("notification must come from the exact private PM outbox")
        row = _json(path, 65536)
        assignment, owner = row.get("assignment", {}), row.get("recipient_account")
        state = _json(self.broker_state)
        intent = state.get("actions", {}).get(path.stem, {})
        action = intent.get("action", {})
        unit = state.get("units", {}).get("auto-" + path.stem[3:], {})
        aid = assignment.get("assignment_id")
        if (owner not in self.contacts or action.get("action") != "assign" or action.get("owner") != owner or
                intent.get("action_id") != path.stem or
                not isinstance(aid, str) or not re.fullmatch(r"PM-[A-Za-z0-9_-]{1,100}", aid) or
                unit.get("assignment_id") != aid or unit.get("task_id") != assignment.get("task_id") or
                action.get("task_id") != assignment.get("task_id")):
            raise MailError("mail assignment is not a fixed recorded PM action/unit")
        for key in ("purpose", "instructions", "acceptance", "requirement_ids"):
            if assignment.get(key) != action.get(key):
                raise MailError("mail content differs from the recorded approved assignment")
        secret_check(canonical(assignment).encode())
        return path.stem, assignment, owner

    def _mime(self, action_id, assignment, owner):
        aid = assignment["assignment_id"]
        rfc_id = "<lgax." + action_id + "@" + self.sender.split("@", 1)[1] + ">"
        subject = "[LGAX " + action_id + "] " + aid + " · " + MEMBER_NAMES[owner]
        issue_number = _json(self.broker_state)["actions"][action_id]["action"].get("issue_number")
        if type(issue_number) is not int or not 1 <= issue_number <= 1000000:
            raise MailError("recorded assignment Issue is not valid")
        report = {"action_id": action_id, "assignment_id": aid, "task_id": assignment["task_id"],
                  "status": "doing", "summary": "작업 경과", "next_action": "다음 행동"}
        text = (MEMBER_NAMES[owner] + "님, 정이량 PM의 LG AX 작업 배정입니다.\n\n" + assignment["purpose"] +
                "\n\n작업 지시\n" + "\n".join("- " + value for value in assignment["instructions"]) +
                "\n\n검수 조건\n" + "\n".join("- " + value for value in assignment["acceptance"]) +
                "\n\n담당 이슈: https://github.com/" + REPO + "/issues/" + str(issue_number) +
                "\n\n이 메일에 회신하면 PM에게 보고 자료가 전달됩니다. 회신은 승인·병합·최종완료를 실행하지 않습니다."
                "\n구조화 보고를 원하면 다음 예시의 상태를 doing/blocked/review_requested 중 하나로 작성하세요."
                "\nLGAX-REPORT\n" + canonical(report))
        if len(text) > 14000:
            raise MailError("outgoing assignment exceeds the complete verifiable mail body bound")
        message = EmailMessage(policy=policy.SMTP)
        for name, value in {"From": self.sender, "To": self.contacts[owner], "Subject": subject,
                            "Message-ID": rfc_id, "Date": formatdate(self.clock(), usegmt=True)}.items():
            message[name] = value
        message.set_content(text)
        message.add_alternative("<p>" + html.escape(text).replace("\n", "<br>") + "</p>", subtype="html")
        return message.as_bytes(), rfc_id

    def _receipt(self, db, action_id, *, status, message=None):
        assignment_id = db.execute("SELECT assignment_id FROM deliveries WHERE action_id=?", (action_id,)).fetchone()[0]
        receipt = {"status": status, "action_id": action_id, "assignment_id": assignment_id,
                   "verified_sent": status == "sent", "message_id": message.get("id") if message else None,
                   "thread_id": message.get("threadId") if message else None}
        if message:
            receipt["rfc_message_id"] = _one(_headers(message), "message-id")
            receipt["sent_metadata_sha256"] = hashlib.sha256(canonical({"id": message["id"], "threadId": message["threadId"],
                "labelIds": sorted(message.get("labelIds", [])), "headers": _headers(message)}).encode()).hexdigest()
            # The connector may choose its own immutable RFC Message-ID.
            db.execute("UPDATE deliveries SET rfc_id=? WHERE action_id=?", (_one(_headers(message), "message-id"), action_id))
        db.execute("UPDATE deliveries SET status=?,gmail_id=?,thread_id=?,receipt=? WHERE action_id=?",
                   (status, receipt["message_id"], receipt["thread_id"], canonical(receipt), action_id))
        self._journal(db, {"kind": "delivery_receipt", **receipt})
        return receipt

    def _verified_sent(self, message, stored):
        try:
            _identifier(message["id"])
            _identifier(message["threadId"])
            headers = _headers(message)
            expected = BytesParser(policy=policy.default).parsebytes(stored["mime"])
            actual_rfc = _one(headers, "message-id")
            rfc_matches = actual_rfc == stored["rfc_id"] if self.custom_message_id else bool(
                re.fullmatch(r"<[^\s<>@]{1,200}@[^\s<>@]{1,200}>", actual_rfc))
            body_matches = self.custom_message_id or (
                self._body(message.get("payload", {})).replace("\r\n", "\n") ==
                expected.get_body(preferencelist=("plain",)).get_content().replace("\r\n", "\n"))
            return ("SENT" in message.get("labelIds", []) and rfc_matches and body_matches and
                    not headers.get("cc") and not headers.get("bcc") and
                    _mailboxes(_one(headers, "from")) == [self.sender] and
                    _mailboxes(_one(headers, "to")) == [self.contacts[stored["owner"]]] and
                    str(make_header(decode_header(_one(headers, "subject")))) == str(expected["Subject"]))
        except (KeyError, MailError):
            return False

    def _stored(self, db, action_id):
        db.row_factory = sqlite3.Row
        value = db.execute("SELECT * FROM deliveries WHERE action_id=?", (action_id,)).fetchone()
        return dict(value) if value else None

    def _reconcile(self, db, stored):
        query = ("in:sent rfc822msgid:" + stored["rfc_id"][1:-1] if self.custom_message_id else
                 'in:sent subject:"LGAX ' + stored["action_id"] + '"')
        matches = self.gmail.request("GET", "messages", params={"q": query,
                                                               "maxResults": 10})
        if matches.get("nextPageToken"):
            return self._receipt(db, stored["action_id"], status="unknown")
        verified = []
        rows = matches.get("messages", [])
        if not isinstance(rows, list) or len(rows) > 10:
            raise MailError("Gmail Sent search exceeded its exact bounded result set")
        for row in rows:
            mid = _identifier(row.get("id"))
            message = self.gmail.request("GET", "messages/" + mid,
                                         params={"format": "metadata" if self.custom_message_id else "full"})
            if message.get("id") == mid and self._verified_sent(message, stored):
                verified.append(message)
        return self._receipt(db, stored["action_id"], status="sent" if len(verified) == 1 else "unknown",
                             message=verified[0] if len(verified) == 1 else None)

    def deliver(self, outbox):
        """Exactly one send attempt; uncertain attempts only search/reconcile."""
        with exclusive_bridge_lock(self.root / "mail.lock"):
            action_id, assignment, owner = self._source(outbox)
            fingerprint = hashlib.sha256(canonical({"assignment": assignment, "owner": owner,
                "to": self.contacts[owner], "from": self.sender}).encode()).hexdigest()
            self.preflight()
            with self.connect() as db:
                self._verify_journal(db)
                stored = self._stored(db, action_id)
                if stored and stored["fingerprint"] != fingerprint:
                    raise MailError("immutable mail assignment ID was reused with different content")
                if not stored:
                    mime, rfc_id = self._mime(action_id, assignment, owner)
                    db.execute("INSERT INTO deliveries VALUES(?,?,?,?,?,?,?,'prepared',NULL,NULL,NULL)",
                               (action_id, assignment["assignment_id"], owner, assignment["task_id"], fingerprint, mime, rfc_id))
                    self._journal(db, {"kind": "mail_prepared", "action_id": action_id, "fingerprint": fingerprint,
                                       "mime_sha256": hashlib.sha256(mime).hexdigest(), "rfc_id": rfc_id})
                    db.commit()
                    stored = self._stored(db, action_id)
                if stored["status"] != "prepared":
                    try:
                        return self._reconcile(db, stored)
                    except MailError:
                        return self._receipt(db, action_id, status="unknown")
                db.execute("UPDATE deliveries SET status='sending' WHERE action_id=?", (action_id,))
                self._journal(db, {"kind": "mail_sending", "action_id": action_id})
                db.commit()  # Persist uncertainty before the network side effect.
                try:
                    result = self.gmail.request("POST", "messages/send", {"raw": base64.urlsafe_b64encode(stored["mime"]).decode()})
                    mid = _identifier(result.get("id"))
                    message = self.gmail.request("GET", "messages/" + mid,
                                                 params={"format": "metadata" if self.custom_message_id else "full"})
                    if message.get("id") != mid or not self._verified_sent(message, stored):
                        raise MailError("actual Gmail SENT identity did not match the fixed assignment")
                    return self._receipt(db, action_id, status="sent", message=message)
                except (MailError, OSError, ValueError):
                    return self._receipt(db, action_id, status="unknown")

    def _body(self, payload, depth=0):
        if depth > 8 or not isinstance(payload, dict) or payload.get("filename"):
            return ""
        if payload.get("mimeType") == "text/plain":
            raw = payload.get("body", {}).get("data", "")
            if not isinstance(raw, str) or len(raw) > 32000:
                raise MailError("reply body exceeds its fixed bound")
            try:
                value = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", errors="strict")
            except (ValueError, UnicodeError):
                raise MailError("reply must be bounded UTF-8 plain text") from None
            if len(value) > 16000:
                raise MailError("reply body exceeds its fixed bound")
            return value
        parts = payload.get("parts", [])
        if not isinstance(parts, list) or len(parts) > 30:
            raise MailError("reply MIME part count exceeds its fixed bound")
        return "\n".join(self._body(part, depth + 1) for part in parts)[:16001]

    def _reply(self, message, stored):
        headers = _headers(message)
        if (message.get("threadId") != stored["thread_id"] or "SENT" in message.get("labelIds", []) or
                _mailboxes(_one(headers, "from")) != [self.contacts[stored["owner"]]] or
                self.sender not in _mailboxes(_one(headers, "to")) or
                stored["rfc_id"] not in _one(headers, "in-reply-to").split()):
            raise MailError("reply is not from the recorded contact in the exact assignment thread")
        # Mail From/thread correlation is not a GitHub identity/approval proof.
        text = self._body(message.get("payload", {}))
        if not text.strip() or len(text) > 16000:
            raise MailError("no bounded plain-text report found")
        secret_check(text.encode())
        lines = []
        for line in text.splitlines():
            if re.fullmatch(r"On .+wrote:|-----Original Message-----|.+님이 작성:", line.strip()):
                break
            if not line.startswith(">"):
                lines.append(line)
        fresh = "\n".join(lines)
        report = {"status": "reported", "summary": fresh[:1000], "next_action": "PM 검토", "text": fresh[:2000]}
        if "LGAX-REPORT" in fresh:
            try:
                value, _end = json.JSONDecoder().raw_decode(fresh.split("LGAX-REPORT", 1)[1].lstrip())
            except ValueError:
                raise MailError("structured report JSON is invalid") from None
            required = {"action_id", "assignment_id", "task_id", "status", "summary", "next_action"}
            if (not isinstance(value, dict) or not required <= set(value) or
                    set(value) - required - {"pr_url", "head_commit"} or
                    value["action_id"] != stored["action_id"] or value["assignment_id"] != stored["assignment_id"] or
                    value["task_id"] != stored["task_id"] or value["status"] not in {"doing", "blocked", "review_requested"} or
                    any(not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 1000
                        for key in ("summary", "next_action"))):
                raise MailError("mail report cannot change authority, assignment or formal Done state")
            if "pr_url" in value or "head_commit" in value:
                url = value.get("pr_url", "")
                match = re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/pull/([1-9][0-9]*)", url)
                head = value.get("head_commit", "")
                if not match or not isinstance(head, str) or not SHA.fullmatch(head):
                    raise MailError("report PR reference is outside the exact repository/head")
                units = _json(self.broker_state).get("units", {}).values()
                if not any(unit.get("assignment_id") == stored["assignment_id"] and
                           unit.get("pr_number") == int(match[1]) and unit.get("head") == head for unit in units):
                    raise MailError("report PR/head is not the immutable issued task result")
            report = {key: value[key] for key in ("status", "summary", "next_action", "pr_url", "head_commit") if key in value}
        secret_check(canonical(report).encode())  # Check decoded JSON too, not only its possibly escaped source.
        for key in ("summary", "next_action", "text"):
            if key in report:
                report[key] = re.sub(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", "[이메일 생략]", report[key])
                report[key] = re.sub(r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)", "[연락처 생략]", report[key])
        return {"event_id": "gmail:" + _identifier(message.get("id")), "source": "gmail_reply",
                "authority": "report_only", "identity_proof": "matched private contact/reply thread; not GitHub authentication",
                "owner": stored["owner"], "action_id": stored["action_id"], "assignment_id": stored["assignment_id"],
                "task_id": stored["task_id"], "report": report,
                "issue_number": _json(self.broker_state)["actions"][stored["action_id"]]["action"]["issue_number"],
                "message_body_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def poll_replies(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MailError("bounded reply polling required")
        with exclusive_bridge_lock(self.root / "mail.lock"), self.connect() as db:
            self._verify_journal(db)
            self.preflight()
            db.row_factory = sqlite3.Row
            deliveries = [dict(row) for row in db.execute("SELECT * FROM deliveries WHERE status='sent' ORDER BY rowid DESC LIMIT ?", (limit,))]
            accepted, quarantined = 0, 0
            for stored in deliveries:
                thread = self.gmail.request("GET", "threads/" + _identifier(stored["thread_id"]), params={"format": "full"})
                rows = thread.get("messages", [])
                if not isinstance(rows, list) or len(rows) > 100:
                    raise MailError("reply thread exceeds its fixed bound")
                for message in rows:
                    mid = _identifier(message.get("id"))
                    if mid == stored["gmail_id"] or db.execute("SELECT 1 FROM inbox WHERE message_id=?", (mid,)).fetchone():
                        continue
                    try:
                        event = self._reply(message, stored)
                        disposition, digest = "report_only", event["message_body_sha256"]
                        accepted += 1
                    except (MailError, ValueError):
                        event = {"event_id": "gmail:" + mid, "authority": "quarantined", "task_id": stored["task_id"],
                                 "action_id": stored["action_id"], "reason": "reply identity/context/authority check failed"}
                        disposition, digest = "quarantined", hashlib.sha256(canonical(message).encode()).hexdigest()
                        quarantined += 1
                    db.execute("INSERT INTO inbox VALUES(?,?,?,?)", (mid, digest, disposition, canonical(event)))
                    self._journal(db, {"kind": "mail_reply", "event_id": event["event_id"], "disposition": disposition,
                                       "digest": digest, "event_sha256": hashlib.sha256(canonical(event).encode()).hexdigest()})
            return {"reports_collected": accepted, "quarantined": quarantined, "github_mutated": False, "formal_state_changed": False}

    def observation_events(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MailError("bounded PM inbox observation required")
        with exclusive_bridge_lock(self.root / "mail.lock"), self.connect() as db:
            self._verify_journal(db)
            return [json.loads(row[0]) for row in db.execute("SELECT event FROM inbox WHERE disposition='report_only' ORDER BY rowid DESC LIMIT ?", (limit,))]
