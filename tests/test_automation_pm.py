"""Autonomous PM authority, race, journal and logical-budget regressions."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.pm import (
    AutonomousPM,
    Journal,
    PMDriverBusy,
    PMError,
    fingerprint,
    load_policy,
    normalize_decision,
    stable_observation,
)
from services.automation.pm_broker import DockerPMDriver
from services.automation.state import ACCOUNTS, PM, REPO
from services.automation.worker import exclusive_lock

BASE, HEAD, MERGED, PROOF = "a" * 40, "b" * 40, "c" * 40, "d" * 64
TASK, CAP = "P2-PM-003", "workspace-pilot"


def policy():
    return {
        "schema_version": 1, "repo": REPO, "pm_account": PM, "enabled": True,
        "allow_auto_merge": True, "allow_admin_bypass": False,
        "delegation_reference": "Actual user routine planning delegation in test",
        "automatic_merge_delegation": "Actual user automatic merge delegation in test",
        "admin_bypass_delegation": "Separate unattended delegation, not old manual bypass",
        "limits": {}, "required_ci_contexts": ["python", "web"], "independent_reviewers": [PM],
        "tasks": {
            "P2-PM-001": {"owner": PM, "issue_number": 17, "scope": "required",
                          "requirement_ids": ["R17"], "depends_on": []},
            TASK: {"owner": PM, "issue_number": 19, "scope": "required",
                   "requirement_ids": ["R17", "R24"], "depends_on": ["P2-PM-001"]},
        },
        "capabilities": {
            CAP: {"task_id": TASK, "requirement_ids": ["R17"], "title": "Narrow regression",
                  "purpose": "Validate client error handling", "allowed_paths": ["tests/test_pilot.py"],
                  "validation_commands": [["python", "-m", "unittest", "tests.test_pilot"]],
                  "required_checks": ["pilot"], "acceptance": ["Actual behavior regresses correctly"],
                  "shared_resources": [], "timeout_seconds": 1800, "priority": 50},
        },
    }


def observation():
    fixed = policy()
    tasks = {key: {**value, "status": "done" if key == "P2-PM-001" else "blocked"}
             for key, value in fixed["tasks"].items()}
    proof = {"verified": True, "collector": "trusted_pm", "head": HEAD, "base": BASE,
             "evidence_sha256": PROOF, "checks": ["pilot"], "result": "passed"}
    return {
        "repo": REPO, "main_commit": BASE, "global_mode": "on", "pm_mode": "on",
        "members": {account: account == PM for account in ACCOUNTS},
        "formal_snapshot": {"approved_commit": BASE, "tasks": tasks},
        "capabilities_ready": [CAP], "jobs": [],
        "readiness": {PM: {"execution_isolation_verified": True,
                           "publisher_separation_verified": True, "login_verified": True}},
        "prs": [{"number": 81, "task_id": TASK, "author": PM, "head": HEAD, "base": BASE,
                 "state": "open", "draft": False, "base_ref": "main", "base_repo": REPO, "head_repo": REPO,
                 "mergeable": True, "changed_paths": ["tests/test_pilot.py"],
                 "ci": [{"context": context, "head": HEAD, "status": "SUCCESS"} for context in ("python", "web")],
                 "independent_review": {"verified": True, "collector": "trusted_pm", "head": HEAD,
                                        "base": BASE, "evidence_sha256": PROOF, "reviewer": PM,
                                        "independent": True, "reviewer_session_id": "fresh-review-session",
                                        "implementation_session_id": "worker-implementation-session",
                                        "outcome": "approve", "findings": []},
                 "integration": proof}],
    }


def decision(kind="assign", **updates):
    value = {"action": kind, "task_id": TASK, "capability_id": CAP,
             "pr_number": 81 if kind in {"merge", "request_changes", "reconcile"} else None,
             "head_commit": HEAD if kind in {"merge", "request_changes", "reconcile"} else None,
             "reason": "Current required acceptance unit", "instructions": ["Implement bounded client test"]
             if kind in {"assign", "request_changes"} else []}
    if kind in {"wait", "escalate"}:
        value.update(capability_id=None)
    value.update(updates)
    return value


class Broker:
    def __init__(self):
        self.state = observation()
        self.identity = {"account": PM, "operator": True}
        self.actions, self.receipts = [], {}
        self.error = False
        self.unknown = False

    def authenticate(self):
        return deepcopy(self.identity)

    def observe(self):
        return deepcopy(self.state)

    def execute(self, action_id, action, expected_fingerprint):
        if fingerprint(stable_observation(self.state)) != expected_fingerprint:
            raise PMError("changed during broker mutation")
        self.actions.append((action_id, deepcopy(action)))
        receipt = {"action_id": action_id, "action": action["action"],
                   "outcome": "unknown" if self.unknown else "applied", "evidence_sha256": PROOF}
        if action["action"] == "merge":
            receipt["merge_commit"] = MERGED
        self.receipts[action_id] = deepcopy(receipt)
        if self.error:
            raise TimeoutError("private network body should never leak")
        return receipt

    def lookup(self, action_id):
        return deepcopy(self.receipts.get(action_id))


class AutonomousPMTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path, self.database = self.root / "policy.json", self.root / "pm.sqlite3"
        self.broker = Broker()
        self.calls = []
        self.response = decision()
        self.usage = {"input_tokens": 50, "output_tokens": 10}
        self.clock_value = 100000
        self.fixed = policy()
        self.pm = self.make_pm()

    def tearDown(self):
        self.temp.cleanup()

    def make_pm(self):
        self.path.write_text(json.dumps(self.fixed), encoding="utf-8")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        return AutonomousPM(policy_path=self.path, policy_sha256=digest, journal_path=self.database,
                            broker=self.broker, decide=self.driver, clock=lambda: self.clock_value)

    def driver(self, context, schema, timeout):
        self.calls.append((deepcopy(context), schema, timeout))
        return {"decision": deepcopy(self.response), "usage": deepcopy(self.usage)}

    def profile_driver(self):
        profile = self.root / "profile"
        profile.mkdir()
        executor = SimpleNamespace(config=SimpleNamespace(auth_root=profile))
        return DockerPMDriver(executor, state_dir=self.root / "driver-state", heartbeat=lambda: True)

    def test_publication_pending_is_owned_by_resumer_and_does_not_enter_pm_marker_lookup(self):
        publication_id = "publication-" + "f" * 64
        ordinary_id = "pm-" + "e" * 40
        with self.pm.journal.connect() as db:
            for action_id, kind, body in (
                    (publication_id, "parent_publication", {"operation": "project", "task_id": TASK}),
                    (ordinary_id, "assign", decision())):
                db.execute("INSERT INTO actions VALUES(?,?,?,'intent',?,NULL)",
                           (action_id, TASK, kind, json.dumps(body)))
            self.pm.journal.append(db, "fixture_mixed_pending", {"ordinary": ordinary_id, "publication": publication_id})
        self.assertEqual([row["action_id"] for row in self.pm.journal.pending()], [ordinary_id])
        self.broker.receipts[ordinary_id] = {"action_id": ordinary_id, "action": "assign",
                                            "outcome": "applied", "evidence_sha256": PROOF}
        self.broker.state["parent_completion"] = {"must_reobserve": True, "main_commit": MERGED}
        # A real PM marker lookup rejects publication-* IDs. This fake mirrors
        # that boundary so the integration must route them to observation's
        # dedicated fixed publisher instead of silently treating all as known.
        original_lookup = self.broker.lookup
        looked_up = []
        def fixed_lookup(action_id):
            looked_up.append(action_id)
            if action_id.startswith("publication-"):
                raise PMError("not a PM marker")
            return original_lookup(action_id)
        with patch.object(self.broker, "lookup", side_effect=fixed_lookup), \
                patch.object(self.broker, "observe", wraps=self.broker.observe) as observed:
            result = self.pm.tick()
        self.assertEqual(result["state"], "reobserve_after_publication")
        self.assertEqual(looked_up, [ordinary_id])
        self.assertEqual(observed.call_count, 1, "publisher resumption must be reachable")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])
        with self.pm.journal.connect() as db:
            self.assertEqual(db.execute("SELECT state FROM actions WHERE action_id=?", (ordinary_id,)).fetchone()[0], "applied")
            self.assertEqual(db.execute("SELECT state FROM actions WHERE action_id=?", (publication_id,)).fetchone()[0], "intent")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 0)
        self.pm.journal.verify()

    def test_publication_recovery_filter_does_not_bypass_unknown_ordinary_mutation(self):
        publication_id = "publication-" + "f" * 64
        ordinary_id = "pm-" + "e" * 40
        with self.pm.journal.connect() as db:
            for action_id, kind in ((publication_id, "parent_publication"), (ordinary_id, "assign")):
                db.execute("INSERT INTO actions VALUES(?,?,?,'intent',?,NULL)",
                           (action_id, TASK, kind, json.dumps({"task_id": TASK})))
        with patch.object(self.broker, "observe", side_effect=AssertionError("ordinary unknown must stop observation")):
            result = self.pm.tick()
        self.assertEqual(result["state"], "reconciliation_required")
        self.assertEqual(result["action_id"], ordinary_id)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])

    def test_changed_parent_publication_observation_spends_no_model_or_action_and_resumes_fresh(self):
        for parent_result in ({"main_commit": MERGED}, {"main_commit": BASE, "must_reobserve": True}):
            with self.subTest(parent_result=parent_result):
                self.broker.state["parent_completion"] = parent_result
                result = self.pm.tick()
                self.assertEqual(result["state"], "reobserve_after_publication")
                self.assertFalse(result["model_called"])
                self.assertFalse(result["mutated"])
                self.assertEqual(self.calls, [])
                self.assertEqual(self.broker.actions, [])
                with self.pm.journal.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 0)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM budgets").fetchone()[0], 0)
        # The next current observation can progress with the same logical task;
        # no fingerprint, budget or failure counter reset is required.
        self.broker.state.update(main_commit=MERGED, parent_completion={"main_commit": MERGED})
        self.broker.state["formal_snapshot"]["approved_commit"] = MERGED
        self.response = decision("wait", task_id=None)
        self.assertEqual(self.pm.tick()["state"], "wait")
        self.assertEqual(len(self.calls), 1)

    def test_worker_profile_contention_does_not_charge_or_poison_same_event(self):
        driver = self.profile_driver()
        self.pm.decide = driver
        proof = {"result": decision(), "usage": deepcopy(self.usage)}
        with patch.object(driver, "_call", return_value=proof) as model:
            with exclusive_lock(driver.executor.config.auth_root / "lgax-worker.lock"):
                for _ in range(3):
                    result = self.pm.tick()
                    self.assertEqual(result["state"], "wait")
                    self.assertFalse(result["model_called"])
                    self.assertFalse(result["mutated"])
                self.assertEqual(model.call_count, 0)
                with self.pm.journal.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 0)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 0)
                    self.assertEqual(db.execute("SELECT SUM(model_calls+tokens+actions) FROM budgets").fetchone()[0], 0)
                    self.assertIsNone(db.execute("SELECT value FROM metadata WHERE key='driver_failures'").fetchone())
            # Release alone suffices: no new fingerprint, nonce or quota reset.
            self.assertEqual(self.pm.tick()["state"], "applied")
            self.assertEqual(model.call_count, 1)
            self.assertEqual(self.pm.tick()["state"], "unchanged")
            self.assertEqual(model.call_count, 1)

    def test_profile_reservation_spans_journal_start_and_model_call(self):
        driver = self.profile_driver()
        self.pm.decide = driver
        def model(*_args, **_kwargs):
            with self.pm.journal.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM seen WHERE state='decision_started'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT SUM(model_calls) FROM budgets").fetchone()[0], 1)
            with self.assertRaises(OSError), exclusive_lock(driver.executor.config.auth_root / "lgax-worker.lock"):
                self.fail("journal reservation released the profile before the call")
            return {"result": decision(), "usage": deepcopy(self.usage)}
        with patch.object(driver, "_call", side_effect=model):
            self.assertEqual(self.pm.tick()["state"], "applied")
        with exclusive_lock(driver.executor.config.auth_root / "lgax-worker.lock"):
            pass

    def test_failure_after_model_reservation_keeps_unknown_usage_fail_closed(self):
        for failure in (OSError("fixture I/O failure after execution"), PMDriverBusy("not a pre-call acquisition")):
            with self.subTest(error=type(failure).__name__):
                driver = self.profile_driver()
                self.pm.decide = driver
                with patch.object(driver, "_call", side_effect=failure) as model:
                    result = self.pm.tick()
                self.assertEqual(result["state"], "decision_rejected")
                self.assertTrue(result["model_called"])
                self.assertEqual(model.call_count, 1)
                with self.pm.journal.connect() as db:
                    budget = db.execute("SELECT model_calls,tokens FROM budgets WHERE scope LIKE 'day:%'").fetchone()
                    self.assertEqual(budget, (1, self.pm.policy["limits"]["max_model_tokens_per_day"]))
                    self.assertEqual(db.execute("SELECT state FROM seen").fetchone()[0], "rejected")
                    self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='driver_failures'").fetchone()[0], "1")
                # Fresh independent test state; no operational ledger is touched.
                self.temp.cleanup()
                self.setUp()

    def test_off_does_not_call_model_or_mutate(self):
        for key, value in (("global_mode", "off"), ("global_mode", "stop"), ("pm_mode", "off")):
            with self.subTest(key=key, value=value):
                self.broker.state = observation()
                self.broker.state[key] = value
                self.assertEqual(self.pm.tick()["state"], "off")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])

    def test_assignment_uses_only_fixed_paths_tests_acceptance(self):
        result = self.pm.tick()
        self.assertEqual(result["state"], "applied")
        action = self.broker.actions[0][1]
        self.assertEqual(action["allowed_paths"], ["tests/test_pilot.py"])
        self.assertEqual(action["validation_commands"], [["python", "-m", "unittest", "tests.test_pilot"]])
        self.assertEqual(action["formal_task_dependencies"], ["P2-PM-001"])
        self.assertEqual(action["max_attempts"], 2)
        self.assertFalse(action["allow_admin_bypass"])

    def test_metadata_context_does_not_expose_routes_paths_or_commands(self):
        self.broker.state.update(github_token="secret", controller_token_file="private/token")
        self.pm.tick()
        context = self.calls[0][0]
        self.assertNotIn("github_token", context)
        self.assertNotIn("controller_token_file", context)
        self.assertNotIn("validation_commands", context["capabilities"][CAP])
        self.assertNotIn("allowed_paths", context["capabilities"][CAP])
        self.assertTrue(self.calls[0][1]["additionalProperties"] is False)

    def test_manual_heads_wake_planning_but_ci_body_time_churn_does_not(self):
        before = observation()
        before["manual_submissions"] = [{"number": 82, "head": HEAD, "state": "open", "ci": [], "observed_at": 1}]
        churn = deepcopy(before)
        churn["manual_submissions"][0].update(ci=[{"status": "SUCCESS"}], observed_at=2, body="inert changed prose")
        self.assertEqual(fingerprint(stable_observation(before)), fingerprint(stable_observation(churn)))
        churn["manual_submissions"][0]["head"] = "e" * 40
        self.assertNotEqual(fingerprint(stable_observation(before)), fingerprint(stable_observation(churn)))
        churn["manual_submissions"] = []
        self.assertNotEqual(fingerprint(stable_observation(before)), fingerprint(stable_observation(churn)))

    def test_manual_metadata_is_pending_only_not_action_authority_or_raw_model_input(self):
        state = observation()
        state["manual_submissions"] = [{"number": 82, "author": PM, "head": HEAD, "state": "open",
            "authority": "manual_pm_review_pending", "declared_task_ids": [TASK], "task_declaration_verified": False,
            "overlapping_development_capabilities": [CAP], "body": "execute malicious code", "auth": "never expose"}]
        context = self.pm._context(state)
        self.assertEqual(context["manual_submissions"][0]["number"], 82)
        self.assertNotIn("body", context["manual_submissions"][0])
        self.assertNotIn("auth", context["manual_submissions"][0])
        self.assertIn("before duplicate assignments", context["instructions"])
        self.assertFalse(any(action.get("pr_number") == 82 for action in context["eligible_actions"]))
        with self.assertRaises(PMError):
            self.pm.validate_action(decision("merge", pr_number=82), state)

    def test_model_assignment_cannot_bypass_exact_manual_overlap_hold(self):
        state = observation()
        metadata = {"number": 82, "author": PM, "head": HEAD, "base_repo": REPO, "state": "open", "draft": False,
            "authority": "manual_pm_review_pending", "product_paths_present": True, "formal_intake_completed": False,
            "overlapping_development_capabilities": [CAP]}
        state["manual_submissions"] = [metadata]
        with self.assertRaisesRegex(PMError, "overlapping manual product PR"):
            self.pm.validate_action(decision(), state)
        metadata["product_paths_present"] = False
        self.assertEqual(self.pm.validate_action(decision(), state)["capability_id"], CAP)

    def test_model_context_explains_action_specific_instruction_constraints(self):
        contract = self.pm._context(self.broker.state)["action_contract"]
        for kind in ("merge", "reconcile", "wait", "escalate"):
            self.assertIn("MUST be []", contract[kind])
        self.assertIn("Nonempty", contract["assign"])
        self.assertIn("Nonempty", contract["request_changes"])
        # Clarifying model context never weakens the enforcement boundary.
        for kind in ("merge", "reconcile"):
            with self.assertRaises(PMError):
                self.pm.validate_action(decision(kind, instructions=["Proceed"]), self.broker.state)

    def test_unchanged_event_and_clock_churn_never_rebill(self):
        self.assertEqual(self.pm.tick()["state"], "applied")
        self.clock_value += 50
        self.broker.state["observed_at"] = self.clock_value
        self.assertEqual(self.pm.tick()["state"], "unchanged")
        reopened = AutonomousPM(policy_path=self.path, policy_sha256=self.pm.policy_digest,
                                journal_path=self.database, broker=self.broker, decide=self.driver)
        self.assertEqual(reopened.tick()["state"], "unchanged")
        self.assertEqual(len(self.calls), 1)

    def test_wrong_pm_or_worker_credentials_fail_closed(self):
        self.broker.identity["operator"] = False
        self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.calls, [])

    def test_new_policy_digest_cannot_silently_reuse_journal(self):
        self.fixed["limits"]["max_actions_per_day"] = 5
        with self.assertRaises(PMError):
            self.make_pm()

    def test_source_controlled_policy_and_journal_forbidden(self):
        (self.root / ".git").mkdir()
        with self.assertRaises(PMError):
            load_policy(self.path, self.pm.policy_digest)

    def test_live_policy_change_stops_before_model(self):
        self.path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.calls, [])

    def test_dependent_task_cannot_invent_dependencies_or_features(self):
        self.broker.state["formal_snapshot"]["tasks"]["P2-PM-001"]["status"] = "blocked"
        with self.assertRaises(PMError):
            self.pm.validate_action(decision(), self.broker.state)
        self.response["task_id"] = "made-up-work"
        self.assertEqual(self.pm.tick()["state"], "decision_rejected")
        self.assertEqual(self.broker.actions, [])

    def test_assignment_requires_released_unit_and_true_isolation(self):
        for key in ("execution_isolation_verified", "publisher_separation_verified", "login_verified"):
            state = observation()
            state["readiness"][PM][key] = False
            with self.subTest(key=key), self.assertRaises(PMError):
                self.pm.validate_action(decision(), state)
        state = observation()
        state["capabilities_ready"] = []
        with self.assertRaises(PMError):
            self.pm.validate_action(decision(), state)

    def test_active_unit_cannot_be_double_dispatched(self):
        for status in ("pending", "running", "stopping", "orphaned", "review_requested"):
            self.broker.state["jobs"] = [{"task_id": TASK, "capability_id": CAP, "status": status}]
            with self.subTest(status=status), self.assertRaises(PMError):
                self.pm.validate_action(decision(), self.broker.state)

    def test_model_cannot_choose_paths_commands_or_new_fields(self):
        raw = decision()
        raw["validation_commands"] = [["gh", "api", "user"]]
        with self.assertRaises(PMError):
            normalize_decision(raw)
        with self.assertRaises(PMError):
            normalize_decision(decision(reason="Token ghp_" + "a" * 25))

    def test_wait_is_inert_and_not_repeated_unchanged(self):
        self.response = decision("wait", task_id=None)
        self.assertEqual(self.pm.tick()["state"], "wait")
        self.assertEqual(self.pm.tick()["state"], "unchanged")
        self.assertEqual(self.broker.actions, [])

    def test_escalation_has_no_hidden_operational_command(self):
        self.response = decision("escalate", task_id=None)
        self.assertEqual(self.pm.tick()["state"], "applied")
        with self.assertRaises(PMError):
            normalize_decision(decision("escalate", pr_number=1))

    def test_mode_turning_off_during_decision_prevents_mutation(self):
        def driver(context, schema, timeout):
            self.broker.state["global_mode"] = "off"
            return {"decision": decision(), "usage": self.usage}
        self.pm.decide = driver
        self.assertEqual(self.pm.tick()["state"], "stale")
        self.assertEqual(self.broker.actions, [])

    def test_head_or_ci_change_during_decision_prevents_mutation(self):
        def driver(context, schema, timeout):
            self.broker.state["prs"][0]["head"] = MERGED
            return {"decision": decision("merge"), "usage": self.usage}
        self.pm.decide = driver
        self.assertEqual(self.pm.tick()["state"], "stale")
        self.assertEqual(self.broker.actions, [])

    def test_merge_exact_head_and_independent_session(self):
        self.response = decision("merge")
        result = self.pm.tick()
        self.assertEqual(result["state"], "applied")
        action = self.broker.actions[0][1]
        self.assertEqual(action["expected_head"], HEAD)
        self.assertEqual(action["expected_base"], BASE)
        self.assertEqual(result["receipt"]["merge_commit"], MERGED)

    def test_manual_bypass_permission_does_not_grant_auto_merge(self):
        self.pm.policy["allow_auto_merge"] = False
        with self.assertRaises(PMError):
            self.pm.validate_action(decision("merge"), self.broker.state)

    def test_auto_bypass_is_separate_explicit_fixed_policy(self):
        self.pm.policy["allow_admin_bypass"] = True
        action = self.pm.validate_action(decision("merge"), self.broker.state)
        self.assertTrue(action["allow_admin_bypass"])
        bad = policy()
        bad["allow_admin_bypass"] = True
        bad.pop("admin_bypass_delegation")
        self.path.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(PMError):
            load_policy(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_merge_ci_success_text_alone_cannot_bypass(self):
        for modify in (
            lambda pr: pr["ci"].append({"context": "python", "head": HEAD, "status": "FAILURE"}),
            lambda pr: pr["ci"].pop(),
            lambda pr: pr["ci"][0].update(head=BASE),
            lambda pr: pr.update(base=MERGED),
            lambda pr: pr.update(mergeable=False),
        ):
            state = observation()
            modify(state["prs"][0])
            with self.assertRaises(PMError):
                self.pm.validate_action(decision("merge"), state)

    def test_merge_missing_stale_or_same_session_review_rejected(self):
        for update in ({"verified": False}, {"collector": "worker"}, {"head": BASE},
                       {"outcome": "request_changes"}, {"findings": ["Wrong product feature"]},
                       {"independent": False}, {"reviewer_session_id": "worker-implementation-session"},
                       {"implementation_session_id": ""}):
            state = observation()
            state["prs"][0]["independent_review"].update(update)
            with self.subTest(update=update), self.assertRaises(PMError):
                self.pm.validate_action(decision("merge"), state)

    def test_merge_integration_evidence_and_paths_enforced(self):
        for update in ({"verified": False}, {"base": MERGED}, {"result": "failed"},
                       {"checks": []}, {"evidence_sha256": ""}):
            state = observation()
            state["prs"][0]["integration"].update(update)
            with self.subTest(update=update), self.assertRaises(PMError):
                self.pm.validate_action(decision("merge"), state)
        self.broker.state["prs"][0]["changed_paths"] += [".github/workflows/harness.yml"]
        with self.assertRaises(ValueError):
            self.pm.validate_action(decision("merge"), self.broker.state)

    def test_merge_accepts_only_two_new_exact_trusted_job_records(self):
        pr = self.broker.state["prs"][0]
        records = [f"docs/{directory}/세션/정이량/current-job.md"
                   for directory in ("작업기록", "작업근거")]
        pr.update(job_id="current-job", added_paths=records)
        pr["changed_paths"] += records
        self.assertEqual(self.pm.validate_action(decision("merge"), self.broker.state)["expected_head"], HEAD)
        self.assertEqual(self.pm.policy["capabilities"][CAP]["allowed_paths"], ["tests/test_pilot.py"])

    def test_session_exception_never_authorizes_history_other_members_or_generic_docs(self):
        for path in ("docs/작업기록/세션/정이량/old-job.md", "docs/작업근거/세션/황대겸/current-job.md",
                     "docs/작업기록/정이량.md", "docs/작업기록/세션/정이량/current-job.md/extra.md",
                     "docs/pm/anything.md"):
            with self.subTest(path=path):
                state = observation()
                state["prs"][0].update(job_id="current-job", changed_paths=["tests/test_pilot.py", path], added_paths=[path])
                with self.assertRaises(PMError):
                    self.pm.validate_action(decision("merge"), state)
        # A broad policy declaration still cannot overwrite personal history.
        self.pm.policy["capabilities"][CAP]["allowed_paths"] += ["docs/작업기록", "docs/작업근거"]
        state = observation()
        old = "docs/작업기록/세션/정이량/old-job.md"
        state["prs"][0].update(job_id="current-job", changed_paths=[old], added_paths=[old])
        with self.assertRaisesRegex(PMError, "new immutable session"):
            self.pm.validate_action(decision("merge"), state)

    def test_session_exception_requires_valid_trusted_job_id_and_actual_addition(self):
        record = "docs/작업기록/세션/정이량/current-job.md"
        for job_id in (None, "", "../current-job", "current/job", "current.job", [], "a" * 101):
            with self.subTest(job_id=job_id):
                state = observation()
                state["prs"][0].update(job_id=job_id, changed_paths=[record], added_paths=[record])
                with self.assertRaises(PMError):
                    self.pm.validate_action(decision("merge"), state)
        for added in (None, [], {record}, ["tests/test_pilot.py"]):
            with self.subTest(added=added):
                state = observation()
                state["prs"][0].update(job_id="current-job", changed_paths=[record], added_paths=added)
                with self.assertRaisesRegex(PMError, "new immutable session"):
                    self.pm.validate_action(decision("merge"), state)

    def test_revision_keeps_contracts_and_uses_original_capability(self):
        self.response = decision("request_changes", instructions=["Correct client HTTP 403 handling"])
        self.assertEqual(self.pm.tick()["state"], "applied")
        action = self.broker.actions[0][1]
        self.assertEqual(action["allowed_paths"], ["tests/test_pilot.py"])
        self.assertNotIn("formal_done", action)

    def test_reconcile_postmerge_proof_without_parent_done(self):
        state = self.broker.state
        state["main_commit"] = MERGED
        pr = state["prs"][0]
        pr.update(state="merged", merged_commit=MERGED,
                  postmerge={**pr["integration"], "commit": MERGED})
        self.response = decision("reconcile")
        self.assertEqual(self.pm.tick()["state"], "applied")
        action = self.broker.actions[0][1]
        self.assertFalse(action["formal_done"])
        self.assertEqual(action["merged_commit"], MERGED)

    def test_reconcile_requires_current_actual_merge_and_postmerge(self):
        state = observation()
        pr = state["prs"][0]
        pr.update(state="merged", merged_commit=MERGED)
        with self.assertRaises(PMError):
            self.pm.validate_action(decision("reconcile"), state)

    def test_formal_done_requires_fixed_full_capability_and_every_requirement(self):
        state = self.broker.state
        state["main_commit"] = MERGED
        pr = state["prs"][0]
        pr.update(state="merged", merged_commit=MERGED,
                  postmerge={**pr["integration"], "commit": MERGED})
        self.pm.policy["capabilities"][CAP].update(completes_task=True, requirement_ids=["R17", "R24"])
        with self.assertRaises(PMError):
            self.pm.validate_action(decision("reconcile"), state)
        pr["postmerge"]["requirement_proofs"] = {
            "R17": {"verified": True, "evidence_sha256": PROOF},
            "R24": {"verified": True, "evidence_sha256": PROOF},
        }
        self.assertTrue(self.pm.validate_action(decision("reconcile"), state)["formal_done"])

    def test_eligible_action_context_excludes_unready_assign_and_stale_merge(self):
        self.broker.state["readiness"][PM]["publisher_separation_verified"] = False
        self.broker.state["prs"][0]["integration"]["verified"] = False
        self.response = decision("wait", task_id=None)
        self.assertEqual(self.pm.tick()["state"], "wait")
        eligible = self.calls[0][0]["eligible_actions"]
        self.assertFalse(any(item["action"] in {"assign", "merge"} for item in eligible))
        self.assertTrue(any(item["action"] == "request_changes" for item in eligible))

    def test_context_explains_stale_base_and_review_contract_without_parent_done_claim(self):
        state = self.broker.state
        state["capabilities_ready"] = []
        state["prs"][0]["independent_review"].update(findings=["Informational old review note"])
        state["parent_completion"] = {"main_commit": BASE, "tasks": {TASK: {"state": "waiting_evidence"}}}
        context = self.pm._context(state)
        blocked = [row for row in context["blocked_actions"] if row["action"] == "merge"]
        self.assertEqual(blocked[0]["reason"], "independent exact-head review is missing or has findings")
        self.assertFalse(context["capabilities"][CAP]["completes_task"])
        self.assertIn("does not require parent", context["instructions"])
        state["prs"][0]["base"] = MERGED
        context = self.pm._context(state)
        blocked = [row for row in context["blocked_actions"] if row["action"] == "merge"]
        self.assertEqual(blocked[0]["reason"], "merge requires reviewed approved exact current main/base")
        self.assertTrue(any(row["action"] == "request_changes" for row in context["eligible_actions"]))

    def test_partial_merge_does_not_require_parent_evidence_but_preserves_done_gate(self):
        self.broker.state["parent_completion"] = {"tasks": {TASK: {"state": "waiting_evidence"}}}
        self.response = decision("merge")
        self.assertEqual(self.pm.tick()["state"], "applied")
        self.assertEqual(self.broker.actions[0][1]["action"], "merge")
        self.assertNotIn("formal_done", self.broker.actions[0][1])
        self.assertEqual(self.broker.state["formal_snapshot"]["tasks"][TASK]["status"], "blocked")

    def test_accepted_logical_unit_is_not_redispatched(self):
        self.broker.state["jobs"] = [{"task_id": TASK, "capability_id": CAP, "status": "accepted"}]
        with self.assertRaises(PMError):
            self.pm.validate_action(decision(), self.broker.state)

    def test_response_loss_reconciles_without_duplicate_mutation(self):
        self.broker.error = True
        self.assertEqual(self.pm.tick()["state"], "reconciliation_required")
        self.broker.error = False
        self.assertEqual(self.pm.tick()["state"], "unchanged")
        self.assertEqual(len(self.broker.actions), 1)
        self.assertEqual(len(self.calls), 1)

    def test_unknown_outcome_halts_all_new_work_until_known(self):
        self.broker.unknown = True
        result = self.pm.tick()
        self.assertEqual(result["state"], "reconciliation_required")
        self.broker.state["operator_resume_nonce"] = "new-event"
        self.assertEqual(self.pm.tick()["state"], "reconciliation_required")
        self.assertEqual(len(self.calls), 1)
        self.broker.receipts[result["action_id"]]["outcome"] = "applied"
        self.broker.unknown = False
        self.assertEqual(self.pm.tick()["state"], "applied")

    def test_missing_receipt_never_retries_unknown_operation(self):
        self.broker.error = True
        result = self.pm.tick()
        self.broker.receipts.clear()
        self.assertEqual(self.pm.tick()["state"], "reconciliation_required")
        self.assertEqual(len(self.broker.actions), 1)
        self.assertEqual(result["state"], "reconciliation_required")

    def test_daily_model_usage_and_actions_persist(self):
        with self.pm.journal.connect() as db:
            self.pm.journal.budget(db, "day:1970-01-02")
            db.execute("UPDATE budgets SET model_calls=24 WHERE scope='day:1970-01-02'")
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")
        self.assertEqual(self.calls, [])

    def test_logical_task_budget_cannot_reset_with_new_head(self):
        self.response = decision("request_changes")
        with self.pm.journal.connect() as db:
            self.pm.journal.budget(db, "task:" + TASK)
            db.execute("UPDATE budgets SET revisions=3 WHERE scope=?", ("task:" + TASK,))
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")
        self.assertEqual(self.broker.actions, [])

    def test_unknown_usage_fail_closed_without_secret_exception_text(self):
        self.pm.decide = lambda *args: {"decision": decision(), "usage": {}}
        result = self.pm.tick()
        self.assertEqual(result["state"], "decision_rejected")
        self.assertNotIn("private", json.dumps(result))
        self.broker.state["operator_resume_nonce"] = "retry"
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")

    def test_journal_chain_and_receipt_are_immutable(self):
        result = self.pm.tick()
        self.pm.journal.verify()
        receipt = deepcopy(result["receipt"])
        receipt["evidence_sha256"] = "e" * 64
        with self.assertRaises(PMError):
            self.pm.journal.receipt(result["action_id"], receipt)
        db = sqlite3.connect(self.database)
        with db:
            db.execute("UPDATE journal SET payload='{}' WHERE seq=1")
        db.close()
        with self.assertRaises(PMError):
            Journal(self.database, self.pm.policy_digest)

    def test_bool_type_confusion_and_extension_policy_forbidden(self):
        for changes in ({"enabled": "true"}, {"tasks": {TASK: {**policy()["tasks"][TASK], "scope": "proposed_extension"}}}):
            fixed = policy()
            fixed.update(changes)
            self.path.write_text(json.dumps(fixed), encoding="utf-8")
            with self.assertRaises(PMError):
                load_policy(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_external_review_calls_count_before_decision(self):
        self.broker.state["external_usage"] = {"day": {"model_calls": 24, "tokens": 2000}, "tasks": {}}
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.broker.actions, [])

    def test_external_lifetime_task_usage_cannot_reset_next_day(self):
        self.clock_value += 86400
        self.broker.state["external_usage"] = {
            "day": {"model_calls": 0, "tokens": 0},
            "tasks": {TASK: {"model_calls": 8, "tokens": 8000}},
        }
        result = self.pm.tick()
        self.assertEqual(result["state"], "budget_exhausted")
        self.assertEqual(result["scope"], "task")
        self.assertEqual(self.calls, [])

    def test_combined_review_and_decision_usage_blocks_mutation(self):
        self.pm.policy["limits"]["max_model_tokens_per_day"] = 100
        self.broker.state["external_usage"] = {"day": {"model_calls": 1, "tokens": 50}, "tasks": {}}
        result = self.pm.tick()
        self.assertEqual(result["state"], "budget_exhausted")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.broker.actions, [])

    def test_fresh_review_usage_rechecked_before_mutation(self):
        def driver(context, schema, timeout):
            self.broker.state["external_usage"] = {
                "day": {"model_calls": 24, "tokens": 2000}, "tasks": {},
            }
            return {"decision": decision(), "usage": self.usage}
        self.pm.decide = driver
        self.assertEqual(self.pm.tick()["state"], "budget_exhausted")
        self.assertEqual(self.broker.actions, [])

    def test_review_usage_is_not_double_charged_in_decision_journal(self):
        self.broker.state["external_usage"] = {
            "day": {"model_calls": 1, "tokens": 50},
            "tasks": {TASK: {"model_calls": 1, "tokens": 50}},
        }
        self.assertEqual(self.pm.tick()["state"], "applied")
        with self.pm.journal.connect() as db:
            self.assertEqual(self.pm.journal.budget(db, "day:1970-01-02")["tokens"], 60)
            self.assertEqual(self.pm.journal.budget(db, "task:" + TASK)["model_calls"], 1)
        self.assertEqual(self.pm.tick()["state"], "unchanged")
        self.assertEqual(len(self.calls), 1)

    def test_malformed_external_usage_does_not_call_model(self):
        self.broker.state["external_usage"] = {"day": {"model_calls": True, "tokens": 0}, "tasks": {}}
        self.assertEqual(self.pm.tick()["state"], "halted")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
