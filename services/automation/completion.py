"""Pure, fail-closed collection of parent-task completion evidence.

The broker supplies immutable bytes and a *protected* admission registry populated
by authenticated, direct collectors. Neither model output, repository JSON,
``verified=True`` nor a successful notification may populate that registry.
This module verifies links/integrity, not network authentication or semantics;
independent acceptance of the literal source criteria remains a PM responsibility.

No code is executed and no harness, snapshot, Project, budget or mode is written.
The returned receipt is a candidate for PM publication, not dependency release.
Adapters normalize actual broker/GitHub/phase2 receipts to the documented fields
below and admit their exact serialized bytes only after observing their sources.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

PM = "jeongiryang"
REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
MEMBERS = {"정이량": PM, "황대겸": "unknownamed", "신진하": "ginaginaring", "최길웅": "choigilung"}
CATALOG = frozenset([f"R{i:02}" for i in range(1, 29)] + [f"E{i:02}" for i in range(1, 4)])
REAL_EXECUTIONS = frozenset({"live_model", "live_service", "live_client"})
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


class CompletionError(ValueError):
    """Untrusted, incomplete, stale or conflicting evidence; never a Done signal."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CompletionError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def criterion_digest(value: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "empty source acceptance criterion")
    return digest(value.encode("utf-8"))


def _path(value: str) -> str:
    _require(isinstance(value, str) and 0 < len(value) <= 1000, "invalid artifact path")
    _require(not value.startswith("/") and not any(c in value for c in ("\\", ":", "\0", "\r", "\n")),
             "unsafe artifact path")
    _require(all(p and p not in {".", "..", ".git"} for p in value.split("/")), "noncanonical artifact path")
    return value


def _strings(value: Any, name: str, *, empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list) and (empty or bool(value)) and
             all(isinstance(v, str) and bool(v) for v in value), f"invalid {name}")
    _require(len(value) == len(set(value)), f"duplicate {name}")
    return tuple(value)


@dataclass(frozen=True)
class ArtifactRef:
    """Logical safe path + exact SHA256 + immutable provenance commit.

    A broker reader decides whether the path resolves in a Git tree or protected
    control store. Never give the reader arbitrary filesystem paths from models.
    """

    path: str
    sha256: str
    commit: str

    def __post_init__(self) -> None:
        _path(self.path)
        _require(isinstance(self.sha256, str) and bool(DIGEST.fullmatch(self.sha256)), "invalid artifact digest")
        _require(isinstance(self.commit, str) and bool(SHA.fullmatch(self.commit)), "invalid artifact commit")

    def as_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "commit": self.commit}

    @classmethod
    def parse(cls, value: Any) -> ArtifactRef:
        _require(isinstance(value, dict) and set(value) == {"path", "sha256", "commit"}, "invalid artifact reference")
        return cls(**value)


Reader = Callable[[ArtifactRef], bytes]


@dataclass(frozen=True)
class Admission:
    kind: str
    commit: str
    collected_by: str = PM


class TrustedReceiptRegistry:
    """Only the protected broker creates this out-of-band admission map.

    A hash is integrity, not authority. Loading this map from a PR/worker/model
    would destroy the trust boundary. Admission follows an authenticated direct
    observation plus immutable control-store write, not a JSON collector label.
    """

    def __init__(self, admissions: Mapping[str, Admission]):
        _require(all(isinstance(k, str) and DIGEST.fullmatch(k) and isinstance(v, Admission) and
                     SHA.fullmatch(v.commit) and v.collected_by == PM for k, v in admissions.items()),
                 "invalid protected receipt admission")
        self._admissions = MappingProxyType(dict(admissions))

    def permits(self, ref: ArtifactRef, kind: str) -> bool:
        return self._admissions.get(ref.sha256) == Admission(kind, ref.commit)


def _bytes(ref: ArtifactRef, read: Reader, *, maximum: int = 2 * 1024 * 1024) -> bytes:
    raw = read(ref)
    _require(isinstance(raw, bytes) and 0 < len(raw) <= maximum and digest(raw) == ref.sha256,
             "artifact bytes/hash mismatch or unavailable")
    return raw


def _object(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(CompletionError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionError("invalid evidence JSON") from exc
    _require(isinstance(value, dict), "evidence must be a JSON object")
    return value


def _receipt(ref: ArtifactRef, kind: str, registry: TrustedReceiptRegistry, read: Reader) -> dict:
    _require(registry.permits(ref, kind), f"receipt not admitted by protected {kind} collector")
    value = _object(_bytes(ref, read))
    _require(value.get("schema_version") == 1 and
             (value.get("kind") == kind or (kind == "policy" and "kind" not in value)),
             "receipt kind/version mismatch")
    return value


@dataclass(frozen=True)
class Capability:
    id: str
    fingerprint: str
    requirement_ids: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    required_checks: tuple[str, ...]


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    owner: str
    source_commit: str
    requirements_source: ArtifactRef
    task_source: ArtifactRef
    policy_source: ArtifactRef
    requirements: tuple[tuple[str, str], ...]
    action_criteria: tuple[str, ...]
    depends_on: tuple[str, ...]
    execution_kinds: tuple[str, ...]
    reviewers: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    fingerprint: str


def load_contract(task_id: str, source_commit: str, requirements_ref: ArtifactRef, task_ref: ArtifactRef,
                  policy_ref: ArtifactRef, registry: TrustedReceiptRegistry, read: Reader) -> TaskContract:
    """Bind the accepted 31-item mapping, actual task actions and protected policy.

    Source refs are selected by the trusted caller at the fixed source commit;
    neither path nor hash can come from the execution model. Historical status /
    coverage flags in those sources are deliberately ignored.
    """
    _require(ID.fullmatch(task_id) is not None and SHA.fullmatch(source_commit) is not None, "invalid source identity")
    _require(requirements_ref.path == "harness/phase2/requirements.json" and
             task_ref.path == f"harness/phase2/tasks/{task_id}.json" and
             requirements_ref.commit == task_ref.commit == policy_ref.commit == source_commit,
             "source requirements/task/policy must be pinned together")
    requirements = _object(_bytes(requirements_ref, read))
    task = _object(_bytes(task_ref, read))
    policy = _receipt(policy_ref, "policy", registry, read)
    source = requirements.get("source", {})
    _require(requirements.get("schema_version") == 1 and source.get("kind") == "accepted_application_commitment_mapping"
             and isinstance(source.get("sha256_at_extraction"), str) and
             DIGEST.fullmatch(source["sha256_at_extraction"]) is not None, "accepted source provenance missing")
    _path(source.get("path"))
    rows = requirements.get("requirements")
    _require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), "invalid requirement catalog")
    ids = _strings([r.get("id") for r in rows], "source catalog IDs")
    _require(set(ids) == CATALOG, "source catalog must contain the 31 unique requirements")
    catalog = {r["id"]: r for r in rows}
    _require(task.get("id") == task_id and task.get("owner") in MEMBERS and task.get("scope") == "required",
             "only accepted required tasks may complete")
    owner = MEMBERS[task["owner"]]
    required = _strings(task.get("requirement_ids"), "task requirements")
    _require(set(required) <= CATALOG, "task requirement outside fixed source")
    dependencies = _strings(task.get("depends_on"), "task dependencies", empty=True)
    _require(task_id not in dependencies and all(ID.fullmatch(v) for v in dependencies), "invalid task dependency")
    execution_kinds = _strings(task.get("allowed_execution_kinds"), "task execution kinds")
    criteria = tuple(criterion_digest(v) for v in _strings(task.get("actions"), "task acceptance actions"))
    expected_requirements = []
    for requirement_id in required:
        row = catalog[requirement_id]
        _require(task_id in _strings(row.get("linked_task_ids"), "requirement linked tasks"),
                 "requirement does not link the source task")
        criterion_digest(row.get("commitment"))
        expected_requirements.append((requirement_id, criterion_digest(row.get("acceptance"))))
    registered = policy.get("tasks", {}).get(task_id, {})
    _require(policy.get("repo") == REPO and policy.get("pm_account") == PM and
             registered.get("owner") == owner and registered.get("scope") == "required" and
             set(_strings(registered.get("requirement_ids"), "policy task requirements")) == set(required) and
             set(_strings(registered.get("depends_on"), "policy dependencies", empty=True)) == set(dependencies),
             "protected policy differs from source task")
    reviewers = _strings(policy.get("independent_reviewers"), "policy reviewers")
    _require(set(reviewers) <= set(MEMBERS.values()), "unknown trusted reviewer")
    capabilities = []
    registered_caps = policy.get("capabilities")
    _require(isinstance(registered_caps, dict) and
             all(isinstance(v, dict) for v in registered_caps.values()), "invalid protected capabilities")
    for key, value in registered_caps.items():
        if value.get("task_id") != task_id:
            continue
        _require(ID.fullmatch(key) is not None, "invalid capability id")
        paths = _strings(value.get("allowed_paths"), "capability paths")
        for path in paths:
            _path(path)
        cap_requirements = _strings(value.get("requirement_ids"), "capability requirements")
        _require(set(cap_requirements) <= set(required), "capability expands source requirements")
        checks = _strings(value.get("required_checks"), "capability checks")
        capabilities.append(Capability(key, digest(_canonical(value)), cap_requirements, paths, checks))
    _require(bool(capabilities), "no registered implementation capability")
    contract_data = {"task_id": task_id, "owner": owner, "sources": [r.as_dict() for r in
                     (requirements_ref, task_ref, policy_ref)], "requirements": expected_requirements,
                     "actions": criteria, "depends_on": dependencies, "execution_kinds": execution_kinds,
                     "reviewers": reviewers, "capabilities": [(c.id, c.fingerprint) for c in capabilities]}
    return TaskContract(task_id, owner, source_commit, requirements_ref, task_ref, policy_ref,
                        tuple(expected_requirements), criteria, dependencies, execution_kinds, reviewers,
                        tuple(capabilities), digest(_canonical(contract_data)))


@dataclass(frozen=True)
class AcceptedUnit:
    acceptance: ArtifactRef
    review: ArtifactRef
    merge: ArtifactRef
    postmerge: ArtifactRef


@dataclass(frozen=True)
class RequirementEvidence:
    requirement_id: str
    job_id: str
    execution: ArtifactRef
    acceptance: ArtifactRef


@dataclass(frozen=True)
class DependencyEvidence:
    task_id: str
    completion: ArtifactRef
    snapshot_ack: ArtifactRef


@dataclass(frozen=True)
class NextUnitNeeded:
    task_id: str
    requirement_ids: tuple[str, ...]
    action_criteria: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class CompletionReceipt:
    raw: bytes
    sha256: str

    @property
    def payload(self) -> dict:
        return _object(self.raw)


@dataclass(frozen=True)
class CompletionAssessment:
    complete: bool
    missing_requirements: tuple[str, ...]
    missing_action_criteria: tuple[str, ...]
    issues: tuple[str, ...]
    next_unit_needed: NextUnitNeeded | None
    receipt: CompletionReceipt | None


def _unit(contract: TaskContract, item: AcceptedUnit, registry: TrustedReceiptRegistry, read: Reader) -> dict:
    accepted = _receipt(item.acceptance, "unit_acceptance", registry, read)
    review = _receipt(item.review, "pm_review", registry, read)
    merge = _receipt(item.merge, "github_merge", registry, read)
    postmerge = _receipt(item.postmerge, "postmerge", registry, read)
    job_id = accepted.get("job_id")
    _require(isinstance(job_id, str) and ID.fullmatch(job_id) is not None, "invalid accepted job id")
    cap = next((c for c in contract.capabilities if c.id == accepted.get("capability_id")), None)
    _require(cap is not None and accepted.get("task_id") == contract.task_id and
             accepted.get("owner") == contract.owner and accepted.get("capability_fingerprint") == cap.fingerprint,
             "accepted unit differs from protected task/capability")
    _require(accepted.get("status") == "accepted" and accepted.get("controller_receipt") and
             accepted.get("project_receipt") and accepted.get("review_sha256") == item.review.sha256 and
             accepted.get("merge_sha256") == item.merge.sha256 and
             accepted.get("postmerge_sha256") == item.postmerge.sha256, "unit acceptance receipt chain incomplete")
    base, head, merged = (accepted.get(k) for k in ("base", "head", "merged_commit"))
    _require(all(isinstance(v, str) and SHA.fullmatch(v) for v in (base, head, merged)) and
             len({base, head, merged}) == 3 and item.acceptance.commit == item.postmerge.commit == merged and
             item.review.commit == item.merge.commit == head, "invalid accepted unit commit chain")
    session = accepted.get("implementation_session_id")
    _require(isinstance(session, str) and ID.fullmatch(session) is not None and
             review.get("reviewer") in contract.reviewers and review.get("implementation_session_id") == session and
             isinstance(review.get("reviewer_session_id"), str) and ID.fullmatch(review["reviewer_session_id"]) and
             review["reviewer_session_id"] != session and review.get("outcome") == "approve" and
             review.get("findings") == [] and review.get("head") == head and review.get("base") == base,
             "independent exact-head review missing or conflicted")
    _require(merge.get("repo") == REPO and merge.get("author") == contract.owner and merge.get("base_ref") == "main"
             and type(merge.get("pr_number")) is int and merge["pr_number"] > 0 and
             merge["pr_number"] == accepted.get("pr_number") and merge.get("head") == head and
             merge.get("base") == base and merge.get("merged_commit") == merged and merge.get("merged") is True and
             merge.get("merge_parents") == [base], "actual conditional GitHub merge receipt mismatch")
    paths = _strings(merge.get("changed_paths"), "complete merge paths")
    modes = merge.get("path_modes")
    _require(isinstance(modes, dict) and set(modes) == set(paths) and
             all(v in {"100644", "100755", "000000"} for v in modes.values()), "complete regular-file mode proof required")
    records = {f"docs/{directory}/세션/{next(k for k, v in MEMBERS.items() if v == contract.owner)}/{job_id}.md"
               for directory in ("작업기록", "작업근거")}
    added = _strings(merge.get("added_paths"), "added merge paths", empty=True)
    _require(set(added) <= set(paths), "added paths absent from complete merge scope")
    record_refs = merge.get("session_record_refs", {})
    _require(records <= set(paths) and isinstance(record_refs, dict) and set(record_refs) == records,
             "both immutable job session records are required")
    for path in paths:
        _path(path)
        if path.casefold().startswith(("docs/작업기록/", "docs/작업근거/")):
            _require(path in records and path in added and modes[path] != "000000", "other or mutable session record")
            ref = ArtifactRef.parse(record_refs[path])
            _require(ref.path == path and ref.commit == head, "session record is not pinned to source head")
            _bytes(ref, read)
        else:
            _require(any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in cap.allowed_paths),
                     "unit changes paths outside protected product scope")
    _require(postmerge.get("head") == head and postmerge.get("base") == base and postmerge.get("commit") == merged
             and postmerge.get("result") == "passed", "actual postmerge execution mismatch")
    checks = postmerge.get("checks")
    _require(isinstance(checks, list) and all(isinstance(c, dict) for c in checks), "postmerge checks missing")
    names = [c.get("id") for c in checks]
    _require(len(names) == len(set(names)) and set(cap.required_checks) <= set(names), "required postmerge check absent/duplicate")
    for check in checks:
        _require(check.get("passed") is True, "postmerge check failed")
        ref = ArtifactRef.parse(check.get("output"))
        _require(ref.commit == merged, "postmerge log from stale commit")
        _bytes(ref, read)
    return {"job_id": job_id, "capability": cap, "head": head, "merged_commit": merged,
            "implementation_session_id": session, "receipt": item.acceptance.as_dict(), "pr_number": merge["pr_number"]}


def _coverage(contract: TaskContract, evidence: RequirementEvidence, unit: dict, current_main: str,
              registry: TrustedReceiptRegistry, read: Reader) -> dict:
    criteria = dict(contract.requirements)
    _require(evidence.requirement_id in criteria and evidence.requirement_id in unit["capability"].requirement_ids,
             "coverage outside registered requirement scope")
    execution = _receipt(evidence.execution, "requirement_execution", registry, read)
    acceptance = _receipt(evidence.acceptance, "requirement_acceptance", registry, read)
    expected = {"task_id": contract.task_id, "requirement_id": evidence.requirement_id,
                "job_id": evidence.job_id, "tested_commit": current_main,
                "criterion_sha256": criteria[evidence.requirement_id], "contract_fingerprint": contract.fingerprint}
    _require(evidence.execution.commit == evidence.acceptance.commit == current_main and
             all(execution.get(k) == v and acceptance.get(k) == v for k, v in expected.items()),
             "coverage source criterion/commit/unit mismatch")
    _require(execution.get("execution_kind") in REAL_EXECUTIONS and
             execution["execution_kind"] in contract.execution_kinds and execution.get("result") == "pass" and
             _strings(execution.get("observations"), "actual execution observations") and
             _strings(execution.get("limitations"), "actual execution limitations"), "real requirement execution required")
    implementation = execution.get("implementation_session_id")
    _require(isinstance(implementation, str) and ID.fullmatch(implementation) is not None and
             implementation == unit["implementation_session_id"] and
             acceptance.get("reviewer") in contract.reviewers and
             isinstance(acceptance.get("reviewer_session_id"), str) and ID.fullmatch(acceptance["reviewer_session_id"]) and
             acceptance["reviewer_session_id"] != implementation and acceptance.get("outcome") == "approve" and
             acceptance.get("findings") == [] and acceptance.get("execution_sha256") == evidence.execution.sha256,
             "independent requirement acceptance missing")
    for field in ("code_versions", "source_versions", "inputs", "outputs"):
        refs = execution.get(field)
        _require(isinstance(refs, list) and bool(refs), f"requirement {field} missing")
        for value in refs:
            ref = ArtifactRef.parse(value)
            _require(ref.commit == current_main, "requirement artifact anchored to stale commit")
            _bytes(ref, read)
    checks = execution.get("checks")
    _require(isinstance(checks, list) and bool(checks) and all(isinstance(c, dict) for c in checks),
             "requirement checks missing")
    names = [c.get("name") for c in checks]
    _require(all(isinstance(v, str) and v for v in names) and len(names) == len(set(names)), "invalid requirement checks")
    for check in checks:
        _require(check.get("passed") is True, "requirement check failed")
        ref = ArtifactRef.parse(check.get("output"))
        _require(ref.commit == current_main, "requirement check output from stale commit")
        _bytes(ref, read)
    if execution["execution_kind"] == "live_model":
        model = execution.get("model", {})
        _require(all(isinstance(model.get(k), str) and model[k] for k in ("model_id", "revision", "license", "runtime"))
                 and isinstance(model.get("settings"), dict) and bool(model["settings"]), "live model provenance missing")
    return {"requirement_id": evidence.requirement_id, "job_id": evidence.job_id,
            "execution": evidence.execution.as_dict(), "acceptance": evidence.acceptance.as_dict()}


def _ack(ack: dict, task_id: str, completion_sha256: str, approved_commit: str) -> bool:
    return (ack.get("repo") == REPO and ack.get("approved_commit") == approved_commit and
            ack.get("outcome") == "accepted" and ack.get("project_receipt") and ack.get("controller_receipt") and
            ack.get("task_states", {}).get(task_id) == "done" and
            ack.get("completion_digests", {}).get(task_id) == completion_sha256)


def assess_parent(contract: TaskContract, accepted_units: Sequence[AcceptedUnit],
                  requirement_evidence: Sequence[RequirementEvidence], parent_acceptance: ArtifactRef | None,
                  dependencies: Sequence[DependencyEvidence], registry: TrustedReceiptRegistry, read: Reader,
                  current_main: str) -> CompletionAssessment:
    """Return exact unmet criteria or a candidate; partial/fake/stale never completes.

    Receipt schema: unit_acceptance links pm_review/github_merge/postmerge hashes,
    direct controller+Project acceptance; requirement_execution carries actual
    hashed code/source/input/output/check artifacts; requirement_acceptance binds
    literal criterion/source fingerprint and distinct review session. The parent
    acceptance must independently approve *all* task action criterion hashes and
    link them to admitted execution hashes. Existing harness booleans are ignored.
    """
    _require(isinstance(current_main, str) and SHA.fullmatch(current_main) is not None, "invalid current main")
    issues: list[str] = []
    units = {}
    coverage = {}
    missing_actions = set(contract.action_criteria)
    dependency_receipts = {}
    for item in accepted_units:
        try:
            unit = _unit(contract, item, registry, read)
            _require(unit["job_id"] not in units, "duplicate/conflicting accepted unit")
            units[unit["job_id"]] = unit
        except (CompletionError, OSError, KeyError, TypeError, ValueError):
            issues.append("invalid or conflicting accepted-unit chain")
    seen_requirements = set()
    for item in requirement_evidence:
        try:
            _require(item.requirement_id not in seen_requirements, "duplicate/conflicting requirement evidence")
            seen_requirements.add(item.requirement_id)
            _require(item.job_id in units, "coverage has no accepted unit")
            coverage[item.requirement_id] = _coverage(contract, item, units[item.job_id], current_main, registry, read)
        except (CompletionError, OSError, KeyError, TypeError, ValueError):
            issues.append("invalid, stale or conflicting requirement evidence")
    for item in dependencies:
        try:
            _require(item.task_id in contract.depends_on and item.task_id not in dependency_receipts,
                     "unexpected/duplicate dependency")
            completed = _receipt(item.completion, "parent_completion", registry, read)
            ack = _receipt(item.snapshot_ack, "snapshot_ack", registry, read)
            _require(completed.get("task_id") == item.task_id and completed.get("decision") == "complete" and
                     completed.get("actor") == PM and isinstance(completed.get("tested_commit"), str) and
                     SHA.fullmatch(completed["tested_commit"]) is not None and
                     item.snapshot_ack.commit == current_main and
                     _ack(ack, item.task_id, item.completion.sha256, current_main), "dependency completion/snapshot not accepted")
            dependency_receipts[item.task_id] = {"completion": item.completion.as_dict(),
                                                 "snapshot_ack": item.snapshot_ack.as_dict()}
        except (CompletionError, OSError, KeyError, TypeError, ValueError):
            issues.append("invalid or unacknowledged dependency completion")
    if set(dependency_receipts) != set(contract.depends_on):
        issues.append("completed dependencies with current accepted snapshot required")
    if parent_acceptance is not None:
        try:
            accepted = _receipt(parent_acceptance, "parent_acceptance", registry, read)
            _require(parent_acceptance.commit == current_main and accepted.get("task_id") == contract.task_id and
                     accepted.get("tested_commit") == current_main and accepted.get("actor") == PM and
                     accepted.get("contract_fingerprint") == contract.fingerprint and
                     accepted.get("outcome") == "approve" and accepted.get("findings") == [] and
                     set(_strings(accepted.get("requirement_ids"), "parent requirement coverage")) ==
                     set(dict(contract.requirements)), "parent acceptance not bound to full fixed task")
            implementation_sessions = {u["implementation_session_id"] for u in units.values()}
            _require(accepted.get("reviewer") in contract.reviewers and
                     isinstance(accepted.get("reviewer_session_id"), str) and
                     ID.fullmatch(accepted["reviewer_session_id"]) is not None and
                     accepted["reviewer_session_id"] not in implementation_sessions,
                     "parent acceptance must be independently reviewed")
            execution_hashes = {r["execution"]["sha256"] for r in coverage.values()}
            actions = accepted.get("actions")
            _require(isinstance(actions, list) and all(isinstance(a, dict) for a in actions), "parent action acceptance missing")
            action_ids = [a.get("criterion_sha256") for a in actions]
            _require(len(action_ids) == len(set(action_ids)) and set(action_ids) == set(contract.action_criteria),
                     "parent task acceptance action missing or expanded")
            _require(all(a.get("outcome") == "approve" and a.get("execution_sha256") in execution_hashes
                         for a in actions), "parent action has no actual accepted execution")
            missing_actions.clear()
        except (CompletionError, OSError, KeyError, TypeError, ValueError):
            issues.append("invalid or incomplete parent action acceptance")
    else:
        issues.append("independent parent acceptance required")
    missing = tuple(r for r, _ in contract.requirements if r not in coverage)
    missing_action_ids = tuple(c for c in contract.action_criteria if c in missing_actions)
    if missing or missing_action_ids or issues:
        return CompletionAssessment(False, missing, missing_action_ids, tuple(issues),
                                    NextUnitNeeded(contract.task_id, missing, missing_action_ids,
                                                   "collect missing actual evidence or repair invalid receipt chain"), None)
    payload = {"schema_version": 1, "kind": "parent_completion", "task_id": contract.task_id,
               "owner": contract.owner, "actor": PM, "decision": "complete", "tested_commit": current_main,
               "contract_fingerprint": contract.fingerprint, "source_commit": contract.source_commit,
               "sources": [r.as_dict() for r in (contract.requirements_source, contract.task_source, contract.policy_source)],
               "parent_acceptance": parent_acceptance.as_dict(), "coverage": [coverage[r] for r, _ in contract.requirements],
               "accepted_units": [units[k]["receipt"] for k in sorted(units)], "dependencies": dependency_receipts,
               "dependency_release_allowed": False,
               "publication_required": "PM harness publication and exact published-commit Project/controller ACK"}
    raw = _canonical(payload) + b"\n"
    return CompletionAssessment(True, (), (), (), None, CompletionReceipt(raw, digest(raw)))


def dependency_release_allowed(receipt: CompletionReceipt, published_commit: str, snapshot_ack: ArtifactRef,
                               registry: TrustedReceiptRegistry, read: Reader) -> bool:
    """Only a newly published, PM-admitted completion + actual dual ACK releases.

    The candidate cannot release by itself. Root writes/commits formal files and
    records the digest at the published commit before admitting this receipt.
    """
    try:
        _require(SHA.fullmatch(published_commit) is not None and digest(receipt.raw) == receipt.sha256,
                 "invalid publication identity")
        payload = receipt.payload
        ref = ArtifactRef("control/completion.json", receipt.sha256, published_commit)
        _require(registry.permits(ref, "parent_completion") and payload.get("kind") == "parent_completion" and
                 payload.get("decision") == "complete" and payload.get("actor") == PM and
                 snapshot_ack.commit == published_commit, "completion not admitted after publication")
        ack = _receipt(snapshot_ack, "snapshot_ack", registry, read)
        return bool(_ack(ack, payload["task_id"], receipt.sha256, published_commit))
    except (CompletionError, OSError, KeyError, TypeError, ValueError):
        return False
