"""PM-owned polling service: immutable deployed code, no branch code execution."""
# Linux polling host uses Python 3.10; Z parsing compatibility is intentional.
# ruff: noqa: FURB162
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# During source tests only; deployed bundle keeps common code beside this file.
if not (Path(__file__).parent / "project_report_common.py").exists():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from project_report_common import (
    FORMAL_STATES,
    PREFIX,
    GitHub,
    digest,
    load_policy,
    now,
    project_snapshot,
    projection,
    published_tasks,
    update_fields,
    validate_submission,
)

SYNC_PREFIX = "/lgax-sync"


def checked_snapshot(tasks, policy):
    """Validate data shape; authority comes only from deployed policy or PM sync."""
    if not isinstance(tasks, dict) or tasks.keys() != policy["tasks"].keys():
        raise ValueError("trusted snapshot must contain exactly the PM-registered tasks")
    for tid, registered in policy["tasks"].items():
        task = tasks[tid]
        if (not isinstance(task, dict) or task.get("id") != tid or task.get("owner") != registered["name"] or
            task.get("status") not in FORMAL_STATES or not isinstance(task.get("depends_on"), list) or
            any(dependency not in tasks for dependency in task["depends_on"])):
            raise ValueError("invalid trusted task snapshot; PM must reconcile")
    # Detach from published API objects and from the in-memory deployed policy.
    return json.loads(json.dumps(tasks, ensure_ascii=False))


def trusted_snapshot(state, policy):
    if not isinstance(policy.get("governance_issue_number"), int) or policy["governance_issue_number"] < 1:
        raise ValueError("PM-deployed governance Issue is required")
    if not re.fullmatch(r"[0-9a-f]{40}", policy.get("approved_main_commit", "")):
        raise ValueError("PM-deployed approved commit is required")
    approved = checked_snapshot(policy.get("approved_tasks"), policy)
    if "trusted_tasks" not in state and "trusted_commit" not in state:
        state.update(trusted_tasks=approved, trusted_commit=policy["approved_main_commit"],
                     trust_source="PM-deployed policy snapshot")
    if not re.fullmatch(r"[0-9a-f]{40}", state.get("trusted_commit", "")):
        raise ValueError("invalid private trusted snapshot commit; refuse an insecure fallback")
    state["trusted_tasks"] = checked_snapshot(state.get("trusted_tasks"), policy)
    return state["trusted_tasks"]


def validate_formal_sync(policy, comment, published_commit):
    """GitHub authenticates the comment actor; JSON is inert snapshot approval."""
    if comment["user"]["login"] != policy["pm_account"]:
        raise ValueError("only the authenticated PM may approve a formal snapshot")
    if comment["issue_url"] != f"https://api.github.com/repos/{policy['repo']}/issues/{policy['governance_issue_number']}":
        raise ValueError("formal sync must be posted to the registered governance Issue")
    if comment["created_at"] != comment["updated_at"]:
        raise ValueError("edited formal sync commands are not accepted; post a new command")
    created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
    floor = datetime.fromisoformat(policy["accept_reports_after"].replace("Z", "+00:00"))
    if created < floor:
        raise ValueError("formal sync predates the PM-deployed acceptance floor")
    match = re.fullmatch(r"/lgax-sync\r?\n```json\r?\n([\s\S]+?)\r?\n```\s*", comment["body"])
    if not match or len(comment["body"]) > 500:
        raise ValueError("formal sync requires exactly one fenced JSON commit object")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate formal sync key")
            result[key] = value
        return result
    command = json.loads(match[1], object_pairs_hook=unique)
    if (not isinstance(command, dict) or command.keys() != {"commit"} or
        not isinstance(command["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", command["commit"])):
        raise ValueError("formal sync accepts only one full immutable commit")
    if command["commit"] != published_commit:
        raise ValueError("formal sync commit must equal the current observed main snapshot")
    return command["commit"]


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def receipt(api, policy, row):
    marker = f"LGAX-RECEIPT {row['comment_id']} "
    comments = api.pages(f"repos/{policy['repo']}/issues/{row['issue_number']}/comments")
    existing = next((c for c in comments if c["user"]["login"] == policy["pm_account"] and c["body"].startswith(marker)), None)
    if existing:
        return existing["html_url"]
    accepted = row["outcome"] == "accepted"
    body = marker + ("ACCEPTED" if accepted else "REJECTED") + "\n"
    if accepted and row.get("type") == "formal_sync":
        body += (f"PM 공식 상태 스냅샷 승인 반영 · commit `{row['commit']}`\n"
                 f"원 승인: {row['url']}\n원문 SHA-256: `{row['body_sha256']}`\n"
                 "인증된 PM의 명시적 승인으로 비공개 공식 상태 기준을 갱신했습니다. "
                 "main 파일 변경만으로 승인하지 않으며 모델 실행 품질을 별도로 입증하지 않습니다.")
    elif accepted:
        body += (f"자동 반영: `{row['task_id']}` · `{row['status']}`\n"
                 f"원 보고: {row['url']}\n원문 SHA-256: `{row['body_sha256']}`\n"
                 f"[프로젝트]({policy['project_url']})의 자기보고·최근 보고·다음 행동과 기본 Status를 갱신했습니다.\n"
                 "계정·담당·기록 버전·PR 조건의 검사입니다. 실제 실행 품질·PM 승인·병합·전체 완료를 판정하지 않습니다.")
    else:
        body += "반영하지 않음: " + row["reason"] + "\n수정 후 새 보고 댓글을 작성하세요. 이전 댓글을 편집하지 마세요."
    return api.api(f"repos/{policy['repo']}/issues/{row['issue_number']}/comments", {"body": body}, "POST")["html_url"]


def tick(api, policy, state_dir):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {
        "since": policy["accept_reports_after"], "seen": {}, "latest": {}}
    started = now()
    tasks = trusted_snapshot(state, policy)
    published, commit = published_tasks(api, policy)
    board = project_snapshot(api, policy)
    if not {"Status", "팀원 보고", "최근 보고", "다음 행동"} <= board["fields"].keys():
        raise ValueError("PM must provision report fields first")
    since = (datetime.fromisoformat(state["since"].replace("Z", "+00:00")) - timedelta(seconds=15)).isoformat()
    from urllib.parse import quote
    comments = api.pages(f"repos/{policy['repo']}/issues/comments?sort=created&direction=asc&since={quote(since)}")
    known_issues = {t["issue_number"] for t in policy["tasks"].values()}
    # Explicit PM snapshot approvals precede self-report validation in the same poll.
    for prefix in (SYNC_PREFIX, PREFIX):
        for comment in sorted(comments, key=lambda c: c["id"]):
            if not comment["body"].startswith(prefix) or str(comment["id"]) in state["seen"]:
                continue
            formal_sync = prefix == SYNC_PREFIX
            if not formal_sync and comment["created_at"] < policy["accept_reports_after"]:
                continue
            issue_number = int(comment["issue_url"].rsplit("/", 1)[-1])
            if not formal_sync and issue_number not in known_issues:
                continue
            base = {"comment_id": comment["id"], "issue_number": issue_number, "url": comment["html_url"],
                    "at": comment["created_at"], "body_sha256": digest(comment["body"]), "receipt_url": None,
                    "type": "formal_sync" if formal_sync else "self_report"}
            try:
                if formal_sync:
                    approved_commit = validate_formal_sync(policy, comment, commit)
                    approved_tasks = checked_snapshot(published, policy)
                else:
                    accepted = validate_submission(api, policy, comment, tasks)
            except (ValueError, KeyError, TypeError) as exc:
                # Transport/permission failures retry and are never user-report rejection.
                state["seen"][str(comment["id"])] = {**base, "outcome": "rejected", "reason": str(exc)}
            else:
                if formal_sync:
                    state.update(trusted_tasks=approved_tasks, trusted_commit=approved_commit,
                                 trust_source=comment["html_url"])
                    tasks = state["trusted_tasks"]
                    state["seen"][str(comment["id"])] = {**base, "outcome": "accepted", "commit": approved_commit}
                else:
                    state["seen"][str(comment["id"])] = {**base, "outcome": "accepted",
                                                        "task_id": accepted["report"]["task_id"],
                                                        "status": accepted["report"]["status"]}
                    state["latest"][accepted["report"]["task_id"]] = accepted
            write_json(state_file, state)  # Durable trust/report intent precedes project writes.
    mutations = []
    for tid, registered in policy["tasks"].items():
        item = board["items"].get(registered["issue_number"])
        if not item or item["id"] != registered["item_id"]:
            raise ValueError("registered project item changed; PM must reconcile")
        updates = update_fields(api, policy, board, item, projection(tasks[tid], state["latest"].get(tid)))
        if updates:
            mutations.append({"task_id": tid, "fields": updates})
    # Receipt only after every projection succeeded. Partial writes retry idempotently.
    for row in state["seen"].values():
        if not row["receipt_url"]:
            row["receipt_url"] = receipt(api, policy, row)
            write_json(state_file, state)
    state["since"] = started
    state["last_success"] = now()
    state["published_main_commit"] = commit
    write_json(state_file, state)
    result = {"at": state["last_success"], "main_commit": commit, "accepted": sum(r["outcome"] == "accepted" for r in state["seen"].values()),
              "rejected": sum(r["outcome"] == "rejected" for r in state["seen"].values()), "mutations": mutations,
              "published_main_commit": commit, "trusted_main_commit": state["trusted_commit"],
              "unapproved_state_changes": [tid for tid in policy["tasks"] if published[tid] != tasks[tid]],
              "authenticated_as": policy["pm_account"], "semantic_verification": False}
    write_json(state_dir / "health.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--policy", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--interval", type=int, default=45)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    if args.interval < 30:
        p.error("minimum poll interval is 30 seconds")
    token_file = Path(args.token_file)
    if os.name != "nt" and (token_file.stat().st_mode & 0o077 or token_file.stat().st_uid != os.getuid()):
        raise ValueError("credential file must be owned by service user, mode 0600")
    policy = load_policy(args.policy)
    api = GitHub(token_file.read_text(encoding="utf-8").strip())
    if api.api("user")["login"] != policy["pm_account"]:
        raise ValueError("service credential must authenticate the configured PM")
    import fcntl
    Path(args.state_dir).mkdir(parents=True, exist_ok=True)
    with (Path(args.state_dir) / "worker.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                result = tick(api, policy, args.state_dir)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as exc:
                # Raw API responses, comments and tokens never go into process logs.
                print(json.dumps({"at": now(), "poll_ok": False, "error_type": type(exc).__name__}), flush=True)
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
