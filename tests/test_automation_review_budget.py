"""Real broker lifecycle: known review usage stays known across fail-closed gates."""
from __future__ import annotations

import time
import unittest
from copy import deepcopy
from unittest.mock import patch

from services.automation.pm import PMError, fingerprint
from tests import test_automation_pm_broker as fixture


class ReviewBudgetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.BrokerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.broker = self.fixture.broker
        self.fixture.add_unit()
        self.pr = self.broker.observe(collect=False)["prs"][0]
        self.capability = self.broker.policy["capabilities"][fixture.CAP]
        self.day = time.strftime("%Y-%m-%d", time.gmtime())
        self.broker.policy["limits"].update(max_model_tokens_per_day=100, max_model_tokens_per_task=50)
        self.budget = {"calls": 0, "tokens": 10, "tasks": {fixture.TASK: 0}, "task_calls": {}}
        self.broker.state["budgets"][self.day] = self.budget
        self.key = fingerprint({"review_head": self.pr["head"], "base": self.pr["base"], "capability": self.capability})

    def review(self):
        return self.broker._review(self.pr, self.capability, "original-implementation-session")

    def assert_uncertain_cached_and_unmergeable(self, calls):
        proof = self.broker.state["proofs"][self.key]
        self.assertFalse(proof["verified"])
        self.assertEqual(proof["outcome"], "unknown")
        self.assertEqual(self.review(), proof)
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(self.budget["calls"], 1)
        self.assertEqual(self.budget["task_calls"][fixture.TASK], 1)
        with self.assertRaises(PMError):
            self.fixture.action("merge")
        self.assertFalse(self.fixture.github.merged)
        self.assertEqual(self.fixture.github.comments, [])

    def test_known_task_exceeded_preserves_actual_cost_and_cannot_merge_or_repeat(self):
        self.budget["tasks"][fixture.TASK] = 29
        original = self.broker.driver.call
        with patch.object(self.broker.driver, "call", side_effect=original) as calls:
            with self.assertRaisesRegex(PMError, "remaining budget"):
                self.review()  # actual24, task29+24>50, day10+24<100
            self.assertEqual(self.budget["tokens"], 34)
            self.assertEqual(self.budget["tasks"][fixture.TASK], 53)
            self.assert_uncertain_cached_and_unmergeable(calls)

    def test_known_day_exceeded_preserves_exact_overspend_not_invented_penalty(self):
        self.budget["tokens"] = 90
        self.broker.policy["limits"]["max_model_tokens_per_task"] = 200
        original = self.broker.driver.call
        with patch.object(self.broker.driver, "call", side_effect=original) as calls:
            with self.assertRaisesRegex(PMError, "remaining budget"):
                self.review()
            self.assertEqual(self.budget["tokens"], 114)
            self.assertEqual(self.budget["tasks"][fixture.TASK], 24)
            self.assert_uncertain_cached_and_unmergeable(calls)

    def test_previous_day_task_usage_is_preserved_when_today_review_crosses_lifetime_gate(self):
        self.broker.state["budgets"]["1900-01-01"] = {"calls": 1, "tokens": 30, "tasks": {fixture.TASK: 30},
                                                           "task_calls": {fixture.TASK: 1}}
        previous = deepcopy(self.broker.state["budgets"]["1900-01-01"])
        original = self.broker.driver.call
        with patch.object(self.broker.driver, "call", side_effect=original) as calls:
            with self.assertRaisesRegex(PMError, "remaining budget"):
                self.review()
            self.assertEqual(self.budget["tokens"], 34)
            self.assertEqual(self.budget["tasks"][fixture.TASK], 24)
            self.assertEqual(self.broker.state["budgets"]["1900-01-01"], previous)
            self.assert_uncertain_cached_and_unmergeable(calls)

    def test_unknown_usage_after_execution_still_consumes_day_and_task_quota(self):
        with patch.object(self.broker.driver, "call", side_effect=OSError("fixture after execution")) as calls:
            with self.assertRaises(OSError):
                self.review()
            self.assertEqual(self.budget["tokens"], 100)
            self.assertEqual(self.budget["tasks"][fixture.TASK], 50)
            self.assert_uncertain_cached_and_unmergeable(calls)

    def test_missing_usage_still_consumes_quota_and_cannot_be_approved(self):
        value = {"session_id": "isolated-review", "usage": {},
                 "result": {"outcome": "approve", "reason": "Unmeasured result", "findings": []}}
        with patch.object(self.broker.driver, "call", return_value=value) as calls:
            with self.assertRaisesRegex(PMError, "usage required"):
                self.review()
            self.assertEqual(self.budget["tokens"], 100)
            self.assertEqual(self.budget["tasks"][fixture.TASK], 50)
            self.assert_uncertain_cached_and_unmergeable(calls)
