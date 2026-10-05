"""Transactional, inert-data queue for PM-approved development packets.

No repository code, user comments, models or GitHub credentials are executed here.
Expiry keeps ownership fenced until a human confirms the old runner stopped.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ACCOUNTS = ("jeongiryang", "unknownamed", "ginaginaring", "choigilung")
PM = "jeongiryang"
REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
ACTIVE = ("running", "stopping", "orphaned")
WORKER_STALE_SECONDS = 180
WORKER_RUNTIME_VERSION = "worker-presence-v1"
WORKER_IDLE_PHASES = {"starting", "idle", "profile_busy"}
WORKER_JOB_PHASES = {"preflight", "model", "validating", "publishing"}
SAFE_EXECUTABLES = {"uv", "python", "python3", "npm", "node"}
FORBIDDEN = (
    "private", ".git", ".github", ".codex", ".claude", "agents.md", "claude.md", ".gitignore",
    "pyproject.toml", "uv.lock", "scripts", "docs/pm",
    "harness", "services/automation", "services/project_reports", "packages/contracts",
    "scripts/phase2.py", "scripts/project_report.py", "scripts/bootstrap_github.py",
    "scripts/sync_github_phase2.py", "scripts/assign_task.py", "scripts/receive_submission.py",
    "scripts/sync_agent_rules.py", "docs/pm/assignments", "docs/pm/현재배정.md",
)
DEFAULT_OWNER_PATHS = {
    "jeongiryang": ("apps/api", "apps/mcp", "evals", "tests", "docs/pm", "docs/automation"),
    "unknownamed": ("packages/core", "skills", "evals", "tests"),
    "ginaginaring": ("data", "services/inference", "packages/core", "evals", "tests"),
    "choigilung": ("apps/web", "tests"),
}
MEMBER_NAMES = {"jeongiryang": "정이량", "unknownamed": "황대겸", "ginaginaring": "신진하",
                "choigilung": "최길웅"}


class ControlError(ValueError):
    def __init__(self, message: str, status: int = 409):
        self.status = status
        super().__init__(message)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_path(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 300:
        raise ControlError("allowed path must be a short repository-relative string", 422)
    value = unicodedata.normalize("NFKC", value)
    if (not value or value != value.strip() or value.startswith(("/", "\\")) or
            "\\" in value or ":" in value or any(c in value for c in "*?[]\x00\r\n")):
        raise ControlError("invalid or ambiguous repository-relative path", 422)
    value = value.rstrip("/")
    if not value or any(p in ("", ".", "..") or p != p.strip() or p.endswith(".") for p in value.split("/")):
        raise ControlError("path traversal and root-wide ownership are forbidden", 422)
    folded = value.casefold()
    if any(part.startswith(".env") or part in ("agents.md", "claude.md", ".gitmodules") for part in folded.split("/")):
        raise ControlError("nested rules, submodule and environment files require manual PM work", 422)
    if any(overlap(folded, blocked.casefold()) for blocked in FORBIDDEN):
        raise ControlError("sensitive operating paths require manual PM work", 422)
    return value


def overlap(left: str, right: str) -> bool:
    left, right = left.casefold().rstrip("/"), right.casefold().rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def string(value: Any, name: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ControlError(f"{name} must be a nonempty string of at most {limit} characters", 422)
    return value


def integer(value: Any, name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ControlError(f"{name} must be an integer in {lower}..{upper}", 422)
    return value


class Store:
    def __init__(self, database: str | Path, config: dict[str, Any], *, clock=time.time):
        self.database = str(database)
        self.config = config
        self.clock = clock
        self.pm = config.get("pm_account", PM)
        self.accounts = tuple(config.get("member_accounts", ACCOUNTS))
        if self.pm != PM or set(self.accounts) != set(ACCOUNTS):
            raise ControlError("fixed team identity mapping must be preserved", 422)
        self.lease_seconds = integer(config.get("lease_seconds", 120), "lease_seconds", 30, 300)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS members(account TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY,packet TEXT NOT NULL,status TEXT NOT NULL,
                    created REAL NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,
                    generation INTEGER NOT NULL DEFAULT 0,lease_hash TEXT,
                    lease_expires REAL,run_deadline REAL,publish_hash TEXT,publish_expires REAL,
                    stop_reason TEXT,result TEXT);
                CREATE TABLE IF NOT EXISTS reservations(
                    id TEXT PRIMARY KEY,owner TEXT NOT NULL,paths TEXT NOT NULL,resources TEXT NOT NULL,
                    expires REAL NOT NULL,status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,at REAL NOT NULL,actor TEXT NOT NULL,
                    event TEXT NOT NULL,details TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS identities(
                    account TEXT PRIMARY KEY,token_digest TEXT NOT NULL,changed REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS worker_presence(
                    account TEXT PRIMARY KEY,instance_id TEXT NOT NULL,received_at REAL NOT NULL,
                    reported_at REAL NOT NULL,metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS worker_presence_sessions(
                    account TEXT NOT NULL,instance_id TEXT NOT NULL,sequence INTEGER NOT NULL,
                    reported_at REAL NOT NULL,retired INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(account,instance_id));
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES('mode','off')")
            for account in self.accounts:
                db.execute("INSERT OR IGNORE INTO members(account) VALUES(?)", (account,))
            initial = config.get("formal_snapshot", {"approved_commit": None, "tasks": {}})
            db.execute("INSERT OR IGNORE INTO settings VALUES('formal_snapshot',?)", (json.dumps(initial),))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def event(self, db, actor, kind, details):
        db.execute("INSERT INTO events(at,actor,event,details) VALUES(?,?,?,?)",
                   (self.clock(), actor, kind, json.dumps(details, ensure_ascii=False)))

    def _pm(self, account):
        if account != self.pm:
            raise ControlError("only the authenticated PM may perform this operation", 403)

    def _enabled(self, db, account):
        mode = db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
        row = db.execute("SELECT enabled FROM members WHERE account=?", (account,)).fetchone()
        return mode == "on" and row is not None and bool(row[0])

    def _expire(self, db):
        expired = db.execute("SELECT id FROM jobs WHERE status IN ('running','stopping') "
                             "AND (lease_expires<=? OR run_deadline<=?)", (self.clock(), self.clock())).fetchall()
        for row in expired:
            db.execute("UPDATE jobs SET status='orphaned',publish_hash=NULL,publish_expires=NULL,"
                       "stop_reason='lease or execution deadline expired; PM reconciliation required' WHERE id=?",
                       (row[0],))
            self.event(db, "controller", "orphaned", {"job_id": row[0]})
        db.execute("UPDATE reservations SET status='orphaned' WHERE status='active' AND expires<=?", (self.clock(),))

    def status(self, account):
        with self.transaction() as db:
            self._expire(db)
            mode = db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
            jobs = [self._public_job(row) for row in db.execute("SELECT * FROM jobs ORDER BY created,id")]
            reservations = [dict(row) for row in db.execute("SELECT id,owner,expires,status FROM reservations")]
            events = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 40")]
            return {"global_mode": mode, "members": {r[0]: bool(r[1]) for r in db.execute("SELECT * FROM members")},
                    "jobs": jobs, "reservations": reservations, "events": events,
                    "workers": self._worker_presence_status(db),
                    "formal_snapshot": json.loads(db.execute("SELECT value FROM settings WHERE key='formal_snapshot'").fetchone()[0]),
                    "observed_at": self.clock(), "viewer": account,
                    "notice": "Automation review_requested/accepted is not formal phase2 Done or human merge approval."}

    def _worker_presence_status(self, db):
        observed_at = self.clock()
        rows = {row["account"]: row for row in db.execute("SELECT * FROM worker_presence")}
        enrolled = {row[0] for row in db.execute("SELECT account FROM identities")}
        result = {}
        for account in self.accounts:
            registered = (account in self.config.get("worker_token_digests", {}) or account in enrolled or
                          (account != self.pm and account in self.config.get("token_digests", {})))
            row = rows.get(account)
            if row:
                age = max(0, observed_at - row["received_at"])
                result[account] = {**json.loads(row["metadata"]), "registered": registered,
                    "last_seen_at": row["received_at"], "reported_at": row["reported_at"],
                    "age_seconds": age, "presence": "online" if age < WORKER_STALE_SECONDS else "stale"}
            else:
                result[account] = {"registered": registered, "presence": "never_seen",
                                   "last_seen_at": None, "reported_at": None, "age_seconds": None}
            result[account].update(stale_after_seconds=WORKER_STALE_SECONDS,
                evidence_kind="authenticated_worker_self_report",
                limitation="Recent fixed-worker metadata is not a readiness, model/test success, "
                           "job completion or independent proof of the entire PC's health.")
        return result

    def worker_presence(self, account, body):
        """Metadata only: never renew a lease, opt in, claim, retry or approve."""
        required = {"schema_version", "source", "runtime_version", "runtime_sha256", "engine", "phase",
                    "instance_id", "sequence", "reported_at", "job_id", "lease_token"}
        if (account not in self.accounts or not isinstance(body, dict) or set(body) != required or
                type(body["schema_version"]) is not int or body["schema_version"] != 1 or
                body["source"] != "fixed_worker" or body["runtime_version"] != WORKER_RUNTIME_VERSION or
                not isinstance(body["engine"], str) or body["engine"] not in {"codex", "claude"} or
                not isinstance(body["phase"], str) or body["phase"] not in WORKER_IDLE_PHASES | WORKER_JOB_PHASES or
                not isinstance(body["runtime_sha256"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", body["runtime_sha256"]) or
                not isinstance(body["instance_id"], str) or
                not re.fullmatch(r"[0-9a-f]{32}", body["instance_id"])):
            raise ControlError("fixed worker metadata has invalid fields or source", 422)
        integer(body["sequence"], "worker sequence", 1, 2147483647)
        reported_at, received_at = body["reported_at"], self.clock()
        if (type(reported_at) not in {int, float} or not -1e12 <= reported_at <= 1e12 or
                not math.isfinite(reported_at) or
                abs(received_at - reported_at) >= WORKER_STALE_SECONDS):
            raise ControlError("worker report timestamp is stale or invalid", 422)
        job_id, token = body["job_id"], body["lease_token"]
        if body["phase"] in WORKER_IDLE_PHASES:
            if job_id is not None or token is not None:
                raise ControlError("idle worker metadata cannot claim a job", 422)
        elif (not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", job_id) or
              not isinstance(token, str) or not 1 <= len(token) <= 256):
            raise ControlError("active worker metadata needs its current job lease", 422)
        with self.transaction() as db:
            if job_id is not None:
                # Inspect the original fence without _expire or UPDATE: this
                # endpoint cannot keep abandoned work alive or change history.
                job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                if (job is None or json.loads(job["packet"])["owner"] != account or
                        job["status"] not in {"running", "stopping"} or not job["lease_hash"] or
                        not hmac.compare_digest(digest(token), job["lease_hash"]) or
                        job["lease_expires"] <= received_at or job["run_deadline"] <= received_at):
                    raise ControlError("worker metadata does not own a live job lease", 403)
            session = db.execute("SELECT * FROM worker_presence_sessions WHERE account=? AND instance_id=?",
                                 (account, body["instance_id"])).fetchone()
            previous = db.execute("SELECT * FROM worker_presence WHERE account=?", (account,)).fetchone()
            if session:
                if (session["retired"] or body["sequence"] <= session["sequence"] or
                        reported_at < session["reported_at"]):
                    raise ControlError("stale, duplicate or retired worker metadata refused")
            elif previous and reported_at < previous["reported_at"]:
                raise ControlError("new worker instance must have a fresh timestamp")
            else:
                db.execute("UPDATE worker_presence_sessions SET retired=1 WHERE account=?", (account,))
            db.execute("INSERT INTO worker_presence_sessions VALUES(?,?,?,?,0) "
                       "ON CONFLICT(account,instance_id) DO UPDATE SET sequence=excluded.sequence,"
                       "reported_at=excluded.reported_at", (account, body["instance_id"], body["sequence"], reported_at))
            metadata = {key: body[key] for key in ("source", "runtime_version", "runtime_sha256", "engine", "phase",
                                                 "instance_id", "sequence", "job_id")}
            db.execute("INSERT INTO worker_presence VALUES(?,?,?,?,?) ON CONFLICT(account) DO UPDATE SET "
                       "instance_id=excluded.instance_id,received_at=excluded.received_at,"
                       "reported_at=excluded.reported_at,metadata=excluded.metadata",
                       (account, body["instance_id"], received_at, reported_at, json.dumps(metadata)))
        return {"accepted": True, "account": str(account), "server_time": received_at,
                "stale_after_seconds": WORKER_STALE_SECONDS, "metadata_only": True}

    def _public_job(self, row):
        packet = json.loads(row["packet"])
        public = {key: packet[key] for key in ("job_id", "owner", "task_id", "assignment_id", "base_commit", "title", "kind", "priority")}
        if packet["kind"] == "review":
            public.update(review_pr_url=packet["review_pr_url"], review_head=packet["review_head"],
                          review_head_commit=packet["review_head_commit"])
        public.update(status=row["status"], attempt=row["attempt"], lease_generation=row["generation"],
                      stop_reason=row["stop_reason"], lease_expires_at=row["lease_expires"],
                      result=json.loads(row["result"]) if row["result"] else None)
        return public

    def mode(self, account, mode, member=None):
        if mode not in ("on", "off", "stop"):
            raise ControlError("mode must be on, off or stop", 422)
        if member is None:
            self._pm(account)
        elif member not in self.accounts or (account != self.pm and account != member):
            raise ControlError("members may only change their own opt-in", 403)
        with self.transaction() as db:
            if member is None:
                db.execute("UPDATE settings SET value=? WHERE key='mode'", (mode,))
            else:
                db.execute("UPDATE members SET enabled=? WHERE account=?", (int(mode == "on"), member))
            if mode != "on":
                rows = db.execute("SELECT id,packet FROM jobs WHERE status IN ('running','stopping')").fetchall()
                for row in rows:
                    if member is None or json.loads(row["packet"])["owner"] == member:
                        reason = f"{mode}: save a checkpoint; no push/PR; manual workflow remains available"
                        db.execute("UPDATE jobs SET status='stopping',stop_reason=?,publish_hash=NULL,"
                                   "publish_expires=NULL WHERE id=?", (reason, row["id"]))
            self.event(db, account, "mode", {"mode": mode, "member": member})
        return self.status(account)

    def formal_snapshot(self, account, body):
        self._pm(account)
        if not re.fullmatch(r"[0-9a-f]{40}", body.get("approved_commit", "")):
            raise ControlError("formal snapshot requires a full approved main commit", 422)
        string(body.get("approval_reference"), "approval_reference")
        tasks = body.get("tasks")
        if not isinstance(tasks, dict) or not tasks:
            raise ControlError("formal snapshot needs PM-approved tasks", 422)
        for task_id, task in tasks.items():
            if not isinstance(task, dict) or task.get("owner") not in self.accounts or not isinstance(task.get("status"), str):
                raise ControlError("invalid PM-approved task snapshot", 422)
            string(task_id, "task ID", 100)
        with self.transaction() as db:
            db.execute("UPDATE settings SET value=? WHERE key='formal_snapshot'", (json.dumps(body),))
            # An authenticated new PM snapshot can revoke, never silently enlarge,
            # an in-flight packet's owner/dependency authority.
            for row in db.execute("SELECT id,packet FROM jobs WHERE status='running'").fetchall():
                packet = json.loads(row["packet"])
                registered = tasks.get(packet["task_id"], {})
                invalid_owner = packet["kind"] == "implementation" and registered.get("owner") != packet["owner"]
                invalid_deps = any(tasks.get(task, {}).get("status") != "done" for task in packet["formal_task_dependencies"])
                if invalid_owner or invalid_deps or not registered:
                    db.execute("UPDATE jobs SET status='stopping',stop_reason='PM snapshot revoked owner/dependency authority',"
                               "publish_hash=NULL,publish_expires=NULL WHERE id=?", (row["id"],))
            self.event(db, account, "formal_snapshot", {"approved_commit": body["approved_commit"],
                                                       "approval_reference": body["approval_reference"]})
        return {"accepted": True}

    def _paths(self, account, paths):
        if not isinstance(paths, list) or not paths or len(paths) > 40:
            raise ControlError("explicit limited allowed_paths are required", 422)
        # Preserve the visible directory suffix; matching is always boundary based.
        paths = list(dict.fromkeys(safe_path(path) + ("/" if path.endswith("/") else "") for path in paths))
        ownership = self.config.get("owner_paths", DEFAULT_OWNER_PATHS).get(account, ())
        own_name = MEMBER_NAMES[account]
        ownership = list(ownership) + [f"docs/작업기록/{own_name}.md", f"docs/작업근거/{own_name}.md",
                                      f"docs/작업기록/sessions/{own_name}", f"docs/작업기록/세션/{own_name}",
                                      f"docs/작업근거/세션/{own_name}"]
        for path in paths:
            if not any(path.casefold().rstrip("/") == p.casefold().rstrip("/") or path.casefold().startswith(p.casefold().rstrip("/") + "/")
                       for p in ownership):
                raise ControlError("path exceeds the registered member ownership", 422)
        return paths

    def _resources(self, resources):
        if not isinstance(resources, list) or len(resources) > 30:
            raise ControlError("shared_resources must be a limited list", 422)
        if any(not isinstance(item, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", item) for item in resources):
            raise ControlError("invalid shared resource name", 422)
        return sorted(set(resources))

    def _commands(self, commands):
        if not isinstance(commands, list) or not commands or len(commands) > 12:
            raise ControlError("implementation requires explicit validation_commands", 422)
        for argv in commands:
            if not isinstance(argv, list) or not argv or len(argv) > 40 or argv[0] not in SAFE_EXECUTABLES:
                raise ControlError("validation commands must be approved executable argument lists", 422)
            if any(not isinstance(arg, str) or not arg or len(arg) > 1000 or
                   any(ch in arg for ch in ("\x00", "\r", "\n", ";", "|", "&", "`")) for arg in argv):
                raise ControlError("shell syntax is forbidden in validation commands", 422)
        return commands

    def register(self, account, body):
        self._pm(account)
        allowed_keys = {"job_id", "owner", "task_id", "assignment_id", "base_commit", "title", "prompt", "approved",
                        "allowed_paths", "shared_resources", "dependency_job_ids", "formal_task_dependencies", "kind",
                        "priority", "max_attempts", "timeout_seconds", "validation_commands", "review_pr_url",
                        "review_head_commit", "review_head", "approval_reference", "formal_dependencies",
                        "approved_snapshot_commit"}
        if not isinstance(body, dict) or set(body) - allowed_keys or body.get("approved") is not True:
            raise ControlError("a PM-approved bounded packet is required; unknown fields are forbidden", 422)
        packet = {key: string(body.get(key), key, 16000 if key == "prompt" else 300)
                  for key in ("job_id", "owner", "task_id", "assignment_id", "base_commit", "title", "prompt", "approval_reference")}
        if packet["owner"] not in self.accounts or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", packet["job_id"]):
            raise ControlError("unknown owner or invalid unique job ID", 422)
        if not re.fullmatch(r"[0-9a-f]{40}", packet["base_commit"]):
            raise ControlError("base_commit must be a fixed full SHA", 422)
        kind = body.get("kind", "implementation")
        if kind not in ("implementation", "review") or (kind == "review" and packet["owner"] != self.pm):
            raise ControlError("review jobs belong to the PM read-only reviewer", 422)
        packet.update(kind=kind, approved=True, priority=integer(body.get("priority", 100), "priority", 0, 1000),
                      max_attempts=integer(body.get("max_attempts", 2), "max_attempts", 1, 2),
                      timeout_seconds=integer(body.get("timeout_seconds", 1800), "timeout_seconds", 30, 3600),
                      allowed_paths=[] if kind == "review" and body.get("allowed_paths") == []
                      else self._paths(packet["owner"], body.get("allowed_paths")),
                      shared_resources=self._resources(body.get("shared_resources", [])),
                      validation_commands=self._commands(body.get("validation_commands")) if kind == "implementation" else [])
        for key in ("dependency_job_ids", "formal_task_dependencies"):
            value = body.get(key, body.get("formal_dependencies", [])) if key == "formal_task_dependencies" else body.get(key, [])
            if key == "formal_task_dependencies" and "formal_dependencies" in body and key in body and body[key] != body["formal_dependencies"]:
                raise ControlError("formal dependency aliases disagree", 422)
            if not isinstance(value, list) or len(value) > 50 or any(not isinstance(i, str) or not i for i in value):
                raise ControlError(f"invalid {key}", 422)
            packet[key] = list(dict.fromkeys(value))
        if kind == "review":
            packet["review_pr_url"] = self._pr(body.get("review_pr_url"))
            review_head = body.get("review_head_commit", body.get("review_head", ""))
            if not re.fullmatch(r"[0-9a-f]{40}", review_head):
                raise ControlError("review requires fixed full PR head", 422)
            packet["review_head_commit"] = review_head
            packet["review_head"] = review_head
        with self.transaction() as db:
            snapshot = json.loads(db.execute("SELECT value FROM settings WHERE key='formal_snapshot'").fetchone()[0])
            tasks = snapshot.get("tasks", {})
            if body.get("approved_snapshot_commit") is not None:
                if body["approved_snapshot_commit"] != snapshot.get("approved_commit"):
                    raise ControlError("job approval refers to a different formal snapshot")
                packet["approved_snapshot_commit"] = body["approved_snapshot_commit"]
            registered = tasks.get(packet["task_id"])
            if not registered or (kind == "implementation" and registered.get("owner") != packet["owner"]):
                raise ControlError("task and owner must exist in the PM-approved formal snapshot", 422)
            if any(task not in tasks for task in packet["formal_task_dependencies"]):
                raise ControlError("unknown formal dependency", 422)
            if any(db.execute("SELECT 1 FROM jobs WHERE id=?", (dependency,)).fetchone() is None
                   for dependency in packet["dependency_job_ids"]):
                raise ControlError("dependencies must be existing immutable jobs", 422)
            previous = db.execute("SELECT packet FROM jobs WHERE id=?", (packet["job_id"],)).fetchone()
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            if previous:
                if previous[0] != serialized:
                    raise ControlError("registered packets are immutable; use a new job/assignment ID")
                return {"registered": True, "duplicate": True, "job_id": packet["job_id"]}
            db.execute("INSERT INTO jobs(id,packet,status,created) VALUES(?,?,'pending',?)",
                       (packet["job_id"], serialized, self.clock()))
            self.event(db, account, "registered", {"job_id": packet["job_id"], "owner": packet["owner"],
                                                   "approval_reference": packet["approval_reference"]})
        return {"registered": True, "duplicate": False, "job_id": packet["job_id"]}

    def _conflict(self, db, owner, paths, resources):
        for row in db.execute("SELECT packet,status FROM jobs WHERE status IN ('running','stopping','orphaned','review_requested')"):
            packet = json.loads(row[0])
            if ((packet["owner"] == owner and row["status"] in ACTIVE) or set(resources) & set(packet["shared_resources"]) or any(
                    overlap(p, q) for p in paths for q in packet["allowed_paths"])):
                return True
        for row in db.execute("SELECT * FROM reservations WHERE status IN ('active','orphaned')"):
            if row["owner"] == owner or set(resources) & set(json.loads(row["resources"])) or any(
                    overlap(p, q) for p in paths for q in json.loads(row["paths"])):
                return True
        return False

    def claim(self, account):
        with self.transaction() as db:
            self._expire(db)
            if not self._enabled(db, account):
                return {"job": None, "reason": "global/member automation is OFF; manual mode remains available"}
            snapshot = json.loads(db.execute("SELECT value FROM settings WHERE key='formal_snapshot'").fetchone()[0])
            rows = list(db.execute("SELECT * FROM jobs WHERE status='pending'"))
            rows.sort(key=lambda r: (json.loads(r["packet"])["priority"], r["created"], r["id"]))
            for row in rows:
                packet = json.loads(row["packet"])
                if packet["owner"] != account or row["attempt"] >= packet["max_attempts"]:
                    continue
                registered = snapshot.get("tasks", {}).get(packet["task_id"])
                if not registered or (packet["kind"] == "implementation" and
                                      (registered.get("owner") != account or registered.get("status") == "done")):
                    continue
                if any(snapshot.get("tasks", {}).get(task, {}).get("status") != "done"
                       for task in packet["formal_task_dependencies"]):
                    continue
                if any(db.execute("SELECT status FROM jobs WHERE id=?", (dep,)).fetchone()[0] != "accepted"
                       for dep in packet["dependency_job_ids"]):
                    continue
                if self._conflict(db, account, packet["allowed_paths"], packet["shared_resources"]):
                    continue
                token = secrets.token_urlsafe(32)
                expires = self.clock() + self.lease_seconds
                db.execute("UPDATE jobs SET status='running',attempt=attempt+1,generation=generation+1,"
                           "lease_hash=?,lease_expires=?,run_deadline=?,stop_reason=NULL,publish_hash=NULL,"
                           "publish_expires=NULL,result=NULL WHERE id=?", (digest(token), expires,
                           self.clock() + packet["timeout_seconds"], row["id"]))
                packet.update(lease_token=token, lease_generation=row["generation"] + 1,
                              lease_expires_at=expires, attempt=row["attempt"] + 1)
                self.event(db, account, "claimed", {"job_id": row["id"], "attempt": packet["attempt"]})
                return {"job": packet}
            return {"job": None, "reason": "no eligible nonconflicting approved work"}

    def _lease(self, db, account, job_id, token):
        self._expire(db)
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ControlError("unknown job", 404)
        if (json.loads(row["packet"])["owner"] != account or not isinstance(token, str) or
                not row["lease_hash"] or not hmac.compare_digest(digest(token), row["lease_hash"])):
            raise ControlError("lease does not belong to this authenticated member", 403)
        if row["status"] not in ("running", "stopping"):
            raise ControlError("lease is fenced or terminal; PM reconciliation required")
        return row

    def heartbeat(self, account, job_id, token):
        try:
            with self.transaction() as db:
                row = self._lease(db, account, job_id, token)
                if row["status"] != "running" or not self._enabled(db, account):
                    return {"continue": False, "reason": row["stop_reason"] or "automation disabled"}
                expires = min(self.clock() + self.lease_seconds, row["run_deadline"])
                db.execute("UPDATE jobs SET lease_expires=? WHERE id=?", (expires, job_id))
                return {"continue": True, "lease_expires_at": expires}
        except ControlError as exc:
            if exc.status == 409:
                return {"continue": False, "reason": str(exc)}
            raise

    def authorize_publish(self, account, job_id, token):
        with self.transaction() as db:
            row = self._lease(db, account, job_id, token)
            if row["status"] != "running" or not self._enabled(db, account):
                raise ControlError("OFF/STOP: publication is revoked")
            if json.loads(row["packet"])["kind"] != "implementation":
                raise ControlError("read-only reviewer cannot publish code or PR", 403)
            capability = secrets.token_urlsafe(32)
            expires = min(self.clock() + 20, row["lease_expires"], row["run_deadline"])
            db.execute("UPDATE jobs SET publish_hash=?,publish_expires=? WHERE id=?",
                       (digest(capability), expires, job_id))
            return {"publish_token": capability, "expires_at": expires}

    def _pr(self, value):
        if not isinstance(value, str) or not re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/pull/[1-9][0-9]*", value):
            raise ControlError("PR URL must belong to the canonical LG repository", 422)
        return value

    def _review_result(self, value):
        required = {"summary", "intent_interpretation", "findings", "limitations", "next_action"}
        if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - {"changes"}:
            raise ControlError("read-only review requires the bounded structured review result", 422)
        try:
            encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError):
            raise ControlError("review result must contain plain JSON data", 422) from None
        if len(encoded) > 24576:
            raise ControlError("structured review result exceeds 24 KiB", 422)
        for key in ("summary", "intent_interpretation", "next_action"):
            string(value[key], "review " + key, 4000)
        for key in ("findings", "limitations", "changes"):
            items = value.get(key, [])
            if not isinstance(items, list) or len(items) > 30:
                raise ControlError("review arrays must contain at most 30 plain strings", 422)
            for item in items:
                string(item, "review " + key, 2000)
        # Defense in depth only; the worker's isolated review context must exclude credentials.
        if re.search(r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
                     r"Bearer\s+[A-Za-z0-9_-]{20,})", encoded.decode("utf-8")):
            raise ControlError("review output resembles a private credential; retain privately and redact", 422)
        return value

    def finish(self, account, job_id, body):
        with self.transaction() as db:
            row = self._lease(db, account, job_id, body.get("lease_token"))
            packet = json.loads(row["packet"])
            outcome = body.get("outcome")
            if outcome not in ("review_requested", "completed_review", "blocked", "failed"):
                raise ControlError("worker cannot report accepted, merged or formal Done", 422)
            summary = string(body.get("summary"), "summary", 4000)
            result = {"outcome": outcome, "summary": summary, "reported_at": self.clock()}
            if outcome == "review_requested":
                capability = body.get("publish_token")
                if (packet["kind"] != "implementation" or row["status"] != "running" or
                        not self._enabled(db, account) or not isinstance(capability, str) or not row["publish_hash"] or
                        not hmac.compare_digest(digest(capability), row["publish_hash"]) or row["publish_expires"] <= self.clock()):
                    raise ControlError("current one-time publish authorization is required")
                result["pr_url"] = self._pr(body.get("pr_url"))
                if not re.fullmatch(r"[0-9a-f]{40}", body.get("head_commit", "")):
                    raise ControlError("published PR head must be a full commit SHA", 422)
                result["head_commit"] = body["head_commit"]
            elif outcome == "completed_review":
                if packet["kind"] != "review" or row["status"] != "running" or not self._enabled(db, account):
                    raise ControlError("only a currently enabled read-only review job can complete review")
                if body.get("pr_url") or body.get("publish_token") or body.get("head_commit"):
                    raise ControlError("review results cannot publish or change a PR", 422)
                result["review_result"] = self._review_result(body.get("review_result"))
            elif body.get("review_result") is not None:
                raise ControlError("structured review output is only accepted for read-only completed reviews", 422)
            db.execute("UPDATE jobs SET status=?,result=?,publish_hash=NULL,publish_expires=NULL,lease_hash=NULL "
                       "WHERE id=?", (outcome, json.dumps(result, ensure_ascii=False), job_id))
            self.event(db, account, "finished", {"job_id": job_id, "outcome": outcome})
            return {"job": self._public_job(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())}

    def reconcile(self, account, job_id, body):
        self._pm(account)
        action = body.get("action")
        if action not in ("requeue", "block", "accept"):
            raise ControlError("reconciliation action must be requeue, block or accept", 422)
        reason = string(body.get("reason"), "reason")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ControlError("unknown job", 404)
            packet = json.loads(row["packet"])
            if row["status"] in ACTIVE and body.get("runner_stopped") is not True:
                raise ControlError("PM must confirm the old runner stopped before releasing ownership")
            if action == "requeue":
                if row["status"] not in ("failed", "blocked", "orphaned", "stopping"):
                    raise ControlError("only a stopped/failed job can be explicitly retried")
                if row["attempt"] >= packet["max_attempts"]:
                    raise ControlError("attempt budget exhausted; new human-approved assignment required")
                status = "pending"
            elif action == "accept":
                if row["status"] not in ("review_requested", "completed_review"):
                    raise ControlError("PM acceptance requires an actual submitted result")
                string(body.get("integration_evidence"), "integration_evidence")
                status = "accepted"
            else:
                status = "blocked"
            db.execute("UPDATE jobs SET status=?,generation=generation+1,lease_hash=NULL,publish_hash=NULL,"
                       "publish_expires=NULL,stop_reason=? WHERE id=?", (status, reason, job_id))
            self.event(db, account, "reconciled", {"job_id": job_id, "action": action, "reason": reason,
                                                  "integration_evidence": body.get("integration_evidence")})
        return {"accepted": True, "status": status, "notice": "Queue acceptance does not modify phase2 formal state."}

    def reserve(self, account, body):
        reservation_id = string(body.get("reservation_id"), "reservation_id", 100)
        paths = self._paths(account, body.get("allowed_paths"))
        resources = self._resources(body.get("shared_resources", []))
        ttl = integer(body.get("ttl_seconds", 1800), "ttl_seconds", 30, 3600)
        with self.transaction() as db:
            self._expire(db)
            if db.execute("SELECT 1 FROM reservations WHERE id=?", (reservation_id,)).fetchone():
                raise ControlError("reservation ID already exists")
            if self._conflict(db, account, paths, resources):
                raise ControlError("manual work conflicts with an existing running/orphaned owner")
            expires = self.clock() + ttl
            db.execute("INSERT INTO reservations VALUES(?,?,?,?,?,'active')", (reservation_id, account,
                       json.dumps(paths), json.dumps(resources), expires))
            self.event(db, account, "manual_reserved", {"reservation_id": reservation_id})
            return {"reserved": True, "reservation_id": reservation_id, "expires_at": expires}

    def reservation_heartbeat(self, account, reservation_id, ttl=1800):
        ttl = integer(ttl, "ttl_seconds", 30, 3600)
        with self.transaction() as db:
            self._expire(db)
            row = db.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None or row["owner"] != account:
                raise ControlError("reservation is not owned by the authenticated member", 403)
            if row["status"] != "active":
                raise ControlError("expired manual reservation requires explicit release/reconciliation")
            expires = self.clock() + ttl
            db.execute("UPDATE reservations SET expires=? WHERE id=?", (expires, reservation_id))
            return {"expires_at": expires}

    def release(self, account, reservation_id):
        with self.transaction() as db:
            row = db.execute("SELECT owner FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise ControlError("unknown reservation", 404)
            if account not in (row[0], self.pm):
                raise ControlError("cannot release another member's manual reservation", 403)
            db.execute("DELETE FROM reservations WHERE id=?", (reservation_id,))
            self.event(db, account, "manual_released", {"reservation_id": reservation_id})
        return {"released": True}

    def enroll(self, account):
        if account not in self.accounts or account == self.pm:
            raise ControlError("enrollment is limited to the three registered worker accounts", 403)
        token = secrets.token_urlsafe(48)
        with self.transaction() as db:
            db.execute("INSERT INTO identities VALUES(?,?,?) ON CONFLICT(account) DO UPDATE SET "
                       "token_digest=excluded.token_digest,changed=excluded.changed", (account, digest(token), self.clock()))
            # Account enrollment does not automatically grant runtime opt-in.
            db.execute("UPDATE members SET enabled=0 WHERE account=?", (account,))
            self.event(db, account, "enrolled", {"account": account, "previous_credential_revoked": True})
        return {"account": account, "automation_token": token, "enabled": False,
                "notice": "Store privately. This token does not change GitHub permissions or PM approval."}

    def authentication_digests(self):
        with self.transaction() as db:
            enrolled = {row[0]: row[1] for row in db.execute("SELECT account,token_digest FROM identities")}
        # Enrolled member credentials supersede static member digests; PM stays private-config only.
        return {**self.config.get("token_digests", {}), **enrolled}

    def authentication_credentials(self):
        with self.transaction() as db:
            enrolled = {row[0]: row[1] for row in db.execute("SELECT account,token_digest FROM identities")}
        credentials = []
        for account, token_digest in self.config.get("token_digests", {}).items():
            if account == self.pm or account not in enrolled:
                credentials.append((account, token_digest, account == self.pm))
        for account, token_digest in self.config.get("worker_token_digests", {}).items():
            if account not in enrolled:
                credentials.append((account, token_digest, False))
        credentials.extend((account, token_digest, False) for account, token_digest in enrolled.items())
        return credentials
