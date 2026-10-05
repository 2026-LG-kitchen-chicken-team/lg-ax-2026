"""Live-broker adapter for requirement collection and parent completion.

Wire ``ParentCollector(broker).tick(observation)`` into the fixed broker callback.
It reads Git/control evidence as data; it never executes repository code on host.
Missing evidence is persisted every tick as explicit follow-up metadata. Existing
formal Done tasks are historical facts, not newly verified requirement coverage.

Two optional *fixed host-code* hooks complete the chain:
``requirement_collector(contract, main, units, store) -> EvidenceBundle`` runs an
approved isolated application evaluation and independent criterion acceptance;
``publisher(contract, candidate, store) -> Publication`` writes PM-owned formal
records, validates/commits them, checks unchanged product source since testing,
obtains actual Project AND controller ACK, then admits the published completion.
Neither hook may be chosen by a model, PR, Issue body or executable config string.
Without either actual hook/evidence this adapter holds; it never fabricates Done.
Coding-agent token logs and fixture validation alone are not application traces.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from services.automation.completion import (
    ID,
    MEMBERS,
    PM,
    REPO,
    SHA,
    AcceptedUnit,
    Admission,
    ArtifactRef,
    CompletionError,
    CompletionReceipt,
    DependencyEvidence,
    RequirementEvidence,
    TaskContract,
    TrustedReceiptRegistry,
    assess_parent,
    dependency_release_allowed,
    digest,
    load_contract,
)
from services.automation.pm import PMError, canonical, fingerprint, protected_path
from services.automation.worker import regular_file, write_json


def _check(condition, reason):
    if not condition:
        raise CompletionError(reason)


@dataclass(frozen=True)
class EvidenceBundle:
    coverage: tuple[RequirementEvidence, ...] = ()
    parent_acceptance: ArtifactRef | None = None
    dependencies: tuple[DependencyEvidence, ...] = ()


@dataclass(frozen=True)
class Publication:
    commit: str
    snapshot_ack: ArtifactRef


class EvidenceStore:
    """Protected immutable byte store; only authenticated fixed collectors admit.

    Public ``admit`` is for the two reviewed host hooks above, never worker/model
    JSON. Metadata/hash maps stay outside clones and executable auth mounts.
    Exact file bytes are preserved; no evidence truncation or path dereference.
    """

    def __init__(self, root: Path):
        self.root = protected_path(Path(root) / "index.json").parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.index = json.loads(regular_file(self.index_path)) if self.index_path.exists() else {
            "schema_version": 1, "admissions": {}, "references": {}, "units": {}}
        _check(self.index.get("schema_version") == 1, "invalid evidence store version")

    @property
    def registry(self):
        return TrustedReceiptRegistry({key: Admission(**value) for key, value in self.index["admissions"].items()})

    def blob(self, path: str, commit: str, raw: bytes) -> ArtifactRef:
        ref = ArtifactRef(path, digest(raw), commit)
        _check(isinstance(raw, bytes) and 0 < len(raw) <= 64 * 1024 * 1024, "bounded evidence bytes required")
        target = self.root / (ref.sha256 + ".blob")
        if target.exists():
            _check(digest(regular_file(target, maximum=64 * 1024 * 1024)) == ref.sha256, "immutable evidence changed")
        else:
            with target.open("xb") as output:
                output.write(raw)
        self.index["references"][self._key(ref)] = ref.sha256
        self.save()
        return ref

    def admit(self, kind: str, commit: str, value: dict | bytes) -> ArtifactRef:
        raw = value if isinstance(value, bytes) else canonical(value).encode() + b"\n"
        ref = self.blob("control/" + digest(raw) + ".json", commit, raw)
        self.index["admissions"][ref.sha256] = {"kind": kind, "commit": commit, "collected_by": PM}
        self.save()
        return ref

    @staticmethod
    def _key(ref: ArtifactRef):
        return ref.commit + ":" + ref.path

    def read(self, ref: ArtifactRef) -> bytes:
        _check(self.index["references"].get(self._key(ref)) == ref.sha256, "unregistered evidence reference")
        raw = regular_file(self.root / (ref.sha256 + ".blob"), maximum=64 * 1024 * 1024)
        _check(digest(raw) == ref.sha256, "protected artifact changed")
        return raw

    def save(self):
        write_json(self.index_path, self.index)


class ParentCollector:
    def __init__(self, broker, *, requirement_collector: Callable[
            [TaskContract, str, tuple[AcceptedUnit, ...], EvidenceStore], EvidenceBundle] | None = None,
            publisher: Callable[[TaskContract, CompletionReceipt, EvidenceStore], Publication] | None = None):
        self.broker = broker
        self.store = EvidenceStore(broker.state_dir / "parent-evidence")
        self.requirement_collector = requirement_collector
        self.publisher = publisher
        self.assessment_path = self.store.root / "assessments.json"

    def _source(self, path: str, commit: str) -> ArtifactRef:
        # Git only reads fixed tree/blob objects. No checkout/import/test/shell.
        probe = ArtifactRef(path, "0" * 64, commit)
        raw = self.broker._git(["ls-tree", "-z", commit, "--", ":(literal)" + path], binary=True)
        parts = raw.split(b"\0")
        _check(len(parts) == 2 and not parts[1], "exact fixed source file required")
        metadata, name = parts[0].split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        _check(mode in {"100644", "100755"} and kind == "blob" and name.decode() == probe.path and
               SHA.fullmatch(oid), "ordinary fixed source blob required")
        data = self.broker._git(["cat-file", "blob", oid], binary=True)
        _check(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == oid,
               "Git blob identity mismatch")
        return self.store.blob(path, commit, data)

    def _contract(self, task_id: str, main: str) -> TaskContract:
        source = self.broker.config.get("parent_contract_source_commit", main)
        _check(isinstance(source, str) and SHA.fullmatch(source), "fixed parent source commit required")
        origin = self.broker._git(["remote", "get-url", "origin"])
        _check(origin in {f"https://github.com/{REPO}", f"https://github.com/{REPO}.git"}, "unexpected source origin")
        self.broker._git(["fetch", "--no-tags", "origin", source])
        requirements = self._source("harness/phase2/requirements.json", source)
        task = self._source(f"harness/phase2/tasks/{task_id}.json", source)
        policy_raw = regular_file(Path(self.broker.config["policy_file"]), maximum=256 * 1024)
        parsed = json.loads(policy_raw)
        _check(digest(policy_raw) == self.broker.config["policy_sha256"] and
               all(parsed.get(k) == self.broker.policy.get(k) for k in
                   ("tasks", "capabilities", "repo", "pm_account", "independent_reviewers")),
               "deployed policy bytes or task/capability scope changed")
        policy = self.store.admit("policy", source, policy_raw)
        return load_contract(task_id, source, requirements, task, policy, self.store.registry, self.store.read)

    def _boundary(self, value: dict, role: str):
        _check(isinstance(value, dict) and value.get("backend") == "docker" and value.get("role") == role and
               value.get("image_id") == self.broker.executor.config.image and value.get("uid") == 1000 and
               all(value.get(k) is True for k in ("readonly_root", "caps_dropped", "no_new_privileges")) and
               value.get("publisher_credentials_mounted") is False and
               value.get("ai_profile_mounted") is (role == "model") and
               value.get("network") == ("none" if role == "validator" else "bridge"),
               "actual isolated role/image boundary missing")

    def _review(self, unit: dict, cap: dict) -> ArtifactRef:
        key = fingerprint({"review_head": unit["head"], "base": unit["base_commit"], "capability": cap})
        proof = self.broker.state["proofs"].get(key, {})
        session = proof.get("reviewer_session_id")
        _check(isinstance(session, str) and ID.fullmatch(session), "fixed independent review session required")
        root = self.broker.state_dir / "driver" / session
        record = json.loads(regular_file(root / "proof.json"))
        _check(fingerprint(record) == proof.get("evidence_sha256") and record.get("session_id") == session and
               proof.get("capability_fingerprint") == fingerprint(cap) and
               proof.get("implementation_session_id") == unit["implementation_session_id"] and
               session != unit["implementation_session_id"], "actual independent review source mismatch")
        self._boundary(record.get("boundary"), "model")
        events = regular_file(root / "events.jsonl", maximum=64 * 1024 * 1024)
        _check(digest(events) == record.get("events_sha256"), "independent review event bytes changed")
        usage = record.get("usage", {})
        _check(all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")),
               "actual independent review usage missing")
        result = record.get("result", {})
        _check(result.get("outcome") == "approve" and result.get("findings") == [] and
               proof.get("outcome") == result["outcome"] and proof.get("findings") == result["findings"],
               "independent review is unresolved")
        return self.store.admit("pm_review", unit["head"], {"schema_version": 1, "kind": "pm_review",
            "head": unit["head"], "base": unit["base_commit"], "reviewer": PM,
            "implementation_session_id": unit["implementation_session_id"], "reviewer_session_id": session,
            "outcome": "approve", "findings": [], "source_record_sha256": fingerprint(record)})

    def _postmerge(self, unit: dict, cap: dict, merged: str) -> ArtifactRef:
        key = fingerprint({"commit": merged, "head": unit["head"], "base": unit["base_commit"],
                           "capability": cap, "postmerge": True})
        proof = self.broker.state["proofs"].get(key, {})
        root = self.broker.state_dir / "integration" / key
        detail = json.loads(regular_file(root / "proof.json"))
        _check(fingerprint(detail) == proof.get("evidence_sha256") and proof.get("result") == "passed" and
               proof.get("capability_fingerprint") == fingerprint(cap) and detail.get("commit") == merged and
               detail.get("head") == unit["head"] and detail.get("base") == unit["base_commit"] and
               detail.get("validation_workspace_readonly") is True and detail.get("host_repo_code_executed") is False,
               "actual postmerge source mismatch")
        rows = detail.get("checks", [])
        _check(len(rows) == len(cap["validation_commands"]), "complete actual postmerge commands required")
        logs = []
        for index, (row, argv) in enumerate(zip(rows, cap["validation_commands"], strict=True)):
            _check(row.get("argv") == argv and row.get("returncode") == 0 and not row.get("stopped_reason"),
                   "actual postmerge command failed/mismatched")
            self._boundary(row.get("boundary"), "validator")
            logs.append(regular_file(root / f"check-{index}.log", maximum=2 * 1024 * 1024))
        combined = b"\n".join(logs)
        log = self.store.blob(f"control/postmerge-{key}.log", merged, combined)
        return self.store.admit("postmerge", merged, {"schema_version": 1, "kind": "postmerge",
            "head": unit["head"], "base": unit["base_commit"], "commit": merged, "result": "passed",
            "source_record_sha256": fingerprint(detail),
            "checks": [{"id": name, "passed": True, "output": log.as_dict()} for name in cap["required_checks"]]})

    def _changes(self, unit: dict, merged: str) -> dict:
        self.broker._git(["fetch", "--no-tags", "origin", unit["base_commit"], unit["head"], merged])
        raw = self.broker._git(["diff", "--raw", "-z", "--no-ext-diff", "--no-textconv", "--no-renames",
                               "--abbrev=40", unit["base_commit"], unit["head"], "--"], binary=True)
        fields = raw.split(b"\0")
        _check(fields[-1] == b"" and (len(fields) - 1) % 2 == 0 and 2 <= len(fields) - 1 <= 2000,
               "complete bounded Git change metadata required")
        paths, added, modes, record_refs = [], [], {}, {}
        account = self.broker.policy["tasks"][unit["task_id"]]["owner"]
        name = next(k for k, v in MEMBERS.items() if v == account)
        records = {f"docs/{d}/세션/{name}/{unit['job_id']}.md" for d in ("작업기록", "작업근거")}
        for index in range(0, len(fields) - 1, 2):
            match = re.fullmatch(rb":(100644|100755|000000) (100644|100755|000000) ([0-9a-f]{40}) ([0-9a-f]{40}) ([AMD])",
                                 fields[index])
            _check(match is not None, "ordinary non-renamed change metadata required")
            old_mode, new_mode, old_oid, new_oid, status = match.groups()
            path = fields[index + 1].decode("utf-8", errors="strict")
            ArtifactRef(path, "0" * 64, unit["head"])
            _check(path.casefold() not in {p.casefold() for p in paths}, "duplicate/alias Git path")
            paths.append(path)
            modes[path] = new_mode.decode()
            if status == b"A":
                _check(old_mode == b"000000" and old_oid == b"0" * 40, "added file has source contents")
                added.append(path)
            elif status == b"D":
                _check(new_mode == b"000000" and new_oid == b"0" * 40, "deleted file has target contents")
            else:
                _check(old_mode != b"000000" and new_mode != b"000000", "modified file has missing source")
            if path in records:
                _check(status == b"A", "session records must be new")
                record_refs[path] = self._source(path, unit["head"]).as_dict()
        return {"changed_paths": paths, "added_paths": added, "path_modes": modes, "session_record_refs": record_refs}

    def _project_ack(self, project: dict, commit: str) -> str:
        def comment(url):
            match = re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/issues/28#issuecomment-([1-9][0-9]*)", url)
            _check(match is not None, "fixed Project approval receipt URL required")
            row = self.broker.github.request("GET", f"repos/{REPO}/issues/comments/{match[1]}")
            _check(row.get("user", {}).get("login") == PM and str(row.get("id")) == match[1], "authenticated Project comment required")
            return row
        approval = comment(project["approval_url"])
        ack = comment(project["receipt_url"])
        expected = '/lgax-sync\n```json\n' + canonical({"commit": commit}) + '\n```'
        _check(approval.get("body") == expected and
               ack.get("body", "").startswith(f"LGAX-RECEIPT {approval['id']} ACCEPTED\n") and
               f"`{commit}`" in ack["body"] and project.get("commit") == commit,
               "actual exact-commit Project ACK missing")
        return project["receipt_url"]

    def _unit(self, unit: dict, jobs: list[dict]) -> AcceptedUnit:
        cap = self.broker.policy["capabilities"][unit["capability_id"]]
        cache_key = fingerprint({"job": unit["job_id"], "head": unit["head"], "cap": cap})
        cached = self.store.index["units"].get(cache_key)
        if cached:
            return AcceptedUnit(*(ArtifactRef.parse(cached[k]) for k in ("acceptance", "review", "merge", "postmerge")))
        _check(unit.get("reconciled") is True and ID.fullmatch(unit["job_id"]), "actual reconciled unit required")
        source = self.broker.github.request("GET", f"repos/{REPO}/pulls/{unit['pr_number']}")
        owner = self.broker.policy["tasks"][unit["task_id"]]["owner"]
        merged = source.get("merge_commit_sha")
        _check(source.get("merged") is True and source.get("head", {}).get("sha") == unit["head"] and
               source.get("user", {}).get("login") == owner and source.get("base", {}).get("ref") == "main" and
               source["base"]["repo"]["full_name"] == source["head"]["repo"]["full_name"] == REPO and
               isinstance(merged, str) and SHA.fullmatch(merged), "actual fixed owned merged PR required")
        parents = self.broker.github.request("GET", f"repos/{REPO}/commits/{merged}").get("parents", [])
        _check([p.get("sha") for p in parents] == [unit["base_commit"]], "actual conditional merge parent mismatch")
        job = next((j for j in jobs if j.get("job_id") == unit["job_id"]), None)
        _check(job is not None and job.get("status") == "accepted" and job.get("task_id") == unit["task_id"] and
               job.get("owner") == owner, "direct controller accepted job missing")
        actions = [a for a in self.broker.state["actions"].values() if a.get("phase") == "receipt" and
                   a.get("receipt", {}).get("action") == "reconcile" and a["receipt"].get("outcome") == "applied" and
                   a.get("details", {}).get("job_id") == unit["job_id"]]
        _check(len(actions) == 1, "unique actual reconciliation receipt required")
        details = actions[0]["details"]
        _check(fingerprint(details) == actions[0]["receipt"]["evidence_sha256"] and
               details.get("merge_commit") == merged and details.get("formal_done") is False,
               "reconciliation detail integrity mismatch")
        project = self._project_ack(details["project_approval"], merged)
        review = self._review(unit, cap)
        postmerge = self._postmerge(unit, cap, merged)
        merge = self.store.admit("github_merge", unit["head"], {"schema_version": 1, "kind": "github_merge",
            "repo": REPO, "author": owner, "base_ref": "main", "pr_number": unit["pr_number"],
            "head": unit["head"], "base": unit["base_commit"], "merged_commit": merged, "merged": True,
            "merge_parents": [unit["base_commit"]], **self._changes(unit, merged)})
        accepted = self.store.admit("unit_acceptance", merged, {"schema_version": 1, "kind": "unit_acceptance",
            "job_id": unit["job_id"], "task_id": unit["task_id"], "capability_id": unit["capability_id"],
            "capability_fingerprint": fingerprint(cap), "owner": owner, "status": "accepted",
            "controller_receipt": fingerprint({"job_id": job["job_id"], "status": job["status"],
                                               "task_id": job["task_id"], "owner": job["owner"]}),
            "project_receipt": project, "base": unit["base_commit"], "head": unit["head"], "merged_commit": merged,
            "pr_number": unit["pr_number"], "implementation_session_id": unit["implementation_session_id"],
            "review_sha256": review.sha256, "merge_sha256": merge.sha256, "postmerge_sha256": postmerge.sha256})
        result = AcceptedUnit(accepted, review, merge, postmerge)
        self.store.index["units"][cache_key] = {k: getattr(result, k).as_dict() for k in ("acceptance", "review", "merge", "postmerge")}
        self.store.save()
        return result

    def tick(self, observation: dict, task_ids: tuple[str, ...] | None = None) -> dict:
        """Called by broker every observation/reconcile; persists actual missing work.

        Returns inert metadata for root's fixed-capability backlog selector. A
        source task already formally Done is preserved without claiming new live
        coverage. ON/OFF is never changed; publishing additionally requires ON.
        """
        self.broker.authenticate()
        main = self.broker.github.request("GET", f"repos/{REPO}/commits/main")["sha"]
        _check(main == observation.get("main_commit") and SHA.fullmatch(main), "main moved before collection")
        selected = task_ids or tuple(self.broker.policy["tasks"])
        _check(len(selected) == len(set(selected)) and set(selected) <= set(self.broker.policy["tasks"]),
               "collection task outside fixed policy")
        status = self.broker.controller.request("/v1/status")
        result = {"schema_version": 1, "main_commit": main, "tasks": {}}
        for task_id in selected:
            formal = status.get("formal_snapshot", {}).get("tasks", {}).get(task_id, {})
            if formal.get("status") == "done":
                result["tasks"][task_id] = {"state": "existing_formal_done", "new_requirement_coverage": False}
                continue
            try:
                contract = self._contract(task_id, main)
                units = []
                failed_units = 0
                for unit in self.broker.state["units"].values():
                    if unit.get("task_id") == task_id and unit.get("reconciled"):
                        try:
                            units.append(self._unit(unit, status.get("jobs", [])))
                        except (CompletionError, PMError, OSError, KeyError, TypeError, ValueError):
                            failed_units += 1
                bundle = (self.requirement_collector(contract, main, tuple(units), self.store)
                          if self.requirement_collector is not None else EvidenceBundle())
                _check(isinstance(bundle, EvidenceBundle), "fixed collector must return typed evidence bundle")
                assessed = assess_parent(contract, units, bundle.coverage, bundle.parent_acceptance,
                                         bundle.dependencies, self.store.registry, self.store.read, main)
                summary = {"state": "candidate" if assessed.complete else "waiting_evidence",
                           "source_commit": contract.source_commit, "contract_fingerprint": contract.fingerprint,
                           "accepted_unit_count": len(units), "uncollected_unit_count": failed_units,
                           "missing_requirements": list(assessed.missing_requirements),
                           "missing_action_criteria": list(assessed.missing_action_criteria), "issues": list(assessed.issues),
                           "next_unit_needed": None if assessed.next_unit_needed is None else {
                               "task_id": task_id, "requirement_ids": list(assessed.next_unit_needed.requirement_ids),
                               "action_criteria": list(assessed.next_unit_needed.action_criteria),
                               "reason": assessed.next_unit_needed.reason}}
                if assessed.complete:
                    candidate = assessed.receipt
                    self.store.blob("control/completion-" + candidate.sha256 + ".json", main, candidate.raw)
                    summary["completion_sha256"] = candidate.sha256
                    if self.publisher is not None and self.broker.enabled():
                        _check(self.broker.github.request("GET", f"repos/{REPO}/commits/main")["sha"] == main,
                               "main moved before formal publication")
                        publication = self.publisher(contract, candidate, self.store)
                        _check(isinstance(publication, Publication) and
                               dependency_release_allowed(candidate, publication.commit, publication.snapshot_ack,
                                                          self.store.registry, self.store.read),
                               "formal publication dual ACK not confirmed")
                        summary.update(state="completed", published_commit=publication.commit)
                    else:
                        summary["publication_pending"] = True
                result["tasks"][task_id] = summary
            except (CompletionError, PMError, OSError, KeyError, TypeError, ValueError):
                result["tasks"][task_id] = {"state": "blocked_evidence", "reason": "fixed source or actual collector evidence unavailable",
                                            "next_unit_needed": {"task_id": task_id, "reason": "repair protected source/evidence intake"}}
        write_json(self.assessment_path, result)
        return result
