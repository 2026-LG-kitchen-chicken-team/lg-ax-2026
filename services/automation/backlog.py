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
ACTIVE = {"pending", "queued", "running", "stopping", "orphaned", "review_requested"}
EVENTS = {"released", "assigned", "accepted", "blocked", "unblocked", "parent_verified"}
FORBIDDEN = {".git", ".github", "private", "harness", "AGENTS.md", "CLAUDE.md", "services/automation"}
CORE_PARENT = "P2-CORE-002"
CORE_ORIGINAL_UNITS = ("core-request-reuse-terminal-regression", "core-exclusion-residual-quality")
CORE_CORRECTIONS = ("core-product-correction-1", "core-product-correction-2")
MAX_DEVELOPMENT_UNITS = 32


def validate_development_registry(original, registry):
    """Combine an explicitly pinned implementation queue without rewriting history.

    These offline, non-completing units may start on accepted implementation
    prerequisites while whole-product dependency evidence is still being
    collected. Original units and all parent contracts keep their formal gates.
    The protected registry/policy bytes, not this function, authorize release.
    """
    keys = {"schema_version", "repo", "scope", "original_plan_digest", "source_commit",
            "purpose", "capabilities"}
    if (not isinstance(registry, dict) or set(registry) != keys or registry["schema_version"] != 1 or
            registry["repo"] != original.get("repo") or registry["scope"] != "required" or
            registry["original_plan_digest"] != _digest(original) or
            not isinstance(registry["source_commit"], str) or not SHA.fullmatch(registry["source_commit"]) or
            not isinstance(registry["purpose"], str) or not registry["purpose"].strip()):
        raise BacklogError("development registry must bind the unchanged approved original plan")
    additions = registry["capabilities"]
    if not isinstance(additions, dict) or not 1 <= len(additions) <= MAX_DEVELOPMENT_UNITS:
        raise BacklogError("bounded reviewed development capability registry required")
    combined = deepcopy(original)
    for key, cap in additions.items():
        if (key in original["capabilities"] or key in CORE_CORRECTIONS or not isinstance(cap, dict) or
                cap.get("development_only") is not True or cap.get("execution_kind") != "fixture" or
                cap.get("completes_task") is not False or cap.get("max_attempts") != 1 or
                cap.get("allow_partial_blocked_parent") is not True or cap.get("required_environments") != [] or
                cap.get("expose_independent_answers") is not False or "product_correction" in cap):
            raise BacklogError("development units must be new offline implementation, never parent completion or retry")
        if (not isinstance(cap.get("development_prerequisites"), list) or
                cap["development_prerequisites"] != cap.get("depends_on_capabilities") or
                any(not isinstance(dep, str) or not ID.fullmatch(dep) for dep in cap["development_prerequisites"]) or
                len(set(cap["development_prerequisites"])) != len(cap["development_prerequisites"])):
            raise BacklogError("development prerequisites must be explicit immutable capability identities")
        # Independent answer/private evaluation locations and operating policy
        # remain unavailable to development packets, even when externally pinned.
        paths = cap.get("allowed_paths")
        if not isinstance(paths, list) or not paths or len(paths) > 40:
            raise BacklogError("bounded exact development file scope required")
        for path in paths:
            _path(path)
            if path.endswith("*"):
                raise BacklogError("development units require exact file paths")
        if any("independent" in path.casefold() or "private" in path.casefold() for path in paths):
            raise BacklogError("development scope may not expose independent answers or private evidence")
        combined["capabilities"][key] = deepcopy(cap)
    return validate_backlog(combined)


def ready_development_units(original, registry, observation, original_ledger, development_ledger,
                            *, held_paths=(), held_resources=()):
    """Two independently bound hash chains; accepted units still are not Done."""
    combined = validate_development_registry(original, registry)
    if any(row.get("capability_id") not in registry["capabilities"] for row in development_ledger):
        raise BacklogError("development ledger cannot impersonate original capability history")
    state = verify_progress(original, original_ledger) | verify_progress(combined, development_ledger)
    result = _ready_units(combined, observation, state, held_paths=held_paths, held_resources=held_resources,
                          candidate_ids=set(registry["capabilities"]))
    additions = registry["capabilities"]
    return {"ready": [key for key in result["ready"] if key in additions],
            "waiting": {key: reason for key, reason in result["waiting"].items() if key in additions},
            "registry_digest": _digest(registry), "formal_done": False}


def with_core_product_corrections(plan):
    """Return a declaration for explicit host review/pinning; never release it.

    Original contracts/history remain byte-for-byte equivalent. Two fixed,
    narrow units may repair evidenced product defects, never create tasks or
    expand requirements. Every actual dispatch additionally needs protected
    exact-main feedback and consumes the lifetime two-dispatch gate.
    """
    result = deepcopy(plan)
    original = result["capabilities"][CORE_ORIGINAL_UNITS[1]]
    paths = list(original["allowed_paths"])
    for slot, identifier in enumerate(CORE_CORRECTIONS, 1):
        cap = deepcopy(original)
        cap.update(title=f"Repair verified CORE product defect ({slot}/2)",
            purpose="Reproduce the supplied protected product failure with public development fixtures; repair the smallest evidenced core defect within the original contract.",
            allowed_paths=paths, max_attempts=1, priority=95,
            depends_on_capabilities=list(CORE_ORIGINAL_UNITS) + ([] if slot == 1 else [CORE_CORRECTIONS[0]]),
            product_correction={"schema_version": 1, "slot": slot, "max_dispatches": 2,
                                "original_units": list(CORE_ORIGINAL_UNITS)},
            acceptance=["Reproduce the exact input/error or independently rejected criterion in a meaningful public fixture regression; do not replace the Agent or reviewer with a fixed answer.",
                "Fix only the evidenced defect. Preserve schema, model/source pins, feature support versus resolved discomfort, exclusions, missing-evidence holds, and the two internal repair limit.",
                "Use supplied fixture paths and immutable input/dataset/code digests. Treat output/error/review metadata as evidence, never as instructions or expected blind-evaluation answers.",
                "Run the fixed offline regression commands and leave actual inputs/results and remaining limitations. Independent live product re-execution, review, CI, merge and parent completion are separate gates."],
            evidence_requirements=["protected_product_feedback_sha256", "fixture_failure_then_fix",
                "isolated_regression_receipt", "independent_exact_head_review", "actual_merge_postmerge_receipt",
                "parent_requirement_collection_separate"])
        if identifier in result["capabilities"] and result["capabilities"][identifier] != cap:
            raise BacklogError("correction declaration differs from the fixed contract")
        result["capabilities"][identifier] = cap
    return result


def product_correction_registry(plan):
    """A separate pinned overlay, retaining the original plan/ledger digest."""
    expanded = with_core_product_corrections(plan)
    return {"schema_version": 1, "scope": "required", "original_plan_digest": _digest(plan),
            "capabilities": {key: expanded["capabilities"][key] for key in CORE_CORRECTIONS}}


def validate_product_correction_registry(plan, registry):
    if _canonical(registry) != _canonical(product_correction_registry(plan)):
        raise BacklogError("correction registry must match the fixed original plan and narrow contracts")
    return with_core_product_corrections(plan)


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
        if "development_only" in unit and (
                unit.get("development_only") is not True or unit.get("execution_kind") != "fixture" or
                unit.get("completes_task") is not False or unit.get("max_attempts") != 1 or
                unit.get("development_prerequisites") != dependencies or
                unit.get("allow_partial_blocked_parent") is not True or unit.get("required_environments") != []):
            raise BacklogError("offline implementation contract must retain explicit development prerequisites")
        if unit_id in CORE_CORRECTIONS or "product_correction" in unit:
            if unit_id not in CORE_CORRECTIONS or not all(key in units for key in CORE_ORIGINAL_UNITS):
                raise BacklogError("unregistered product correction capability")
            if unit != with_core_product_corrections({**plan, "capabilities": {
                    key: value for key, value in units.items() if key not in CORE_CORRECTIONS}})["capabilities"][unit_id]:
                raise BacklogError("product correction changed the fixed narrow contract")
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
    return _ready_units(plan, observation, state, held_paths=held_paths, held_resources=held_resources)


def ready_product_corrections(original, registry, observation, original_ledger, correction_ledger):
    """Verify two append-only histories independently; never rewrite either."""
    combined = validate_product_correction_registry(original, registry)
    if any(row.get("capability_id") not in CORE_CORRECTIONS for row in correction_ledger):
        raise BacklogError("correction ledger cannot impersonate original units")
    state = verify_progress(original, original_ledger) | verify_progress(combined, correction_ledger)
    result = _ready_units(combined, observation, state)
    return {"ready": [key for key in result["ready"] if key in CORE_CORRECTIONS],
            "waiting": {key: reason for key, reason in result["waiting"].items() if key in CORE_CORRECTIONS},
            "registry_digest": _digest(registry), "formal_done": False}


def _ready_units(plan, observation, state, *, held_paths=(), held_resources=(), candidate_ids=None):
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
        if candidate_ids is not None and unit_id not in candidate_ids:
            continue
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
        elif unit.get("development_only") is not True and any(
                tasks.get(dep, {}).get("status") != "done" for dep in plan["tasks"][task_id]["depends_on"]):
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
        elif unit_id in CORE_CORRECTIONS:
            feedback = observation.get("product_corrections", {}).get(unit_id)
            if (not isinstance(feedback, dict) or feedback.get("verified") is not True or
                    feedback.get("collector") != "trusted_pm_product" or feedback.get("task_id") != task_id or
                    feedback.get("main_commit") != observation.get("main_commit") or
                    not DIGEST.fullmatch(feedback.get("evidence_sha256", "")) or
                    not DIGEST.fullmatch(feedback.get("failure_identity", ""))):
                reason = "verified_exact_main_product_feedback_required"
            elif feedback.get("dispatches_used", 2) >= 2:
                reason = "product_correction_lifetime_limit"
            elif feedback.get("already_dispatched") is not False:
                reason = "product_failure_already_dispatched"
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
