"""Pinned useful implementation queue, separate from final product evidence.

No subscription model, Gmail delivery, remote GitHub mutation or service start.
Actual SQLite controller tests exercise register/claim dependency fencing.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from services.automation.backlog import (
    BacklogError,
    append_progress,
    product_correction_registry,
    ready_development_units,
    ready_units,
    validate_development_registry,
    verify_progress,
)
from services.automation.orchestration import Orchestration
from services.automation.pm import AutonomousPM, PMError, load_policy
from services.automation.pm_broker import TrustedPMBroker
from services.automation.state import PM, Store
from tests import test_automation_orchestration as lifecycle
from tests import test_automation_pm_broker as broker_fixture

ROOT = Path(__file__).resolve().parents[1]
FIRST = "dev-core-source-model-scope"
SECOND = "dev-core-feature-support-states"
DATA = "dev-data-review-import"
WEB = "dev-web-evidence-trace-panel"
PM_UNIT = "dev-pm-api-run-failure-contract"


class DevelopmentQueueTests(unittest.TestCase):
    def result(self, key, **kwargs):
        original = self.plan
        try:
            self.plan = self.combined
            return lifecycle.OrchestrationLifecycleTests.result(self, key, **kwargs)
        finally:
            self.plan = original

    def setUp(self):
        lifecycle.OrchestrationLifecycleTests.setUp(self)
        self.registry = json.loads((ROOT / "docs/pm/development-queue-20261005.json").read_bytes())
        self.combined = validate_development_registry(self.plan, self.registry)
        self.path = self.root / "development-registry.json"
        self.path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.broker.config["development_queue_registry"] = {
            "path": str(self.path), "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.broker.policy["capabilities"] = deepcopy(self.combined["capabilities"])
        self.released = set(self.combined["capabilities"])
        self.live = Orchestration(self.broker)
        self.broker.state.setdefault("backlog_ledger", [])
        self.broker.state.setdefault("development_ledger", [])
        # None of the whole-product parent dependencies are declared Done.
        for task in self.observation["formal_snapshot"]["tasks"].values():
            task["status"] = "ready"

    def ready(self, observation=None):
        return ready_development_units(self.plan, self.registry, observation or self.observation,
            self.broker.state["backlog_ledger"], self.broker.state["development_ledger"])

    def rejected(self, registry):
        with self.assertRaises(BacklogError):
            validate_development_registry(self.plan, registry)

    def minimal_policy(self):
        value = broker_fixture.policy()
        value["tasks"] = deepcopy(self.plan["tasks"])
        value["capabilities"] = deepcopy(self.combined["capabilities"])
        path = self.root / "development-policy.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def action(self, key=FIRST):
        gate = object.__new__(AutonomousPM)
        gate.policy = self.minimal_policy()
        observation = deepcopy(self.observation)
        observation["capabilities_ready"] = [key]
        decision = {"action": "assign", "task_id": self.combined["capabilities"][key]["task_id"],
                    "capability_id": key, "pr_number": None, "head_commit": None,
                    "reason": "Pinned required implementation unit", "instructions": ["Implement exact contract"]}
        return gate.validate_action(decision, observation), observation

    def prepare(self, key=FIRST):
        action, observation = self.action(key)
        broker = object.__new__(TrustedPMBroker)
        broker.policy, broker.state, broker.orchestration = self.broker.policy, self.broker.state, self.live
        return TrustedPMBroker._prepare_assignment(broker, "pm-" + "f" * 40, action, observation=observation)

    def test_catalog_has_six_useful_product_code_units_per_owner_and_no_new_parent(self):
        self.assertEqual(len(self.registry["capabilities"]), 24)
        self.assertEqual(self.combined["tasks"], self.plan["tasks"])
        self.assertEqual({key: self.combined["capabilities"][key] for key in self.plan["capabilities"]}, self.plan["capabilities"])
        owners = {}
        for key, cap in self.registry["capabilities"].items():
            owners[cap["owner"]] = owners.get(cap["owner"], 0) + 1
            self.assertFalse(cap["completes_task"], key)
            self.assertTrue(any(path.startswith(("packages/core/", "apps/", "services/inference/", "evals/"))
                                and ".test." not in path for path in cap["allowed_paths"]), key)
            self.assertFalse(any(path.startswith(("docs/", "harness/", "scripts/")) for path in cap["allowed_paths"]), key)
            self.assertLessEqual(len(cap["allowed_paths"]), 40)
            self.assertLessEqual(len(cap["validation_commands"]), 12)
            # Tests must actually match the existing Vitest include rule.
            if cap["owner"] == "choigilung":
                self.assertTrue(any(path.endswith(".test.ts") for path in cap["allowed_paths"]))
        self.assertEqual(set(owners.values()), {6})

    def test_original_plan_binding_and_original_capability_override_are_refused(self):
        changed = deepcopy(self.registry)
        changed["original_plan_digest"] = "f" * 64
        self.rejected(changed)
        changed = deepcopy(self.registry)
        changed["capabilities"][lifecycle.FIRST] = deepcopy(changed["capabilities"].pop(FIRST))
        self.rejected(changed)

    def test_cross_owner_parent_and_requirement_expansion_are_refused(self):
        for update in ({"owner": "jeongiryang"}, {"requirement_ids": ["E03"]}, {"task_id": "P2-DATA-005"}):
            changed = deepcopy(self.registry)
            changed["capabilities"][FIRST].update(update)
            self.rejected(changed)

    def test_live_generation_or_completion_cannot_use_implementation_dependency_mode(self):
        for update in ({"execution_kind": "live_model"}, {"execution_kind": "live_service"},
                       {"completes_task": True}, {"max_attempts": 2}, {"required_environments": ["gpu"]},
                       {"expose_independent_answers": True}, {"development_only": False}):
            changed = deepcopy(self.registry)
            changed["capabilities"][FIRST].update(update)
            self.rejected(changed)

    def test_private_policy_wildcard_and_independent_answer_scopes_are_refused(self):
        for path in ("private/a.json", "harness/state.json", "AGENTS.md", "services/automation/pm.py",
                     "packages/core/*", "evals/independent/answers.json", "../a.py", 5):
            changed = deepcopy(self.registry)
            changed["capabilities"][FIRST]["allowed_paths"] = [path]
            self.rejected(changed)

    def test_invented_mismatched_or_cyclic_implementation_dependencies_are_refused(self):
        for update in ({"development_prerequisites": ["not-registered"], "depends_on_capabilities": ["not-registered"]},
                       {"development_prerequisites": [SECOND], "depends_on_capabilities": []},
                       {"development_prerequisites": [SECOND], "depends_on_capabilities": [SECOND]},
                       {"development_prerequisites": [{}], "depends_on_capabilities": [{}]}):
            changed = deepcopy(self.registry)
            changed["capabilities"][FIRST].update(update)
            self.rejected(changed)

    def test_extra_fields_unbounded_units_and_wrong_source_identity_are_refused(self):
        for update in ({"schema_version": 2}, {"source_commit": "main"}, {"repo": "another/repo"},
                       {"scope": "proposed_extension"}, {"commands": ["anything"]}, {"capabilities": {}}):
            changed = deepcopy(self.registry)
            changed.update(update)
            self.rejected(changed)
        changed = deepcopy(self.registry)
        changed["capabilities"] = {str(index): deepcopy(changed["capabilities"][FIRST]) for index in range(33)}
        self.rejected(changed)

    def test_fixture_implementation_can_start_before_formal_done_without_changing_original_gates(self):
        before = deepcopy(self.observation)
        result = self.ready()
        self.assertEqual(set(result["ready"]), {FIRST, DATA, WEB, PM_UNIT})
        self.assertFalse(result["formal_done"])
        self.assertEqual(self.observation, before)
        original = ready_units(self.plan, self.observation, [])
        self.assertEqual(original["waiting"][lifecycle.FIRST], "formal_dependencies_incomplete")
        self.assertEqual(original["waiting"]["pm-paired-blind-evaluation-measurement"], "formal_dependencies_incomplete")

    def test_off_stale_snapshot_and_unverified_owner_still_hold_development_work(self):
        for field, change, reason in (("global_mode", "off", "automation_off"),
                                      ("pm_mode", "off", "automation_off"),
                                      ("main_commit", "b" * 40, "formal_snapshot_not_current_main")):
            observation = deepcopy(self.observation)
            observation[field] = change
            result = self.ready(observation)
            self.assertEqual(result["ready"], [])
            self.assertEqual(set(result["waiting"].values()), {reason})
        self.observation["readiness"]["ginaginaring"]["login_verified"] = False
        self.assertEqual(self.ready()["waiting"][DATA], "owner_unavailable_or_unverified")

    def test_active_review_and_cross_owner_exact_path_hold_are_enforced(self):
        self.observation["jobs"].append({"job_id": "pending-core-review", "owner": "unknownamed",
                                         "capability_id": lifecycle.SECOND, "status": "review_requested"})
        self.assertEqual(self.ready()["waiting"][FIRST], "owner_has_active_work")
        self.observation["jobs"] = []
        self.observation["jobs"].append({"job_id": "scoped-other-owner", "owner": "ginaginaring",
                                         "capability_id": FIRST, "status": "running"})
        self.assertEqual(self.ready()["waiting"][FIRST], "scope_or_resource_conflict")

    def test_new_acceptance_preserves_original_hash_chain_and_advances_only_new_chain(self):
        self.result("data-document-store-frozen-snapshot")
        self.live.synchronize(self.observation)
        original = deepcopy(self.broker.state["backlog_ledger"])
        self.result(FIRST)
        self.live.synchronize(self.observation)
        self.assertEqual(self.broker.state["backlog_ledger"], original)
        self.assertEqual(verify_progress(self.combined, self.broker.state["development_ledger"])[FIRST], "accepted")
        self.assertEqual(self.ready()["waiting"][SECOND], "owner_has_active_work")
        self.result("dev-core-source-instruction-boundary")
        self.live.synchronize(self.observation)
        self.assertIn(SECOND, self.ready()["ready"])
        self.assertNotIn(FIRST, self.ready()["ready"])
        with self.assertRaises(BacklogError):
            append_progress(self.plan, original, event_id="cannot-spoof-original", capability_id=FIRST,
                            event="released", receipt={"base_commit": lifecycle.BASE})

    def test_development_ledger_cannot_claim_original_events_or_other_registry(self):
        self.result(FIRST)
        self.live.synchronize(self.observation)
        actual_ledger = deepcopy(self.broker.state["development_ledger"])
        self.broker.state["development_ledger"][0]["capability_id"] = lifecycle.FIRST
        with self.assertRaisesRegex(PMError, "history cannot"):
            Orchestration(self.broker)
        changed = deepcopy(self.registry)
        changed["capabilities"][FIRST]["priority"] += 1
        self.assertNotEqual(self.registry, changed)
        # A previously accepted chain remains tied to its whole combined plan,
        # even if a different protected catalogue was approved later.
        with self.assertRaises(BacklogError):
            verify_progress(validate_development_registry(self.plan, changed), actual_ledger)

    def test_protected_file_hash_or_policy_contract_mismatch_is_refused_before_side_effects(self):
        self.path.write_text(json.dumps({**self.registry, "purpose": "edited"}), encoding="utf-8")
        with self.assertRaisesRegex(PMError, "registry changed"):
            Orchestration(self.broker)
        self.path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.broker.policy["capabilities"][FIRST]["priority"] += 1
        with self.assertRaisesRegex(PMError, "policy differ"):
            Orchestration(self.broker)
        self.github.request.assert_not_called()

    def test_original_and_two_correction_contracts_coexist_with_development_registry(self):
        correction = product_correction_registry(self.plan)
        path = self.root / "correction.json"
        path.write_text(json.dumps(correction), encoding="utf-8")
        self.broker.config["product_correction_registry"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.broker.policy["capabilities"].update(correction["capabilities"])
        live = Orchestration(self.broker)
        self.assertEqual(len(live.capabilities), 49)
        self.assertEqual(live.plan, self.plan)
        self.assertEqual(live.capabilities[FIRST], self.registry["capabilities"][FIRST])
        self.assertEqual(live.capabilities["core-product-correction-1"], correction["capabilities"]["core-product-correction-1"])

    def test_prior_offers_fence_owners_across_registries_and_release_remains_explicit(self):
        self.live.synchronize(self.observation)
        owners = [self.live.capabilities[key]["owner"] for key in self.observation["capabilities_ready"]]
        self.assertEqual(len(owners), len(set(owners)))
        self.released = set(self.plan["capabilities"])
        self.live.synchronize(self.observation)
        self.assertFalse(set(self.observation["capabilities_ready"]) & set(self.registry["capabilities"]))
        self.released = {FIRST, DATA, WEB, PM_UNIT}
        self.broker.state["held_capabilities"] = {FIRST: {"reason": "known preparation rejection"}}
        self.live.synchronize(self.observation)
        self.assertNotIn(FIRST, self.observation["capabilities_ready"])
        self.assertEqual(self.observation["backlog"]["waiting"][FIRST], "fixed_assignment_preparation_rejected_requires_PM_followup")

    def test_only_offline_development_action_uses_separate_implementation_dependencies(self):
        action, _ = self.action()
        self.assertEqual(action["formal_task_dependencies"], [])
        self.assertEqual(action["max_attempts"], 1)
        self.assertEqual(self.plan["tasks"]["P2-CORE-002"]["depends_on"], ["P2-CORE-001"])
        with self.assertRaisesRegex(PMError, "formal dependencies"):
            self.action(lifecycle.FIRST)

    def test_explicit_finite_task_action_envelope_supports_queue_without_changing_daily_limits(self):
        fixed = self.minimal_policy()
        before = deepcopy(fixed["limits"])
        fixed["limits"]["max_actions_per_task"] = 64
        path = self.root / "reviewed-envelope.json"
        path.write_text(json.dumps(fixed), encoding="utf-8")
        actual = load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(actual["limits"]["max_actions_per_task"], 64)
        for key in before.keys() - {"max_actions_per_task"}:
            self.assertEqual(actual["limits"][key], before[key])
        fixed["limits"]["max_actions_per_task"] = 65
        path.write_text(json.dumps(fixed), encoding="utf-8")
        with self.assertRaises(PMError):
            load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_prerequisite_needs_actual_accepted_queue_job_not_just_ledger_metadata(self):
        self.result(FIRST)
        self.live.synchronize(self.observation)
        expected = ["job-" + FIRST]
        self.assertEqual(self.live.development_dependency_jobs(SECOND, self.observation), expected)
        for changed in ({"jobs": []}, {"jobs": [{"job_id": expected[0], "status": "review_requested"}]}):
            observation = {**deepcopy(self.observation), **changed}
            with self.assertRaisesRegex(PMError, "actual accepted queue"):
                self.live.development_dependency_jobs(SECOND, observation)
        with self.assertRaisesRegex(PMError, "externally pinned"):
            self.live.development_dependency_jobs(lifecycle.FIRST, self.observation)

    def test_packet_has_bounded_single_attempt_and_no_private_answer_or_parent_done(self):
        assignment, packet, previous = self.prepare()
        self.assertIsNone(previous)
        self.assertTrue(assignment["development_only"])
        self.assertIn("never grants parent Done", assignment["parent_completion"])
        self.assertEqual(packet["dependency_job_ids"], [])
        self.assertEqual(packet["formal_task_dependencies"], [])
        self.assertEqual(packet["max_attempts"], 1)
        self.assertLess(len(packet["prompt"].encode()), 16000)
        self.assertFalse(any(path.startswith("private/") for path in packet["allowed_paths"]))

    def test_actual_controller_claims_development_while_final_parent_dependencies_remain_incomplete(self):
        _, packet, _ = self.prepare()
        packet["approval_reference"] = "Pinned PM fixture approval"
        store = Store(self.root / "queue.sqlite", {"formal_snapshot": self.observation["formal_snapshot"]})
        store.mode(PM, "on")
        store.mode(PM, "on", member="unknownamed")
        self.assertTrue(store.register(PM, packet)["registered"])
        claimed = store.claim("unknownamed")["job"]
        self.assertEqual(claimed["job_id"], packet["job_id"])
        self.assertEqual(claimed["formal_task_dependencies"], [])
        snapshot = store.status(PM)["formal_snapshot"]
        self.assertEqual(snapshot["tasks"]["P2-CORE-001"]["status"], "ready")
        self.assertEqual(snapshot["tasks"]["P2-CORE-002"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
