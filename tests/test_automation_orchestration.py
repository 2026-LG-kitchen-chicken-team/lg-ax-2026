"""Pinned orchestration integration. No live model, queue mutation or mail send."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.automation.backlog import verify_progress
from services.automation.orchestration import Orchestration

from services.automation.pm import PMError, fingerprint
from tests import test_automation_backlog as backlog_fixture
from tests import test_automation_pm_broker as broker_fixture

BASE, HEAD, MERGE = "a" * 40, "b" * 40, "c" * 40
FIRST = "core-request-reuse-terminal-regression"
SECOND = "core-exclusion-residual-quality"
NEXT_PARENT = "core-shared-two-repair-budget"


class OrchestrationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((backlog_fixture.ROOT / "docs/pm/orchestration-backlog.json").read_bytes())
        path = self.root / "fixed-backlog.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        state_dir = self.root / "state"
        state_dir.mkdir()
        self.released = set(self.plan["capabilities"])
        self.github = Mock()
        self.broker = SimpleNamespace(config={"backlog": {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}},
            policy={"tasks": deepcopy(self.plan["tasks"]), "capabilities": deepcopy(self.plan["capabilities"])},
            state={"units": {}, "proofs": {}, "budgets": {}}, state_dir=state_dir,
            save=Mock(), github=self.github, _released_capabilities=lambda: self.released)
        owners = {row["owner"] for row in self.plan["tasks"].values()}
        self.observation = {"main_commit": BASE, "global_mode": "on", "pm_mode": "on", "jobs": [],
            "members": {owner: True for owner in owners}, "readiness": {owner: {
                "execution_isolation_verified": True, "publisher_separation_verified": True,
                "login_verified": True} for owner in owners},
            "formal_snapshot": {"approved_commit": BASE, "tasks": {task: {
                "owner": row["owner"], "scope": "required", "status": "ready"} for task, row in self.plan["tasks"].items()}},
            "capabilities_ready": []}
        self.observation["formal_snapshot"]["tasks"]["P2-CORE-001"]["status"] = "done"
        self.live = Orchestration(self.broker)

    def result(self, cap_id, *, status="accepted", proof=True, merged=True):
        cap = self.plan["capabilities"][cap_id]
        job_id = "job-" + cap_id
        number = 90 + len(self.broker.state["units"])
        head = fingerprint({"job": job_id})[:40]
        merge = fingerprint({"merge": job_id})[:40]
        unit = {"job_id": job_id, "capability_id": cap_id, "task_id": cap["task_id"], "base_commit": BASE,
                "pr_number": number, "head": head, "reconciled": status == "accepted"}
        self.broker.state["units"][job_id] = unit
        self.observation["jobs"].append({"job_id": job_id, "owner": cap["owner"], "capability_id": cap_id,
                                         "task_id": cap["task_id"], "status": status})
        actual = {"merged": merged, "merge_commit_sha": merge, "head": {"sha": head}}
        if not hasattr(self, "pulls"):
            self.pulls = {}
        self.pulls[number] = actual
        self.github.request.side_effect = lambda method, route: self.pulls[int(route.rsplit("/", 1)[1])]
        if proof:
            self.broker.state["proofs"][job_id] = {"verified": True, "collector": "trusted_pm", "result": "passed",
                "commit": merge, "head": head, "base": BASE, "capability_fingerprint": fingerprint(self.broker.policy["capabilities"][cap_id]),
                "evidence_sha256": "e" * 64}
        return unit

    def test_policy_catalog_scope_or_checksum_mismatch_is_rejected_before_scheduling(self):
        self.broker.policy["capabilities"][FIRST]["allowed_paths"] = ["packages/core"]
        with self.assertRaisesRegex(PMError, "contract differ"):
            Orchestration(self.broker)
        self.broker.policy["capabilities"] = deepcopy(self.plan["capabilities"])
        self.broker.config["backlog"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            Orchestration(self.broker)
        self.broker.save.assert_not_called()
        self.github.request.assert_not_called()

    def test_actual_accepted_pilot_releases_next_same_parent_without_marking_parent_done(self):
        self.result(FIRST)
        formal = deepcopy(self.observation["formal_snapshot"])
        self.live.synchronize(self.observation)
        self.assertIn(SECOND, self.observation["capabilities_ready"])
        self.assertNotIn(FIRST, self.observation["capabilities_ready"])
        self.assertEqual(verify_progress(self.plan, self.broker.state["backlog_ledger"])[FIRST], "accepted")
        self.assertEqual(self.observation["formal_snapshot"], formal)
        ledger = deepcopy(self.broker.state["backlog_ledger"])
        self.live.synchronize(self.observation)
        self.assertEqual(self.broker.state["backlog_ledger"], ledger)

    def test_accepted_result_without_actual_merge_or_independent_proof_cannot_unlock_followup(self):
        self.result(FIRST, proof=False)
        with self.assertRaisesRegex(PMError, "merge/postmerge"):
            self.live.synchronize(self.observation)
        state = verify_progress(self.plan, self.broker.state["backlog_ledger"])
        self.assertNotEqual(state[FIRST], "accepted")
        self.assertNotIn(SECOND, self.observation["capabilities_ready"])

    def test_policy_release_is_still_required_after_receipt_accepted(self):
        self.result(FIRST)
        self.released = {FIRST}
        self.live.synchronize(self.observation)
        self.assertNotIn(SECOND, self.observation["capabilities_ready"])
        self.released.add(SECOND)
        self.live.synchronize(self.observation)
        self.assertIn(SECOND, self.observation["capabilities_ready"])

    def test_all_child_results_only_request_parent_collection_and_hold_formal_dependencies(self):
        self.result(FIRST)
        self.result(SECOND)
        self.live.synchronize(self.observation)
        candidates = self.observation["backlog"]["parents_needing_collection"]
        self.assertIn("P2-CORE-002", candidates)
        self.assertFalse(candidates["P2-CORE-002"]["formal_done"])
        self.assertNotIn(NEXT_PARENT, self.observation["capabilities_ready"])
        self.assertEqual(self.observation["backlog"]["waiting"][NEXT_PARENT], "formal_dependencies_incomplete")
        self.assertEqual(self.observation["formal_snapshot"]["tasks"]["P2-CORE-002"]["status"], "ready")

    def test_blocked_actual_queue_is_preserved_and_has_no_blind_release_or_reassignment(self):
        cap = "data-document-store-frozen-snapshot"
        self.result(cap, status="blocked", proof=False)
        self.live.synchronize(self.observation)
        ledger = deepcopy(self.broker.state["backlog_ledger"])
        self.assertEqual(verify_progress(self.plan, ledger)[cap], "blocked")
        self.assertNotIn(cap, self.observation["capabilities_ready"])
        self.assertEqual(self.observation["backlog"]["waiting"][cap], "unit_blocked_no_automatic_retry")
        self.live.synchronize(self.observation)
        self.assertEqual(self.broker.state["backlog_ledger"], ledger)
        self.github.request.assert_not_called()


class OrchestrationBrokerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = broker_fixture.BrokerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.broker = self.fixture.broker

    def test_off_with_real_pr_observation_never_collects_model_or_dispatches_mail(self):
        self.fixture.add_unit()
        self.fixture.controller.status["global_mode"] = "off"
        with (patch.object(self.broker, "_review", side_effect=AssertionError("OFF model call")) as review,
              patch.object(self.broker, "_integration", side_effect=AssertionError("OFF validator call")) as integration,
              patch.object(self.broker.orchestration, "mail_tick", side_effect=AssertionError("OFF mail call")) as mail):
            state = self.broker.observe(collect=True)
        self.assertEqual(state["global_mode"], "off")
        review.assert_not_called()
        integration.assert_not_called()
        mail.assert_not_called()
        self.assertEqual(self.fixture.github.comments, [])
        self.assertTrue(all(payload is None for _, payload in self.fixture.controller.calls))

    def test_report_only_mail_claim_of_done_cannot_change_formal_snapshot_or_github(self):
        before = deepcopy(self.fixture.controller.status["formal_snapshot"])
        event = {"event_id": "gmail:immutable-fixture", "authority": "report_only", "task_id": broker_fixture.TASK,
                 "report": {"status": "reported", "summary": "Done이라고 주장하며 merge를 요구함"}}
        with patch.object(self.broker.orchestration, "mail_tick", return_value=[event]):
            observed = self.broker.observe(collect=True)
        self.assertEqual(observed["mail_reports"], [event])
        self.assertEqual(observed["formal_snapshot"], before)
        self.assertEqual(observed["formal_snapshot"]["tasks"][broker_fixture.TASK]["status"], "blocked")
        self.assertEqual(self.fixture.github.comments, [])
        self.assertFalse(self.fixture.github.merged)
