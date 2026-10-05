"""Protected product failures reach bounded jobs; no live/auth/model operations."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from services.automation.backlog import (
    CORE_CORRECTIONS,
    CORE_ORIGINAL_UNITS,
    BacklogError,
    product_correction_registry,
    ready_product_corrections,
    validate_product_correction_registry,
    with_core_product_corrections,
)
from services.automation.orchestration import Orchestration
from services.automation.parent_collector import EvidenceStore
from services.automation.pm import canonical, fingerprint, stable_observation
from services.automation.pm_broker import ProductCorrectionRejected, TrustedPMBroker
from services.automation.product_evidence import (
    DATASET,
    MANIFEST,
    ProductCaseBinding,
    ProductEvidenceProducer,
)
from services.automation.product_rpc import DIGEST, MODEL
from tests import test_automation_orchestration as lifecycle_fixture
from tests.test_automation_product_evidence import boundary
from tests.test_automation_product_rpc import SETTINGS, completion, generation


class ProductCorrectionTests(unittest.TestCase):
    result = lifecycle_fixture.OrchestrationLifecycleTests.result

    def setUp(self):
        lifecycle_fixture.OrchestrationLifecycleTests.setUp(self)
        original = deepcopy(self.plan)
        self.expanded = with_core_product_corrections(self.plan)
        self.registry = product_correction_registry(self.plan)
        self.assertEqual({key: self.expanded["capabilities"][key] for key in original["capabilities"]}, original["capabilities"])
        path = self.root / "correction-registry.json"
        path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.broker.config["product_correction_registry"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.broker.policy["capabilities"] = deepcopy(self.expanded["capabilities"])
        self.broker.policy["independent_reviewers"] = ["jeongiryang"]
        self.released = set(self.expanded["capabilities"])
        self.live = Orchestration(self.broker)
        self.result(CORE_ORIGINAL_UNITS[0])
        self.result(CORE_ORIGINAL_UNITS[1])
        self.live.synchronize(self.observation)
        self.origin = self.broker.state["units"]["job-" + CORE_ORIGINAL_UNITS[1]]
        self.gitroot = self.root / "git"
        self.gitroot.mkdir()
        self.git(["init", "--quiet"])
        self.input_path = "evals/core-planning/examples/fridge.input.json"
        self.source = {self.input_path: {"request_id": "development-fridge"}, DATASET: {"documents": []},
            MANIFEST: {"models": [{"model_id": MODEL, "revision": DIGEST, "license": "fixture"}]},
            "packages/core/src/lgax_core/planning_agent.py": "# public fixture code\n"}
        for name, value in self.source.items():
            p = self.gitroot / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(value if isinstance(value, str) else canonical(value), encoding="utf-8")
        self.git(["add", "."])
        self.commit()
        self.broker._git = lambda argv, binary=False: self.git(argv, binary=binary)
        self.broker.state["actions"] = {}
        self.broker.enabled = Mock(return_value=True)
        self.store = EvidenceStore(self.root / "protected-evidence")
        self.live.parent = SimpleNamespace(store=self.store, tick=Mock(return_value={
            "main_commit": self.main, "tasks": {"P2-CORE-002": {"state": "waiting_evidence", "missing_requirements": ["R09"]}}}))
        self.producer = object.__new__(ProductEvidenceProducer)
        self.producer.broker = SimpleNamespace(executor=SimpleNamespace(config=SimpleNamespace(
            image="sha256:" + "a" * 64, model_network="bridge")))
        self.producer.options = {"settings": deepcopy(SETTINGS)}
        self.producer.evaluator_versions = {"product_evidence.py": "f" * 64, "product_rpc.py": "e" * 64}
        self.producer.bindings = {"fridge-normal": ProductCaseBinding("fridge-normal", self.input_path, DATASET, ("R01", "R09"))}
        self.product_state = {"schema_version": 1, "runs": {"test": {"state": "failed", "main": self.main}}, "case_runs": {}}
        self.producer._current_state = lambda: deepcopy(self.product_state)
        self.live.product_producer = self.producer
        self.make_case()

    def git(self, argv, *, binary=False):
        r = subprocess.run(["git", "-c", "core.hooksPath=" + str(self.root / "empty-hooks"),
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *argv],
            cwd=self.gitroot, capture_output=True, check=True)
        return r.stdout if binary else r.stdout.decode().strip()

    def commit(self):
        self.git(["commit", "--quiet", "-m", "public fixture"])
        self.main = self.git(["rev-parse", "HEAD"])
        self.observation["main_commit"] = self.main
        self.observation["formal_snapshot"]["approved_commit"] = self.main

    def make_case(self, *, status="failed", error="GAP_MANUAL_MISSING", run_id="product-fixed-normal"):
        body, response = generation(), completion()
        call = {"formatted_prompt": body["prompt"], "formatted_prompt_sha256": hashlib.sha256(body["prompt"].encode()).hexdigest(),
            "schema": body["format"], "raw_response": json.loads(response)["response"], "metadata": {
                "model_id": MODEL, "revision": DIGEST, "generation_settings": SETTINGS, "thinking_enabled": False,
                "prompt_eval_count": 11, "eval_count": 7}}
        product = {"execution_kind": "live_model", "status": status, "original_input": self.source[self.input_path],
            "model_calls": [call], "trace": [{"stage": "review", "violations": [{"code": error, "stage": "compare"}]}],
            "output": {"unresolved": [error]}}
        origin = {"task_id": "P2-CORE-002", "job_id": self.origin["job_id"], "tested_commit": self.main,
                  "capability_fingerprint": fingerprint(self.plan["capabilities"][CORE_ORIGINAL_UNITS[1]])}
        relay = {"run_id": run_id, "approved_origin": origin, "settings": SETTINGS, "allow_generation": True,
            "requests": [{"generation": True, "state": "completed", "request": {"body": body},
            "response_base64": base64.b64encode(response).decode(), "usage": {"prompt_eval_count": 11, "eval_count": 7}}]}
        refs = {name: self.store.blob(f"control/product/{run_id}/{name}.json", self.main, canonical(value).encode()).as_dict()
                for name, value in (("output", product), ("relay", relay))}
        self.case = {"case_id": "fridge-normal", "tested_commit": self.main, "execution_mode": "live_model",
            "approved_origin": origin,
            "refs": refs, "status": status, "evaluator_versions": deepcopy(self.producer.evaluator_versions),
            "actual_product_calls": 1, "actual_product_tokens": 18, "usage_unknown": False, "relay_failed": False}
        self.product_state["case_runs"] = {run_id: self.case}
        return product

    def feedback(self):
        return self.live._product_correction_feedback(self.observation)

    def ready(self):
        return ready_product_corrections(self.plan, self.registry, self.observation,
            self.broker.state["backlog_ledger"], self.broker.state.get("correction_ledger", []))["ready"]

    def test_verified_semantic_failure_survives_later_transport_failure_without_self_approval(self):
        self.product_state["case_runs"]["product-unverified-changed"] = {
            **deepcopy(self.case), "status": "unverified", "case_id": "fridge-changed"}
        feedback = self.feedback()[CORE_CORRECTIONS[0]]
        self.assertEqual(feedback["cases"][0]["error_codes"], ["GAP_MANUAL_MISSING"])
        self.assertEqual(feedback["cases"][0]["input"]["path"], self.input_path)
        self.assertFalse(feedback["already_dispatched"])
        self.assertIn("unverified_product_transport_or_usage", canonical(self.observation["product_escalations"]))
        self.assertNotIn("expected_answers", canonical(feedback))
        self.assertNotIn(str(self.root), canonical(feedback))

    def test_forged_status_trace_tokens_original_input_or_source_never_becomes_ready(self):
        for change in ({"status": "unverified"}, {"usage_unknown": True}, {"relay_failed": True},
                       {"actual_product_calls": 0}, {"evaluator_versions": {"invented": "f" * 64}}):
            old = deepcopy(self.case)
            self.case.update(change)
            with self.subTest(change=change):
                self.assertFalse(self.feedback())
            self.case.clear()
            self.case.update(old)
        raw = self.store.root / (self.case["refs"]["output"]["sha256"] + ".blob")
        raw.write_bytes(b'{"status":"failed"}')
        self.assertFalse(self.feedback())

    def test_transport_error_alone_escalates_and_never_routes_a_core_repair(self):
        self.make_case(status="unverified", error="MODEL_UNAVAILABLE")
        self.assertFalse(self.feedback())

    def test_original_independent_missing_verdict_routes_completed_case_but_fake_proof_does_not(self):
        self.make_case(status="completed")
        session = "product-review-known"
        folder = self.broker.state_dir / "driver" / session
        folder.mkdir(parents=True)
        events = b'{"fixture_original_event":true}\n'
        (folder / "events.jsonl").write_bytes(events)
        verdicts = {"R09": {"outcome": "missing", "reason": "Incomplete feature versus remaining discomfort comparison"}}
        proof = {"session_id": session, "result": verdicts, "events_sha256": hashlib.sha256(events).hexdigest(),
                 "boundary": boundary("model")}
        (folder / "proof.json").write_text(canonical(proof), encoding="utf-8")
        self.product_state["runs"]["test"].update(state="partial", cases=[{"run_id": "product-fixed-normal"}],
            reviewer_session_id=session, events_sha256=proof["events_sha256"], verdicts=verdicts)
        feedback = self.feedback()[CORE_CORRECTIONS[0]]
        self.assertEqual(feedback["cases"][0]["rejected_criteria"][0]["requirement_id"], "R09")
        proof["result"] = {"R09": {"outcome": "approve", "reason": "Invented approval"}}
        (folder / "proof.json").write_text(canonical(proof), encoding="utf-8")
        self.assertFalse(self.feedback())
        proof["result"] = verdicts
        (folder / "proof.json").write_text(canonical(proof), encoding="utf-8")
        (folder / "events.jsonl").write_bytes(b'{}\n')
        self.assertFalse(self.feedback())
        self.assertTrue(self.observation["product_escalations"])
        self.make_case(status="failed", error="MODEL_UNAVAILABLE")
        self.assertFalse(self.feedback())

    def test_pending_review_partial_original_acceptance_and_moved_main_hold(self):
        self.product_state["runs"]["test"]["state"] = "review_started"
        self.assertFalse(self.feedback())
        self.product_state["runs"]["test"]["state"] = "failed"
        old = self.observation["main_commit"]
        self.observation["main_commit"] = "f" * 40
        self.assertFalse(self.feedback())
        self.observation["main_commit"] = old
        self.broker.state["backlog_ledger"] = self.broker.state["backlog_ledger"][:3]
        self.assertFalse(self.feedback())

    def test_ready_on_verified_feedback_but_off_and_budget_and_dedupe_hold(self):
        feedback = self.feedback()
        self.observation["product_corrections"] = feedback
        self.assertIn(CORE_CORRECTIONS[0], self.ready())
        self.observation["global_mode"] = "off"
        self.assertNotIn(CORE_CORRECTIONS[0], self.ready())
        self.observation["global_mode"] = "on"
        value = feedback[CORE_CORRECTIONS[0]]
        self.broker.state["actions"]["pm-" + "1" * 40] = {"phase": "intent", "product_correction": value}
        self.observation["product_corrections"] = self.feedback()
        self.assertEqual(self.observation["product_corrections"][CORE_CORRECTIONS[0]]["dispatches_used"], 1)
        self.assertNotIn(CORE_CORRECTIONS[0], self.ready())
        self.broker.state["actions"]["pm-" + "2" * 40] = {"product_correction": {**value, "failure_identity": "a" * 64}}
        self.observation["product_corrections"] = self.feedback()
        self.assertEqual(self.observation["product_corrections"][CORE_CORRECTIONS[0]]["dispatches_used"], 2)
        self.assertNotIn(CORE_CORRECTIONS[0], self.ready())

    def test_restart_and_docs_only_new_main_cannot_repeat_same_failure(self):
        first = self.feedback()[CORE_CORRECTIONS[0]]
        self.broker.state["actions"]["pm-" + "1" * 40] = {"product_correction": first}
        p = self.gitroot / "public-note.md"
        p.write_text("docs only", encoding="utf-8")
        self.git(["add", "."])
        self.commit()
        self.product_state["runs"]["test"]["main"] = self.main
        self.make_case(run_id="product-new-main-normal")
        later = self.feedback()[CORE_CORRECTIONS[0]]
        self.assertEqual(first["failure_identity"], later["failure_identity"])
        self.assertTrue(later["already_dispatched"])
        restarted = Orchestration(self.broker)
        restarted.parent, restarted.product_producer = self.live.parent, self.producer
        self.assertTrue(restarted._product_correction_feedback(self.observation)[CORE_CORRECTIONS[0]]["already_dispatched"])

    def test_new_product_code_changes_identity_without_resetting_lifetime_dispatches(self):
        first = self.feedback()[CORE_CORRECTIONS[0]]
        self.broker.state["actions"]["pm-" + "1" * 40] = {"product_correction": first}
        p = self.gitroot / "packages/core/src/lgax_core/planning_agent.py"
        p.write_text("# minimal new code\n", encoding="utf-8")
        self.git(["add", "."])
        self.commit()
        self.product_state["runs"]["test"]["main"] = self.main
        self.make_case(run_id="product-fixed-new-code")
        later = self.feedback()[CORE_CORRECTIONS[1]]
        self.assertNotEqual(first["failure_identity"], later["failure_identity"])
        self.assertEqual(later["dispatches_used"], 1)
        self.assertFalse(later["already_dispatched"])

    def test_synchronize_and_fresh_revalidation_attach_identical_feedback_without_models(self):
        before = deepcopy(self.broker.state["units"])
        self.live.synchronize(self.observation, collect=False)
        self.assertIn(CORE_CORRECTIONS[0], self.observation["capabilities_ready"])
        fresh = deepcopy(self.observation)
        self.live.synchronize(fresh, collect=False)
        self.assertEqual(fingerprint(stable_observation(fresh)), fingerprint(stable_observation(self.observation)))
        self.assertIn("GAP_MANUAL_MISSING", canonical(fresh["parent_completion"]))
        self.assertEqual(self.broker.state["units"], before)
        self.live.parent.tick.assert_not_called()

    def test_assignment_is_small_portable_existing_worker_prompt_with_proof_linkage(self):
        self.live.synchronize(self.observation)
        action = {**self.expanded["capabilities"][CORE_CORRECTIONS[0]], "owner": "unknownamed", "task_id": "P2-CORE-002",
            "capability_id": CORE_CORRECTIONS[0], "instructions": ["Fix the evidenced failure"],
            "formal_task_dependencies": ["P2-CORE-001"], "approved_snapshot_commit": self.main, "base_commit": self.main}
        broker = object.__new__(TrustedPMBroker)
        broker.orchestration, broker.state = self.live, self.broker.state
        assignment, packet, previous = broker._prepare_assignment("pm-" + "1" * 40, action, observation=self.observation)
        self.assertIsNone(previous)
        self.assertLess(len(packet["prompt"].encode()), 16000)
        self.assertIn(self.input_path, packet["prompt"])
        self.assertIn("GAP_MANUAL_MISSING", packet["prompt"])
        self.assertEqual(assignment["product_correction"]["evidence_sha256"], self.feedback()[CORE_CORRECTIONS[0]]["evidence_sha256"])
        self.assertNotIn("product_correction", packet)  # Existing Worker schema stays unchanged.
        self.assertEqual(packet["max_attempts"], 1)
        self.make_case(status="unverified")
        with self.assertRaises(ProductCorrectionRejected):
            broker._prepare_assignment("pm-" + "2" * 40, action, observation=self.observation)

    def test_correction_contract_cannot_expand_paths_owner_requirements_or_attempts(self):
        validate_product_correction_registry(self.plan, self.registry)
        for field, value in (("allowed_paths", ["packages/core/*"]), ("owner", "jeongiryang"),
                             ("requirement_ids", ["E01"]), ("max_attempts", 5)):
            altered = deepcopy(self.registry)
            altered["capabilities"][CORE_CORRECTIONS[0]][field] = value
            with self.subTest(field=field), self.assertRaises(BacklogError):
                validate_product_correction_registry(self.plan, altered)

    def test_original_caps_records_and_budgets_are_not_changed_by_feedback(self):
        before = deepcopy(self.broker.state)
        caps = deepcopy(self.broker.policy["capabilities"])
        self.feedback()
        self.assertEqual(self.broker.state, before)
        self.assertEqual(self.broker.policy["capabilities"], caps)

    def test_separate_overlay_history_preserves_original_digest_and_cannot_impersonate_old_events(self):
        before = deepcopy(self.broker.state["backlog_ledger"])
        self.live._event(CORE_CORRECTIONS[0], "known", "released", {"base_commit": self.main})
        self.assertEqual(self.broker.state["backlog_ledger"], before)
        self.assertTrue(self.broker.state["correction_ledger"])
        self.assertNotEqual(self.broker.state["correction_ledger"][0]["plan_digest"], before[0]["plan_digest"])
        self.live._progress()
        self.broker.state["correction_ledger"] = before
        with self.assertRaises(BacklogError):
            self.ready()

    def test_only_independent_exact_head_rejection_can_use_remaining_correction_slot(self):
        feedback = self.feedback()[CORE_CORRECTIONS[0]]
        cap = self.expanded["capabilities"][CORE_CORRECTIONS[0]]
        job = "auto-" + "1" * 40
        self.broker.state["units"][job] = {"job_id": job, "capability_id": CORE_CORRECTIONS[0],
            "task_id": "P2-CORE-002", "base_commit": self.main, "head": "b" * 40,
            "implementation_session_id": "implementation-known", "revision_requested": True,
            "product_correction": feedback}
        self.broker.state["actions"]["pm-" + "1" * 40] = {"product_correction": feedback}
        proof = {"verified": True, "collector": "trusted_pm", "head": "b" * 40, "base": self.main,
            "reviewer": "jeongiryang",
            "outcome": "request_changes", "capability_fingerprint": fingerprint(cap),
            "implementation_session_id": "implementation-known", "reviewer_session_id": "review-distinct",
            "evidence_sha256": "c" * 64}
        self.assertTrue(self.feedback()[CORE_CORRECTIONS[0]]["already_dispatched"])
        self.broker.state["proofs"]["correction-review"] = proof
        corrected = self.feedback()[CORE_CORRECTIONS[0]]
        self.assertFalse(corrected["already_dispatched"])
        self.assertEqual(corrected["dispatches_used"], 1)  # Intent + unit count once.
        self.assertEqual(corrected["revision_of"]["review_evidence_sha256"], "c" * 64)
        for change in ({"head": "e" * 40}, {"verified": False}, {"reviewer_session_id": "implementation-known"},
                       {"outcome": "approve"}, {"reviewer": "unregistered"}, {"evidence_sha256": "not-a-hash"}):
            self.broker.state["proofs"]["correction-review"] = {**proof, **change}
            with self.subTest(change=change):
                self.assertTrue(self.feedback()[CORE_CORRECTIONS[0]]["already_dispatched"])
        self.broker.state["proofs"]["correction-review"] = proof
        self.broker.state["actions"]["pm-" + "2" * 40] = {"product_correction": corrected}
        self.observation["product_corrections"] = self.feedback()
        self.assertEqual(self.observation["product_corrections"][CORE_CORRECTIONS[0]]["dispatches_used"], 2)
        self.assertNotIn(CORE_CORRECTIONS[0], self.ready())


if __name__ == "__main__":
    unittest.main()
