"""Authenticated process metadata is separate from leases and product evidence."""
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from services.automation.controller import create_app
from services.automation.state import ACCOUNTS, Store, digest
from services.automation.worker import WorkerPresence


class WorkerPresenceControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = 1000.0
        self.tokens = {account: f"fixture-{account}-private-credential-123456789" for account in ACCOUNTS}
        self.pm_worker_token = "fixture-PM-worker-separate-credential-123456789"
        self.config = {"database": str(self.root / "controller.sqlite3"),
            "token_digests": {account: digest(token) for account, token in self.tokens.items()},
            "worker_token_digests": {"jeongiryang": digest(self.pm_worker_token)},
            "formal_snapshot": {"approved_commit": "a" * 40, "tasks": {
                "WEB": {"owner": "choigilung", "status": "doing"}}}}
        self.store = Store(self.config["database"], self.config, clock=lambda: self.now)
        self.client = TestClient(create_app(config=self.config, store=self.store))
        self.addCleanup(self.client.close)

    def body(self, **updates):
        value = {"schema_version": 1, "source": "fixed_worker", "runtime_version": "worker-presence-v1",
            "runtime_sha256": "a" * 64, "engine": "claude", "phase": "idle", "instance_id": "a" * 32,
            "sequence": 1, "reported_at": self.now, "job_id": None, "lease_token": None}
        return {**value, **updates}

    def post(self, route, body, account="choigilung", token=None):
        return self.client.post(route, json=body,
                                headers={"Authorization": "Bearer " + (token or self.tokens[account])})

    def status(self):
        return self.client.get("/v1/status", headers={"Authorization": "Bearer " + self.tokens["jeongiryang"]}).json()

    def presence(self, body=None, **kwargs):
        return self.post("/v1/worker-presence", body or self.body(), **kwargs)

    def running(self):
        packet = {"job_id": "WEB-J1", "owner": "choigilung", "task_id": "WEB", "assignment_id": "A1",
            "base_commit": "a" * 40, "title": "Bounded fixture", "prompt": "Approved fixture only",
            "approved": True, "approval_reference": "PM fixture", "allowed_paths": ["apps/web/src/"],
            "shared_resources": [], "validation_commands": [["python", "-m", "unittest"]],
            "priority": 1, "max_attempts": 1, "timeout_seconds": 300}
        self.assertEqual(self.post("/v1/jobs", packet, "jeongiryang").status_code, 200)
        self.assertEqual(self.post("/v1/mode", {"mode": "on"}, "jeongiryang").status_code, 200)
        self.assertEqual(self.post("/v1/mode", {"mode": "on", "member": "choigilung"}).status_code, 200)
        return self.post("/v1/claim", {}).json()["job"]

    def job_row(self):
        with closing(sqlite3.connect(self.config["database"])) as db:
            return db.execute("SELECT status,lease_expires,run_deadline,attempt,generation,result FROM jobs").fetchone()

    def test_presence_is_auth_required_and_only_updates_the_authenticated_owner(self):
        self.assertEqual(self.client.post("/v1/worker-presence", json=self.body()).status_code, 401)
        self.assertEqual(self.presence(self.body(owner="unknownamed")).status_code, 422)
        self.assertEqual(self.presence().status_code, 200)
        status = self.status()
        self.assertEqual(status["workers"]["choigilung"]["presence"], "online")
        self.assertEqual(status["workers"]["unknownamed"]["presence"], "never_seen")
        self.assertEqual(status["workers"]["choigilung"]["last_seen_at"], 1000)
        self.assertEqual(status["global_mode"], "off")
        self.assertFalse(any(status["members"].values()))

    def test_operator_cannot_impersonate_worker_but_separate_pm_worker_token_can_report(self):
        self.assertEqual(self.presence(account="jeongiryang").status_code, 403)
        self.assertEqual(self.presence(account="jeongiryang", token=self.pm_worker_token).status_code, 200)
        self.assertTrue(self.status()["workers"]["jeongiryang"]["registered"])
        self.assertEqual(self.post("/v1/mode", {"mode": "on"}, "jeongiryang",
                                   token=self.pm_worker_token).status_code, 403)

    def test_fixed_source_engine_schema_no_paths_contacts_or_extra_fields(self):
        cases = [{"source": "issue_comment"}, {"engine": "untrusted"}, {"engine": {}}, {"phase": []},
                 {"phase": "done"}, {"schema_version": True}, {"runtime_sha256": "changed"},
                 {"runtime_version": "arbitrary"}, {"instance_id": "../../private"}, {"sequence": True},
                 {"account": "unknownamed"}, {"email": "fixture@example.invalid"},
                 {"auth_path": "C:/private/auth"}, {"reported_at": True}, {"reported_at": 10 ** 1000}]
        for values in cases:
            with self.subTest(values=values):
                self.assertEqual(self.presence(self.body(**values)).status_code, 422)
        self.assertEqual(self.status()["workers"]["choigilung"]["presence"], "never_seen")

    def test_online_becomes_stale_at_exact_server_threshold_without_forged_client_time(self):
        self.assertEqual(self.presence().status_code, 200)
        self.now += 179
        self.assertEqual(self.status()["workers"]["choigilung"]["presence"], "online")
        self.now += 1
        stale = self.status()["workers"]["choigilung"]
        self.assertEqual(stale["presence"], "stale")
        self.assertEqual(stale["age_seconds"], 180)
        self.assertEqual(stale["stale_after_seconds"], 180)
        self.assertEqual(self.presence(self.body(sequence=2, reported_at=1000)).status_code, 422)
        self.assertEqual(self.presence(self.body(sequence=2, reported_at=self.now + 180)).status_code, 422)
        self.assertEqual(self.status()["workers"]["choigilung"]["last_seen_at"], 1000)

    def test_delayed_duplicate_and_retired_instances_cannot_refresh_last_seen(self):
        self.assertEqual(self.presence().status_code, 200)
        self.now += 2
        self.assertEqual(self.presence(self.body()).status_code, 409)
        self.assertEqual(self.presence(self.body(sequence=2, reported_at=999)).status_code, 409)
        self.assertEqual(self.presence(self.body(sequence=2)).status_code, 200)
        self.now += 1
        self.assertEqual(self.presence(self.body(instance_id="b" * 32)).status_code, 200)
        self.now += 1
        self.assertEqual(self.presence(self.body(sequence=3)).status_code, 409)
        self.assertEqual(self.status()["workers"]["choigilung"]["instance_id"], "b" * 32)
        self.assertEqual(self.status()["workers"]["choigilung"]["last_seen_at"], 1003)

    def test_initial_delivery_loss_does_not_permanently_disable_future_metadata(self):
        # The first HTTP response can be lost before the server receives it.
        self.assertEqual(self.presence(self.body(sequence=2)).status_code, 200)
        self.now += 1
        self.assertEqual(self.presence(self.body(sequence=3)).status_code, 200)

    def test_active_job_requires_current_owner_and_lease_and_never_renews_or_mutates_job(self):
        job = self.running()
        before = self.job_row()
        body = self.body(phase="validating", job_id=job["job_id"], lease_token=job["lease_token"])
        self.now += 30
        body["reported_at"] = self.now
        self.assertEqual(self.presence(body).status_code, 200)
        self.assertEqual(self.job_row(), before)
        self.assertEqual(self.presence({**body, "sequence": 2}, account="unknownamed").status_code, 403)
        self.assertEqual(self.presence({**body, "sequence": 2, "lease_token": "wrong"}).status_code, 403)
        public = json.dumps(self.status())
        self.assertNotIn(job["lease_token"], public)
        self.assertNotIn("lease_token", json.dumps(self.status()["workers"]))
        self.now += 91
        self.assertEqual(self.presence({**body, "sequence": 2, "reported_at": self.now}).status_code, 403)
        self.assertEqual(self.job_row(), before)

    def test_idle_cannot_launder_an_active_job_and_restart_preserves_original_queue_and_presence(self):
        job = self.running()
        self.assertEqual(self.presence(self.body(job_id=job["job_id"], lease_token=job["lease_token"])).status_code, 422)
        self.assertEqual(self.presence().status_code, 200)
        before = self.job_row()
        with closing(sqlite3.connect(self.config["database"])) as db:
            history = db.execute("SELECT * FROM events").fetchall()
        restarted = Store(self.config["database"], self.config, clock=lambda: self.now)
        self.assertEqual(restarted.status("jeongiryang")["workers"]["choigilung"]["presence"], "online")
        self.assertEqual(self.job_row(), before)
        with closing(sqlite3.connect(self.config["database"])) as db:
            self.assertEqual(db.execute("SELECT * FROM events").fetchall(), history)


class WorkerPresenceEmitterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = SimpleNamespace(engine="codex", state_dir=self.root)

    def test_metadata_has_no_contacts_auth_paths_or_model_calls(self):
        client = Mock()
        presence = WorkerPresence(client, self.config, clock=lambda: 1000)
        presence.update("idle")
        with patch("services.automation.worker.DockerExecutor") as docker, \
                patch("services.automation.worker.command") as command:
            presence.emit()
            presence.emit()
        docker.assert_not_called()
        command.assert_not_called()
        first, second = [call.args for call in client.request.call_args_list]
        self.assertEqual(first[0], "/v1/worker-presence")
        self.assertEqual((first[1]["sequence"], second[1]["sequence"]), (1, 2))
        self.assertIsNone(first[1]["job_id"])
        self.assertIsNone(first[1]["lease_token"])
        self.assertNotIn(str(self.root), json.dumps(first[1]))
        self.assertEqual(len(first[1]["runtime_sha256"]), 64)

    def test_failure_retains_only_error_type_and_does_not_run_or_modify_jobs(self):
        client = Mock()
        client.request.side_effect = RuntimeError("private-email-and-credential-must-not-leak")
        presence = WorkerPresence(client, self.config, clock=lambda: 1000)
        presence.emit()
        observed = json.loads((self.root / "last-presence-error.json").read_bytes())
        self.assertEqual(observed["error_type"], "RuntimeError")
        self.assertNotIn("private", json.dumps(observed))
        self.assertEqual(client.request.call_args.args[0], "/v1/worker-presence")

    def test_active_metadata_uses_only_current_job_id_lease_and_phase(self):
        client = Mock()
        presence = WorkerPresence(client, self.config, clock=lambda: 1000)
        presence.update("validating", {"job_id": "APPROVED-JOB", "lease_token": "fixture-lease",
                                      "prompt": "do not send", "token_file": "do not send"})
        presence.emit()
        body = client.request.call_args.args[1]
        self.assertEqual(body["phase"], "validating")
        self.assertEqual(body["job_id"], "APPROVED-JOB")
        self.assertNotIn("prompt", body)
        self.assertNotIn("token_file", body)

    def test_timer_keeps_idle_worker_observable_without_cli_model_or_claim_calls(self):
        reports = []
        received = threading.Event()

        def request(route, payload):
            reports.append((route, payload))
            if len(reports) >= 2:
                received.set()
            return {"accepted": True}

        client = SimpleNamespace(request=request)
        with WorkerPresence(client, self.config, clock=lambda: 1000, interval_seconds=0.01) as presence:
            presence.update("idle")
            self.assertTrue(received.wait(1))
        self.assertTrue(all(route == "/v1/worker-presence" for route, _ in reports))
        self.assertGreaterEqual(len(reports), 2)
        self.assertIsNone(client._presence)


if __name__ == "__main__":
    unittest.main()
