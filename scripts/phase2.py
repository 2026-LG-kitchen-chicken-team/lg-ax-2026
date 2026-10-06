"""Phase-2 task packets and evidence gates; never executes an Agent or submits files.

AGENTS/CLAUDE govern who may make decisions. --actor records a declared identity,
not an authentication check. Actual GitHub approval/merge links belong in evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "harness/phase2"
EXPECTED_REQUIREMENTS = {f"R{i:02d}" for i in range(1, 29)} | {f"E{i:02d}" for i in range(1, 4)}


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8-sig"))


def write(root, path, value):
    target = root / path
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(target)


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def fingerprint(root, path):
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f"evidence must be an existing file inside repository: {path}")
    return {"path": target.relative_to(root.resolve()).as_posix(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def record_errors(root, record):
    if not isinstance(record, dict):
        return ["path/sha256 evidence record required"]
    # Source hashes can point at a frozen commit, so later unrelated edits do not
    # invalidate every historical task. Run JSON/output evidence stays file based.
    if record.get("git_commit"):
        path = record.get("path", "")
        if not isinstance(path, str) or not path or not (root / path).resolve().is_relative_to(root.resolve()):
            return ["versioned source path outside repository"]
        if not re.fullmatch(r"[0-9a-f]{40}", record["git_commit"]):
            return ["full source commit required"]
        result = subprocess.run(["git", "--no-replace-objects", "show", f"{record['git_commit']}:{path}"], cwd=root, capture_output=True, check=False)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest() != record.get("sha256"):
            return [f"versioned source hash mismatch: {path}"]
        return []
    try:
        actual = fingerprint(root, record.get("path", ""))
    except (ValueError, OSError, TypeError):
        return ["evidence missing or outside repository"]
    if any(actual[k] != record.get(k) for k in ("path", "sha256")):
        return [f"evidence changed: {actual['path']}"]
    return []


def intake_errors(root, bundle, task):
    """Offline integrity of PM intake; not fresh GitHub identity/PR authentication."""
    stamp = task.get("pm_intake")
    if stamp is None:
        if any(row.get("action") == "PM_receive_submission" for row in task.get("history", [])):
            return ["PM intake action requires its receipt record"]
        return []
    errors = record_errors(root, stamp)
    if errors:
        return errors
    try:
        actual = fingerprint(root, stamp["path"])
    except (ValueError, OSError, TypeError):
        return ["PM intake receipt missing locally"]
    if any(actual[k] != stamp.get(k) for k in ("path", "sha256")):
        return ["PM intake receipt local bytes differ from recorded fingerprint"]
    try:
        receipt = read(root, stamp["path"])
    except (ValueError, OSError, TypeError):
        return ["PM intake receipt must be readable JSON"]
    if not isinstance(receipt, dict):
        return ["PM intake receipt must be an object"]
    pm = bundle["workflow"]["pm"]
    role = next((r for r in bundle["workflow"]["roles"] if r.get("name") == task.get("owner")), {})
    if (receipt.get("schema_version") != 1 or receipt.get("task_id") != task.get("id")
            or receipt.get("owner") != task.get("owner") or receipt.get("pm") != pm.get("name")
            or receipt.get("authenticated_pm") != pm.get("account")
            or receipt.get("submitted_by") != role.get("account") or receipt.get("decision") != "received"):
        errors.append("PM intake task/owner/PM/submitted account or decision mismatch")
    source = receipt.get("source")
    if not isinstance(source, dict):
        errors.append("PM intake PR source object required")
        source = {}
    number = source.get("pull_request_number")
    # A transfer preserves Git objects and immutable intake receipts. Accept only
    # the two explicitly verified identities of repository ID 1389435290.
    repo = source.get("repo")
    known_repos = {"jeongiryang/lg-ax-2026", "2026-LG-kitchen-chicken-team/lg-ax-2026"}
    if (not isinstance(number, int) or isinstance(number, bool) or number <= 0
            or not isinstance(repo, str) or repo not in known_repos
            or source.get("pull_request_url") != f"https://github.com/{repo}/pull/{number}"
            or source.get("author") != role.get("account") or source.get("base_ref") != "main"
            or source.get("kind") != "GitHub PR API + immutable Git blobs"):
        errors.append("PM intake PR/repository/owner source mismatch")
    if (not isinstance(source.get("merged"), bool)
            or (source.get("state"), source.get("merged")) not in (("open", False), ("closed", True))):
        errors.append("PM intake must reference an open or actually merged PR")
    head = source.get("head_commit")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        errors.append("PM intake actual full PR head required")
    submitted = receipt.get("individual_evidence")
    individual = task.get("individual_evidence")
    if (not isinstance(submitted, dict) or not isinstance(individual, dict)
            or any(submitted.get(k) != individual.get(k) for k in ("path", "sha256"))
            or submitted.get("git_commit") != head):
        errors.append("PM intake must match exact original owner evidence and PR head")
    elif isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head):
        errors.extend(record_errors(root, submitted))
        if not record_errors(root, individual):
            owner_artifact = read(root, individual["path"])
            tested = receipt.get("owner_tested_commit")
            if (not isinstance(owner_artifact, dict) or tested != owner_artifact.get("tested_commit")
                    or not isinstance(tested, str) or not re.fullmatch(r"[0-9a-f]{40}", tested)):
                errors.append("PM intake tested commit must match original owner artifact")
            else:
                ancestry = subprocess.run(["git", "--no-replace-objects", "merge-base", "--is-ancestor", tested, head],
                                          cwd=root, capture_output=True, check=False)
                if ancestry.returncode:
                    errors.append("PM intake owner tested commit must precede submitted PR head")
    dependencies = receipt.get("dependencies")
    expected = [{"task_id": dep, "status": "done"} for dep in task.get("depends_on", [])]
    if dependencies != expected:
        errors.append("PM intake dependency snapshot mismatch")
    if any(bundle["tasks"].get(dep, {}).get("status") != "done" for dep in task.get("depends_on", [])):
        errors.append("PM intake unfinished dependencies")
    try:
        observed = datetime.fromisoformat(receipt.get("observed_at", ""))
        if observed.tzinfo is None:
            errors.append("PM intake observation must include timezone")
    except (ValueError, TypeError):
        errors.append("PM intake observation timestamp required")
    return errors


def load(root):
    bundle = {name: read(root, f"{BASE}/{file}") for name, file in (
        ("workflow", "workflow.json"), ("state", "state.json"),
        ("requirements", "requirements.json"), ("checks", "checks.json"),
        ("sources", "sources.lock.json"), ("archive", "phase1_archive.lock.json"),
        ("models", "models.lock.json"))}
    bundle["tasks"] = {p.stem: read(root, p.relative_to(root)) for p in sorted((root / BASE / "tasks").glob("*.json"))}
    bundle["_root"] = root
    return bundle


def task_path(task_id):
    if not re.fullmatch(r"P2-[A-Z]+-\d{3}", task_id):
        raise ValueError("invalid task ID")
    return f"{BASE}/tasks/{task_id}.json"


def get_task(bundle, task_id):
    if task_id not in bundle["tasks"]:
        raise ValueError("unknown task ID")
    return bundle["tasks"][task_id]


def is_pm(bundle, actor):
    pm = bundle["workflow"]["pm"]
    if actor not in (pm["name"], pm["account"]):
        raise ValueError("PM actor required; record actual review and merge evidence")


def is_owner(bundle, task, actor):
    role = next(r for r in bundle["workflow"]["roles"] if r["name"] == task["owner"])
    if actor not in (role["name"], role["account"]):
        raise ValueError("task owner actor required")


def adoption_errors(root, bundle, task):
    """A proposed expansion remains an inactive proposal until PM adoption."""
    if task.get("scope") != "proposed_extension":
        return []
    errors = []
    if task.get("adoption_required") is not True:
        errors.append("proposed extension must explicitly require PM adoption")
    record = task.get("adoption")
    if not record:
        return errors + ["PM adoption evidence required before extension execution"]
    errors.extend(record_errors(root, record))
    if errors:
        return errors
    a = read(root, record["path"])
    if not isinstance(a, dict) or a.get("task_id") != task["id"] or a.get("pm") != bundle["workflow"]["pm"]["name"]:
        return ["extension adoption requires configured PM and exact task ID"]
    if a.get("decision") != "adopted" or not a.get("observations"):
        errors.append("explicit PM adoption decision and observations required")
    if a.get("instruction_source") not in ("PM assignment", "user instruction") or not a.get("instruction_quote"):
        errors.append("actual assignment source and instruction quote required")
    return errors


def adopt_extension(root, bundle, tid, artifact_path, actor):
    is_pm(bundle, actor)
    task = get_task(bundle, tid)
    if task.get("scope") != "proposed_extension" or task["status"] not in ("pending", "deferred", "blocked"):
        raise ValueError("only inactive proposed extensions can be adopted")
    adopted = {**task, "adoption": fingerprint(root, artifact_path)}
    errors = adoption_errors(root, bundle, adopted)
    if errors:
        raise ValueError("; ".join(errors))
    task.update(adoption=adopted["adoption"], status="ready" if all(bundle["tasks"][d]["status"] == "done" for d in task["depends_on"]) else "pending", block_reason=None)
    save_task(root, task, "PM_adopt_extension")


def artifact_errors(root, artifact, kinds):
    if not isinstance(artifact, dict):
        return ["execution artifact must be a JSON object"]
    errors = []
    if artifact.get("execution_kind") not in kinds:
        errors.append("execution_kind does not satisfy task/check contract")
    if artifact.get("result") != "pass":
        errors.append("passing observed result required")
    for field in ("observations", "limitations", "checks", "code_versions", "source_versions"):
        if not isinstance(artifact.get(field), list) or not artifact[field]:
            errors.append(f"nonempty {field} required")
    for row in artifact.get("code_versions", []) if isinstance(artifact.get("code_versions"), list) else []:
        errors.extend(record_errors(root, row))
    for row in artifact.get("checks", []) if isinstance(artifact.get("checks"), list) else []:
        if not isinstance(row, dict):
            errors.append("each check must be a JSON object")
            continue
        if not row.get("name") or row.get("passed") is not True:
            errors.append("each check requires a name and observed passing result")
        errors.extend(record_errors(root, row.get("evidence")))
    for row in artifact.get("source_versions", []) if isinstance(artifact.get("source_versions"), list) else []:
        errors.extend(record_errors(root, row))
    if artifact.get("execution_kind") == "live_model":
        models = artifact.get("models", [])
        if not isinstance(models, list) or not models or not all(isinstance(m, dict) and all(m.get(k) for k in ("model_id", "revision", "license", "runtime", "settings")) for m in models):
            errors.append("live_model requires model ID/revision/license/runtime/settings")
    text = json.dumps(artifact, ensure_ascii=False)
    if "REPLACE_WITH_ACTUAL_RESULT" in text:
        errors.append("placeholder is not evidence")
    return errors


def automatic_completion_errors(root, task):
    """Check an exported multi-unit receipt's integrity, never live authority.

    Authentication, actual publication and both online acknowledgements belong
    to the separately deployed PM broker. A manifest is not their substitute.
    """
    from services.automation.completion import ArtifactRef, CompletionError, validate_completion_bundle

    try:
        stamp = task.get("completion") or {}
        receipt_hash = stamp.get("parent_receipt_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", receipt_hash):
            raise ValueError("exact parent receipt digest required")
        prefix = f"evals/automation-completion/{task['id']}/{receipt_hash}/"
        if stamp.get("path") != prefix + "bundle.json" or task.get("status") != "done":
            raise ValueError("automatic completion needs canonical bundle and Done state")
        errors = record_errors(root, stamp)
        if errors:
            return errors
        raw = (root / stamp["path"]).read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("completion bundle exceeds bound")
        manifest = json.loads(raw)
        files = manifest.get("artifact_files", {})
        if not isinstance(files, dict) or not 1 <= len(files) <= 256:
            raise ValueError("bounded artifact map required")
        total = 0
        assets = {}
        for digest, path in files.items():
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid artifact digest")
            if path != prefix + f"assets/{digest}.blob":
                raise ValueError("noncanonical artifact path")
            target = root / path
            # Reject symlinks/junctions at every component, even if they resolve
            # inside the checkout. CI reads the same literal immutable bytes.
            cursor = target
            while cursor != root:
                if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
                    raise ValueError("linked completion artifact prohibited")
                cursor = cursor.parent
            data = target.read_bytes()
            total += len(data)
            if len(data) > 2 * 1024 * 1024 or total > 16 * 1024 * 1024:
                raise ValueError("completion artifacts exceed bound")
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("completion artifact changed")
            assets[digest] = data

        def reader(ref):
            if ref.sha256 not in assets:
                raise ValueError("unexported completion artifact")
            return assets[ref.sha256]

        validate_completion_bundle(manifest, reader, expected_task_id=task["id"],
                                   expected_receipt_sha256=receipt_hash)
        source = json.loads(reader(ArtifactRef.parse(manifest["sources"]["task"])))
        for key in ("id", "owner", "scope", "requirement_ids", "actions", "depends_on", "allowed_execution_kinds"):
            if source.get(key) != task.get(key):
                raise ValueError("current task differs from immutable completion contract: " + key)
        return []
    except (CompletionError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return ["automatic parent completion invalid: " + str(exc)]


def validate(root, bundle):
    errors = []
    workflow = bundle["workflow"]
    roles = workflow.get("roles", [])
    owners = {r.get("name") for r in roles}
    if len(owners) != 4 or len({r.get("account") for r in roles}) != 4:
        errors.append("four unique owner names and accounts required")
    if workflow.get("pm", {}).get("name") not in owners:
        errors.append("PM must be a configured owner")
    requirements = bundle["requirements"].get("requirements", [])
    ids = [r.get("id") for r in requirements]
    if set(ids) != EXPECTED_REQUIREMENTS or len(ids) != 31:
        errors.append("exactly R01-R28/E01-E03 required")
    for r in requirements:
        if r.get("owner") not in owners or not r.get("acceptance") or not r.get("commitment"):
            errors.append(f"requirement {r.get('id')}: owner/commitment/acceptance required")
        if r.get("status") not in ("pending", "implemented", "verified"):
            errors.append(f"requirement {r.get('id')}: invalid status")
        if r.get("status") == "verified":
            coverage = r.get("coverage") or {}
            errors.extend(record_errors(root, coverage.get("evidence")))
            if coverage.get("pm") != workflow["pm"]["name"]:
                errors.append(f"requirement {r['id']}: PM coverage decision required")
            if coverage.get("evidence") and not record_errors(root, coverage["evidence"]):
                a = read(root, coverage["evidence"]["path"])
                if r["id"] not in a.get("requirement_ids", []):
                    errors.append(f"requirement {r['id']}: evidence must name requirement")
                errors.extend(f"requirement {r['id']}: {e}" for e in artifact_errors(root, a, ["live_service", "live_model", "live_client"]))
            task = bundle["tasks"].get(coverage.get("task_id"))
            if not task or task.get("status") != "done" or r["id"] not in task.get("requirement_ids", []):
                errors.append(f"requirement {r['id']}: completed linked task required")
    for tid, task in bundle["tasks"].items():
        if task.get("id") != tid or task.get("owner") not in owners:
            errors.append(f"task {tid}: owner/ID mismatch")
        if task.get("status") not in workflow["statuses"]:
            errors.append(f"task {tid}: invalid status")
        if not set(task.get("requirement_ids", [])) <= EXPECTED_REQUIREMENTS:
            errors.append(f"task {tid}: unknown requirement")
        if not set(task.get("depends_on", [])) <= set(bundle["tasks"]) or tid in task.get("depends_on", []):
            errors.append(f"task {tid}: invalid dependency")
        if task.get("status") == "blocked" and not task.get("block_reason"):
            errors.append(f"task {tid}: explicit block reason required")
        if task.get("scope") == "proposed_extension":
            if task.get("adoption_required") is not True:
                errors.append(f"task {tid}: proposed extension adoption_required must be true")
            if task.get("adoption") or task.get("status") not in ("pending", "blocked", "deferred"):
                errors.extend(f"task {tid}/adoption: {e}" for e in adoption_errors(root, bundle, task))
        protocol = task.get("completion_protocol")
        if protocol:
            if protocol != "trusted_auto_parent_v1":
                errors.append(f"task {tid}: unknown completion protocol")
            else:
                errors.extend(f"{tid}/completion: {e}" for e in automatic_completion_errors(root, task))
            continue
        for key in ("individual_evidence", "pm_review", "merge", "integration", "completion"):
            if task.get(key):
                errors.extend(f"{tid}/{key}: {e}" for e in record_errors(root, task[key]))
        errors.extend(f"{tid}/pm_intake: {e}" for e in intake_errors(root, bundle, task))
        individual = task.get("individual_evidence")
        if individual and not record_errors(root, individual):
            a = read(root, individual["path"])
            if a.get("task_id") != tid or a.get("owner") != task.get("owner"):
                errors.append(f"task {tid}: individual task/owner mismatch")
            errors.extend(f"{tid}/individual: {e}" for e in artifact_errors(root, a, task["allowed_execution_kinds"]))
        for key in ("pm_review", "merge", "integration", "completion"):
            record = task.get(key)
            if record and not record_errors(root, record):
                a = read(root, record["path"])
                if a.get("task_id") != tid or a.get("pm") != workflow["pm"]["name"]:
                    errors.append(f"task {tid}/{key}: configured PM/task ID required")
                if not individual or a.get("individual_evidence_sha256") != individual["sha256"]:
                    errors.append(f"task {tid}/{key}: individual evidence version mismatch")
                if key == "pm_review" and task.get("status") not in ("doing", "blocked") and a.get("decision") != "approved":
                    errors.append(f"task {tid}: PM has not approved")
                if key == "merge" and (not re.fullmatch(r"[0-9a-f]{40}", a.get("merge_commit", "")) or not a.get("pull_request_url")):
                    errors.append(f"task {tid}: actual merge commit/PR URL required")
                elif key == "merge":
                    commit = subprocess.run(["git", "cat-file", "-t", a["merge_commit"]], cwd=root, capture_output=True, text=True, check=False)
                    if commit.returncode or commit.stdout.strip() != "commit":
                        errors.append(f"task {tid}: merge commit not present locally; fetch history")
                if key == "integration":
                    errors.extend(f"{tid}/integration: {e}" for e in artifact_errors(root, a, task["allowed_execution_kinds"]))
                    mr = task.get("merge")
                    if not mr or record_errors(root, mr) or a.get("tested_commit") != read(root, mr["path"]).get("merge_commit"):
                        errors.append(f"task {tid}: integration does not match merge commit")
                if key == "completion" and (a.get("decision") != "complete" or not task.get("integration") or a.get("integration_evidence_sha256") != task["integration"]["sha256"]):
                    errors.append(f"task {tid}: exact integration evidence and explicit PM completion required")
        chain = ["individual_verified", "pm_review_requested", "pm_approved", "merged", "integration_verified", "done"]
        status = task.get("status")
        if status in chain:
            needed = ["individual_evidence"]
            if chain.index(status) >= 2:
                needed.append("pm_review")
            if chain.index(status) >= 3:
                needed.append("merge")
            if chain.index(status) >= 4:
                needed.append("integration")
            if status == "done":
                needed.append("completion")
            for key in needed:
                if not task.get(key):
                    errors.append(f"task {tid}: {status} requires {key}")
    # Detect cycles without rejecting uncompleted but well-formed backlogs.
    visiting, visited = set(), set()
    def walk(tid):
        if tid in visiting:
            errors.append(f"task dependency cycle: {tid}")
            return
        if tid in visited or tid not in bundle["tasks"]:
            return
        visiting.add(tid)
        for dep in bundle["tasks"][tid].get("depends_on", []):
            walk(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in bundle["tasks"]:
        walk(tid)
    for record in bundle["archive"].get("records", []):
        errors.extend(f"phase1 archive: {e}" for e in record_errors(root, record))
    for source in bundle["sources"].get("sources", []):
        if (root / source["path"]).exists() or source.get("required_when_missing", True):
            errors.extend(f"source {source['id']}: {e}" for e in record_errors(root, source))
    for check in bundle["checks"].get("checks", []):
        if check.get("status") == "verified":
            errors.extend(record_errors(root, check.get("evidence")))
            if check.get("evidence") and not record_errors(root, check["evidence"]):
                a = read(root, check["evidence"]["path"])
                if a.get("check_id") != check["id"]:
                    errors.append(f"check {check['id']}: check ID mismatch")
                errors.extend(f"check {check['id']}: {e}" for e in artifact_errors(root, a, check["allowed_execution_kinds"]))
        elif check.get("status") not in ("pending", "blocked"):
            errors.append(f"check {check.get('id')}: invalid status")
    return sorted(set(errors))


def ready_tasks(bundle, member=None):
    roles = bundle["workflow"]["roles"]
    if member and member not in {x for r in roles for x in (r["name"], r["account"])}:
        raise ValueError("unknown member")
    selected = []
    for t in bundle["tasks"].values():
        role = next(r for r in roles if r["name"] == t["owner"])
        if member and member not in (role["name"], role["account"]):
            continue
        if adoption_errors(bundle.get("_root", ROOT), bundle, t):
            continue
        if t["status"] in ("pending", "ready", "doing") and all(bundle["tasks"][d]["status"] == "done" for d in t["depends_on"]):
            selected.append(t)
    return sorted(selected, key=lambda t: (t["scope"] != "required", t["status"] != "doing", t["id"]))


def packet(bundle, tid):
    t = get_task(bundle, tid)
    return {"task": t, "notice": "Packet is an instruction to the current worker, not background execution.",
            "execution_authorized": not adoption_errors(bundle.get("_root", ROOT), bundle, t),
            "adoption_blockers": adoption_errors(bundle.get("_root", ROOT), bundle, t),
            "read_first": ["AGENTS.md", "CLAUDE.md", "docs/작업기록/README.md", f"docs/작업기록/{t['owner']}/README.md", f"docs/작업근거/{t['owner']}/README.md"],
            "evidence_contract": {"task_id": tid, "owner": t["owner"], "result": "pass", "execution_kind": t["allowed_execution_kinds"],
              "observations": ["actual result"], "code_versions": [{"path": "changed source", "sha256": "actual hash"}],
              "source_versions": [{"path": "fixed source/contract/input", "sha256": "actual hash"}], "models": [], "checks": [{"name": "actual command/check", "passed": True, "evidence": {"path": "immutable output", "sha256": "actual hash"}}], "limitations": ["actual limitation"]},
            "next_state_after_finish": "individual_verified; PM review/actual merge/integration still required"}


def save_task(root, task, action):
    task["history"].append({"at": now(), "action": action, "status": task["status"]})
    write(root, task_path(task["id"]), task)


def finish_task(root, bundle, tid, artifact_path, actor):
    task = get_task(bundle, tid)
    is_owner(bundle, task, actor)
    if adoption_errors(root, bundle, task):
        raise ValueError("proposed extension requires actual PM adoption before finish")
    if task["status"] not in ("ready", "pending", "doing", "blocked", "individual_verified", "pm_review_requested"):
        raise ValueError("task cannot finish from this status; reopen approved/merged work as a new task")
    if any(bundle["tasks"][d]["status"] != "done" for d in task["depends_on"]):
        raise ValueError("unfinished dependencies; fixture development may continue but completion is blocked")
    stamp = fingerprint(root, artifact_path)
    artifact = read(root, stamp["path"])
    errors = artifact_errors(root, artifact, task["allowed_execution_kinds"])
    if artifact.get("task_id") != tid or artifact.get("owner") != task["owner"]:
        errors.append("artifact task/owner mismatch")
    if errors:
        raise ValueError("; ".join(errors))
    task.update(status="individual_verified", individual_evidence=stamp, pm_review=None, merge=None, integration=None, completion=None, block_reason=None)
    save_task(root, task, "owner_finish")


def lifecycle(root, bundle, action, tid, artifact_path, actor):
    is_pm(bundle, actor)
    task = get_task(bundle, tid)
    if adoption_errors(root, bundle, task):
        raise ValueError("proposed extension requires actual PM adoption before review or completion")
    expected = {"review": ("individual_verified", "pm_review_requested"), "merge": ("pm_approved",), "verify": ("merged",), "complete": ("integration_verified",)}
    if task["status"] not in expected[action]:
        raise ValueError(f"{action} requires {expected[action]}")
    prior = task.get("individual_evidence")
    if not prior or record_errors(root, prior):
        raise ValueError("individual evidence stale or missing")
    # Ensure the tested source/output files still match the owner's observation.
    errors = artifact_errors(root, read(root, prior["path"]), task["allowed_execution_kinds"])
    if errors:
        raise ValueError("; ".join(errors))
    stamp = fingerprint(root, artifact_path)
    a = read(root, stamp["path"])
    if a.get("task_id") != tid or a.get("pm") != bundle["workflow"]["pm"]["name"] or not a.get("observations"):
        raise ValueError("task ID, actual PM review and observations required")
    if a.get("individual_evidence_sha256") != prior["sha256"]:
        raise ValueError("review must refer to exact individual evidence version")
    if action == "review":
        if a.get("decision") not in ("approved", "changes_requested"):
            raise ValueError("explicit PM decision required")
        task.update(status="pm_approved" if a["decision"] == "approved" else "doing", pm_review=stamp)
    elif action == "merge":
        commit = a.get("merge_commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or not a.get("pull_request_url"):
            raise ValueError("actual merge commit and PR URL required")
        check = subprocess.run(["git", "cat-file", "-t", commit], cwd=root, capture_output=True, text=True, check=False)
        if check.returncode or check.stdout.strip() != "commit":
            raise ValueError("merge commit must resolve to a real local Git commit")
        task.update(status="merged", merge=stamp)
    elif action == "verify":
        errors = artifact_errors(root, a, task["allowed_execution_kinds"])
        if errors:
            raise ValueError("; ".join(errors))
        merge_record = read(root, task["merge"]["path"])
        if a.get("tested_commit") != merge_record["merge_commit"]:
            raise ValueError("integration must test actual merge commit")
        task.update(status="integration_verified", integration=stamp)
    else:
        if a.get("decision") != "complete" or a.get("integration_evidence_sha256") != task["integration"]["sha256"]:
            raise ValueError("explicit PM completion and exact integration evidence required")
        task.update(status="done", completion=stamp)
    save_task(root, task, action)


def cover_requirement(root, bundle, rid, tid, artifact_path, actor):
    is_pm(bundle, actor)
    task = get_task(bundle, tid)
    row = next((r for r in bundle["requirements"]["requirements"] if r["id"] == rid), None)
    if not row or rid not in task["requirement_ids"] or task["status"] != "done":
        raise ValueError("linked done task required for requirement coverage")
    stamp = fingerprint(root, artifact_path)
    a = read(root, stamp["path"])
    if rid not in a.get("requirement_ids", []) or a.get("result") != "pass" or a.get("execution_kind") not in ("live_service", "live_model", "live_client"):
        raise ValueError("requirement coverage requires actual execution evidence naming the requirement")
    errors = artifact_errors(root, a, ["live_service", "live_model", "live_client"])
    if errors:
        raise ValueError("; ".join(errors))
    row.update(status="verified", coverage={"task_id": tid, "evidence": stamp, "pm": bundle["workflow"]["pm"]["name"], "at": now()})
    write(root, f"{BASE}/requirements.json", bundle["requirements"])


def record_check(root, bundle, artifact_path, actor):
    is_pm(bundle, actor)
    stamp = fingerprint(root, artifact_path)
    a = read(root, stamp["path"])
    row = next((r for r in bundle["checks"]["checks"] if r["id"] == a.get("check_id")), None)
    if not row:
        raise ValueError("unknown gate check ID")
    errors = artifact_errors(root, a, row["allowed_execution_kinds"])
    if errors:
        raise ValueError("; ".join(errors))
    row.update(status="verified", evidence=stamp, block_reason=None)
    write(root, f"{BASE}/checks.json", bundle["checks"])


def gate(root, bundle, name):
    errors = validate(root, bundle)
    if name not in bundle["workflow"]["gates"]:
        raise ValueError("unknown gate")
    checked = set()
    def check_group(group):
        if group in checked:
            return
        checked.add(group)
        for dep in bundle["workflow"]["gate_dependencies"].get(group, []):
            check_group(dep)
        for cid in bundle["workflow"]["gates"][group]:
            if cid in bundle["workflow"]["gates"]:
                check_group(cid)
                continue
            row = next((r for r in bundle["checks"]["checks"] if r["id"] == cid), None)
            if not row or row["status"] != "verified":
                reason = row.get("block_reason") if row else "check missing"
                errors.append(f"{group}/{cid}: {reason or 'actual evidence not yet verified'}")
    check_group(name)
    if name in ("integration", "evaluation", "release", "submission"):
        for r in bundle["requirements"]["requirements"]:
            if name == "integration" and (r["id"].startswith("E") or r["id"] == "R28"):
                continue
            if name == "evaluation" and r["id"] == "R28":
                continue
            if r["status"] != "verified":
                errors.append(f"requirement {r['id']}: actual implementation/evidence not verified")
    if name == "submission":
        deadline = bundle["workflow"]["deadline"]
        if not deadline.get("exact_time") or not deadline.get("submission_channel"):
            errors.append("exact submission time/channel still unconfirmed")
    return sorted(set(errors))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["status", "next", "packet", "adopt", "start", "block", "finish", "request-review", "review", "merge", "verify", "complete", "cover", "record-check", "validate", "gate"])
    p.add_argument("items", nargs="*")
    p.add_argument("--member")
    p.add_argument("--actor")
    p.add_argument("--reason")
    args = p.parse_args(argv)
    try:
        b = load(ROOT)
        cmd, items = args.command, args.items
        if cmd == "status":
            result = {"phase": "phase2", "framework_valid": not validate(ROOT, b), "external_success": False,
              "tasks": {tid: {**{k: t[k] for k in ("owner", "title", "status", "issue_url", "scope")},
                             "adoption_required": t.get("adoption_required", False), "adoption": t.get("adoption")} for tid, t in b["tasks"].items()},
              "requirement_coverage": {"verified": sum(r["status"] == "verified" for r in b["requirements"]["requirements"]), "total": 31},
              "setup_components": {n: {"pass": not gate(ROOT, b, n), "missing": gate(ROOT, b, n)} for n in ("setup_framework", "setup_external")},
              "legacy_state": b["archive"]["legacy_validation"], "note": b["workflow"]["notice"]}
            result["external_success"] = result["setup_components"]["setup_external"]["pass"]
        elif cmd == "next":
            ready = ready_tasks(b, args.member)
            result = {"member": args.member, "ready": [packet(b, t["id"]) for t in ready], "note": "No background execution or automatic task completion."}
        elif cmd == "packet":
            result = packet(b, items[0])
        elif cmd in ("validate", "gate"):
            errors = validate(ROOT, b) if cmd == "validate" else gate(ROOT, b, items[0])
            result = {"valid": not errors, "errors": errors, "meaning": "record structure/evidence integrity only" if cmd == "validate" else "actual gate readiness", "legacy": b["archive"]["legacy_validation"]["status"]}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if errors else 0
        elif cmd in ("start", "block", "request-review"):
            task = get_task(b, items[0])
            is_owner(b, task, args.actor)
            if cmd == "start":
                if task not in ready_tasks(b, task["owner"]):
                    raise ValueError("task not ready; inspect dependencies")
                task["status"] = "doing"
            elif cmd == "block":
                if not args.reason:
                    raise ValueError("explicit block reason required")
                task.update(status="blocked", block_reason=args.reason)
            else:
                if task["status"] != "individual_verified":
                    raise ValueError("individual verification required before review request")
                task["status"] = "pm_review_requested"
            save_task(ROOT, task, cmd)
            result = {"task_id": task["id"], "status": task["status"]}
        else:
            if cmd == "adopt":
                adopt_extension(ROOT, b, items[0], items[1], args.actor)
            elif cmd == "finish":
                finish_task(ROOT, b, items[0], items[1], args.actor)
            elif cmd in ("review", "merge", "verify", "complete"):
                lifecycle(ROOT, b, cmd, items[0], items[1], args.actor)
            elif cmd == "cover":
                cover_requirement(ROOT, b, items[0], items[1], items[2], args.actor)
            elif cmd == "record-check":
                record_check(ROOT, b, items[0], args.actor)
            result = {"recorded": cmd, "items": items, "note": "Recorded evidence does not authenticate actor or perform GitHub/Agent actions."}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        print(json.dumps({"valid": False, "blocked": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
