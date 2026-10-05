"""Do not spend validator time on an independently rejected immutable PR."""
from __future__ import annotations

import time
import unittest
from copy import deepcopy
from unittest.mock import patch

from services.automation.pm import PMError, fingerprint
from tests import test_automation_pm_broker as fixture


class RejectedReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.BrokerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.broker = self.fixture.broker
        self.fixture.add_unit()

    def reject(self):
        self.broker.driver.call = lambda *_args, **_kwargs: {
            "session_id": "fresh-independent-review", "usage": {"input_tokens": 20, "output_tokens": 4},
            "result": {"outcome": "request_changes", "reason": "Exact-head behavior needs correction",
                       "findings": ["The fixed output contract is not met."]}}

    def test_verified_exact_rejection_skips_integration_keeps_review_and_caches_real_usage(self):
        self.reject()
        formal = deepcopy(self.fixture.controller.status["formal_snapshot"])
        with patch.object(self.broker, "_integration", side_effect=AssertionError("rejected head must not run validators")) as integration:
            first = self.broker.observe()["prs"][0]
            second = self.broker.observe()["prs"][0]
        integration.assert_not_called()
        self.assertEqual(first["independent_review"]["outcome"], "request_changes")
        self.assertEqual(first["independent_review"], second["independent_review"])
        self.assertNotIn("integration", first)
        self.assertEqual(self.fixture.controller.status["formal_snapshot"], formal)
        daily = self.broker.state["budgets"][time.strftime("%Y-%m-%d", time.gmtime())]
        self.assertEqual((daily["calls"], daily["tokens"]), (1, 24))
        with self.assertRaisesRegex(PMError, "independent exact-head review"):
            self.fixture.gate.validate_action({"action": "merge", "task_id": fixture.TASK,
                "capability_id": fixture.CAP, "pr_number": 81, "head_commit": fixture.HEAD,
                "reason": "Review cannot be bypassed", "instructions": []}, self.broker.observe(collect=False))

    def test_approved_head_and_postmerge_still_run_full_integration(self):
        proof = {"verified": True, "collector": "trusted_pm", "commit": fixture.HEAD, "head": fixture.HEAD,
                 "base": fixture.BASE, "result": "passed", "checks": ["client-unit"],
                 "evidence_sha256": "d" * 64, "capability_fingerprint": fingerprint(self.broker.policy["capabilities"][fixture.CAP])}
        with patch.object(self.broker, "_integration", return_value=proof) as integration:
            observed = self.broker.observe()["prs"][0]
            self.assertEqual(observed["independent_review"]["outcome"], "approve")
            self.assertEqual(observed["integration"], proof)
            integration.assert_called_once()
            self.fixture.github.merged = True
            self.fixture.github.main = fixture.MERGED
            merged = self.broker.observe()["prs"][0]
            self.assertEqual(merged["postmerge"], proof)
            self.assertEqual(integration.call_count, 2)
            self.assertTrue(integration.call_args.kwargs["postmerge"])

    def test_unverified_stale_capability_or_nonindependent_rejection_cannot_skip_checks(self):
        self.reject()
        pr = self.broker.observe(collect=False)["prs"][0]
        valid = self.broker._review(pr, self.broker.policy["capabilities"][fixture.CAP], "implementation-session")
        changes = ({"verified": False}, {"head": "f" * 40}, {"base": "f" * 40},
                   {"capability_fingerprint": "0" * 64}, {"collector": "worker"}, {"independent": False},
                   {"reviewer_session_id": "implementation-session"}, {"implementation_session_id": "other-unit"},
                   {"reviewer": "unregistered"}, {"evidence_sha256": "missing"}, {"outcome": "unknown"})
        for update in changes:
            with self.subTest(update=update), \
                    patch.object(self.broker, "_review", return_value={**valid, **update}), \
                    patch.object(self.broker, "_integration", return_value={"actual_validator": True}) as integration:
                observed = self.broker.observe()["prs"][0]
                integration.assert_called_once()
                self.assertEqual(observed["integration"], {"actual_validator": True})

