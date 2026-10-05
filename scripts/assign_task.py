"""PM assignment -> shared Issue record -> private Gmail outbox -> actual send receipt.

Gmail is sent by the PM AI through the connected Gmail tool, not by this script.
Never share Gmail/Project credentials or private recipient addresses with teammates.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

from project_report_common import GitHub, load_policy, now, project_snapshot, safe_text

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "harness/phase2/project-reports.policy.json"
PRIVATE = ROOT / "private/team-notifications"
PUBLIC = ROOT / "docs/pm/assignments"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def assignment_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"PM-\d{8}-[A-Za-z0-9-]{1,60}", value):
        raise ValueError("assignment_id must be PM-YYYYMMDD-unique-suffix")
    return value


def check_assignment(assignment, policy):
    required = {"assignment_id", "task_id", "purpose", "instructions", "acceptance", "next_action"}
    optional = {"deadline", "source", "requirement_ids", "pm_account", "recipient_account", "assignment_url"}
    if not isinstance(assignment, dict) or not required <= assignment.keys() or assignment.keys() - required - optional:
        raise ValueError("invalid assignment fields")
    assignment_id(assignment["assignment_id"])
    if assignment["task_id"] not in policy["tasks"]:
        raise ValueError("registered task required; PM must register new tasks before assignment")
    registered = policy["tasks"][assignment["task_id"]]
    # prepare writes these public provenance fields back to the assignment file.
    # Re-reading that file must preserve idempotency without accepting forged targets.
    for key, expected in (("pm_account", policy["pm_account"]), ("recipient_account", registered["account"])):
        if key in assignment and assignment[key] != expected:
            raise ValueError("recorded assignment metadata mismatch")
    if "assignment_url" in assignment:
        prefix = f"https://github.com/{policy['repo']}/issues/{registered['issue_number']}#issuecomment-"
        if not isinstance(assignment["assignment_url"], str) or not re.fullmatch(re.escape(prefix) + r"\d+", assignment["assignment_url"]):
            raise ValueError("recorded assignment metadata mismatch")
    for key in ("purpose", "next_action"):
        if not isinstance(assignment[key], str) or not assignment[key].strip() or len(assignment[key]) > 2000:
            raise ValueError("nonempty purpose/next_action required")
    for key in ("instructions", "acceptance"):
        if not isinstance(assignment[key], list) or not assignment[key] or not all(isinstance(x, str) and x.strip() for x in assignment[key]):
            raise ValueError("instructions and acceptance must be nonempty text lists")
    safe_text(json.dumps(assignment, ensure_ascii=False))
    return registered


def pm_only(api, policy):
    if api.api("user")["login"] != policy["pm_account"]:
        raise ValueError("authenticated PM account required")


def pm_field(api, policy, registered, values):
    if values.keys() - {"최근 배정", "메일 안내"}:
        raise ValueError("assignment updater allows only assignment/mail metadata fields")
    board = project_snapshot(api, policy)
    item = board["items"][registered["issue_number"]]
    if item["id"] != registered["item_id"]:
        raise ValueError("wrong project item")
    for key, value in values.items():
        if item["values"].get(key) == value:
            continue
        api.graphql("""mutation($project:ID!,$item:ID!,$field:ID!,$value:ProjectV2FieldValue!){
          updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:$value}){projectV2Item{id}}}""",
          {"project": policy["project_id"], "item": item["id"], "field": board["fields"][key]["id"], "value": {"text": value}})


def remote_markers(api, policy, registered, aid):
    comments = api.pages(f"repos/{policy['repo']}/issues/{registered['issue_number']}/comments")
    return [c for c in comments if c["user"]["login"] == policy["pm_account"] and
            c["body"].startswith("LGAX-MAIL " + aid + " ")]


def prepare(api, policy, assignment, contacts, apply=False):
    pm_only(api, policy)
    registered = check_assignment(assignment, policy)
    if registered["account"] == policy["pm_account"]:
        raise ValueError("teammate notifications only; do not email the PM a teammate task")
    contact = contacts.get("contacts", {}).get(registered["account"], {})
    address = contact.get("email", "")
    if contact.get("name") != registered["name"] or not contact.get("source") or not contact.get("verified_at"):
        raise ValueError("verified private name/email evidence required; do not guess")
    if not re.fullmatch(r"[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+", address) or "noreply" in address.lower():
        raise ValueError("valid deliverable teammate email required")
    issue_path = f"repos/{policy['repo']}/issues/{registered['issue_number']}"
    issue = api.api(issue_path)
    if issue["state"] != "open" or "pull_request" in issue:
        raise ValueError("open task Issue required")
    aid = assignment["assignment_id"]
    marker = "LGAX-ASSIGNMENT " + aid + "\n"
    text = (marker + f"PM 정이량의 작업 배정 · `{assignment['task_id']}` · {registered['name']}\n\n"
            + "목적: " + assignment["purpose"] + "\n\n작업 지시\n"
            + "\n".join("- " + x for x in assignment["instructions"])
            + "\n\n검수 조건\n" + "\n".join("- " + x for x in assignment["acceptance"])
            + "\n\n다음 행동: " + assignment["next_action"]
            + "\n기한: " + assignment.get("deadline", "별도 작업 시한 미지정; 대회 제출 10/20 준비")
            + "\n\n자기 의도·수행·근거 기록과 상태 보고를 연결하고, PR을 PM에게 검수 요청하세요. 최종 완료는 PM 판정입니다.")
    comments = api.pages(issue_path + "/comments")
    existing = next((c for c in comments if c["user"]["login"] == policy["pm_account"] and c["body"].startswith(marker)), None)
    if existing and existing["body"] != text:
        raise ValueError("assignment ID already has different instructions; create a revision ID")
    global_comments = api.pages(f"repos/{policy['repo']}/issues/comments")
    for other in global_comments:
        if (other["user"]["login"] == policy["pm_account"] and other["body"].startswith(marker) and
            ((other.get("issue_url") and other["issue_url"] != f"https://api.github.com/{issue_path}") or other["body"] != text)):
            raise ValueError("assignment ID conflict in another Issue/version; rejected before mutation")
    outbox_path = PRIVATE / "outbox" / (aid + ".json")
    prior = json.loads(outbox_path.read_text(encoding="utf-8")) if outbox_path.exists() else None
    if prior and (prior["task_id"] != assignment["task_id"] or prior["assignment_sha256"] != hashlib.sha256(text.encode()).hexdigest()):
        raise ValueError("local assignment ID conflict; rejected before public mutation")
    if not apply:
        return {"ready": True, "applied": False, "assignment_id": aid, "recipient_name": registered["name"],
                "issue_number": registered["issue_number"], "body": text}
    api.api(issue_path + "/assignees", {"assignees": [registered["account"]]}, "POST")
    comment = existing or api.api(issue_path + "/comments", {"body": text}, "POST")
    issue_url = issue["html_url"]
    subject = f"[LG AX 작업배정 {aid}] {registered['name']} · {assignment['purpose']}"
    def bullets(values):
        return "<ul>" + "".join("<li>" + html.escape(x) + "</li>" for x in values) + "</ul>"
    body = (f"<p>{html.escape(registered['name'])}님, 정이량 PM입니다.</p>"
            f"<p><strong>{html.escape(assignment['purpose'])}</strong> 작업을 배정합니다.</p>"
            + "<h3>해야 할 일</h3>" + bullets(assignment["instructions"])
            + "<h3>검수 조건</h3>" + bullets(assignment["acceptance"])
            + f"<p><strong>다음 행동:</strong> {html.escape(assignment['next_action'])}</p>"
            + f"<p>기한: {html.escape(assignment.get('deadline', '별도 작업 시한 미지정; 대회 제출 10/20 준비'))}</p>"
            + f'<p><a href="{comment["html_url"]}">PM 배정 원문</a> · <a href="{issue_url}">담당 이슈</a> · '
            + f'<a href="{policy["project_url"]}">프로젝트 현황</a> · '
            + f'<a href="https://github.com/{policy["repo"]}/blob/main/docs/협업체계.md">협업 안내</a></p>'
            + "<p>AI는 프로젝트와 자기 기록을 읽고 진행하세요. 작업 의도·AI 해석·수행·검증·남은 일은 개인 docs에 남기고, "
            "담당 이슈에 상태 보고와 PR을 연결하세요. 개별 작업 종료와 PM 검수·병합·전체 완료는 구분합니다. "
            "검수 대기에는 PM이 배정한 다음 Ready 작업을 이어가세요.</p><p>새 작업 안내 메일을 확인해 주세요.</p>")
    if not prior:
        markers = remote_markers(api, policy, registered, aid)
        state = "sent" if any(" SENT\n" in c["body"] for c in markers) else "unknown" if markers else "prepared"
        prior = {"assignment_id": aid, "task_id": assignment["task_id"], "recipient_account": registered["account"],
                 "recipient_name": registered["name"], "to": address, "subject": subject, "html": body,
                 "assignment_url": comment["html_url"], "assignment_sha256": hashlib.sha256(text.encode()).hexdigest(),
                 "status": state, "created_at": now(), "message_id": None,
                 "private_contact_source": contact["source"]}
        write(outbox_path, prior)
    write(PUBLIC / (aid + ".json"), {**assignment, "pm_account": policy["pm_account"],
                                    "recipient_account": registered["account"], "assignment_url": comment["html_url"]})
    pm_field(api, policy, registered, {"최근 배정": f"{comment['html_url']}\n{aid} · {assignment['purpose']}",
                                     "메일 안내": f"{prior['status']} · {aid}"})
    return {"applied": True, "assignment_id": aid, "recipient_name": registered["name"],
            "assignment_url": comment["html_url"], "private_outbox": str(outbox_path), "mail_state": prior["status"],
            "next": "PM AI uses connected Gmail, then records actual message ID. Do not infer send from prepare."}


def record(api, policy, aid, action, receipt_data=None):
    pm_only(api, policy)
    assignment_id(aid)
    path = PRIVATE / "outbox" / (aid + ".json")
    row = json.loads(path.read_text(encoding="utf-8"))
    registered = policy["tasks"][row["task_id"]]
    if action == "sending":
        if row["status"] != "prepared" or remote_markers(api, policy, registered, aid):
            raise ValueError("already sending/sent/unknown; check Gmail Sent for this assignment ID before retry")
        api.api(f"repos/{policy['repo']}/issues/{registered['issue_number']}/comments",
                {"body": f"LGAX-MAIL {aid} SENDING\nPM AI가 Gmail 발송을 시작합니다. 결과 확인 전 발송 완료로 기록하지 않습니다."}, "POST")
        row.update(status="sending", sending_at=now())
    elif action == "sent":
        if row["status"] not in ("sending", "unknown", "sent"):
            raise ValueError("must mark sending first; no duplicate send")
        if not isinstance(receipt_data, dict) or not re.fullmatch(r"[0-9a-f]{10,40}", receipt_data.get("message_id", "")):
            raise ValueError("actual Gmail message ID required")
        if receipt_data.get("assignment_id") != aid or receipt_data.get("source") not in ("Gmail send_email result", "Gmail Sent reconciliation"):
            raise ValueError("receipt must match assignment and an actual Gmail result")
        contacts = json.loads((PRIVATE / "contacts.json").read_text(encoding="utf-8"))
        if (receipt_data.get("recipient_email") != row["to"] or
            receipt_data.get("sender_email") != contacts["sender"]["email"] or
            receipt_data.get("subject") != row["subject"] or receipt_data.get("sent_observed") is not True):
            raise ValueError("Gmail Sent metadata must match verified PM sender, private recipient and exact assignment subject")
        if row["status"] == "sent" and row["message_id"] != receipt_data["message_id"]:
            raise ValueError("existing send has a different Gmail message ID")
        row.update(status="sent", message_id=receipt_data["message_id"], sent_at=row.get("sent_at") or now())
        write(path, row)  # Gmail send is durable even if later Issue/Project updates fail.
        receipt = {"assignment_id": aid, "task_id": row["task_id"], "recipient_account": row["recipient_account"],
                   "status": "sent", "sent_at": row["sent_at"],
                   "source": receipt_data["source"], "recipient_read_confirmed": False}
        write(PUBLIC / (aid + ".notification.json"), receipt)
        if not any(" SENT\n" in c["body"] for c in remote_markers(api, policy, registered, aid)):
            api.api(f"repos/{policy['repo']}/issues/{registered['issue_number']}/comments",
                    {"body": f"LGAX-MAIL {aid} SENT\n정이량 PM 명의 Gmail 발송 결과를 확인했습니다. 상세 수신증은 비공개로 보관합니다.\n"
                             "주소는 비공개로 관리하며 수신자의 열람·작업 착수는 아직 확인하지 않았습니다."}, "POST")
    else:
        raise ValueError("unsupported notification action")
    write(path, row)
    pm_field(api, policy, registered, {"메일 안내": f"{row['status']} · {aid}"})
    return {"assignment_id": aid, "recipient_name": row["recipient_name"], "state": row["status"],
            "message_id": row["message_id"], "recipient_read_confirmed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("assignment_file")
    prep.add_argument("--apply", action="store_true")
    sending = sub.add_parser("sending")
    sending.add_argument("assignment_id")
    sent = sub.add_parser("sent")
    sent.add_argument("assignment_id")
    sent.add_argument("--receipt-file", required=True)
    args = p.parse_args()
    try:
        api, policy = GitHub(), load_policy(POLICY)
        if args.command == "prepare":
            assignment = json.loads(Path(args.assignment_file).read_text(encoding="utf-8"))
            contacts = json.loads((PRIVATE / "contacts.json").read_text(encoding="utf-8"))
            result = prepare(api, policy, assignment, contacts, args.apply)
        else:
            receipt = json.loads(Path(args.receipt_file).read_text(encoding="utf-8")) if args.command == "sent" else None
            result = record(api, policy, args.assignment_id, args.command, receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
