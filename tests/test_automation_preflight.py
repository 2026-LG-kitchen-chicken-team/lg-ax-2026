"""Preflight uses the selected container CLI, never a Windows auth proxy."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest.mock import patch

from scripts import automation_isolation
from services.automation import worker


class WorkerPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.repo = self.path / "repo"
        self.repo.mkdir()
        self.config = worker.WorkerConfig(
            account="choigilung", repository=self.repo, state_dir=self.path / "state",
            controller_url="https://example.invalid/lgax", token_file=self.path / "worker.token",
            engine="claude", claude_home=self.path / "claude-auth",
            executor_image="sha256:" + "a" * 64, execution_root=self.path / "execution",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, *, configured=True, auth=None, failure=None, preflight=True,
                 locks=None, request=None, execute=None, sleep=None, continuous=False):
        if not configured:
            self.config = worker.WorkerConfig(**{**self.config.__dict__, "executor_image": None,
                                                "execution_root": None})
        output = io.StringIO()
        argv = ["worker", "--config", str(self.path / "config.json")]
        if preflight:
            argv.append("--preflight")
        elif not continuous:
            argv.append("--once")
        with patch.object(worker.WorkerConfig, "load", return_value=self.config), \
                patch.object(worker, "exclusive_lock", side_effect=locks or (lambda path: nullcontext())), \
                patch.object(worker, "github_identity"), \
                patch.object(worker, "ControllerClient") as client, \
                patch.object(worker, "WorkerPresence"), \
                patch.object(worker, "DockerExecutor") as docker, \
                patch.object(worker, "validate_auth") as host, \
                patch.object(worker, "validate_container_auth", side_effect=failure,
                             return_value=auth or {"verified": True, "source": "actual_isolated_cli"}) as guest, \
                patch.object(worker, "execute_job", side_effect=execute) as execution, \
                patch.object(worker.time, "sleep", side_effect=sleep), \
                patch("sys.argv", argv), patch("sys.stdout", output):
            client.return_value.request.return_value = {"job": None}
            client.return_value.request.side_effect = request
            docker.return_value.preflight.return_value = {"backend": "docker", "native_fallback": False}
            worker.main()
            if execute is None:
                execution.assert_not_called()
            return json.loads(output.getvalue()) if output.getvalue() else None, host, guest, client, docker

    def test_configured_claude_uses_container_auth_not_host_keychain(self):
        result, host, guest, client, docker = self.run_main()
        host.assert_not_called()
        guest.assert_called_once()
        docker.return_value.preflight.assert_called_once()
        self.assertEqual(result["preflight"], "passed")
        self.assertTrue(result["container_auth_verified"])
        self.assertFalse(result["model_executed"])
        self.assertFalse(result["canary_verified"])
        self.assertFalse(result["automation_ready"])
        client.return_value.request.assert_called_once_with("/v1/status")

    def test_no_image_is_metadata_only_not_ready(self):
        result, host, guest, client, docker = self.run_main(configured=False)
        host.assert_not_called()
        guest.assert_not_called()
        docker.assert_not_called()
        self.assertEqual(result["preflight"], "metadata_only")
        self.assertFalse(result["container_auth_verified"])
        self.assertFalse(result["automation_ready"])
        self.assertFalse(result["execution_started"])
        client.return_value.request.assert_called_once_with("/v1/status")

    def test_host_login_cannot_hide_failed_container_login(self):
        with self.assertRaises(ValueError):
            self.run_main(failure=ValueError("isolated CLI needs own login"))

    def test_unverified_container_auth_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_main(auth={"verified": False})

    def test_normal_loop_validates_container_before_claim(self):
        result, host, guest, client, _ = self.run_main(preflight=False)
        self.assertIsNone(result)
        host.assert_not_called()
        guest.assert_called_once()
        client.return_value.request.assert_called_once_with("/v1/claim", {})

    def test_idle_worker_releases_ai_profile_but_retains_worker_lock(self):
        active = set()

        @contextmanager
        def locks(path):
            active.add(path.name)
            try:
                yield
            finally:
                active.remove(path.name)

        def request(route, payload=None):
            self.assertEqual(route, "/v1/claim")
            self.assertEqual(active, {"worker.lock", "lgax-worker.lock"})
            return {"job": None}

        def sleep(_seconds):
            self.assertEqual(active, {"worker.lock"})
            raise RuntimeError("stop idle loop")

        with self.assertRaisesRegex(RuntimeError, "stop idle loop"):
            self.run_main(preflight=False, continuous=True, locks=locks, request=request, sleep=sleep)
        self.assertEqual(active, set())

    def test_profile_contention_after_auth_never_claims_or_executes(self):
        attempts = 0

        @contextmanager
        def locks(path):
            nonlocal attempts
            if path.name == "lgax-worker.lock":
                attempts += 1
                if attempts == 2:
                    raise BlockingIOError("PM uses the shared owner profile")
            yield

        result, host, guest, client, _ = self.run_main(preflight=False, locks=locks)
        self.assertEqual(result["state"], "profile_busy")
        self.assertFalse(result["model_executed"])
        self.assertFalse(result["execution_started"])
        host.assert_not_called()
        guest.assert_called_once()
        client.return_value.request.assert_not_called()
        self.assertEqual(attempts, 2)

    def test_actual_os_profile_contention_returns_busy_without_claim(self):
        actual_lock = worker.exclusive_lock
        with actual_lock(self.config.agent_home / "lgax-worker.lock"):
            result, host, guest, client, _ = self.run_main(preflight=False, locks=actual_lock)
        self.assertEqual(result["state"], "profile_busy")
        host.assert_not_called()
        guest.assert_not_called()
        client.return_value.request.assert_not_called()

    def test_actual_os_profile_available_during_idle_worker_remains_exclusive(self):
        actual_lock = worker.exclusive_lock

        def sleep(_seconds):
            with actual_lock(self.config.agent_home / "lgax-worker.lock"):
                pass
            with self.assertRaises(OSError), actual_lock(self.config.state_dir / "worker.lock"):
                self.fail("a second worker acquired the active service lock")
            raise RuntimeError("stop verified idle worker")

        with self.assertRaisesRegex(RuntimeError, "stop verified idle worker"):
            self.run_main(preflight=False, continuous=True, locks=actual_lock, sleep=sleep)

    def test_startup_contention_waits_without_claim_and_recovers(self):
        attempts, sleeps, claims = 0, 0, 0

        @contextmanager
        def locks(path):
            nonlocal attempts
            if path.name == "lgax-worker.lock":
                attempts += 1
                if attempts == 1:
                    raise BlockingIOError("profile temporarily busy")
            yield

        def request(route, payload=None):
            nonlocal claims
            self.assertEqual(route, "/v1/claim")
            claims += 1
            return {"job": None}

        def sleep(_seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 1:
                self.assertEqual(claims, 0)
                self.assertEqual(attempts, 1)
            else:
                raise RuntimeError("stop recovered worker")

        with self.assertRaisesRegex(RuntimeError, "stop recovered worker"):
            self.run_main(preflight=False, continuous=True, locks=locks, request=request, sleep=sleep)
        self.assertEqual((sleeps, claims, attempts), (2, 1, 3))

    def test_claimed_job_holds_profile_through_execution(self):
        active = set()

        @contextmanager
        def locks(path):
            active.add(path.name)
            try:
                yield
            finally:
                active.remove(path.name)

        def request(route, payload=None):
            self.assertEqual(route, "/v1/claim")
            self.assertEqual(active, {"worker.lock", "lgax-worker.lock"})
            return {"job": {"job_id": "fixed-job"}}

        def execute(config, client, job):
            self.assertEqual(active, {"worker.lock", "lgax-worker.lock"})
            return {"job_id": job["job_id"], "state": "review_requested"}

        result, _, _, _, _ = self.run_main(preflight=False, locks=locks, request=request, execute=execute)
        self.assertEqual(result["job_id"], "fixed-job")
        self.assertEqual(active, set())

    def test_canary_proof_rejects_checkout_output_before_setup(self):
        (self.repo / ".git").mkdir()
        with patch.object(automation_isolation, "setup") as setup, self.assertRaises(ValueError):
            automation_isolation.verify(self.path / "config.json", self.repo / "readiness.json")
        setup.assert_not_called()

    def test_canary_proof_is_fresh_not_overwritten(self):
        output = self.path / "readiness.json"
        output.write_text("old evidence", encoding="utf-8")
        with patch.object(automation_isolation, "setup") as setup, self.assertRaises(ValueError):
            automation_isolation.verify(self.path / "config.json", output)
        setup.assert_not_called()
        self.assertEqual(output.read_text(), "old evidence")

    def test_canary_proof_rejects_guest_writable_output(self):
        self.config.execution_root.mkdir()
        output = self.config.execution_root / "readiness.json"
        with patch.object(automation_isolation, "setup", return_value=(self.config, None, None, None, None)), \
                self.assertRaises(ValueError):
            automation_isolation.verify(self.path / "config.json", output)


if __name__ == "__main__":
    unittest.main()
