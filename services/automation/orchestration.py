"""Trusted live adapter for the pinned backlog and private, report-only mail.

Only the deployed broker instantiates this adapter. Repository plans are not
releases: their copied bytes and capability definitions must match pinned policy.
The caller already holds the PM process lock; no model or worker supplies receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from services.automation.backlog import (
    CORE_CORRECTIONS,
    CORE_ORIGINAL_UNITS,
    CORE_PARENT,
    append_progress,
    collector_candidates,
    load_backlog,
    ready_development_units,
    ready_product_corrections,
    ready_units,
    validate_development_registry,
    validate_product_correction_registry,
    verify_progress,
)
from services.automation.isolation import regular_file
from services.automation.pm import PMError, canonical, fingerprint, protected_path
from services.automation.state import PM, REPO
from services.automation.worker import write_json

DEVELOPMENT_PROJECT = {
    "id": "PVT_kwDOFCE5QM4Blr0A", "owner": "2026-LG-kitchen-chicken-team", "number": 1,
    "url": "https://github.com/orgs/2026-LG-kitchen-chicken-team/projects/1",
    "fields": {"Status": "PVTSSF_lADOFCE5QM4Blr0AzhkXp80",
               "다음 행동": "PVTF_lADOFCE5QM4Blr0AzhkXp-I",
               "실행 증빙": "PVTF_lADOFCE5QM4Blr0AzhkXp9w",
               "최근 배정": "PVTF_lADOFCE5QM4Blr0AzhkXp-M"},
    "statuses": {"Todo": "f75ad846", "In Progress": "47fc9ee4", "Done": "98236657"}}


class DevelopmentIssueMirror:
    """Fixed PM metadata publisher. No model, dispatch, Issue close or parent Done.

    Only four compiled fields on this organization's existing Project may be
    written. Readback precedes durable cache acceptance; unknown outcomes are
    reread next time as idempotent field assignments, never counted as applied.
    """

    def __init__(self, orchestration, options):
        self.live, self.broker = orchestration, orchestration.broker
        if not isinstance(options, dict) or set(options) != {"path", "sha256"}:
            raise PMError("protected development Issue map needs only path and sha256")
        self.path, self.digest = protected_path(options["path"]), options["sha256"]
        self.mapping = self._read()

    def _read(self):
        raw = regular_file(self.path, maximum=128 * 1024)
        if hashlib.sha256(raw).hexdigest() != self.digest:
            raise PMError("protected development Issue map changed")
        value = json.loads(raw)
        expected = {"schema_version", "repo", "project", "registration_receipt", "capabilities"}
        if (not isinstance(value, dict) or set(value) != expected or value["schema_version"] != 1 or
                value["repo"] != REPO or value["project"] != DEVELOPMENT_PROJECT):
            raise PMError("development Issue map cannot select another Project or fields")
        receipt = value["registration_receipt"]
        if (not isinstance(receipt, dict) or set(receipt) != {"path", "sha256", "commit"} or
                receipt["path"] != "docs/pm/development-queue-issues-20261005.json" or
                not re.fullmatch(r"[a-f0-9]{64}", str(receipt["sha256"])) or
                not re.fullmatch(r"[a-f0-9]{40}", str(receipt["commit"]))):
            raise PMError("fixed original registration receipt provenance required")
        caps = value["capabilities"]
        declared = (self.live.development_registry or {}).get("capabilities", {})
        if not isinstance(caps, dict) or len(caps) != 24 or set(caps) != set(declared):
            raise PMError("development Issue map must bind exactly the 24 protected units")
        seen = {"number": set(), "issue_id": set(), "project_item_id": set()}
        for key, row in caps.items():
            cap = self.broker.policy["capabilities"].get(key)
            if (not isinstance(row, dict) or set(row) != {"owner", "parent_task_id", "parent_issue_number",
                    "number", "issue_id", "url", "project_item_id", "capability_fingerprint"} or
                    cap != declared[key] or row["owner"] != cap["owner"] or row["parent_task_id"] != cap["task_id"] or
                    row["capability_fingerprint"] != fingerprint(cap) or
                    row["parent_issue_number"] != self.live.plan["tasks"][cap["task_id"]]["issue_number"] or
                    row["url"] != f"https://github.com/{REPO}/issues/{row['number']}" or
                    type(row["number"]) is not int or not 1 <= row["number"] <= 1_000_000 or
                    type(row["issue_id"]) is not int or row["issue_id"] <= 0 or
                    not isinstance(row["project_item_id"], str) or
                    not re.fullmatch(r"PVTI_[A-Za-z0-9_-]{10,100}", row["project_item_id"])):
                raise PMError("development Issue identity, owner, parent or capability scope changed")
            for name, identities in seen.items():
                if row[name] in identities:
                    raise PMError("development Issue map identities must be unique")
                identities.add(row[name])
        return value

    def _graphql(self, query, variables):
        raw = self.broker.github.command(["api", "--hostname", "github.com", "graphql", "--input", "-"],
            data=canonical({"query": query, "variables": variables}).encode())
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
            raise PMError("development Project operation was not confirmed")
        return result["data"]

    def _project(self):
        query = """query($p:ID!){node(id:$p){... on ProjectV2{id number url owner{... on Organization{login}}
          fields(first:30){pageInfo{hasNextPage} nodes{... on ProjectV2Field{id name}
            ... on ProjectV2SingleSelectField{id name options{id name}}}}
          items(first:100){pageInfo{hasNextPage} nodes{id content{... on Issue{id number url repository{nameWithOwner}}}
            fieldValues(first:30){pageInfo{hasNextPage} nodes{... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2Field{id}}}
              ... on ProjectV2ItemFieldSingleSelectValue{name optionId field{... on ProjectV2SingleSelectField{id}}}}}}}}}}"""
        project = self._graphql(query, {"p": DEVELOPMENT_PROJECT["id"]}).get("node")
        if (not isinstance(project, dict) or any(project.get(key) != DEVELOPMENT_PROJECT[key]
                for key in ("id", "number", "url")) or
                project.get("owner", {}).get("login") != DEVELOPMENT_PROJECT["owner"] or
                project["fields"]["pageInfo"]["hasNextPage"] or project["items"]["pageInfo"]["hasNextPage"]):
            raise PMError("actual development Project identity or bounded metadata changed")
        fields = {row.get("id"): row for row in project["fields"]["nodes"]}
        for name, field_id in DEVELOPMENT_PROJECT["fields"].items():
            if fields.get(field_id, {}).get("name") != name:
                raise PMError("actual allowed development Project field changed")
        options = fields[DEVELOPMENT_PROJECT["fields"]["Status"]].get("options", [])
        if {row["name"]: row["id"] for row in options} != DEVELOPMENT_PROJECT["statuses"]:
            raise PMError("actual development status options changed")
        items = {row["id"]: row for row in project["items"]["nodes"]}
        for row in self.mapping["capabilities"].values():
            item = items.get(row["project_item_id"], {})
            content = item.get("content") or {}
            if (content.get("url") != row["url"] or content.get("number") != row["number"] or
                    content.get("repository", {}).get("nameWithOwner") != REPO or
                    item.get("fieldValues", {}).get("pageInfo", {}).get("hasNextPage") is not False):
                raise PMError("actual development Issue and Project item association changed")
        return items

    @staticmethod
    def _values(item):
        values = {}
        for row in item["fieldValues"]["nodes"]:
            field = row.get("field", {}).get("id")
            if field in DEVELOPMENT_PROJECT["fields"].values():
                if field in values:
                    raise PMError("development Project contains duplicate field values")
                values[field] = row.get("text", row.get("name"))
        return values

    def _facts(self, key, observation, progress):
        row = self.mapping["capabilities"][key]
        cap = self.broker.policy["capabilities"][key]
        jobs = {job["job_id"]: job for job in observation["jobs"]}
        units = [unit for unit in self.broker.state["units"].values()
                 if unit.get("capability_id") == key and not unit.get("superseded_by")]
        if len(units) > 1:
            raise PMError("development Project needs one current job per unit")
        state, action, evidence, allocation = "Todo", "대기 · 선행 인수/원 부모 PR/Worker 준비 확인", "", "미배정 · 실제 자동 claim은 별도"
        if key in observation.get("capabilities_ready", []):
            action = "Ready · PM의 고정 개발 배정 대기"
        if units:
            unit = units[0]
            job = jobs.get(unit.get("job_id"))
            if (not job or unit.get("task_id") != cap["task_id"] or job.get("task_id") != cap["task_id"] or
                    job.get("owner") != cap["owner"] or job.get("capability_id") != key or
                    not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", str(unit.get("job_id"))) or
                    not re.fullmatch(r"[a-f0-9]{40}", str(unit.get("base_commit")))):
                raise PMError("actual controller job does not match development unit ownership")
            status = job.get("status")
            actions = {"pending": "배정됨 · Worker claim 대기", "running": "실행 중 · 구현/검사/자기 검수",
                       "review_requested": "검수 대기 · PR/CI/통합 확인", "completed_review": "검수 결과 인수 대기",
                       "stopping": "중단 처리 대기 · 기존 실행/증빙 보존", "blocked": "막힘 · PM 원인 검토; 자동 재시도 없음",
                       "failed": "실패 · PM 원인 검토; 자동 재시도 없음", "orphaned": "연결/lease 확인 대기; 자동 재시도 없음",
                       "accepted": "실제 인수 증빙 대기 · 부모 Done은 별도"}
            if status not in actions:
                raise PMError("unrecognized actual development queue status")
            state = "Todo" if status == "pending" else "In Progress"
            action = actions[status]
            if unit.get("revision_requested"):
                action = "수정 작업 대기 · 원 PR 보존; 새 bounded 작업/검수 필요"
            elif unit.get("reconciled") and status == "accepted" and progress.get(key) in {"accepted", "parent_verified"}:
                state, action = "Done", "개발 단위 인수 완료 · 부모 품질/독립 평가/제출은 별도"
            number = unit.get("pr_number")
            if number is not None:
                if type(number) is not int or number <= 0 or not re.fullmatch(r"[a-f0-9]{40}", str(unit.get("head"))):
                    raise PMError("bounded development PR identity required")
                evidence = f"https://github.com/{REPO}/pull/{number} · head {unit['head']} · job {unit['job_id']}"
            allocation = f"{row['owner']} · job {unit['job_id']} · base {unit['base_commit']}"
        return {"Status": state, "다음 행동": action, "실행 증빙": evidence, "최근 배정": allocation}

    def synchronize(self, observation, *, collect=False):
        # Execution revalidation and OFF polling are strictly read-only. Keep
        # metadata cache out of model observation so this mirror cannot wake AI.
        self.mapping = self._read()
        if not collect or observation.get("global_mode") != "on" or observation.get("pm_mode") != "on":
            return {"state": "read_only", "updated": 0, "model_called": False}
        progress = self.live._progress()
        desired = {key: self._facts(key, observation, progress) for key in self.mapping["capabilities"]}
        cache = self.broker.state.setdefault("development_project_mirror", {"map_sha256": self.digest, "items": {}})
        if (not isinstance(cache, dict) or set(cache) != {"map_sha256", "items"} or
                cache.get("map_sha256") != self.digest or not isinstance(cache.get("items"), dict) or
                not set(cache["items"]) <= set(desired) or
                any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
                    for value in cache["items"].values())):
            raise PMError("development Project cache requires explicit map migration")
        changed = {key: fields for key, fields in desired.items()
                   if cache["items"].get(key) != fingerprint({"map": self.digest, "fields": fields})}
        if not changed:
            return {"state": "unchanged", "updated": 0, "model_called": False}
        if self.broker.authenticate() != {"account": PM, "operator": True} or not self.broker.enabled():
            raise PMError("authenticated ON PM required for development Project updates")
        items = self._project()
        parents = {}
        # Validate every changed Issue before the first write in this batch.
        for key in changed:
            row = self.mapping["capabilities"][key]
            actual = self.broker.github.request("GET", f"repos/{REPO}/issues/{row['number']}")
            if (actual.get("id") != row["issue_id"] or actual.get("html_url") != row["url"] or
                    {v.get("login") for v in actual.get("assignees", [])} != {row["owner"]} or
                    f"<!-- lgax-development-capability:{key} -->" not in (actual.get("body") or "")):
                raise PMError("actual development Issue identity/owner/marker changed")
            parent = row["parent_issue_number"]
            if parent not in parents:
                parents[parent] = self.broker.github.request("GET", f"repos/{REPO}/issues/{parent}/sub_issues?per_page=100")
            if not any(child.get("id") == row["issue_id"] for child in parents[parent]):
                raise PMError("actual development Issue parent relationship changed")
        updated = 0
        for key, fields in changed.items():
            item_id = self.mapping["capabilities"][key]["project_item_id"]
            existing = self._values(items[item_id])
            mutations, variables = [], {"p": DEVELOPMENT_PROJECT["id"], "i": item_id}
            for name, value in fields.items():
                field_id = DEVELOPMENT_PROJECT["fields"][name]
                if existing.get(field_id, "") == value:
                    continue
                index = len(mutations)
                variables[f"f{index}"] = field_id
                variables[f"v{index}"] = {"singleSelectOptionId": DEVELOPMENT_PROJECT["statuses"][value]} if name == "Status" else {"text": value}
                mutations.append(f'v{index}:updateProjectV2ItemFieldValue(input:{{projectId:$p,itemId:$i,fieldId:$f{index},value:$v{index}}}){{projectV2Item{{id}}}}')
            if mutations:
                declaration = ",".join(["$p:ID!", "$i:ID!"] + [part for index in range(len(mutations))
                    for part in (f"$f{index}:ID!", f"$v{index}:ProjectV2FieldValue!")])
                response = self._graphql("mutation(" + declaration + "){" + " ".join(mutations) + "}", variables)
                if any(response.get(f"v{index}", {}).get("projectV2Item", {}).get("id") != item_id for index in range(len(mutations))):
                    raise PMError("development Project update outcome remains unknown")
                # ACK alone is insufficient; accept the cache only after actual
                # field values have been observed on the same immutable item.
                current = self._project()
                actual = self._values(current[item_id])
                if any(actual.get(DEVELOPMENT_PROJECT["fields"][name], "") != value for name, value in fields.items()):
                    raise PMError("development Project update readback did not match")
                items = current
            cache["items"][key] = fingerprint({"map": self.digest, "fields": fields})
            self.broker.save()
            updated += 1
        return {"state": "applied", "updated": updated, "model_called": False}


class Orchestration:
    def __init__(self, broker):
        self.broker = broker
        options = broker.config.get("backlog")
        self.plan = None
        self.correction_registry = self.correction_plan = None
        self.development_registry = self.development_plan = None
        if options:
            self.plan = load_backlog(protected_path(options["path"]), options["sha256"],
                                     registered_tasks=broker.policy["tasks"])
            for key, capability in self.plan["capabilities"].items():
                actual = broker.policy["capabilities"].get(key)
                if not actual or any(actual.get(field) != capability.get(field) for field in (
                        "task_id", "requirement_ids", "allowed_paths", "acceptance",
                        "validation_commands", "required_checks", "shared_resources", "title", "purpose",
                        "product_correction")):
                    raise PMError("fixed backlog and deployed capability contract differ")
            verify_progress(self.plan, broker.state.get("backlog_ledger", []))
        registry = broker.config.get("product_correction_registry")
        if registry:
            if not self.plan or not isinstance(registry, dict) or set(registry) != {"path", "sha256"}:
                raise PMError("a pinned original backlog and protected correction registry are required")
            raw = regular_file(protected_path(registry["path"]))
            if hashlib.sha256(raw).hexdigest() != registry["sha256"]:
                raise PMError("protected product correction registry changed")
            self.correction_registry = json.loads(raw)
            self.correction_plan = validate_product_correction_registry(self.plan, self.correction_registry)
            for key, cap in self.correction_registry["capabilities"].items():
                if broker.policy["capabilities"].get(key) != cap:
                    raise PMError("correction registry and deployed policy differ")
            if any(row.get("capability_id") not in CORE_CORRECTIONS for row in broker.state.get("correction_ledger", [])):
                raise PMError("correction history cannot contain original unit events")
            verify_progress(self.correction_plan, broker.state.get("correction_ledger", []))
        registry = broker.config.get("development_queue_registry")
        if registry:
            if not self.plan or not isinstance(registry, dict) or set(registry) != {"path", "sha256"}:
                raise PMError("a pinned original backlog and protected development registry are required")
            raw = regular_file(protected_path(registry["path"]))
            if hashlib.sha256(raw).hexdigest() != registry["sha256"]:
                raise PMError("protected development queue registry changed")
            self.development_registry = json.loads(raw)
            self.development_plan = validate_development_registry(self.plan, self.development_registry)
            for key, cap in self.development_registry["capabilities"].items():
                if broker.policy["capabilities"].get(key) != cap:
                    raise PMError("development registry and deployed policy differ")
            if any(row.get("capability_id") not in self.development_registry["capabilities"]
                   for row in broker.state.get("development_ledger", [])):
                raise PMError("development history cannot contain original or correction unit events")
            verify_progress(self.development_plan, broker.state.get("development_ledger", []))
        self.development_issues = None
        if "development_issue_registry" in broker.config:
            self.development_issues = DevelopmentIssueMirror(self, broker.config["development_issue_registry"])
        self.mail = None
        mail = broker.config.get("mail")
        if mail:
            from services.automation.mail_broker import MailBroker
            from services.automation.mail_connector import CodexGmailTransport

            raw = regular_file(protected_path(mail["path"]))
            if hashlib.sha256(raw).hexdigest() != mail["sha256"]:
                raise PMError("fixed private mail configuration changed")
            config = json.loads(raw)
            if config.get("transport") != "codex_appserver":
                raise PMError("live orchestration requires the verified CLI mail transport")
            binary = regular_file(Path(config["codex_executable"]), maximum=512 * 1024 * 1024)
            if hashlib.sha256(binary).hexdigest() != config.get("codex_executable_sha256"):
                raise PMError("pinned CLI mail executable changed")
            transport = CodexGmailTransport(executable=config["codex_executable"],
                                           workspace=config["connector_workspace"], timeout_seconds=45)
            self.mail = MailBroker(config, gmail=transport)
        self._mail_checked = False
        self._mail_poll_at = None
        self.parent = None
        self.product_producer = None
        self._parent_key = None
        self._parent_result = None
        if self.plan and broker.config.get("parent_completion_enabled") is True:
            from services.automation.completion_publish import CompletionPublisher
            from services.automation.parent_collector import ParentCollector

            product = broker.config.get("product_evidence")
            if product is not None and not isinstance(product, dict):
                raise PMError("fixed protected product evidence settings must be an object")
            if product and product.get("enabled") is True:
                from services.automation.product_evidence import ProductEvidenceProducer

                # This callable is selected by reviewed host code. Models,
                # backlog files and issue text cannot choose an evaluator.
                self.product_producer = ProductEvidenceProducer(broker)
            self.parent = ParentCollector(broker, requirement_collector=self.product_producer,
                                          publisher=CompletionPublisher(broker))

    def _collection_key(self, observation, latest):
        value = {"main": observation["main_commit"], "units": latest, "store": self.parent.store.index}
        if self.product_producer is not None:
            value["product_evidence"] = self.product_producer.state_fingerprint
        return fingerprint(value)

    def _event(self, cap_id, suffix, event, receipt):
        broker = self.broker
        event_id = event + "-" + fingerprint({"cap": cap_id, "id": suffix})[:48]
        if self.development_registry and cap_id in self.development_registry["capabilities"]:
            key, plan = "development_ledger", self.development_plan
        elif cap_id in CORE_CORRECTIONS:
            key, plan = "correction_ledger", self.correction_plan
        else:
            key, plan = "backlog_ledger", self.plan
        broker.state[key] = append_progress(plan,
            broker.state.get(key, []), event_id=event_id,
            capability_id=cap_id, event=event, receipt=receipt)
        broker.save()

    @property
    def capabilities(self):
        result = deepcopy(self.plan["capabilities"]) if self.plan else {}
        if self.correction_registry:
            result.update(self.correction_registry["capabilities"])
        if self.development_registry:
            result.update(self.development_registry["capabilities"])
        return result

    def _progress(self):
        value = verify_progress(self.plan, self.broker.state.get("backlog_ledger", []))
        if self.correction_plan:
            value |= verify_progress(self.correction_plan, self.broker.state.get("correction_ledger", []))
        if self.development_plan:
            value |= verify_progress(self.development_plan, self.broker.state.get("development_ledger", []))
        return value

    def development_dependency_jobs(self, capability_id, observation):
        """Derive immutable accepted queue dependencies from protected receipts."""
        if not self.development_registry or capability_id not in self.development_registry["capabilities"]:
            raise PMError("only an externally pinned offline development unit may use implementation prerequisites")
        cap = self.development_registry["capabilities"][capability_id]
        progress, jobs = self._progress(), {row["job_id"]: row for row in observation["jobs"]}
        result = []
        for prerequisite in cap["development_prerequisites"]:
            if progress.get(prerequisite) not in {"accepted", "parent_verified"}:
                raise PMError("development prerequisite has no independently accepted receipt")
            candidates = [unit for unit in self.broker.state["units"].values()
                if unit.get("capability_id") == prerequisite and unit.get("reconciled") and
                not unit.get("superseded_by") and jobs.get(unit["job_id"], {}).get("status") == "accepted"]
            if len(candidates) != 1:
                raise PMError("development prerequisite needs one actual accepted queue job")
            result.append(candidates[0]["job_id"])
        return result

    def _correction_dispatches(self):
        """Intents count conservatively: unknown delivery never buys a retry."""
        dispatched = {}
        for action_id, value in self.broker.state.get("actions", {}).items():
            feedback = value.get("product_correction")
            if feedback:
                dispatched[action_id] = feedback
        for unit in self.broker.state.get("units", {}).values():
            feedback = unit.get("product_correction")
            if feedback:
                dispatched[unit["job_id"].removeprefix("auto-")] = feedback
        # An intent and its unit denote one job, never two paid follow-ups.
        return {key.removeprefix("pm-"): value for key, value in dispatched.items()}

    def _product_source(self, main, binding):
        """Read fixed Git objects as data, without another export or host imports."""
        from services.automation.product_evidence import MANIFEST

        paths = [binding.input_path, binding.dataset_path, MANIFEST]
        raw = self.broker._git(["ls-tree", "-r", "-z", "--full-tree", main, "--",
            "packages/core/src/lgax_core/", *paths], binary=True)
        rows = raw.split(b"\0")
        if rows[-1] or not 1 <= len(rows) - 1 <= 150:
            raise PMError("bounded fixed product source tree required")
        objects = {}
        for row in rows[:-1]:
            match = re.fullmatch(rb"100(?:644|755) blob ([a-f0-9]{40})\t([^\x00]+)", row)
            if not match:
                raise PMError("product correction source must be ordinary fixed blobs")
            path = match[2].decode("utf-8", errors="strict")
            if path in objects or not (path in paths or path.startswith("packages/core/src/lgax_core/")):
                raise PMError("product correction source escaped the fixed tree")
            objects[path] = match[1].decode()
        if any(path not in objects for path in paths):
            raise PMError("public product fixture provenance missing")
        source = {}
        for path in paths:
            value = self.broker._git(["show", main + ":" + path], binary=True)
            if len(value) > 2 * 1024 * 1024:
                raise PMError("product fixture exceeds bounds")
            source[path] = {"path": path, "sha256": hashlib.sha256(value).hexdigest(),
                            "git_blob": objects[path], "value": json.loads(value)}
        return source, {path: oid for path, oid in objects.items() if path.startswith("packages/core/src/lgax_core/")}

    @staticmethod
    def _semantic_codes(product):
        codes = set()
        stack, inspected = [(product.get("trace", []), 0), (product.get("output", {}), 0)], 0
        while stack:
            value, depth = stack.pop()
            inspected += 1
            if inspected > 4000 or depth > 12:
                raise PMError("product failure detail exceeds bounded traversal")
            if isinstance(value, dict):
                code = value.get("code")
                if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
                    codes.add(code)
                for key, item in value.items():
                    if key in {"unresolved", "no_candidate_reasons"} and isinstance(item, list):
                        codes.update(s for s in item if isinstance(s, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", s))
                    stack.append((item, depth + 1))
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
        return sorted(code for code in codes if code.startswith(("GAP_", "CONCEPT_", "EVIDENCE_")) or
            code in {"OUTPUT_SCHEMA", "INVALID_SEMANTIC_REVIEW", "INVALID_EVIDENCE_ID", "EXCLUDED_FEATURE"})

    def _product_correction_feedback(self, observation):
        """Recollect protected original bytes on execution revalidation, no AI call.

        A verified failed case remains actionable when a later transport case
        prevents the parent reviewer from running. An unverified case, unknown
        usage, or connection failure alone is a PM escalation, never a code fix.
        """
        if not self.product_producer or not self.parent:
            return {}
        from services.automation.artifacts import secret_check
        from services.automation.completion import ArtifactRef
        from services.automation.product_evidence import DIGEST, MANIFEST, MODEL

        progress = verify_progress(self.plan, self.broker.state.get("backlog_ledger", []))
        if any(progress.get(key) not in {"accepted", "parent_verified"} for key in CORE_ORIGINAL_UNITS):
            return {}
        state = self.product_producer._current_state()
        if state.get("review_halt") or any(row.get("state") in {"started", "review_started", "executed"}
                and row.get("main") == observation["main_commit"] for row in state["runs"].values()):
            return {}
        main, store = observation["main_commit"], self.parent.store
        dispatches = self._correction_dispatches()
        jobs = {row["job_id"]: row for row in observation["jobs"]}
        cases, escalations = [], []
        for run_id, case in sorted(state.get("case_runs", {}).items()):
            if case.get("tested_commit") != main or case.get("execution_mode") != "live_model":
                continue
            origin = case.get("approved_origin", {})
            unit = self.broker.state["units"].get(origin.get("job_id"), {})
            job = jobs.get(origin.get("job_id"), {})
            if (origin.get("task_id") != CORE_PARENT or origin.get("tested_commit") != main or
                    unit.get("task_id") != CORE_PARENT or not unit.get("reconciled") or
                    job.get("status") != "accepted" or job.get("owner") != "unknownamed" or
                    origin.get("capability_fingerprint") != fingerprint(self.broker.policy["capabilities"].get(unit.get("capability_id"))) or
                    case.get("evaluator_versions") != self.product_producer.evaluator_versions):
                continue
            if case.get("status") == "unverified" or case.get("usage_unknown") or case.get("relay_failed"):
                escalations.append({"case_id": case.get("case_id"), "reason": "unverified_product_transport_or_usage"})
                continue
            binding = self.product_producer.bindings.get(case.get("case_id"))
            if not binding or case.get("status") not in {"failed", "completed"}:
                continue
            try:
                if not re.fullmatch(r"product-[A-Za-z0-9_-]{1,90}", run_id):
                    raise PMError("fixed bounded product run identity required")
                refs = {name: ArtifactRef.parse(case["refs"][name]) for name in ("output", "relay")}
                if any(ref.commit != main or ref.path != f"control/product/{run_id}/{name}.json" for name, ref in refs.items()):
                    raise PMError("original product reference does not match the fixed run")
                raw = {name: store.read(ref) for name, ref in refs.items()}
                for value in raw.values():
                    secret_check(value)
                product, relay = (json.loads(raw[name]) for name in ("output", "relay"))
                if (relay.get("run_id") != run_id or relay.get("approved_origin") != origin or
                        relay.get("settings") != self.product_producer.options["settings"] or
                        relay.get("allow_generation") is not True or relay.get("failure")):
                    raise PMError("original product relay provenance changed")
                if (case.get("actual_product_calls", 0) <= 0 or product.get("execution_kind") != "live_model" or
                        product.get("status") != case["status"] or not isinstance(product.get("trace"), list) or
                        not product["trace"] or len(product.get("model_calls", [])) != case["actual_product_calls"]):
                    raise PMError("verified original live execution required")
                self.product_producer._verify_calls(product, relay, self.product_producer.options["settings"])
                source, code = self._product_source(main, binding)
                if product.get("original_input") != source[binding.input_path]["value"]:
                    raise PMError("original product input does not match the public fixture")
                models = source[MANIFEST]["value"].get("models", [])
                if not any(row.get("model_id") == MODEL and row.get("revision") == DIGEST for row in models):
                    raise PMError("product model does not match the fixed manifest")
                semantic = self._semantic_codes(product) if product["status"] == "failed" else []
                verdicts = []
                for entry in state["runs"].values():
                    if entry.get("main") != main or entry.get("state") != "partial" or not entry.get("reviewer_session_id"):
                        continue
                    if not any(row.get("run_id") == run_id for row in entry.get("cases", [])):
                        continue
                    session = entry["reviewer_session_id"]
                    if (not re.fullmatch(r"product-review-[A-Za-z0-9_-]{1,80}", session) or
                            session == unit.get("implementation_session_id")):
                        raise PMError("actual independent reviewer session required")
                    proof_path = self.broker.state_dir / "driver" / session / "proof.json"
                    proof = json.loads(regular_file(proof_path))
                    if (proof.get("session_id") != entry["reviewer_session_id"] or
                            proof.get("result") != entry.get("verdicts") or
                            proof.get("events_sha256") != entry.get("events_sha256") or
                            hashlib.sha256(regular_file(proof_path.with_name("events.jsonl"), maximum=64 * 1024 * 1024)).hexdigest() != entry["events_sha256"]):
                        raise PMError("original independent product verdict changed")
                    self.product_producer._boundary(proof.get("boundary"), "model")
                    for requirement, verdict in entry["verdicts"].items():
                        if requirement in binding.requirement_ids and verdict.get("outcome") in {"missing", "changes_requested"}:
                            verdicts.append({"requirement_id": requirement, "outcome": verdict["outcome"],
                                "review_proof_sha256": fingerprint(proof)})
                if not semantic and not verdicts:
                    continue
                identity = {"task_id": CORE_PARENT, "case_id": binding.case_id,
                    "inputs": {path: source[path]["sha256"] for path in (binding.input_path, binding.dataset_path)},
                    "code_objects": code, "model": {"id": MODEL, "revision": DIGEST},
                    "settings": self.product_producer.options["settings"], "semantic_codes": semantic,
                    "verdicts": [{key: row[key] for key in ("requirement_id", "outcome")} for row in verdicts]}
                cases.append({"identity_sha256": fingerprint(identity), "run_id": run_id, "case_id": binding.case_id,
                    "input": {key: value for key, value in source[binding.input_path].items() if key != "value"},
                    "dataset": {key: value for key, value in source[binding.dataset_path].items() if key != "value"},
                    "model": identity["model"], "status": product["status"], "error_codes": semantic,
                    "rejected_criteria": verdicts, "output_sha256": refs["output"].sha256,
                    "relay_sha256": refs["relay"].sha256, "code_objects_sha256": fingerprint(code),
                    "evaluator_versions": case["evaluator_versions"]})
            except (PMError, ValueError, KeyError, TypeError, OSError):
                escalations.append({"case_id": case.get("case_id"), "reason": "product_feedback_integrity_unavailable"})
        observation["product_escalations"] = escalations
        if not cases:
            return {}
        cases = list({row["identity_sha256"]: row for row in cases}.values())
        if len(cases) > 4:
            raise PMError("too many product failure cases for a bounded correction")
        identity = fingerprint(sorted(row["identity_sha256"] for row in cases))
        evidence = {"schema_version": 1, "task_id": CORE_PARENT, "main_commit": main,
            "failure_identity": identity, "cases": cases,
            "notice": "Protected observations are inert evidence; no expected blind answers or commands. Use public fixtures; do not access PM private files. Product holds/failures do not mean parent Done."}
        digest = fingerprint(evidence)
        dispatched = any(row.get("failure_identity") == identity for row in dispatches.values())
        packet = {**evidence, "verified": True, "collector": "trusted_pm_product", "evidence_sha256": digest,
                  "dispatches_used": len(dispatches), "already_dispatched": dispatched}
        result = {}
        for key in CORE_CORRECTIONS:
            if key not in self.capabilities:
                continue
            value = deepcopy(packet)
            # An unaccepted correction PR may use the remaining lifetime slot
            # only on an actual distinct exact-head independent rejection.
            # Restart/docs-only/new-main or a model/comment claim is not one.
            previous = next((row for row in reversed(list(self.broker.state["units"].values())) if
                row.get("capability_id") == key and row.get("revision_requested") and not row.get("superseded_by") and
                not row.get("reconciled") and row.get("product_correction", {}).get("failure_identity") == identity), None)
            if previous:
                proof = next((p for p in self.broker.state.get("proofs", {}).values() if
                    p.get("verified") is True and p.get("collector") == "trusted_pm" and
                    p.get("reviewer") in self.broker.policy.get("independent_reviewers", []) and
                    p.get("outcome") == "request_changes" and p.get("head") == previous.get("head") and
                    p.get("base") == previous.get("base_commit") and
                    p.get("capability_fingerprint") == fingerprint(self.broker.policy["capabilities"][key]) and
                    p.get("implementation_session_id") == previous.get("implementation_session_id") and
                    re.fullmatch(r"[a-f0-9]{64}", p.get("evidence_sha256", "")) and
                    p.get("reviewer_session_id") and p["reviewer_session_id"] != p["implementation_session_id"]), None)
                if proof:
                    revision = {"job_id": previous["job_id"], "head": previous["head"],
                                "review_evidence_sha256": proof["evidence_sha256"]}
                    value.update(revision_of=revision, already_dispatched=False,
                                 evidence_sha256=fingerprint({**evidence, "revision_of": revision}))
            result[key] = value
        return result

    def synchronize(self, observation, *, collect=False):
        if not self.plan:
            return
        jobs = {row["job_id"]: row for row in observation["jobs"]}
        state = self._progress()
        # Old accepted pilot/revision jobs seed the ledger from the direct queue,
        # actual GitHub merge, and protected independent postmerge proof.
        latest = {unit["capability_id"]: unit for unit in self.broker.state["units"].values()
                  if not unit.get("superseded_by") and unit["job_id"] in jobs}
        for unit in latest.values():
            cap_id = unit["capability_id"]
            if cap_id not in self.capabilities or unit.get("superseded_by"):
                continue
            job = jobs.get(unit["job_id"])
            if not job:
                continue
            if unit.get("superseded_by"):
                continue
            prior = state.get(cap_id)
            if prior in {"accepted", "parent_verified", "blocked"}:
                continue
            if prior is None:
                self._event(cap_id, unit["job_id"], "released", {"base_commit": unit["base_commit"]})
                prior = "released"
            if prior in {"released", "unblocked"}:
                self._event(cap_id, unit["job_id"], "assigned", {
                    "base_commit": unit["base_commit"], "job_id": unit["job_id"]})
            if unit.get("revision_requested"):
                if prior != "unblocked":
                    self._event(cap_id, unit["job_id"], "blocked", {
                        "reason": "Independent exact-head PM correction requires a new bounded job",
                        "operator_reference": "protected-revision:" + unit["job_id"]})
                    self._event(cap_id, unit["job_id"], "unblocked", {
                        "reason": "Recorded PM correction releases this fixed capability only",
                        "operator_reference": "protected-revision:" + unit["job_id"]})
                    state = self._progress()
                continue
            if job.get("status") in {"blocked", "orphaned"}:
                self._event(cap_id, unit["job_id"], "blocked", {
                    "reason": "Actual queue blocked/orphaned; no automatic retry",
                    "operator_reference": "controller-job:" + unit["job_id"]})
            elif unit.get("reconciled") and job.get("status") == "accepted":
                actual = self.broker.github.request("GET", f"repos/{REPO}/pulls/{unit['pr_number']}")
                cap_fp = fingerprint(self.broker.policy["capabilities"][cap_id])
                proof = next((p for p in self.broker.state["proofs"].values()
                    if p.get("verified") is True and p.get("collector") == "trusted_pm"
                    and p.get("result") == "passed" and p.get("commit") == actual.get("merge_commit_sha")
                    and p.get("head") == unit.get("head") and p.get("base") == unit["base_commit"]
                    and p.get("capability_fingerprint") == cap_fp), None)
                if not actual.get("merged") or actual.get("head", {}).get("sha") != unit.get("head") or not proof:
                    raise PMError("accepted legacy unit lacks direct merge/postmerge collection")
                self._event(cap_id, unit["job_id"], "accepted", {
                    "base_commit": unit["base_commit"], "merge_commit": actual["merge_commit_sha"],
                    "integration_evidence_sha256": proof["evidence_sha256"], "queue_status": "accepted"})
            state = self._progress()
        result = ready_units(self.plan, observation, self.broker.state.get("backlog_ledger", []))
        observation["capabilities_ready"] = [key for key in result["ready"]
                                              if key in self.broker._released_capabilities()]
        held = self.broker.state.get("held_capabilities", {})
        observation["capabilities_ready"] = [key for key in observation["capabilities_ready"] if key not in held]
        for key in held:
            if key in self.plan["capabilities"]:
                result["waiting"][key] = "fixed_assignment_preparation_rejected_requires_PM_followup"
        observation["backlog"] = {"plan_digest": result["plan_digest"], "waiting": result["waiting"],
                                  "parents_needing_collection": collector_candidates(self.plan,
                                      self.broker.state.get("backlog_ledger", []))}
        write_json(self.broker.state_dir / "backlog-observation.json", observation["backlog"])
        if self.parent and collect and self.broker.enabled():
            selected = tuple(sorted({unit["task_id"] for unit in latest.values() if unit.get("reconciled")}))
            key = self._collection_key(observation, latest)
            # Current-head and protected evidence changes wake collection;
            # unchanged polling does not rerun product tests or model reviews.
            pending = self._parent_result and any(row.get("publication_pending") for row in
                                                  self._parent_result["tasks"].values())
            pending = pending or (self.product_producer is not None and
                                  getattr(self.product_producer, "pending_review", False) is True)
            if selected and (key != self._parent_key or pending):
                self._parent_result = self.parent.tick(observation, task_ids=selected)
                self._parent_key = self._collection_key(observation, latest)
        # execute(collect=False) must see the same fixed evidence as decision
        # observations without invoking collectors again. Never attach a result
        # from another main; a collecting tick's explicit publication change is
        # retained only to force the no-model reobserve gate.
        cached = self._parent_result
        if cached and (cached.get("main_commit") == observation["main_commit"] or
                       (collect and cached.get("must_reobserve") is True)):
            observation["parent_completion"] = deepcopy(cached)
            if collect and any(row.get("state") == "completed" and row.get("published_commit") != observation["main_commit"]
                               for row in cached.get("tasks", {}).values()):
                observation["parent_completion"]["must_reobserve"] = True
        if self.correction_registry:
            feedback = self._product_correction_feedback(observation)
            observation["product_corrections"] = feedback
            # Ready calculation happens again after collection so a newly
            # observed actual failure can reach the next bounded dispatch.
            result = ready_product_corrections(self.plan, self.correction_registry, observation,
                self.broker.state.get("backlog_ledger", []), self.broker.state.get("correction_ledger", []))
            observation["capabilities_ready"] += [key for key in result["ready"]
                if key in self.broker._released_capabilities() and key not in held]
            observation["backlog"]["waiting"].update(result["waiting"])
            observation["backlog"]["correction_registry_digest"] = result["registry_digest"]
            summary = observation.setdefault("parent_completion", {"main_commit": observation["main_commit"], "tasks": {}})
            parent = summary["tasks"].setdefault(CORE_PARENT, {"state": "waiting_evidence"})
            if feedback:
                parent["product_feedback"] = deepcopy(next(iter(feedback.values())))
            parent["product_escalations"] = deepcopy(observation.get("product_escalations", []))
            write_json(self.broker.state_dir / "backlog-observation.json", observation["backlog"])
        if self.development_registry:
            # Prior offers hold owner/path/resource authority in this same tick;
            # a second registry cannot invent parallel jobs for the same owner.
            offers = observation["capabilities_ready"]
            selection = deepcopy(observation)
            held_paths, held_resources = [], []
            for key in offers:
                cap = self.capabilities[key]
                selection["jobs"].append({"owner": cap["owner"], "status": "pending"})
                held_paths.extend(cap["allowed_paths"])
                held_resources.extend(cap.get("shared_resources", []))
            result = ready_development_units(self.plan, self.development_registry, selection,
                self.broker.state.get("backlog_ledger", []), self.broker.state.get("development_ledger", []),
                held_paths=held_paths, held_resources=held_resources)
            observation["capabilities_ready"] += [key for key in result["ready"]
                if key in self.broker._released_capabilities() and key not in held]
            observation["backlog"]["waiting"].update(result["waiting"])
            for key in held:
                if key in self.development_registry["capabilities"]:
                    observation["backlog"]["waiting"][key] = "fixed_assignment_preparation_rejected_requires_PM_followup"
            observation["backlog"]["development_registry_digest"] = result["registry_digest"]
            observation["backlog"]["development_units"] = len(self.development_registry["capabilities"])
            write_json(self.broker.state_dir / "backlog-observation.json", observation["backlog"])
        if self.development_issues is not None:
            self.development_issues.synchronize(observation, collect=collect)

    def mail_snapshot(self):
        """Read immutable local inbox events without profile/auth/network calls."""
        return self.mail.observation_events(limit=20) if self.mail is not None else []

    def mail_tick(self, *, poll=True):
        import time

        if self.mail is None:
            return []
        if not self._mail_checked:
            self.mail.preflight()
            self._mail_checked = True
        if poll and (self._mail_poll_at is None or time.monotonic() - self._mail_poll_at >= 60):
            self.mail.poll_replies(limit=20)
            self._mail_poll_at = time.monotonic()
        return self.mail.observation_events(limit=20)

    def notify(self, outbox):
        if self.mail is None:
            return None
        self.mail.preflight()
        receipt = self.mail.deliver(outbox)
        write_json(Path(outbox).with_suffix(".receipt.json"), receipt)
        return "sent_verified" if receipt.get("verified_sent") else "unknown"

    def close(self):
        if self.mail:
            self.mail.gmail.close()
