"""Trusted failure classification fixtures; no live model or remote PC evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.worker import WorkerConfig, execute_job, prompt_for


class WorkerSelfReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "repo"
        self.repository.mkdir()
        self.config = WorkerConfig(account="choigilung", repository=self.repository,
            state_dir=self.root / "state", controller_url="http://127.0.0.1:18871",
            token_file=self.root / "worker.token", engine="claude", claude_home=self.root / "claude-auth",
            isolation_acknowledged=True, executor_image="sha256:" + "a" * 64,
            execution_root=self.root / "execution")
        self.job = {"job_id": "WEB-SELF-REVIEW", "owner": "choigilung", "kind": "implementation",
            "base_commit": "a" * 40, "lease_token": "private-lease-fixture", "timeout_seconds": 120,
            "prompt": "Fixed held-reason comparison regression", "allowed_paths": ["apps/web/"],
            "validation_commands": [["python", "-m", "unittest"]],
            "acceptance": ["Retain previous run and show actual changed reason"]}
        self.result = {"summary": "Fixture edits awaiting trusted tests", "intent_interpretation": "fixed task",
            "changes": [], "limitations": ["No live model or PC"], "findings": [], "next_action": "PM review"}

    def execute(self, *, validation_exit=0, stopped_reason=None, validation_error=None):
        receipts = []
        client = SimpleNamespace(heartbeat=lambda _job: True,
            request=lambda _route, payload: receipts.append(payload) or {})
        roles = []

        def run(_argv, **kwargs):
            roles.append(kwargs["role"])
            if kwargs["role"] == "model":
                kwargs["output"].write_text(json.dumps({"type": "result", "subtype": "success",
                    "is_error": False, "structured_output": self.result, "permission_denials": []}))
                return SimpleNamespace(returncode=0, elapsed_seconds=0.01, stopped_reason=None)
            self.assertEqual(kwargs["env"], {})
            if validation_error:
                raise validation_error
            return SimpleNamespace(returncode=validation_exit, elapsed_seconds=0.01,
                                   stopped_reason=stopped_reason)

        with patch("services.automation.worker.github_identity"), \
                patch("services.automation.worker.prepare_worktree",
                      return_value=(self.repository, "fixture-branch", "a" * 40, [], [])), \
                patch("services.automation.worker.DockerExecutor") as docker, \
                patch("services.automation.worker.validate_container_auth", return_value={}), \
                patch("services.automation.worker.private_ai_values", return_value=[]), \
                patch("services.automation.worker.artifacts.export_tracked", return_value={}), \
                patch("services.automation.worker.artifacts.files", return_value={}), \
                patch("services.automation.worker.artifacts.write_copy"), \
                patch("services.automation.worker.artifacts.import_checked", return_value=[]), \
                patch("services.automation.worker.check_scope", return_value=[]), \
                patch("services.automation.worker.git", return_value="a" * 40), \
                patch("services.automation.worker.send_project_report", return_value={}), \
                patch("services.automation.worker.publish", return_value={}) as publish:
            docker.return_value.run.side_effect = run
            docker.return_value.preflight.return_value = {"backend": "docker"}
            observed = execute_job(self.config, client, self.job)
            published = publish.call_count
        return observed, receipts, roles, published

    def test_own_review_maps_acceptance_to_evidence_without_fabricating_trusted_tests(self):
        prompt = prompt_for(self.job, "choigilung")
        for required in ("every acceptance item", "correct defects", "zero-authentication validator",
                         "do not execute repository code here", "cannot approve a PR",
                         "still pending", "private-lease-fixture"):
            with self.subTest(required=required):
                if required == "private-lease-fixture":
                    self.assertNotIn(required, prompt)
                else:
                    self.assertIn(required, prompt)
        review = prompt_for({**self.job, "kind": "review"}, "choigilung")
        self.assertIn("Read-only independent review", review)
        self.assertNotIn("correct defects", review)

    def test_completed_test_failure_blocks_original_attempt_without_pausing_or_publishing(self):
        observed, receipts, roles, published = self.execute(validation_exit=1)
        self.assertEqual(observed["state"], "blocked")
        self.assertIs(observed["ordinary_validation_failure"], True)
        self.assertFalse(observed.get("halt_worker", False))
        self.assertEqual(observed["checks"][0]["returncode"], 1)
        self.assertIn("check 0, exit 1", receipts[-1]["summary"])
        self.assertEqual(receipts[-1]["outcome"], "blocked")
        self.assertEqual(roles, ["model", "validator"])
        self.assertEqual(published, 0)
        self.assertIsNone(receipts[-1].get("publish_token"))
        checkpoint = self.config.state_dir / "runs/WEB-SELF-REVIEW-attempt1-g1/checkpoint.json"
        self.assertTrue(checkpoint.is_file())
        with self.assertRaisesRegex(ValueError, "no automatic overwrite/retry"):
            execute_job(self.config, object(), self.job)

    def test_stopped_validator_keeps_member_pause_and_does_not_publish(self):
        observed, receipts, roles, published = self.execute(validation_exit=1, stopped_reason="timeout")
        self.assertIs(observed["halt_worker"], True)
        self.assertNotIn("ordinary_validation_failure", observed)
        self.assertEqual(receipts[-1]["outcome"], "blocked")
        self.assertEqual(roles, ["model", "validator"])
        self.assertEqual(published, 0)

    def test_executor_boundary_failure_keeps_member_pause_and_does_not_publish(self):
        observed, receipts, roles, published = self.execute(validation_error=ValueError("invalid validator mount"))
        self.assertIs(observed["halt_worker"], True)
        self.assertNotIn("ordinary_validation_failure", observed)
        self.assertEqual(receipts[-1]["outcome"], "blocked")
        self.assertEqual(roles, ["model", "validator"])
        self.assertEqual(published, 0)

    def test_signal_timeout_or_container_start_failure_remains_a_member_pause(self):
        for exit_code in (-9, 124, 125, 126, 127, 137):
            with self.subTest(exit_code=exit_code):
                self.job["job_id"] = f"WEB-INFRA-{abs(exit_code)}"
                observed, receipts, _roles, published = self.execute(validation_exit=exit_code)
                self.assertIs(observed["halt_worker"], True)
                self.assertNotIn("ordinary_validation_failure", observed)
                self.assertEqual(receipts[-1]["outcome"], "blocked")
                self.assertEqual(published, 0)

    def test_success_still_requires_zero_auth_tests_and_publisher_before_review_requested(self):
        observed, receipts, roles, published = self.execute()
        self.assertEqual(observed["state"], "review_requested")
        self.assertNotIn("ordinary_validation_failure", observed)
        self.assertEqual(roles, ["model", "validator"])
        self.assertEqual(published, 1)
        self.assertEqual(receipts[-1]["outcome"], "review_requested")
        self.assertNotIn(receipts[-1]["outcome"], {"accepted", "done"})


if __name__ == "__main__":
    unittest.main()
