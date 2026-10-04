"""Receive an owner's immutable PR evidence as the authenticated PM, never as owner_finish.

Only local intake/individual records change. No GitHub mutation, owner execution,
PM approval, merge, integration, requirement coverage, or final completion occurs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

if __package__:
    from .phase2 import (
        ROOT,
        adoption_errors,
        artifact_errors,
        fingerprint,
        get_task,
        is_pm,
        load,
        now,
        read,
        save_task,
        task_path,
        write,
    )
    from .project_report_common import GitHub
else:
    from phase2 import (
        ROOT,
        adoption_errors,
        artifact_errors,
        fingerprint,
        get_task,
        is_pm,
        load,
        now,
        read,
        save_task,
        task_path,
        write,
    )
    from project_report_common import GitHub

REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
PM_ACCOUNT = "jeongiryang"
ALLOWED = {"ready", "pending", "doing", "blocked", "individual_verified"}


def git(root, *args):
    result = subprocess.run(
        ["git", "--no-replace-objects", *args], cwd=root, capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("fixed Git object missing or invalid; fetch the submitted history before intake")
    return result.stdout


def path_in_repo(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError("nonempty repository-relative path required")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts or ":" in value:
        raise ValueError("unsafe repository-relative path")
    if path.parts[0] in {".git", "private"}:
        raise ValueError("private/Git internals cannot be public intake evidence")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise ValueError("evidence/receipt must stay inside repository without symlinks")
    return path.as_posix(), target


def blob(root, commit, path):
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("full immutable Git commit required")
    normalized, _ = path_in_repo(root, path)
    entry = git(root, "ls-tree", "-z", commit, "--", normalized)
    if not entry or entry.split(b" ", 1)[0] not in {b"100644", b"100755"}:
        raise ValueError("submitted path must be a tracked regular Git blob")
    return git(root, "show", f"{commit}:{normalized}")


def validate_pr(pr, number, account):
    if (pr.get("number") != number or pr.get("user", {}).get("login") != account
            or pr.get("html_url") != f"https://github.com/{REPO}/pull/{number}"):
        raise ValueError("actual assigned owner's PR in the registered repository required")
    if (pr.get("head", {}).get("repo", {}).get("full_name") != REPO
            or pr.get("base", {}).get("repo", {}).get("full_name") != REPO
            or pr.get("base", {}).get("ref") != "main"):
        raise ValueError("same-repository, main-target PR required; reconcile stacked PR base first")
    if pr.get("draft") or (pr.get("state") != "open" and pr.get("merged") is not True):
        raise ValueError("non-draft open or actually merged owner PR required")
    head = pr.get("head", {}).get("sha")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("actual full PR head SHA required")
    return head


def receive(root, bundle, tid, number, evidence_path, receipt_path, api, *, apply=False):
    """Read live GitHub identity/source, then optionally record PM intake only."""
    root = Path(root).resolve()
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise ValueError("positive PR number required")
    actual_pm = api.api("user").get("login")
    if actual_pm != PM_ACCOUNT or bundle["workflow"]["pm"]["account"] != PM_ACCOUNT:
        raise ValueError("actual authenticated GitHub PM account jeongiryang required")
    is_pm(bundle, actual_pm)
    task = get_task(bundle, tid)
    if task.get("status") not in ALLOWED:
        raise ValueError("intake cannot reopen approved/merged/review-requested work")
    errors = adoption_errors(root, bundle, task)
    if errors:
        raise ValueError("; ".join(errors))
    waiting = [dep for dep in task["depends_on"] if bundle["tasks"][dep]["status"] != "done"]
    if waiting:
        raise ValueError("unfinished dependencies; no intake/state mutation: " + ", ".join(waiting))
    account = next(r["account"] for r in bundle["workflow"]["roles"] if r["name"] == task["owner"])
    pr = api.api(f"repos/{REPO}/pulls/{number}")
    head = validate_pr(pr, number, account)
    normalized, _ = path_in_repo(root, evidence_path)
    stamp = fingerprint(root, normalized)
    source_bytes = blob(root, head, normalized)
    if hashlib.sha256(source_bytes).hexdigest() != stamp["sha256"]:
        raise ValueError("local owner artifact bytes must match the actual PR head blob")
    artifact = json.loads(source_bytes.decode("utf-8-sig"))
    if not isinstance(artifact, dict) or artifact.get("task_id") != tid or artifact.get("owner") != task["owner"]:
        raise ValueError("owner artifact task/owner mismatch")
    tested = artifact.get("tested_commit")
    if not isinstance(tested, str) or not re.fullmatch(r"[0-9a-f]{40}", tested):
        raise ValueError("owner evidence must name its actual full tested commit")
    git(root, "merge-base", "--is-ancestor", tested, head)
    for record in artifact.get("code_versions", []) + artifact.get("source_versions", []):
        if not isinstance(record, dict):
            raise TypeError("version records must be objects")
        version = record.get("git_commit", tested)
        observed = blob(root, version, record.get("path"))
        if hashlib.sha256(observed).hexdigest() != record.get("sha256"):
            raise ValueError("owner source/code hash does not match the fixed Git blob")
        if blob(root, tested, record["path"]) != observed:
            raise ValueError("version record differs from the claimed owner tested commit")
        if blob(root, head, record["path"]) != observed:
            raise ValueError("tested code/source changed at submitted PR head; fresh owner evidence required")
    for check in artifact.get("checks", []):
        record = check.get("evidence") if isinstance(check, dict) else None
        if not isinstance(record, dict):
            raise TypeError("each check needs fixed output evidence")
        output = blob(root, head, record.get("path"))
        if hashlib.sha256(output).hexdigest() != record.get("sha256"):
            raise ValueError("output evidence hash does not match submitted PR head")
    errors = artifact_errors(root, artifact, task["allowed_execution_kinds"])
    if errors:
        raise ValueError("; ".join(errors))
    if task.get("individual_evidence") and task["individual_evidence"] != stamp:
        raise ValueError("existing owner evidence differs; preserve it and request an explicit revision")
    receipt_rel, receipt_file = path_in_repo(root, receipt_path)
    if receipt_file.suffix != ".json" or receipt_file.exists() or receipt_rel == normalized:
        raise ValueError("new .json receipt path required; never overwrite owner/source evidence")
    if receipt_rel.startswith("harness/phase2/tasks/"):
        raise ValueError("receipt cannot replace a task record")
    receipt = {
        "schema_version": 1, "task_id": tid, "pm": bundle["workflow"]["pm"]["name"],
        "authenticated_pm": actual_pm, "submitted_by": account, "owner": task["owner"],
        "decision": "received", "observed_at": now(),
        "source": {"kind": "GitHub PR API + immutable Git blobs", "repo": REPO,
                   "pull_request_url": pr["html_url"], "pull_request_number": number,
                   "author": account, "head_commit": head, "base_ref": "main",
                   "state": pr["state"], "merged": pr.get("merged") is True},
        "individual_evidence": {**stamp, "git_commit": head}, "owner_tested_commit": tested,
        "dependencies": [{"task_id": dep, "status": "done"} for dep in task["depends_on"]],
        "observations": ["Owner PR/artifact/code/source/output provenance and declared passing checks matched."],
        "limitations": ["Intake does not independently rerun owner checks or authenticate their execution.",
                        "No PM approval, actual merge, post-merge integration, requirement coverage or Done is recorded."],
    }
    result = {"validated": True, "applied": False, "task_id": tid, "receipt_path": receipt_rel,
              "next_state": "individual_verified", "receipt": receipt}
    if not apply:
        return result
    # Refuse races rather than silently replacing a newer submission/dependency record.
    for task_id in [tid, *task["depends_on"]]:
        if read(root, task_path(task_id)) != bundle["tasks"][task_id]:
            raise ValueError("task/dependency changed during intake; reload and inspect again")
    latest = api.api(f"repos/{REPO}/pulls/{number}")
    if validate_pr(latest, number, account) != head or latest.get("state") != pr.get("state"):
        raise ValueError("PR changed during intake; inspect the new version")
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    write(root, receipt_rel, receipt)
    intake_stamp = fingerprint(root, receipt_rel)
    updated = copy.deepcopy(task)
    updated.update(status="individual_verified", individual_evidence=stamp, pm_intake=intake_stamp,
                   block_reason=None)
    save_task(root, updated, "PM_receive_submission")
    bundle["tasks"][tid] = updated
    result.update(applied=True, pm_intake=intake_stamp)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = receive(ROOT, load(ROOT), args.task_id, args.pr, args.evidence, args.receipt,
                         GitHub(), apply=args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({"ok": False, "applied": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
