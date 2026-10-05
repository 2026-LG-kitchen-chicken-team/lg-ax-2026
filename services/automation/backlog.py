"""Fixed required-project backlog, with pure scheduling and append-only receipts.

This module never runs a model, changes policy, authenticates a sender, or marks a
phase2 task Done. The trusted PM persists its returned ledger under the existing
broker lock. Accepted inputs must come from collected broker receipts, not PR text.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath


class BacklogError(ValueError):
    """A fixed plan, receipt, or observation could not be safely interpreted."""


ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
OWNERS = {"jeongiryang", "unknownamed", "ginaginaring", "choigilung"}
ACTIVE = {"pending", "queued", "running", "stopping", "orphaned", "review_requested", "completed_review"}
EVENTS = {"released", "assigned", "accepted", "blocked", "unblocked", "parent_verified"}
FORBIDDEN = {".git", ".github", "private", "harness", "AGENTS.md", "CLAUDE.md", "services/automation"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise BacklogError("invalid immutable identifier")
    return value


def _path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "**" in value:
        raise BacklogError("expected narrow repository-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in value.split("/")):
        raise BacklogError("path escapes the assigned repository area")
    if any(value == item or value.startswith(item + "/") for item in FORBIDDEN):
        raise BacklogError("backlog may not edit protected operating policy or secrets")
    if any(char in value for char in "?[]") or "*" in value[:-1] or value == "*":
        raise BacklogError("only a terminal directory wildcard is allowed")
    return value


def paths_overlap(left, right):
    """Conservative conflict check for exact paths and directory-terminal globs."""
    left, right = _path(left), _path(right)
    if left == right:
        return True
    if left.endswith("*") and right.startswith(left[:-1]):
        return True
    return right.endswith("*") and left.startswith(right[:-1])


def validate_backlog(plan, *, registered_tasks=None):
    """Validate approved metadata; new tasks and extensions cannot be invented."""
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise BacklogError("unsupported fixed backlog")
    if plan.get("scope") != "required" or plan.get("repo") != "2026-LG-kitchen-chicken-team/lg-ax-2026":
        raise BacklogError("wrong repository or non-required scope")
    tasks, units = plan.get("tasks"), plan.get("capabilities")
    if not isinstance(tasks, dict) or not tasks or not isinstance(units, dict) or not units:
        raise BacklogError("fixed task and capability mappings are required")
    for task_id, task in tasks.items():
        _identifier(task_id)
        if task.get("owner") not in OWNERS or task.get("scope") != "required":
            raise BacklogError("required task owner/scope must be registered")
        if not isinstance(task.get("requirement_ids"), list) or not task["requirement_ids"]:
            raise BacklogError("parent requirements are required")
        if len(set(task["requirement_ids"])) != len(task["requirement_ids"]):
            raise BacklogError("duplicate parent requirement")
        if not isinstance(task.get("depends_on"), list) or any(dep not in tasks for dep in task["depends_on"]):
            raise BacklogError("parent dependency missing from fixed backlog")
        if registered_tasks is not None:
            original = registered_tasks.get(task_id)
            if original is None or any(task.get(key) != original.get(key) for key in
                    ("owner", "scope", "requirement_ids", "depends_on", "issue_number")):
                raise BacklogError("backlog changed registered parent contract")
    coverage = {task_id: set() for task_id in tasks}
    for unit_id, unit in units.items():
        _identifier(unit_id)
        task = tasks.get(unit.get("task_id"))
        if not task or unit.get("owner") != task["owner"] or unit.get("completes_task") is not False:
            raise BacklogError("capability must retain registered owner and never claim parent Done")
        requirements = unit.get("requirement_ids")
        if not isinstance(requirements, list) or not requirements or not set(requirements) <= set(task["requirement_ids"]):
            raise BacklogError("capability requirements escaped parent")
        coverage[unit["task_id"]].update(requirements)
        if not unit.get("allowed_paths") or not unit.get("acceptance") or not unit.get("evidence_requirements"):
            raise BacklogError("narrow implementation and evidence contract is required")
        for path in unit["allowed_paths"]:
            _path(path)
        commands = unit.get("validation_commands")
        if not isinstance(commands, list) or not commands or any(
                not isinstance(argv, list) or not argv or argv[0] not in {"uv", "npm"} or
                any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in argv) for argv in commands):
            raise BacklogError("fixed validation argv required; no arbitrary shell")
        dependencies = unit.get("depends_on_capabilities", [])
        if not isinstance(dependencies, list) or any(dep not in units or dep == unit_id for dep in dependencies):
            raise BacklogError("capability dependency missing or self-referential")
        if unit.get("execution_kind") not in {"fixture", "live_model", "live_service", "tooling"}:
            raise BacklogError("explicit execution kind required")
        if not isinstance(unit.get("required_environments", []), list):
            raise BacklogError("environment gates must be explicit")
        if unit.get("expose_independent_answers") is not False:
            raise BacklogError("developer may never receive independent evaluation answers")
    for task_id in tasks:
        if coverage[task_id] != set(tasks[task_id]["requirement_ids"]):
            raise BacklogError("fixed units do not cover every parent requirement")
    # Reject dependency cycles before a worker can enter a permanent silent wait.
    def acyclic(mapping, key):
        visiting, seen = set(), set()
        def visit(identifier):
            if identifier in visiting:
                raise BacklogError("fixed backlog has cyclic dependencies")
            if identifier not in seen:
                visiting.add(identifier)
                for dep in mapping[identifier].get(key, []):
                    visit(dep)
                visiting.remove(identifier)
                seen.add(identifier)
        for identifier in mapping:
            visit(identifier)
    acyclic(tasks, "depends_on")
    acyclic(units, "depends_on_capabilities")
    return deepcopy(plan)


def load_backlog(path: Path | str, expected_sha256: str, *, registered_tasks=None):
    """Read only a separately pinned plan; a repository file is not approval."""
    if not isinstance(expected_sha256, str) or not DIGEST.fullmatch(expected_sha256):
        raise BacklogError("actual reviewed plan SHA256 required")
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise BacklogError("fixed backlog digest mismatch")
    def strict_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BacklogError("duplicate JSON metadata key")
            result[key] = value
        return result
    return validate_backlog(json.loads(raw, object_pairs_hook=strict_object), registered_tasks=registered_tasks)


def verify_progress(plan, ledger):
    """Recompute immutable hash chain and parent mapping; never trust a flag."""
    if not isinstance(ledger, list):
        raise BacklogError("append-only ledger array required")
    previous, identifiers = "0" * 64, set()
    state = {}
    for index, record in enumerate(ledger, 1):
        if not isinstance(record, dict):
            raise BacklogError("malformed progress record")
        body = {key: value for key, value in record.items() if key != "digest"}
        if record.get("seq") != index or record.get("previous") != previous or record.get("plan_digest") != _digest(plan) or record.get("digest") != _digest(body):
            raise BacklogError("progress chain was changed or belongs to another plan")
        event_id = _identifier(record.get("event_id"))
        if event_id in identifiers:
            raise BacklogError("replayed progress event")
        identifiers.add(event_id)
        _validate_event(plan, state, record)
        state[record["capability_id"]] = record["event"]
        previous = record["digest"]
    return state


def _validate_event(plan, state, record):
    unit_id = record.get("capability_id")
    unit = plan["capabilities"].get(unit_id)
    event = record.get("event")
    if not unit or event not in EVENTS or record.get("task_id") != unit["task_id"]:
        raise BacklogError("progress event escaped fixed parent mapping")
    prior = state.get(unit_id)
    transitions = {None: {"released", "blocked"}, "released": {"assigned", "blocked"},
                  "assigned": {"accepted", "blocked"}, "blocked": {"unblocked"},
                  "unblocked": {"released", "assigned", "blocked"}, "accepted": {"parent_verified"},
                  "parent_verified": set()}
    if event not in transitions.get(prior, set()):
        raise BacklogError("progress transition would rerun accepted work or bypass a blocker")
    receipt = record.get("receipt")
    if not isinstance(receipt, dict):
        raise BacklogError("explicit trusted receipt required")
    if event in {"released", "assigned", "accepted", "parent_verified"} and not SHA.fullmatch(receipt.get("base_commit", "")):
        raise BacklogError("actual fixed base commit is required")
    if event == "assigned" and not ID.fullmatch(receipt.get("job_id", "")):
        raise BacklogError("actual queued job ID is required")
    if event == "accepted" and (not SHA.fullmatch(receipt.get("merge_commit", "")) or not DIGEST.fullmatch(receipt.get("integration_evidence_sha256", "")) or receipt.get("queue_status") != "accepted"):
        raise BacklogError("acceptance requires actual merge/postmerge/queue receipt")
    if event == "parent_verified":
        if not DIGEST.fullmatch(receipt.get("collector_receipt_sha256", "")) or not isinstance(receipt.get("requirement_proofs"), dict) or set(receipt["requirement_proofs"]) != set(plan["tasks"][unit["task_id"]]["requirement_ids"]):
            raise BacklogError("parent verification requires every separately collected requirement")
        if any(not DIGEST.fullmatch(value) for value in receipt["requirement_proofs"].values()):
            raise BacklogError("unverified or malformed parent requirement proof")
        siblings = [key for key, value in plan["capabilities"].items() if value["task_id"] == unit["task_id"]]
        if any(state.get(key) not in {"accepted", "parent_verified"} for key in siblings):
            raise BacklogError("parent collector cannot hide unfinished implementation units")
    if event in {"blocked", "unblocked"} and (not receipt.get("reason") or not receipt.get("operator_reference")):
        raise BacklogError("block/recovery requires a recorded reason and trusted operator reference")


def append_progress(plan, ledger, *, event_id, capability_id, event, receipt):
    """Return a new ledger. Existing event replay is idempotent, mutation is not.

    The caller writes this under its existing broker/process lock. This is an
    integrity record, not proof of authentication or of the receipt's truth.
    """
    state = verify_progress(plan, ledger)
    task = plan["capabilities"].get(capability_id, {}).get("task_id")
    for prior in ledger:
        if prior["event_id"] == event_id:
            if any(prior.get(key) != value for key, value in {"capability_id": capability_id,
                    "event": event, "receipt": receipt, "task_id": task}.items()):
                raise BacklogError("immutable event ID was reused with different intent")
            return deepcopy(ledger)
    record = {"seq": len(ledger) + 1, "previous": ledger[-1]["digest"] if ledger else "0" * 64,
              "plan_digest": _digest(plan), "event_id": _identifier(event_id), "capability_id": capability_id,
              "task_id": task, "event": event, "receipt": deepcopy(receipt)}
    _validate_event(plan, state, record)
    record["digest"] = _digest(record)
    return deepcopy(ledger) + [record]


def ready_units(plan, observation, ledger, *, held_paths=(), held_resources=()):
    """Return next approved units and explicit waits, without changing runtime.

    Formal dependencies only use the authenticated controller snapshot. A unit
    acceptance never substitutes for parent Done. A caller must revalidate the
    returned candidates immediately before posting or enqueueing.
    """
    state = verify_progress(plan, ledger)
    snapshot = observation.get("formal_snapshot", {})
    tasks = snapshot.get("tasks", {})
    waiting, ready = {}, []
    jobs = [job for job in observation.get("jobs", []) if job.get("status") in ACTIVE]
    held_paths, held_resources = list(held_paths), set(held_resources)
    for job in jobs:
        unit = plan["capabilities"].get(job.get("capability_id"), {})
        held_paths.extend(unit.get("allowed_paths", []))
        held_resources.update(unit.get("shared_resources", []))
    for unit_id, unit in sorted(plan["capabilities"].items(), key=lambda item: (-item[1]["priority"], item[0])):
        task_id, owner = unit["task_id"], unit["owner"]
        actual = tasks.get(task_id)
        reason = None
        if state.get(unit_id) in {"accepted", "parent_verified"} or (actual and actual.get("status") == "done"):
            continue
        if observation.get("global_mode") != "on" or observation.get("pm_mode") != "on":
            reason = "automation_off"
        elif not actual or actual.get("owner") != owner or actual.get("scope", "required") != "required":
            reason = "registered_parent_mismatch"
        elif observation.get("main_commit") != snapshot.get("approved_commit"):
            reason = "formal_snapshot_not_current_main"
        elif not observation.get("members", {}).get(owner) or not all(
                observation.get("readiness", {}).get(owner, {}).get(key) is True for key in
                ("execution_isolation_verified", "publisher_separation_verified", "login_verified")):
            reason = "owner_unavailable_or_unverified"
        elif actual.get("status") in {"blocked", "deferred"} and unit.get("allow_partial_blocked_parent") is not True:
            reason = "parent_blocked"
        elif any(tasks.get(dep, {}).get("status") != "done" for dep in plan["tasks"][task_id]["depends_on"]):
            reason = "formal_dependencies_incomplete"
        elif any(state.get(dep) not in {"accepted", "parent_verified"} for dep in unit.get("depends_on_capabilities", [])):
            reason = "previous_unit_not_accepted"
        elif state.get(unit_id) == "blocked":
            reason = "unit_blocked_no_automatic_retry"
        elif state.get(unit_id) == "assigned" or any(job.get("owner") == owner for job in jobs):
            reason = "owner_has_active_work"
        elif any(paths_overlap(path, other) for path in unit["allowed_paths"] for other in held_paths) or set(unit.get("shared_resources", [])) & held_resources:
            reason = "scope_or_resource_conflict"
        elif any(observation.get("environments", {}).get(key) is not True for key in unit.get("required_environments", [])):
            reason = "reviewed_environment_not_ready"
        if reason:
            waiting[unit_id] = reason
        else:
            ready.append(unit_id)
            # One deterministic offer per available owner; prevent same-tick
            # overlapping units before the actual controller lock is acquired.
            jobs.append({"owner": owner})
            held_paths.extend(unit["allowed_paths"])
            held_resources.update(unit.get("shared_resources", []))
    return {"ready": ready, "waiting": waiting, "plan_digest": _digest(plan),
            "base_commit": observation.get("main_commit"), "formal_done": False}


def collector_candidates(plan, ledger):
    """Parents needing independent requirement collection, never a Done list."""
    state = verify_progress(plan, ledger)
    result = {}
    for task_id, task in plan["tasks"].items():
        siblings = [key for key, value in plan["capabilities"].items() if value["task_id"] == task_id]
        if siblings and all(state.get(key) in {"accepted", "parent_verified"} for key in siblings) and not any(state.get(key) == "parent_verified" for key in siblings):
            result[task_id] = {"requirement_ids": list(task["requirement_ids"]), "capability_ids": siblings,
                               "state": "needs_independent_collection", "formal_done": False}
    return result
