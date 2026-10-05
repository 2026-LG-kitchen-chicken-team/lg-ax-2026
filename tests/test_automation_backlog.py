"""Actual scheduling transitions: chaining, parent evidence, conflict and OFF."""
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from services.automation.backlog import (
    BacklogError,
    append_progress,
    collector_candidates,
    load_backlog,
    paths_overlap,
    ready_units,
    validate_backlog,
    verify_progress,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = "a" * 40
MERGE = "b" * 40


class RequiredBacklogTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "docs/pm/orchestration-backlog.json"
        self.plan = load_backlog(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.observation = {"global_mode": "on", "pm_mode": "on", "main_commit": BASE,
            "formal_snapshot": {"approved_commit": BASE, "tasks": {
                key: {"owner": task["owner"], "scope": "required", "status": "ready"}
                for key, task in self.plan["tasks"].items()}},
            "members": {owner: True for owner in {task["owner"] for task in self.plan["tasks"].values()}},
            "readiness": {owner: {key: True for key in
                ("execution_isolation_verified", "publisher_separation_verified", "login_verified")}
                for owner in {task["owner"] for task in self.plan["tasks"].values()}}, "jobs": []}
        self.ledger = []

    def accept(self, unit):
        receipts = (("released", {"base_commit": BASE}),
            ("assigned", {"base_commit": BASE, "job_id": "auto-test-job"}),
            ("accepted", {"base_commit": BASE, "merge_commit": MERGE,
                          "integration_evidence_sha256": "c" * 64, "queue_status": "accepted"}))
        for event, receipt in receipts:
            self.ledger = append_progress(self.plan, self.ledger, event_id=unit + "-" + event,
                capability_id=unit, event=event, receipt=receipt)

    def test_every_required_parent_is_exactly_mapped_and_extensions_are_absent(self):
        self.assertEqual(len(self.plan["tasks"]), 19)
        self.assertEqual(len(self.plan["capabilities"]), 23)
        self.assertNotIn("P2-WEB-005", self.plan["tasks"])
        self.assertNotIn("P2-DATA-005", self.plan["tasks"])
        for key, task in self.plan["tasks"].items():
            original = json.loads((ROOT / "harness/phase2/tasks" / (key + ".json")).read_text("utf-8"))
            self.assertEqual(task["requirement_ids"], original["requirement_ids"])
            self.assertEqual(task["depends_on"], original["depends_on"])
            units = [unit for unit in self.plan["capabilities"].values() if unit["task_id"] == key]
            self.assertEqual(set().union(*(set(unit["requirement_ids"]) for unit in units)), set(task["requirement_ids"]))
            self.assertTrue(all(unit["completes_task"] is False and unit["expose_independent_answers"] is False for unit in units))

    def test_accepting_first_core_unit_automatically_offers_next_without_parent_done(self):
        self.observation["formal_snapshot"]["tasks"]["P2-CORE-001"]["status"] = "done"
        before = ready_units(self.plan, self.observation, self.ledger)
        self.assertIn("core-request-reuse-terminal-regression", before["ready"])
        self.assertEqual(before["waiting"]["core-exclusion-residual-quality"], "previous_unit_not_accepted")
        self.accept("core-request-reuse-terminal-regression")
        after = ready_units(self.plan, self.observation, self.ledger)
        self.assertIn("core-exclusion-residual-quality", after["ready"])
        self.assertNotIn("core-request-reuse-terminal-regression", after["ready"])
        self.assertEqual(after["waiting"]["core-shared-two-repair-budget"], "formal_dependencies_incomplete")
        self.assertFalse(after["formal_done"])
        self.assertNotIn("P2-CORE-002", collector_candidates(self.plan, self.ledger))

    def test_all_small_units_only_request_independent_collection_not_done(self):
        self.accept("core-request-reuse-terminal-regression")
        self.accept("core-exclusion-residual-quality")
        candidate = collector_candidates(self.plan, self.ledger)["P2-CORE-002"]
        self.assertFalse(candidate["formal_done"])
        self.assertEqual(candidate["state"], "needs_independent_collection")
        self.assertEqual(set(candidate["requirement_ids"]), set(self.plan["tasks"]["P2-CORE-002"]["requirement_ids"]))
        unit = "core-exclusion-residual-quality"
        proof = {"base_commit": BASE, "collector_receipt_sha256": "d" * 64,
                 "requirement_proofs": {req: "e" * 64 for req in candidate["requirement_ids"]}}
        self.ledger = append_progress(self.plan, self.ledger, event_id="core002-collected",
            capability_id=unit, event="parent_verified", receipt=proof)
        self.assertNotIn("P2-CORE-002", collector_candidates(self.plan, self.ledger))
        # The metadata receipt does not forge authenticated formal Done.
        self.assertEqual(ready_units(self.plan, self.observation, self.ledger)["waiting"]
                         ["core-shared-two-repair-budget"], "formal_dependencies_incomplete")

    def test_fake_acceptance_and_parent_proof_cannot_unlock_backlog(self):
        with self.assertRaises(BacklogError):
            append_progress(self.plan, [], event_id="fake-accept", capability_id="data-document-store-frozen-snapshot",
                            event="accepted", receipt={"base_commit": BASE})
        self.accept("core-request-reuse-terminal-regression")
        with self.assertRaises(BacklogError):
            append_progress(self.plan, self.ledger, event_id="fake-parent", capability_id="core-request-reuse-terminal-regression",
                event="parent_verified", receipt={"base_commit": BASE, "collector_receipt_sha256": "d" * 64,
                    "requirement_proofs": {req: "e" * 64 for req in self.plan["tasks"]["P2-CORE-002"]["requirement_ids"]}})

    def test_off_unavailable_readiness_and_stale_snapshot_all_wait(self):
        for field, change, reason in (
            ("global_mode", "off", "automation_off"),
            ("main_commit", MERGE, "formal_snapshot_not_current_main")):
            observation = deepcopy(self.observation); observation[field] = change
            result = ready_units(self.plan, observation, [])
            self.assertEqual(result["ready"], [])
            self.assertEqual(set(result["waiting"].values()), {reason})
        self.observation["readiness"]["ginaginaring"]["publisher_separation_verified"] = False
        self.assertEqual(ready_units(self.plan, self.observation, [])["waiting"]
                         ["data-document-store-frozen-snapshot"], "owner_unavailable_or_unverified")

    def test_scope_and_resources_are_locked_across_owners_and_same_tick(self):
        result = ready_units(self.plan, self.observation, [],
            held_paths=["packages/core/src/lgax_core/document_store.py"], held_resources=["web-planning-history"])
        self.assertEqual(result["waiting"]["data-document-store-frozen-snapshot"], "scope_or_resource_conflict")
        self.assertEqual(result["waiting"]["web-concept-text-change-history"], "formal_dependencies_incomplete")
        self.observation["formal_snapshot"]["tasks"]["P2-WEB-002"]["status"] = "done"
        result = ready_units(self.plan, self.observation, [], held_resources=["web-planning-history"])
        self.assertEqual(result["waiting"]["web-concept-text-change-history"], "scope_or_resource_conflict")
        self.assertTrue(paths_overlap("data/demo/*", "data/demo/dataset.json"))
        self.assertFalse(paths_overlap("data/demo/*", "data/demonstration.json"))

    def test_blocked_unit_never_retries_without_new_trusted_recovery_record(self):
        unit = "data-document-store-frozen-snapshot"
        self.ledger = append_progress(self.plan, [], event_id="git128", capability_id=unit, event="blocked",
            receipt={"reason": "actual publisher git128; original attempt preserved", "operator_reference": "PM-receipt"})
        self.assertEqual(ready_units(self.plan, self.observation, self.ledger)["waiting"][unit], "unit_blocked_no_automatic_retry")
        with self.assertRaises(BacklogError):
            append_progress(self.plan, self.ledger, event_id="blind-retry", capability_id=unit, event="released", receipt={"base_commit": BASE})
        self.ledger = append_progress(self.plan, self.ledger, event_id="fixed-publisher", capability_id=unit,
            event="unblocked", receipt={"reason": "minimal fix verified without broad ACL changes", "operator_reference": "actual-diagnostic-receipt"})
        self.assertIn(unit, ready_units(self.plan, self.observation, self.ledger)["ready"])

    def test_existing_active_work_blocks_owner_and_path_while_other_owner_can_progress(self):
        self.observation["jobs"] = [{"owner": "ginaginaring", "status": "running", "capability_id": "data-document-store-frozen-snapshot"}]
        result = ready_units(self.plan, self.observation, [])
        self.assertEqual(result["waiting"]["data-document-store-frozen-snapshot"], "owner_has_active_work")
        self.assertTrue(any(self.plan["capabilities"][key]["owner"] == "unknownamed" for key in result["ready"]))

    def test_append_only_hash_chain_detects_tampering_and_event_replay_is_idempotent(self):
        unit = "data-document-store-frozen-snapshot"
        self.ledger = append_progress(self.plan, [], event_id="release-data", capability_id=unit,
            event="released", receipt={"base_commit": BASE})
        replay = append_progress(self.plan, self.ledger, event_id="release-data", capability_id=unit,
            event="released", receipt={"base_commit": BASE})
        self.assertEqual(replay, self.ledger)
        self.assertIsNot(replay, self.ledger)
        with self.assertRaises(BacklogError):
            append_progress(self.plan, self.ledger, event_id="release-data", capability_id=unit,
                            event="released", receipt={"base_commit": MERGE})
        changed = deepcopy(self.ledger); changed[0]["task_id"] = "P2-PM-003"
        with self.assertRaises(BacklogError): verify_progress(self.plan, changed)
        changed = deepcopy(self.ledger); changed[0]["receipt"]["base_commit"] = MERGE
        with self.assertRaises(BacklogError): verify_progress(self.plan, changed)

    def test_fixed_plan_digest_owner_extensions_protected_paths_and_cycles_are_rejected(self):
        with self.assertRaises(BacklogError): load_backlog(self.path, "0" * 64)
        for mutate in (
            lambda p: p["tasks"]["P2-DATA-001"].update(scope="proposed_extension"),
            lambda p: p["capabilities"]["data-document-store-frozen-snapshot"].update(owner="unknownamed"),
            lambda p: p["capabilities"]["data-document-store-frozen-snapshot"].update(allowed_paths=["harness/phase2/state.json"]),
            lambda p: p["capabilities"]["data-document-store-frozen-snapshot"].update(allowed_paths=["../private/auth.json"]),
            lambda p: p["capabilities"]["core-request-reuse-terminal-regression"].update(depends_on_capabilities=["core-exclusion-residual-quality"]),
            lambda p: p["capabilities"]["data-document-store-frozen-snapshot"].update(expose_independent_answers=True)):
            plan = deepcopy(self.plan); mutate(plan)
            with self.assertRaises(BacklogError): validate_backlog(plan)
        original = deepcopy(self.plan["tasks"])
        original["P2-CORE-002"]["depends_on"] = []
        with self.assertRaises(BacklogError): validate_backlog(self.plan, registered_tasks=original)

    def test_duplicate_json_fields_are_not_silently_reinterpreted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixed.json"; path.write_bytes(b'{"schema_version":1,"schema_version":2}')
            with self.assertRaises(BacklogError): load_backlog(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
