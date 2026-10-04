"""Shared-budget boundaries; these are owner operations, not model execution."""
import unittest
from concurrent.futures import ThreadPoolExecutor

from lgax_core.correction_budget import CorrectionBudget
from lgax_core.errors import DomainError


class CorrectionBudgetTests(unittest.TestCase):
    def test_stage_retry_and_revision_callback_share_two_attempts(self):
        budget = CorrectionBudget()
        stage_scheduler, revision_session = budget, budget
        stage_scheduler.claim(expected_revision_count=0, operation="stage_retry")
        revision_session.claim(expected_revision_count=1, operation="review_revision")
        for scheduler in (stage_scheduler, revision_session):
            with self.assertRaises(DomainError):
                scheduler.claim(expected_revision_count=2, operation="review_revision")
            with self.assertRaises(DomainError):
                scheduler.claim(expected_revision_count=0, operation="stage_retry")
        self.assertEqual([row["operation"] for row in budget.snapshot["attempts"]],
                         ["stage_retry", "review_revision"])

    def test_malformed_output_does_not_refund_attempt_and_other_path_cannot_reset(self):
        budget = CorrectionBudget()
        generated = []

        def correction(operation, expected):
            count = budget.claim(expected_revision_count=expected, operation=operation)
            generated.append(count)
            raise DomainError("VALIDATION_FAILED", "작성된 깨진 출력", {})

        with self.assertRaises(DomainError):
            correction("review_revision", 0)
        with self.assertRaises(DomainError):
            correction("stage_retry", 0)
        with self.assertRaises(DomainError):
            correction("stage_retry", 1)
        with self.assertRaises(DomainError):
            correction("review_revision", 2)
        self.assertEqual(generated, [1, 2])

    def test_concurrent_replays_have_one_winner_per_remaining_round(self):
        budget = CorrectionBudget()

        def claim(count):
            try:
                return budget.claim(expected_revision_count=count, operation="review_revision")
            except DomainError:
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            first = list(executor.map(claim, [0] * 16))
            second = list(executor.map(claim, [1] * 16))
            exhausted = list(executor.map(claim, [2] * 16))
        self.assertEqual([value for value in first if value is not None], [1])
        self.assertEqual([value for value in second if value is not None], [2])
        self.assertEqual(exhausted, [None] * 16)

    def test_owner_verified_existing_count_cannot_regain_spent_attempts(self):
        budget = CorrectionBudget(initial_count=1)
        with self.assertRaises(DomainError):
            budget.claim(expected_revision_count=0, operation="review_revision")
        budget.claim(expected_revision_count=1, operation="review_revision")
        with self.assertRaises(DomainError):
            budget.claim(expected_revision_count=2, operation="stage_retry")
        terminal = CorrectionBudget(initial_count=2)
        with self.assertRaises(DomainError):
            terminal.claim(expected_revision_count=2, operation="review_revision")

    def test_hold_and_backend_or_policy_failure_close_both_paths(self):
        for reason in CorrectionBudget.CLOSE_REASONS:
            with self.subTest(reason=reason):
                budget = CorrectionBudget()
                budget.close(reason=reason)
                for operation in CorrectionBudget.OPERATIONS:
                    with self.assertRaises(DomainError):
                        budget.claim(expected_revision_count=0, operation=operation)
                self.assertEqual(budget.snapshot["revision_count"], 0)
                self.assertEqual(budget.snapshot["terminal_reason"], reason)

    def test_snapshot_mutation_cannot_change_or_refund_shared_budget(self):
        budget = CorrectionBudget()
        budget.claim(expected_revision_count=0, operation="stage_retry")
        snapshot = budget.snapshot
        snapshot.update(revision_count=0, closed=False)
        snapshot["attempts"].clear()
        with self.assertRaises(DomainError):
            budget.claim(expected_revision_count=0, operation="review_revision")
        self.assertEqual(len(budget.snapshot["attempts"]), 1)

    def test_invalid_or_model_selected_operations_do_not_spend_a_correction(self):
        budget = CorrectionBudget()
        for count in (True, -1, 3, "0", None):
            with self.subTest(count=count), self.assertRaises(DomainError):
                budget.claim(expected_revision_count=count, operation="stage_retry")
        for operation in ("tool_call", "reset", "semantic_review", None, []):
            with self.subTest(operation=operation), self.assertRaises(DomainError):
                budget.claim(expected_revision_count=0, operation=operation)
        with self.assertRaises(DomainError):
            budget.close(reason="model_requested_reset")
        self.assertEqual(budget.snapshot["attempts"], [])
        self.assertFalse(budget.snapshot["closed"])

    def test_invalid_owner_initial_count_is_rejected(self):
        for count in (True, -1, 3, "0", None):
            with self.subTest(count=count), self.assertRaises(DomainError):
                CorrectionBudget(initial_count=count)
