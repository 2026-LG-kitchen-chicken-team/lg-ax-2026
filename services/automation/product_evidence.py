"""Actual, partial CORE002 product execution and independent PM intake.

Instantiate ONLY from fixed deployed host configuration and pass this object as
ParentCollector.requirement_collector. Repository/model JSON cannot select the
executor, endpoint, cases or reviewer. The first two cases do not prove all eight
CORE002 requirements. No product test runs on the credential-bearing host.
"""
from __future__ import annotations

import base64
import json
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from services.automation.artifacts import secret_check
from services.automation.completion import (
    ID,
    PM,
    REPO,
    AcceptedUnit,
    ArtifactRef,
    CompletionError,
    RequirementEvidence,
    TaskContract,
    _unit,
    criterion_digest,
    digest,
)
from services.automation.isolation import regular_file, snapshot_files
from services.automation.parent_collector import EvidenceBundle, EvidenceStore
from services.automation.pm import PMDriverBusy, PMError, canonical, fingerprint, protected_path
from services.automation.product_rpc import DIGEST, MODEL, FileRelay, RPCError, checked_settings, positive
from services.automation.worker import exclusive_lock, write_json

TASK = "P2-CORE-002"
SUPPORTED = ("R01", "R09", "R12", "R15", "R26")
DATASET = "evals/core-planning/examples/dataset.json"
CASES = {"fridge-normal": "evals/core-planning/examples/fridge.input.json",
         "fridge-changed": "evals/core-planning/examples/fridge-changed.input.json"}
MANIFEST = "evals/bootstrap-models/models-manifest.json"


@dataclass(frozen=True)
class ProductCaseBinding:
    """Registered by reviewed host code, never a path/answer chosen by a model.

    Future source-controlled negative inputs can expand coverage. A zero-model
    guard is separately labelled and cannot make a model call. The parent still
    needs actual live cases plus independent full literal/action acceptance.
    """
    case_id: str
    input_path: str
    dataset_path: str
    requirement_ids: tuple[str, ...]
    execution_mode: str = "live_model"

    def __post_init__(self):
        require(isinstance(self.case_id, str) and ID.fullmatch(self.case_id), "fixed case identity required")
        for path in (self.input_path, self.dataset_path):
            require(isinstance(path, str) and path.startswith(("evals/core-planning/examples/", "evals/core-contract/development/"))
                and ".." not in path.split("/") and "\\" not in path and ":" not in path and
                path.endswith(".json") and not any(word in path.casefold() for word in ("fixture-output", "reviewer", "answer")),
                "only approved source input/data paths may be registered")
        require(self.input_path.endswith(".input.json") and self.dataset_path.endswith(("/dataset.json", ".dataset.json")) and
            self.execution_mode in {"live_model", "deterministic_guard"} and bool(self.requirement_ids) and
            len(set(self.requirement_ids)) == len(self.requirement_ids) and
            set(self.requirement_ids) <= {"R01", "R09", "R10", "R11", "R12", "R15", "R16", "R26"},
            "bounded source CORE002 case declaration required")


RUNNER = '''import json,pathlib,runpy,sys
from lgax_core.model_client import ModelConfig,OllamaAdapter,StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore
rpc=runpy.run_path('_trusted_product_rpc.py')
cfg=json.loads(pathlib.Path('/artifacts/result-schema.json').read_bytes())
config=ModelConfig('http://127.0.0.1:18873',rpc['MODEL'],rpc['DIGEST'],timeout_seconds=195,
                   max_output_tokens=cfg['settings']['num_predict'],context_tokens=cfg['settings']['num_ctx'],thinking=False)
payload=json.loads(pathlib.Path(cfg['input']).read_text('utf-8-sig'))
dataset=json.loads(pathlib.Path(cfg['dataset']).read_text('utf-8-sig'))
transport=rpc['FileTransport'](pathlib.Path('/artifacts'),cfg['run_id'])
with StructuredModelClient(OllamaAdapter(config,transport=transport)) as client:
 result=PlanningAgent(client,DemoStore(dataset),execution_kind='live_model' if cfg['execution_mode']=='live_model' else 'fixture').run(payload)
result['product_evaluation_mode']=cfg['execution_mode']
pathlib.Path('/artifacts/result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'actual_product_model_calls':len(result['model_calls'])}))
# held is a product decision, not a process/connection failure; the independent
# criterion reviewer, not this exit code, decides what the result proves.
sys.exit(0 if result['status'] in {'completed','held','failed'} else 2)
'''


def require(value, reason):
    if not value:
        raise CompletionError(reason)


class ProductEvidenceProducer:
    def __init__(self, broker, *, options=None, upstream=None, case_bindings=None):
        self.broker = broker
        supplied = options if options is not None else broker.config.get("product_evidence", {})
        self.options = json.loads(canonical(supplied))
        require(isinstance(self.options, dict), "fixed product evidence configuration required")
        self.upstream = upstream  # injection only from fixed host code/tests.
        bindings = tuple(case_bindings) if case_bindings is not None else tuple(
            ProductCaseBinding(key, path, DATASET, SUPPORTED) for key, path in CASES.items())
        require(2 <= len(bindings) <= 10 and all(isinstance(case, ProductCaseBinding) for case in bindings) and
            len({case.case_id for case in bindings}) == len(bindings) and
            any(case.execution_mode == "live_model" for case in bindings), "fixed bounded host case bindings required")
        self.bindings = {case.case_id: case for case in bindings}
        self.root = protected_path(broker.state_dir / "product-evidence" / "state.json").parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"
        self.state = json.loads(regular_file(self.state_path)) if self.state_path.exists() else {"schema_version": 1, "runs": {}}
        require(self.state.get("schema_version") == 1, "invalid protected product state")

    def _save(self):
        write_json(self.state_path, self.state)

    @property
    def state_fingerprint(self):
        """Root cache key may include this; no model-selected state wakes calls."""
        return fingerprint(self.state)

    @staticmethod
    def _registered(contract, main, store):
        key = fingerprint({"task": contract.task_id, "contract": contract.fingerprint, "main": main})
        value = store.index.get("requirement_bundles", {}).get(key, {})
        rows = tuple(RequirementEvidence(row["requirement_id"], row["job_id"], ArtifactRef.parse(row["execution"]),
                    ArtifactRef.parse(row["acceptance"])) for row in value.get("coverage", []))
        parent = value.get("parent_acceptance")
        return EvidenceBundle(rows, None if parent is None else ArtifactRef.parse(parent))

    def _boundary(self, row, role):
        require(isinstance(row, dict) and row.get("backend") == "docker" and row.get("role") == role and
            row.get("image_id") == self.broker.executor.config.image and row.get("uid") == 1000 and
            all(row.get(key) is True for key in ("readonly_root", "caps_dropped", "no_new_privileges")) and
            row.get("publisher_credentials_mounted") is False and row.get("ai_profile_mounted") is (role == "model") and
            row.get("network") == ("none" if role == "validator" else self.broker.executor.config.model_network),
            "actual product/reviewer isolated boundary missing")

    def _actual_main(self, main):
        self.broker.authenticate()
        require(self.broker.enabled() and self.broker.github.request("GET", f"repos/{REPO}/commits/main")["sha"] == main,
                "product evidence OFF or source main moved")

    def _case(self, case_id, main, run_id, settings, store, origin):
        from services.automation import product_rpc

        work, artifacts = self.broker._source(main, "product-" + case_id)
        binding = self.bindings[case_id]
        initial = snapshot_files(work)
        require(binding.dataset_path in initial and binding.input_path in initial and MANIFEST in initial,
                "fixed main product input/dataset/model provenance missing")
        manifest = json.loads(regular_file(work / MANIFEST, maximum=2 * 1024 * 1024))
        models = [row for row in manifest.get("models", []) if row.get("model_id") == MODEL and row.get("revision") == DIGEST]
        require(len(models) == 1 and isinstance(models[0].get("license"), str) and models[0]["license"] and
                isinstance(models[0].get("license_text_sha256"), str) and len(models[0]["license_text_sha256"]) == 64,
                "pinned source model/license provenance missing")
        for name in ("_trusted_product_rpc.py", "_trusted_product_runner.py"):
            require(not (work / name).exists(), "source shadows fixed product evaluator")
        (work / "_trusted_product_rpc.py").write_bytes(regular_file(Path(product_rpc.__file__), maximum=2 * 1024 * 1024))
        (work / "_trusted_product_runner.py").write_text(RUNNER, encoding="utf-8", newline="\n")
        frozen = snapshot_files(work)
        write_json(artifacts / "result-schema.json", {"run_id": run_id, "input": binding.input_path,
            "dataset": binding.dataset_path, "settings": settings, "execution_mode": binding.execution_mode})
        private = self.root / run_id
        private.mkdir(exist_ok=True)
        relay = FileRelay(artifacts, private / "relay.json", run_id, settings=settings,
            max_generations=self.options["max_generations_per_case"], max_tokens=self.options["max_product_tokens_per_case"],
            enabled=self.broker.enabled, upstream=self.upstream, origin=origin,
            allow_generation=binding.execution_mode == "live_model")
        stop, failures = threading.Event(), []

        def dispatch():
            while not stop.is_set():
                try:
                    relay.step()
                except (RPCError, OSError, ValueError, TypeError, KeyError):
                    failures.append("actual_product_relay_failed")
                    return
                stop.wait(0.05)

        thread = threading.Thread(target=dispatch, daemon=True)
        thread.start()
        output = private / "executor.log"
        try:
            result = self.broker.executor.run(["python", "_trusted_product_runner.py"], cwd=work, artifacts=artifacts,
                env={}, output=output, timeout_seconds=self.options["timeout_seconds"],
                heartbeat=lambda: self.broker.enabled() and not failures, heartbeat_interval=1,
                role="validator", readonly_workspace=True)
        finally:
            stop.set()
            thread.join(timeout=195)
            retained = {}
            # Failed/held runs remain observable but are not success admissions.
            # No exception from the model/network is included in public status.
            for name, target, maximum in (("output", artifacts / "result.json", 2 * 1024 * 1024),
                    ("relay", private / "relay.json", 16 * 1024 * 1024), ("process", output, 2 * 1024 * 1024)):
                if target.exists():
                    content = regular_file(target, maximum=maximum)
                    secret_check(content)
                    retained[name] = store.blob(f"control/product/{run_id}/{name}.json", main, content).as_dict()
            self.state.setdefault("case_runs", {})[run_id] = {
                "approved_origin": origin, "case_id": case_id, "tested_commit": main, "refs": retained,
                "execution_mode": binding.execution_mode,
                "actual_product_tokens": relay.state["tokens"], "actual_product_calls": relay.state["generations"],
                "usage_unknown": any(row.get("usage_unknown") for row in relay.state["requests"]),
                "status": "unverified", "relay_failed": bool(failures or relay.failure)}
            self._save()
        require(not thread.is_alive() and not failures and not relay.failure and result.returncode == 0 and
                result.stopped_reason is None and frozen == snapshot_files(work), "actual product execution incomplete/source changed")
        boundary = self.broker.executor.last_boundary
        self._boundary(boundary, "validator")
        self._actual_main(main)
        raw = regular_file(artifacts / "result.json", maximum=2 * 1024 * 1024)
        secret_check(raw)
        product = json.loads(raw)
        mode = binding.execution_mode
        require(product.get("execution_kind") == ("live_model" if mode == "live_model" else "fixture") and
                product.get("status") in {"completed", "held", "failed"} and
                product.get("original_input") == json.loads(regular_file(work / binding.input_path)) and
                isinstance(product.get("trace"), list) and (bool(product["trace"]) or mode == "deterministic_guard" and
                    product["status"] == "failed" and isinstance(product.get("error"), dict)),
                "actual product trace/input mismatch")
        calls = product.get("model_calls", [])
        if mode == "live_model":
            self._verify_calls(product, relay.state, settings)
        else:
            require(not calls and relay.state["generations"] == 0 and product["status"] in {"failed", "held"},
                    "deterministic guard incorrectly used a model or accepted invalid input")
        references = retained
        self.state["case_runs"][run_id]["status"] = product["status"]
        self._save()
        code = [store.blob(path, main, regular_file(work / path)).as_dict() for path in sorted(initial)
                if path.startswith("packages/core/src/lgax_core/") and path.endswith(".py")]
        source = [store.blob(path, main, regular_file(work / path)).as_dict()
                  for path in (binding.dataset_path, binding.input_path, MANIFEST)]
        return {"case_id": case_id, "refs": references, "code_versions": code, "source_versions": source,
                "model": {"model_id": MODEL, "revision": DIGEST, "license": models[0]["license"],
                    "runtime": "actual Ollama via fixed file RPC; Docker validator network=none/noauth", "settings": settings},
                "boundary": boundary, "source_manifest_sha256": fingerprint(initial),
                "execution_mode": mode, "requirement_ids": list(binding.requirement_ids),
                "actual_product_calls": len(calls), "actual_product_tokens": relay.state["tokens"]}

    @staticmethod
    def _verify_calls(product, relay_state, settings):
        generations = [row for row in relay_state["requests"] if row["generation"]]
        calls = product.get("model_calls", [])
        require(bool(calls) and len(calls) == len(generations) and all(row["state"] == "completed" for row in generations),
                "coding/no-model/fabricated product call count")
        for call, record in zip(calls, generations, strict=True):
            observed = json.loads(base64.b64decode(record["response_base64"], validate=True))
            metadata = call.get("metadata", {})
            require(call.get("formatted_prompt") == record["request"]["body"]["prompt"] and
                    call.get("schema") == record["request"]["body"]["format"] and
                    call.get("formatted_prompt_sha256") == digest(call["formatted_prompt"].encode()) and
                    call.get("raw_response") == observed["response"] and metadata.get("model_id") == MODEL and
                    metadata.get("revision") == DIGEST and metadata.get("generation_settings") == settings and
                    metadata.get("thinking_enabled") is False and
                    metadata.get("prompt_eval_count") == record["usage"]["prompt_eval_count"] and
                    metadata.get("eval_count") == record["usage"]["eval_count"], "product trace differs from actual relay completion")
    def _review_budget(self, task_id):
        day = time.strftime("%Y-%m-%d", time.gmtime())
        budget = self.broker.state["budgets"].setdefault(day, {"calls": 0, "tokens": 0, "tasks": {}, "task_calls": {}})
        budget.setdefault("task_calls", {})
        limits = self.broker.policy["limits"]
        decision_tokens = decision_calls = task_tokens = task_calls = 0
        journal = self.broker.config.get("journal_file")
        require(journal and Path(journal).is_file(), "actual PM decision budget journal required")
        with closing(sqlite3.connect(Path(journal).as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT tokens,model_calls FROM budgets WHERE scope=?", ("day:" + day,)).fetchone()
            decision_tokens, decision_calls = row or (0, 0)
            row = db.execute("SELECT tokens,model_calls FROM budgets WHERE scope=?", ("task:" + task_id,)).fetchone()
            task_tokens, task_calls = row or (0, 0)
        old_tokens = sum(value.get("tasks", {}).get(task_id, 0) for value in self.broker.state["budgets"].values())
        old_calls = sum(value.get("task_calls", {}).get(task_id, 0) for value in self.broker.state["budgets"].values())
        require(budget["calls"] < self.broker.config.get("max_reviews_per_day", 16) and
                budget["calls"] + decision_calls < limits["max_model_calls_per_day"] and
                budget["tokens"] + decision_tokens < limits["max_model_tokens_per_day"] and
                old_tokens + task_tokens < limits["max_model_tokens_per_task"] and
                old_calls + task_calls < limits["max_model_calls_per_task"], "independent product review budget exhausted")
        budget["calls"] += 1
        budget["task_calls"][task_id] = budget["task_calls"].get(task_id, 0) + 1
        self.broker.save()
        return budget, (decision_tokens, task_tokens + old_tokens)

    def _review(self, contract, main, unit, cases, store, entry):
        criteria = dict(contract.requirements)
        supported = {key for case in cases for key in case.get("requirement_ids", SUPPORTED)}
        selected = tuple(key for key in criteria if key in supported and key in unit["capability"].requirement_ids)
        require(bool(selected), "no approved implementation criterion covered by these cases")
        require(any(case.get("execution_mode", "live_model") == "live_model" and case["actual_product_calls"] > 0
                    for case in cases), "actual live product execution required for CORE002 aggregate")
        rows = {key: {"type": "object", "additionalProperties": False,
            "properties": {"outcome": {"enum": ["approve", "missing", "changes_requested"]},
                           "reason": {"type": "string", "minLength": 1, "maxLength": 1500}},
            "required": ["outcome", "reason"]} for key in selected}
        schema = {"type": "object", "additionalProperties": False, "properties": rows, "required": list(selected)}
        full_scope = set(selected) == set(criteria)
        if full_scope:
            action_schema = {"type": "object", "additionalProperties": False, "properties": {
                key: {"type": "object", "additionalProperties": False, "properties": {
                    "outcome": {"enum": ["approve", "missing", "changes_requested"]},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 1500}}, "required": ["outcome", "reason"]}
                for key in contract.action_criteria}, "required": list(contract.action_criteria)}
            schema["properties"]["task_actions"] = action_schema
            schema["required"].append("task_actions")
        requirements = json.loads(store.read(contract.requirements_source))["requirements"]
        sources = {row["id"]: row for row in requirements}
        context = {"purpose": "Independently assess actual product execution per literal requirement. This is partial CORE002 evidence.",
            "tested_commit": main, "task_id": TASK, "requirements": [{"id": key, "acceptance": sources[key]["acceptance"],
               "criterion_sha256": criteria[key]} for key in selected],
            "notice": "Synthetic inputs do not prove customer demand. Agent semantic_reviews are self-review, not your independent judgement. Missing data is missing. A deterministic_guard case made no model call; assess it together with actual live cases, never call it live_model. Review the entire literal criterion, not just its easier half. Partial criteria cannot imply parent Done.",
            "cases": [{"case_id": case["case_id"], "input": json.loads(store.read(ArtifactRef.parse(case["source_versions"][1]))),
                "execution_mode": case.get("execution_mode", "live_model"),
                "criterion_scope": case.get("requirement_ids", list(SUPPORTED)),
                "dataset": json.loads(store.read(ArtifactRef.parse(case["source_versions"][0]))),
                "actual_output": self._review_output(json.loads(store.read(ArtifactRef.parse(case["refs"]["output"])))),
                "relay_sha256": case["refs"]["relay"]["sha256"], "actual_product_calls": case["actual_product_calls"]} for case in cases]}
        if full_scope:
            task = json.loads(store.read(contract.task_source))
            actions = {criterion_digest(value): value for value in task["actions"]}
            require(set(actions) == set(contract.action_criteria), "source task action binding changed")
            context["task_actions"] = actions
            context["fixed_core_source"] = [{"path": ref["path"], "sha256": ref["sha256"],
                "source": store.read(ArtifactRef.parse(ref)).decode("utf-8")}
                for ref in cases[0]["code_versions"] if ref["path"].endswith(("planning_agent.py", "model_client.py"))]
            require(len(context["fixed_core_source"]) == 2, "whole-action review requires frozen Agent and adapter source")
        require(len(canonical(context).encode()) <= 128 * 1024, "complete product review context exceeds bound; split cases")
        reserve = getattr(self.broker.driver, "reserve_profile", None)
        require(callable(reserve), "actual isolated reviewer profile reservation required")
        with reserve():
            budget, prior = self._review_budget(TASK)
            entry["state"] = "review_started"
            self._save()
            used = None
            try:
                record = self.broker.driver.call(context, schema, self.broker.policy["limits"]["decision_timeout_seconds"],
                                                 purpose="product-review")
                usage = record.get("usage", {})
                require(all(type(usage.get(key)) is int and usage[key] >= 0 for key in ("input_tokens", "output_tokens")),
                        "actual independent review CLI usage missing")
                used = sum(usage[key] for key in ("input_tokens", "output_tokens"))
                budget["tokens"] += used
                budget["tasks"][TASK] = budget["tasks"].get(TASK, 0) + used
                self.broker.save()
                limits = self.broker.policy["limits"]
                require(budget["tokens"] + prior[0] <= limits["max_model_tokens_per_day"] and
                        used + prior[1] <= limits["max_model_tokens_per_task"], "actual product-review quota exceeded")
            finally:
                if used is None:
                    limits = self.broker.policy["limits"]
                    budget["tokens"] = max(budget["tokens"], limits["max_model_tokens_per_day"])
                    budget["tasks"][TASK] = max(budget["tasks"].get(TASK, 0), limits["max_model_tokens_per_task"])
                    self.broker.save()
        session = record.get("session_id")
        require(isinstance(session, str) and ID.fullmatch(session) and session.startswith("product-review-") and
                session != unit["implementation_session_id"], "actual distinct product reviewer required")
        original = json.loads(regular_file(self.broker.state_dir / "driver" / session / "proof.json", maximum=2 * 1024 * 1024))
        require(fingerprint(original) == fingerprint(record) and
                digest(regular_file(self.broker.state_dir / "driver" / session / "events.jsonl", maximum=64 * 1024 * 1024)) ==
                record.get("events_sha256"), "original independent review/event bytes changed")
        self._boundary(record.get("boundary"), "model")
        verdicts = record.get("result")
        action_verdicts = verdicts.get("task_actions") if isinstance(verdicts, dict) else None
        expected_keys = set(selected) | ({"task_actions"} if full_scope else set())
        require(isinstance(verdicts, dict) and set(verdicts) == expected_keys and all(isinstance(row, dict) and
                set(row) == {"outcome", "reason"} and row["outcome"] in {"approve", "missing", "changes_requested"} and
                isinstance(row["reason"], str) and 0 < len(row["reason"]) <= 1500 for key, row in verdicts.items()
                if key != "task_actions") and (not full_scope or isinstance(action_verdicts, dict) and
                    set(action_verdicts) == set(contract.action_criteria) and all(isinstance(row, dict) and
                        set(row) == {"outcome", "reason"} and row["outcome"] in {"approve", "missing", "changes_requested"} and
                        isinstance(row["reason"], str) and 0 < len(row["reason"]) <= 1500 for row in action_verdicts.values())),
                "independent product criterion verdict malformed")
        self._actual_main(main)
        review_ref = store.blob(f"control/product/{session}/review.json", main, canonical(record).encode() + b"\n")
        result = []
        for requirement_id in selected:
            verdict = verdicts[requirement_id]
            if verdict["outcome"] != "approve":
                continue
            common = {"schema_version": 1, "task_id": TASK, "requirement_id": requirement_id, "job_id": unit["job_id"],
                "tested_commit": main, "criterion_sha256": criteria[requirement_id], "contract_fingerprint": contract.fingerprint}
            execution = store.admit("requirement_execution", main, {**common, "kind": "requirement_execution",
                "execution_kind": "live_model", "result": "pass", "implementation_session_id": unit["implementation_session_id"],
                "evaluator_session_ids": [case["run_id"] for case in cases],
                "observations": ["Actual product executions correlated with original upstream completions; zero-model guards are explicitly distinguished", verdict["reason"]],
                "limitations": ["Synthetic development examples, not blind evaluation or real customer demand", "Only independently approved complete literal criteria are counted; formal completion/dual ACK remains separate", "PM CLI review tokens are separate from recorded product tokens"],
                "code_versions": cases[0]["code_versions"], "source_versions": [ref for case in cases for ref in case["source_versions"]],
                "inputs": [case["source_versions"][1] for case in cases], "outputs": [case["refs"]["output"] for case in cases],
                "checks": [{"name": case["case_id"] + "-upstream-correlation", "passed": True, "output": case["refs"]["relay"]} for case in cases],
                "model": cases[0]["model"], "independent_review": review_ref.as_dict()})
            acceptance = store.admit("requirement_acceptance", main, {**common, "kind": "requirement_acceptance",
                "reviewer": PM, "reviewer_session_id": session, "outcome": "approve", "findings": [],
                "execution_sha256": execution.sha256, "review_evidence": review_ref.as_dict(), "criterion_reason": verdict["reason"]})
            result.append(RequirementEvidence(requirement_id, unit["job_id"], execution, acceptance))
        parent = None
        if full_scope and {row.requirement_id for row in result} == set(criteria) and all(
                row["outcome"] == "approve" for row in action_verdicts.values()):
            parent = store.admit("parent_acceptance", main, {"schema_version": 1, "kind": "parent_acceptance",
                "task_id": TASK, "tested_commit": main, "actor": PM, "contract_fingerprint": contract.fingerprint,
                "outcome": "approve", "findings": [], "requirement_ids": list(criteria), "reviewer": PM,
                "reviewer_session_id": session, "actions": [{"criterion_sha256": key, "outcome": "approve",
                    "execution_sha256": result[0].execution.sha256, "reason": action_verdicts[key]["reason"]}
                    for key in contract.action_criteria], "review_evidence": review_ref.as_dict()})
        entry.update(state="partial", reviewer_session_id=session, actual_review_usage=record["usage"],
                     parent_acceptance=None if parent is None else parent.as_dict(),
                     verdicts=verdicts, coverage=[{"requirement_id": row.requirement_id, "job_id": row.job_id,
                        "execution": row.execution.as_dict(), "acceptance": row.acceptance.as_dict()} for row in result])
        self._save()
        return EvidenceBundle(tuple(result), parent)

    def __call__(self, contract: TaskContract, main: str, units: tuple[AcceptedUnit, ...], store: EvidenceStore) -> EvidenceBundle:
        registered = self._registered(contract, main, store)
        if contract.task_id != TASK or self.options.get("enabled") is not True:
            return registered
        require(self.options.get("case_ids") == list(self.bindings), "exact registered product cases required")
        require(set(self.options) == {"enabled", "case_ids", "max_generations_per_case", "max_product_tokens_per_case",
            "max_product_cases_per_task", "timeout_seconds", "settings"}, "unreviewed product execution option")
        require("live_model" in contract.execution_kinds, "source does not authorize actual model execution")
        positive(self.options.get("max_generations_per_case"), 12)
        positive(self.options.get("max_product_tokens_per_case"), 1000000)
        positive(self.options.get("max_product_cases_per_task"), 10)
        require(type(self.options.get("timeout_seconds")) is int and 1 <= self.options["timeout_seconds"] <= 3600,
                "bounded product execution timeout required")
        settings = self.options.get("settings")
        checked_settings(settings)
        self._actual_main(main)
        candidates = []
        for accepted in units:
            require(store.registry.permits(accepted.acceptance, "unit_acceptance"), "actual accepted implementation required")
            row = _unit(contract, accepted, store.registry, store.read)
            if set(SUPPORTED) & set(row["capability"].requirement_ids):
                candidates.append(row)
        if not candidates:
            return registered
        unit = candidates[-1]
        require(isinstance(unit.get("job_id"), str) and ID.fullmatch(unit["job_id"]) and
                isinstance(unit.get("implementation_session_id"), str) and ID.fullmatch(unit["implementation_session_id"]),
                "fixed accepted unit origin missing")
        key = fingerprint({"main": main, "contract": contract.fingerprint, "job": unit["job_id"], "options": self.options,
            "bindings": [asdict(case) for case in self.bindings.values()]})
        with exclusive_lock(self.root / "producer.lock"):
            # Two pre-created PM callbacks must not replay a paid case after
            # waiting for the same protected lock with stale in-memory state.
            if self.state_path.exists():
                self.state = json.loads(regular_file(self.state_path))
                require(self.state.get("schema_version") == 1 and isinstance(self.state.get("runs"), dict),
                        "invalid current protected product state")
            entry = self.state["runs"].get(key)
            if entry and entry.get("state") == "partial":
                return EvidenceBundle(tuple(RequirementEvidence(row["requirement_id"], row["job_id"],
                    ArtifactRef.parse(row["execution"]), ArtifactRef.parse(row["acceptance"])) for row in entry["coverage"]),
                    None if entry.get("parent_acceptance") is None else ArtifactRef.parse(entry["parent_acceptance"]))
            if entry and entry.get("state") not in {"executed"}:
                return registered  # Crash/failure/unknown is never an automatic model retry.
            if entry is None:
                actual_cases = sum(len(value.get("case_ids_reserved", [])) for value in self.state["runs"].values())
                require(actual_cases + len(self.bindings) <= self.options["max_product_cases_per_task"], "logical product-case budget exhausted")
                entry = {"state": "started", "main": main, "task_id": TASK, "job_id": unit["job_id"],
                         "case_ids_reserved": list(self.bindings), "full_task_complete": False}
                self.state["runs"][key] = entry
                self._save()  # Started/failed units retain quota across restarts and fresh main.
                try:
                    cases = []
                    for case_id in self.bindings:
                        run_id = "product-" + fingerprint({"key": key, "case": case_id})[:40]
                        origin = {"task_id": TASK, "job_id": unit["job_id"], "tested_commit": main,
                            "contract_fingerprint": contract.fingerprint,
                            "capability_fingerprint": unit["capability"].fingerprint, "owner": contract.owner}
                        case = self._case(case_id, main, run_id, settings, store, origin)
                        case["run_id"] = run_id
                        cases.append(case)
                    entry.update(state="executed", cases=cases)
                    self._save()
                except (CompletionError, RPCError, PMError, OSError, ValueError, TypeError, KeyError):
                    entry.update(state="failed", reason="actual product execution unavailable/unverified; no invented coverage")
                    self._save()
                    return registered
            try:
                self._review(contract, main, unit, entry["cases"], store, entry)
            except PMDriverBusy:
                return registered  # Profile reservation precedes billable review.
            except (CompletionError, RPCError, PMError, OSError, ValueError, TypeError, KeyError):
                entry.update(state="failed", reason="actual independent product acceptance unavailable; no invented coverage")
                self._save()
                return registered
            # Default cases never create parent acceptance. A future fixed host
            # case set can do so only after complete literal/action review.
            saved_key = fingerprint({"task": contract.task_id, "contract": contract.fingerprint, "main": main})
            previous = store.index.setdefault("requirement_bundles", {}).get(saved_key, {})
            combined = {row["requirement_id"]: row for row in previous.get("coverage", [])}
            for row in entry["coverage"]:
                # Existing admitted criterion evidence is not silently replaced.
                if entry.get("parent_acceptance"):
                    combined[row["requirement_id"]] = row
                else:
                    combined.setdefault(row["requirement_id"], row)
            store.index["requirement_bundles"][saved_key] = {**previous, "coverage": list(combined.values()),
                "parent_acceptance": entry.get("parent_acceptance") or previous.get("parent_acceptance"),
                "dependencies": previous.get("dependencies", [])}
            store.save()
            return self._registered(contract, main, store)

    @staticmethod
    def _review_output(product):
        """Complete result/trace and raw completions, without repeated prompt schemas.

        Full original model_calls remain immutable in the referenced output; the
        host independently checks each prompt/schema/upstream digest beforehand.
        No answer is truncated. Schemas are protocol, not evaluation answers.
        """
        return {key: value for key, value in product.items() if key != "model_calls"} | {
            "model_calls": [{key: call[key] for key in ("stage", "skill_id", "raw_response", "metadata", "error")
                             if key in call} for call in product.get("model_calls", [])]}
