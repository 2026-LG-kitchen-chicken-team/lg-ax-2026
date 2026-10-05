"""Fixed Ready assignment still uses the authenticated, bounded PM broker."""
from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.orchestration import Orchestration
from services.automation.pm import AutonomousPM, PMDriverBusy, PMError
from services.automation.pm_broker import DockerPMDriver, TrustedPMBroker
from services.automation.worker import exclusive_lock
from tests import test_automation_pm as fixture


class FixedOrchestration(SimpleNamespace):
    capabilities = Orchestration.capabilities


class FixedBroker(fixture.Broker):
    allow_fixed_ready_dispatch = TrustedPMBroker.allow_fixed_ready_dispatch
    fixed_ready_assignment = TrustedPMBroker.fixed_ready_assignment
    _released_capabilities = TrustedPMBroker._released_capabilities

    def __init__(self):
        super().__init__()
        self.policy = fixture.policy()
        self.config = {"allow_fixed_ready_dispatch": True, "released_capabilities": [fixture.CAP]}
        self.orchestration = FixedOrchestration(
            plan={"capabilities": deepcopy(self.policy["capabilities"])}, correction_plan=None,
            correction_registry=None, development_registry=None)
        self.collect_calls = []
        self.collection_busy = False

    def observe(self, *, collect=True):
        self.collect_calls.append(collect)
        if collect and self.collection_busy:
            raise PMDriverBusy("independent reviewer has no free profile")
        return super().observe()


class FixedDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.broker = FixedBroker()
        self.clock = 100000
        fixed = fixture.policy()
        self.path = self.root / "policy.json"
        self.path.write_text(json.dumps(fixed), encoding="utf-8")
        self.policy_digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.calls = []
        self.pm = AutonomousPM(policy_path=self.path, policy_sha256=self.policy_digest,
            journal_path=self.root / "pm.sqlite3", broker=self.broker, decide=self.driver, clock=lambda: self.clock)

    def driver(self, *_args):
        self.calls.append(True)
        return {"decision": fixture.decision("wait"), "usage": {"input_tokens": 5, "output_tokens": 2}}

    def budgets(self):
        day = "day:" + time.strftime("%Y-%m-%d", time.gmtime(self.clock))
        with self.pm.journal.connect() as db:
            return self.pm.journal.budget(db, day), self.pm.journal.budget(db, "task:" + fixture.TASK)

    def test_real_busy_profile_assigns_without_model_or_review_collection_and_accounts_actions_only(self):
        profile = self.root / "profile"
        profile.mkdir()
        executor = SimpleNamespace(config=SimpleNamespace(auth_root=profile))
        self.pm.decide = DockerPMDriver(executor, state_dir=self.root / "driver", heartbeat=lambda: True)
        self.broker.collection_busy = True
        with exclusive_lock(profile / "lgax-worker.lock"):
            result = self.pm.tick()
        self.assertEqual(result["state"], "applied")
        self.assertFalse(result["model_called"])
        self.assertEqual(result["source"], "fixed_released_backlog")
        self.assertEqual(self.broker.collect_calls, [False, False])
        daily, task = self.budgets()
        self.assertEqual(daily, {"model_calls": 0, "actions": 1, "revisions": 0, "tokens": 0})
        self.assertEqual(task, daily)
        self.assertEqual(self.broker.state["formal_snapshot"]["tasks"][fixture.TASK]["status"], "blocked")
        action = self.broker.actions[0][1]
        self.assertEqual(action["allowed_paths"], self.pm.policy["capabilities"][fixture.CAP]["allowed_paths"])
        self.assertEqual(action["acceptance"], self.pm.policy["capabilities"][fixture.CAP]["acceptance"])
        with self.pm.journal.connect() as db:
            payload = json.loads(db.execute("SELECT payload FROM journal WHERE event='fixed_assignment'").fetchone()[0])
            self.assertEqual(payload["usage"], {"input_tokens": 0, "output_tokens": 0})
            self.assertEqual(payload["source"], "fixed_released_backlog")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM journal WHERE event='decision_started'").fetchone()[0], 0)
        self.pm.journal.verify()

    def test_unchanged_fixed_assignment_is_not_reposted(self):
        self.assertEqual(self.pm.tick()["state"], "applied")
        self.assertEqual(self.pm.tick()["state"], "unchanged")
        self.assertEqual(len(self.broker.actions), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.budgets()[0]["actions"], 1)

    def test_flag_missing_or_false_preserves_model_planning(self):
        for value in (None, False):
            with self.subTest(value=value):
                self.broker.config.pop("allow_fixed_ready_dispatch", None)
                if value is not None:
                    self.broker.config["allow_fixed_ready_dispatch"] = value
                self.broker.state["operator_resume_nonce"] = str(value)
                result = self.pm.tick()
                self.assertEqual(result["state"], "wait")
                self.assertTrue(result["model_called"])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(self.broker.collect_calls))

    def test_truthy_non_boolean_host_flag_is_rejected(self):
        for value in ("true", 1, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(PMError, "host boolean"):
                TrustedPMBroker({"allow_fixed_ready_dispatch": value})

    def test_release_scope_and_completion_cannot_be_expanded_by_ready_metadata(self):
        self.broker.config.pop("released_capabilities")
        self.assertIsNone(self.broker.fixed_ready_assignment(self.broker.state))
        self.broker.config["released_capabilities"] = []
        self.assertIsNone(self.broker.fixed_ready_assignment(self.broker.state))
        self.broker.config["released_capabilities"] = [fixture.CAP]
        self.broker.state["capabilities_ready"] = ["new-unregistered-task"]
        self.assertIsNone(self.broker.fixed_ready_assignment(self.broker.state))
        self.broker.state["capabilities_ready"] = [fixture.CAP]
        self.broker.policy["capabilities"][fixture.CAP]["completes_task"] = True
        self.assertIsNone(self.broker.fixed_ready_assignment(self.broker.state))
        self.assertEqual(self.broker.actions, [])

    def test_fixed_dispatch_requires_verified_pinned_backlog_not_policy_alone(self):
        self.broker.orchestration.plan = None
        self.assertIsNone(self.broker.fixed_ready_assignment(self.broker.state))
        self.assertTrue(self.pm.tick()["model_called"])
        self.assertEqual(self.broker.actions, [])

    def test_fixed_selector_cannot_request_merge_instead_of_assignment(self):
        with patch.object(self.broker, "fixed_ready_assignment", return_value=fixture.decision("merge")):
            result = self.pm.tick()
        self.assertEqual(result["state"], "halted")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])

    def test_off_or_unready_worker_never_dispatches(self):
        self.broker.state["global_mode"] = "off"
        self.assertEqual(self.pm.tick()["state"], "off")
        self.broker.state["global_mode"] = "on"
        self.broker.state["readiness"][fixture.PM]["login_verified"] = False
        self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])

    def test_changed_main_or_revoked_flag_is_rejected_before_intent(self):
        original = self.broker.observe
        for change in ("main", "flag"):
            with self.subTest(change=change):
                self.broker.config["allow_fixed_ready_dispatch"] = True
                self.broker.state["main_commit"] = fixture.BASE
                self.broker.state["operator_resume_nonce"] = change
                observed = 0
                def race(*, collect=True, change=change):
                    nonlocal observed
                    observed += 1
                    if observed == 2:
                        if change == "main":
                            self.broker.state["main_commit"] = fixture.MERGED
                        else:
                            self.broker.config["allow_fixed_ready_dispatch"] = False
                    return original(collect=collect)
                with patch.object(self.broker, "observe", side_effect=race):
                    result = self.pm.tick()
                self.assertEqual(result["state"], "stale")
                self.assertFalse(result["model_called"])
        self.assertEqual(self.broker.actions, [])
        self.assertEqual(self.budgets()[0]["actions"], 0)

    def test_new_ready_unit_with_active_same_unit_is_rejected(self):
        self.broker.state["jobs"] = [{"job_id": "already-running", "task_id": fixture.TASK,
                                      "capability_id": fixture.CAP, "status": "running"}]
        self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.broker.actions, [])
        self.assertEqual(self.calls, [])

    def test_fresh_ci_or_lock_change_remains_stale_before_mutation(self):
        original = self.broker.observe
        for change in ("ci", "lock"):
            with self.subTest(change=change):
                self.broker.state = fixture.observation()
                self.broker.state["operator_resume_nonce"] = change
                observed = 0
                def race(*, collect=True, change=change):
                    nonlocal observed
                    observed += 1
                    if observed == 2:
                        if change == "ci":
                            self.broker.state["prs"][0]["ci"][0]["status"] = "FAILURE"
                        else:
                            self.broker.state["jobs"] = [{"job_id": "new-lock", "owner": fixture.PM, "status": "running"}]
                    return original(collect=collect)
                with patch.object(self.broker, "observe", side_effect=race):
                    self.assertEqual(self.pm.tick()["state"], "stale")
        self.assertEqual(self.broker.actions, [])
        self.assertEqual(self.calls, [])

    def test_worker_identity_is_not_pm_authority_at_fresh_mutation_boundary(self):
        original = self.broker.observe
        def revoke(*, collect=True):
            value = original(collect=collect)
            self.broker.identity["operator"] = False
            return value
        with patch.object(self.broker, "observe", side_effect=revoke):
            self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.broker.actions, [])
        self.assertEqual(self.calls, [])

    def test_unknown_mutation_stays_pending_without_model_or_blind_retry(self):
        self.broker.unknown, self.broker.error = True, True
        first = self.pm.tick()
        self.assertEqual(first["state"], "reconciliation_required")
        self.assertFalse(first["model_called"])
        second = self.pm.tick()
        self.assertEqual(second["state"], "reconciliation_required")
        self.assertEqual(first["action_id"], second["action_id"])
        self.assertEqual(len(self.broker.actions), 1)
        self.assertEqual(self.budgets()[0]["actions"], 1)
        self.assertEqual(self.calls, [])

    def test_existing_usage_is_preserved_and_action_limits_still_halt(self):
        day = "day:" + time.strftime("%Y-%m-%d", time.gmtime(self.clock))
        with self.pm.journal.connect() as db:
            self.pm.journal.budget(db, day)
            db.execute("UPDATE budgets SET model_calls=3,tokens=50 WHERE scope=?", (day,))
        self.assertEqual(self.pm.tick()["state"], "applied")
        self.assertEqual(self.budgets()[0], {"model_calls": 3, "tokens": 50, "actions": 1, "revisions": 0})
        self.broker.state["operator_resume_nonce"] = "budget-full"
        with self.pm.journal.connect() as db:
            db.execute("UPDATE budgets SET actions=? WHERE scope=?", (self.pm.policy["limits"]["max_actions_per_day"], day))
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")
        self.assertEqual(self.budgets()[0]["tokens"], 50)
        self.assertEqual(len(self.broker.actions), 1)
        self.assertEqual(self.calls, [])

    def test_no_ready_unit_keeps_independent_collection_and_model_path(self):
        self.broker.state["capabilities_ready"] = []
        self.assertTrue(self.pm.tick()["model_called"])
        self.assertEqual(self.broker.collect_calls, [False, True])
        self.assertEqual(self.calls, [True])
        self.assertEqual(self.broker.actions, [])
