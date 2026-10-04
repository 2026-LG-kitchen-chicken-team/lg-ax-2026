"""Fail-closed controls, ownership, fencing and authenticated opt-in tests."""
from __future__ import annotations

import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from services.automation.controller import create_app, github_enrollment_identity, load_config
from services.automation.state import ACCOUNTS, REPO, ControlError, Store, digest


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.tokens = {account: f"test-private-{account}-credential-0123456789" for account in ACCOUNTS}
        self.config = {
            "database": str(Path(self.temp.name) / "queue.sqlite3"),
            "token_digests": {account: digest(token) for account, token in self.tokens.items()},
            "formal_snapshot": {"approved_commit": "a" * 40, "approval_reference": "PM fixed snapshot",
                                "tasks": {f"TASK-{account}": {"owner": account, "status": "doing"} for account in ACCOUNTS}},
        }
        self.store = Store(self.config["database"], self.config, clock=self.clock)
        self.client = TestClient(create_app(config=self.config, store=self.store))
        self.addCleanup(self.client.close)

    def headers(self, account="jeongiryang"):
        return {"Authorization": "Bearer " + self.tokens[account]}

    def post(self, path, body, account="jeongiryang"):
        return self.client.post(path, json=body, headers=self.headers(account))

    def packet(self, job_id="J1", owner="choigilung", **values):
        path = {"choigilung": "apps/web/src/", "unknownamed": "packages/core/src/",
                "ginaginaring": "data/demo/", "jeongiryang": "docs/automation/"}.get(owner, "apps/web/src/")
        body = {"job_id": job_id, "owner": owner, "task_id": f"TASK-{owner}", "assignment_id": "ASSIGN-" + job_id,
                "base_commit": "a" * 40, "title": "Bounded approved change", "prompt": "Implement the approved task and verify it.",
                "approved": True, "approval_reference": "User explicitly approved this packet",
                "allowed_paths": [path], "shared_resources": [], "validation_commands": [["python", "-m", "unittest"]],
                "priority": 10, "max_attempts": 2, "timeout_seconds": 300}
        body.update(values)
        return body

    def enabled(self, account="choigilung"):
        self.assertEqual(self.post("/v1/mode", {"mode": "on"}).status_code, 200)
        self.assertEqual(self.post("/v1/mode", {"mode": "on", "member": account}, account).status_code, 200)

    def register(self, body=None):
        response = self.post("/v1/jobs", body or self.packet())
        self.assertEqual(response.status_code, 200, response.text)

    def claimed(self, account="choigilung"):
        response = self.post("/v1/claim", {}, account)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["job"]

    def running(self):
        self.register()
        self.enabled()
        return self.claimed()

    def test_defaults_and_restart_preserve_off(self):
        self.register()
        self.assertIsNone(self.claimed())
        status = self.store.status("jeongiryang")
        self.assertEqual(status["global_mode"], "off")
        self.assertFalse(any(status["members"].values()))
        restarted = Store(self.config["database"], self.config, clock=self.clock)
        self.assertEqual(restarted.status("jeongiryang")["global_mode"], "off")

    def test_health_minimal_and_all_status_authenticated(self):
        self.assertEqual(self.client.get("/health").json(), {"service": "lgax-automation", "ok": True})
        self.assertEqual(self.client.get("/v1/status").status_code, 401)
        response = self.client.get("/v1/status", headers={"Authorization": "Bearer wrong-credential-with-length"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("token_digests", response.text)

    def test_member_cannot_enable_global_or_someone_else(self):
        self.assertEqual(self.post("/v1/mode", {"mode": "on"}, "choigilung").status_code, 403)
        self.assertEqual(self.post("/v1/mode", {"mode": "on", "member": "unknownamed"}, "choigilung").status_code, 403)
        self.assertEqual(self.post("/v1/mode", {"mode": "on", "member": "choigilung"}, "choigilung").status_code, 200)
        self.assertEqual(self.post("/v1/mode", {"mode": "bad"}).status_code, 422)

    def test_global_and_member_opt_in_both_required(self):
        self.register()
        self.post("/v1/mode", {"mode": "on"})
        self.assertIsNone(self.claimed())
        self.post("/v1/mode", {"mode": "on", "member": "choigilung"}, "choigilung")
        self.assertIsNotNone(self.claimed())

    def test_pm_registration_only_immutable_duplicate(self):
        body = self.packet()
        self.assertEqual(self.post("/v1/jobs", body, "choigilung").status_code, 403)
        self.register(body)
        self.assertTrue(self.post("/v1/jobs", body).json()["duplicate"])
        body["prompt"] = "Changed scope requires new approval"
        self.assertEqual(self.post("/v1/jobs", body).status_code, 409)

    def test_unapproved_unknown_owner_and_task_rejected(self):
        for values in ({"approved": False}, {"owner": "outsider"}, {"task_id": "NOT-REGISTERED"},
                       {"task_id": "TASK-unknownamed"}, {"shell": "arbitrary command"}, {"base_commit": "main"}):
            with self.subTest(values=values):
                self.assertEqual(self.post("/v1/jobs", self.packet(**values)).status_code, 422)

    def test_protected_paths_traversal_glob_unicode_case_rejected(self):
        paths = ["private/key", "AGENTS.md", "ClAuDe.Md", ".github/workflows/agent.yml", "harness/phase2/state.json",
                 "services/automation/state.py", "scripts/phase2.py", "packages/contracts/a.json",
                 "apps/web/../private/key", "apps\\web\\a.ts", "/apps/web", "C:/data", ".", "apps/web/*",
                 "apps/web//src", "apps/web/．．/private", "apps/web/\x00file", "apps/web/ ", "apps/web"]
        for path in paths:
            with self.subTest(path=path):
                status = self.post("/v1/jobs", self.packet(allowed_paths=[path])).status_code
                # Broad apps/web itself is valid ownership, retained separately below.
                if path == "apps/web":
                    self.assertEqual(status, 200)
                else:
                    self.assertEqual(status, 422)

    def test_other_member_log_disallowed_own_log_allowed(self):
        self.assertEqual(self.post("/v1/jobs", self.packet(allowed_paths=["docs/작업기록/황대겸.md"])).status_code, 422)
        self.register(self.packet(allowed_paths=["docs/작업기록/최길웅.md", "docs/작업근거/최길웅.md"]))

    def test_bounded_attempt_timeout_commands_and_resources(self):
        for values in ({"max_attempts": 3}, {"max_attempts": True}, {"timeout_seconds": 3601},
                       {"validation_commands": []}, {"validation_commands": [["powershell", "evil"]]},
                       {"validation_commands": [["python", "test; rm"]]}, {"shared_resources": ["space resource"]}):
            with self.subTest(values=values):
                self.assertEqual(self.post("/v1/jobs", self.packet(**values)).status_code, 422)

    def test_atomic_concurrent_claims_one_winner(self):
        self.register()
        self.enabled()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.claim("choigilung"), range(8)))
        self.assertEqual(sum(result["job"] is not None for result in results), 1)
        self.assertEqual(self.store.status("jeongiryang")["jobs"][0]["attempt"], 1)

    def test_priority_one_active_job_per_member(self):
        self.register(self.packet("J-low", priority=100, allowed_paths=["apps/web/low.ts"]))
        self.register(self.packet("J-high", priority=1, allowed_paths=["apps/web/high.ts"]))
        self.enabled()
        self.assertEqual(self.claimed()["job_id"], "J-high")
        self.assertIsNone(self.claimed())

    def test_directory_and_resource_conflicts_across_owners(self):
        self.register(self.packet("J1", owner="unknownamed", allowed_paths=["packages/core/src/"]))
        self.register(self.packet("J2", owner="ginaginaring", allowed_paths=["packages/core/src/search.py"]))
        self.enabled("unknownamed")
        self.enabled("ginaginaring")
        self.assertIsNotNone(self.claimed("unknownamed"))
        self.assertIsNone(self.claimed("ginaginaring"))
        self.register(self.packet("J3", owner="choigilung", shared_resources=["gpu:0"]))
        self.register(self.packet("J4", owner="jeongiryang", shared_resources=["gpu:0"]))
        self.enabled("choigilung")
        self.enabled("jeongiryang")
        self.assertIsNotNone(self.claimed("choigilung"))
        self.assertIsNone(self.claimed("jeongiryang"))

    def test_expiry_orphans_and_retains_lock_until_explicit_reconciliation(self):
        job = self.running()
        self.clock.now += 121
        self.assertFalse(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])
        self.assertEqual(self.store.status("jeongiryang")["jobs"][0]["status"], "orphaned")
        self.assertIsNone(self.claimed())
        self.assertEqual(self.post("/v1/jobs/J1/reconcile", {"action": "requeue", "reason": "restart"}).status_code, 409)
        self.assertEqual(self.post("/v1/jobs/J1/reconcile", {"action": "requeue", "reason": "old process stopped",
                                                         "runner_stopped": True}).status_code, 200)
        new_job = self.claimed()
        self.assertEqual(new_job["attempt"], 2)
        self.assertNotEqual(new_job["lease_token"], job["lease_token"])
        self.assertEqual(self.post("/v1/jobs/J1/heartbeat", {"lease_token": job["lease_token"]}, "choigilung").status_code, 403)

    def test_heartbeat_has_fixed_absolute_execution_deadline(self):
        job = self.running()
        for _ in range(4):
            self.clock.now += 60
            self.assertTrue(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])
        self.clock.now += 61
        self.assertFalse(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])

    def test_wrong_actor_and_token_cannot_heartbeat_or_publish(self):
        job = self.running()
        for account, token in (("unknownamed", job["lease_token"]), ("choigilung", "fake-token")):
            self.assertEqual(self.post("/v1/jobs/J1/heartbeat", {"lease_token": token}, account).status_code, 403)
            self.assertEqual(self.post("/v1/jobs/J1/authorize-publish", {"lease_token": token}, account).status_code, 403)

    def test_off_midjob_revokes_publish_and_preserves_manual_mode(self):
        job = self.running()
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        self.post("/v1/mode", {"mode": "off"})
        self.assertFalse(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])
        self.assertEqual(self.post("/v1/jobs/J1/authorize-publish", {"lease_token": job["lease_token"]}, "choigilung").status_code, 409)
        finish = {"lease_token": job["lease_token"], "publish_token": cap["publish_token"],
                  "outcome": "review_requested", "summary": "Attempted late publication",
                  "pr_url": f"https://github.com/{REPO}/pull/100", "head_commit": "b" * 40}
        self.assertEqual(self.post("/v1/jobs/J1/finish", finish, "choigilung").status_code, 409)
        self.assertEqual(self.post("/v1/jobs/J1/finish", {"lease_token": job["lease_token"], "outcome": "blocked",
                                                       "summary": "Saved local checkpoint; OFF"}, "choigilung").status_code, 200)
        self.assertEqual(self.post("/v1/reservations", {"reservation_id": "MANUAL", "allowed_paths": ["apps/web/src/"]}, "choigilung").status_code, 200)

    def test_stop_and_reenable_does_not_resume_old_job(self):
        job = self.running()
        self.post("/v1/mode", {"mode": "stop"})
        self.post("/v1/mode", {"mode": "on"})
        self.assertIsNone(self.claimed())
        self.assertFalse(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])

    def test_member_off_leaves_other_member_enabled(self):
        self.enabled("choigilung")
        self.enabled("unknownamed")
        self.post("/v1/mode", {"mode": "off", "member": "choigilung"}, "choigilung")
        members = self.store.status("jeongiryang")["members"]
        self.assertFalse(members["choigilung"])
        self.assertTrue(members["unknownamed"])

    def test_capability_expiration_one_time_and_no_secrets_in_status(self):
        job = self.running()
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        finish = {"lease_token": job["lease_token"], "publish_token": cap["publish_token"], "outcome": "review_requested",
                  "summary": "Actual fixed PR result", "pr_url": f"https://github.com/{REPO}/pull/100", "head_commit": "b" * 40}
        self.clock.now += 21
        self.assertEqual(self.post("/v1/jobs/J1/finish", finish, "choigilung").status_code, 409)
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        finish["publish_token"] = cap["publish_token"]
        self.assertEqual(self.post("/v1/jobs/J1/finish", finish, "choigilung").status_code, 200)
        self.assertEqual(self.post("/v1/jobs/J1/finish", finish, "choigilung").status_code, 403)
        text = self.client.get("/v1/status", headers=self.headers()).text
        self.assertNotIn(job["lease_token"], text)
        self.assertNotIn(cap["publish_token"], text)
        self.assertNotIn("prompt", text)
        self.assertNotIn("lease_hash", text)

    def test_fake_done_bad_pr_and_short_head_rejected(self):
        job = self.running()
        for outcome in ("done", "accepted", "merged"):
            self.assertEqual(self.post("/v1/jobs/J1/finish", {"lease_token": job["lease_token"], "outcome": outcome,
                                                           "summary": "invalid"}, "choigilung").status_code, 422)
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        body = {"lease_token": job["lease_token"], "publish_token": cap["publish_token"], "outcome": "review_requested",
                "summary": "actual result", "pr_url": "https://github.com/other/repo/pull/1", "head_commit": "b" * 40}
        self.assertEqual(self.post("/v1/jobs/J1/finish", body, "choigilung").status_code, 422)
        body.update(pr_url=f"https://github.com/{REPO}/pull/1", head_commit="abc")
        self.assertEqual(self.post("/v1/jobs/J1/finish", body, "choigilung").status_code, 422)

    def test_retry_only_pm_bounded_two_attempts(self):
        job = self.running()
        for attempt in (1, 2):
            self.assertEqual(job["attempt"], attempt)
            self.store.finish("choigilung", "J1", {"lease_token": job["lease_token"], "outcome": "failed", "summary": "transient error"})
            body = {"action": "requeue", "reason": "PM reviewed transient error"}
            self.assertEqual(self.post("/v1/jobs/J1/reconcile", body, "choigilung").status_code, 403)
            response = self.post("/v1/jobs/J1/reconcile", body)
            self.assertEqual(response.status_code, 200 if attempt == 1 else 409)
            if attempt == 1:
                job = self.claimed()

    def test_dependencies_need_pm_accept_not_worker_submission(self):
        self.register()
        self.register(self.packet("J2", allowed_paths=["apps/web/other/"], dependency_job_ids=["J1"]))
        self.enabled()
        job = self.claimed()
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        self.store.finish("choigilung", "J1", {"lease_token": job["lease_token"], "publish_token": cap["publish_token"],
                          "outcome": "review_requested", "summary": "actual PR", "pr_url": f"https://github.com/{REPO}/pull/100", "head_commit": "b" * 40})
        self.assertIsNone(self.claimed())
        self.assertEqual(self.post("/v1/jobs/J1/reconcile", {"action": "accept", "reason": "reviewed"}).status_code, 422)
        self.assertEqual(self.post("/v1/jobs/J1/reconcile", {"action": "accept", "reason": "actual merge reviewed",
                                                         "integration_evidence": "Fixed merge SHA and integration run"}).status_code, 200)
        self.assertEqual(self.claimed()["job_id"], "J2")

    def test_pending_review_holds_paths_but_not_other_work_slot(self):
        job = self.running()
        cap = self.store.authorize_publish("choigilung", "J1", job["lease_token"])
        self.store.finish("choigilung", "J1", {"lease_token": job["lease_token"], "publish_token": cap["publish_token"],
                          "outcome": "review_requested", "summary": "actual PR", "pr_url": f"https://github.com/{REPO}/pull/100", "head_commit": "b" * 40})
        self.register(self.packet("J2", allowed_paths=["apps/web/src/overlap.ts"], priority=0))
        self.register(self.packet("J3", allowed_paths=["apps/web/docs/"]))
        self.assertEqual(self.claimed()["job_id"], "J3")

    def test_formal_dependencies_approved_snapshot_no_main_json_authority(self):
        self.register(self.packet(formal_dependencies=["TASK-unknownamed"], approved_snapshot_commit="a" * 40))
        self.enabled()
        self.assertIsNone(self.claimed())
        snapshot = copy.deepcopy(self.config["formal_snapshot"])
        snapshot["tasks"]["TASK-unknownamed"]["status"] = "done"
        self.assertEqual(self.post("/v1/formal-snapshot", snapshot, "unknownamed").status_code, 403)
        self.assertEqual(self.post("/v1/formal-snapshot", snapshot).status_code, 200)
        self.assertIsNotNone(self.claimed())

    def test_unknown_dependencies_and_mismatching_snapshot_rejected(self):
        for values in ({"dependency_job_ids": ["absent"]}, {"formal_task_dependencies": ["unknown"]},
                       {"approved_snapshot_commit": "b" * 40}, {"formal_task_dependencies": [], "formal_dependencies": ["TASK-unknownamed"]}):
            self.assertIn(self.post("/v1/jobs", self.packet(**values)).status_code, (409, 422))

    def test_review_readonly_fixed_head_no_publish(self):
        body = self.packet("REVIEW1", owner="jeongiryang", kind="review", allowed_paths=[],
                           review_head="b" * 40, review_pr_url=f"https://github.com/{REPO}/pull/73")
        self.register(body)
        self.enabled("jeongiryang")
        job = self.claimed("jeongiryang")
        self.assertEqual(job["review_head"], "b" * 40)
        self.assertEqual(job["validation_commands"], [])
        self.assertEqual(self.post("/v1/jobs/REVIEW1/authorize-publish", {"lease_token": job["lease_token"]}).status_code, 403)
        response = self.post("/v1/jobs/REVIEW1/finish", {"lease_token": job["lease_token"], "outcome": "completed_review",
                                                       "summary": "Read-only fixed-head review, no human approval",
                                                       "review_result": {"summary": "Fixed-head inspection finished",
                                                                         "intent_interpretation": "Review only, no code execution",
                                                                         "findings": ["[P2] A possible validation gap"],
                                                                         "limitations": ["Actual model was not executed"],
                                                                         "next_action": "PM should check this finding"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["status"], "completed_review")
        status = self.store.status("jeongiryang")["jobs"][0]
        self.assertEqual(status["review_head"], "b" * 40)
        self.assertEqual(status["review_pr_url"], f"https://github.com/{REPO}/pull/73")
        self.assertEqual(status["result"]["review_result"]["findings"], ["[P2] A possible validation gap"])

    def test_manual_off_reservation_locks_auto_and_other_owners(self):
        manual = {"reservation_id": "MANUAL1", "allowed_paths": ["packages/core/src/"], "shared_resources": ["gpu:0"]}
        self.assertEqual(self.post("/v1/reservations", manual, "unknownamed").status_code, 200)
        self.register(self.packet(owner="ginaginaring", allowed_paths=["packages/core/src/search.py"]))
        self.enabled("ginaginaring")
        self.assertIsNone(self.claimed("ginaginaring"))
        self.assertEqual(self.client.delete("/v1/reservations/MANUAL1", headers=self.headers("choigilung")).status_code, 403)
        self.assertEqual(self.client.delete("/v1/reservations/MANUAL1", headers=self.headers("unknownamed")).status_code, 200)
        self.assertIsNotNone(self.claimed("ginaginaring"))

    def test_manual_reservation_expiry_never_reassigns_old_work(self):
        self.post("/v1/reservations", {"reservation_id": "MANUAL", "allowed_paths": ["apps/web/src/"], "ttl_seconds": 30}, "choigilung")
        self.clock.now += 31
        self.register()
        self.enabled()
        self.assertIsNone(self.claimed())
        self.assertEqual(self.post("/v1/reservations/MANUAL/heartbeat", {}, "choigilung").status_code, 409)
        self.assertEqual(self.store.status("jeongiryang")["reservations"][0]["status"], "orphaned")

    def test_authentication_and_claim_body_identity_spoofing_rejected(self):
        self.assertEqual(self.post("/v1/claim", {"owner": "jeongiryang"}, "choigilung").status_code, 422)
        self.assertEqual(self.client.post("/v1/mode", json={"mode": "on"}).status_code, 401)

    def test_request_size_and_content_type_limits(self):
        response = self.client.post("/v1/jobs", content=b"x" * 65537,
                                    headers={**self.headers(), "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        response = self.client.post("/v1/mode", content="mode=on", headers=self.headers())
        self.assertEqual(response.status_code, 415)

    def test_enrollment_disabled_default_and_rotates_own_token(self):
        body = {"github_token": "ghp_private-test-token-0123456789"}
        self.assertEqual(self.client.post("/v1/enroll", json=body).status_code, 403)
        config = {**self.config, "enable_github_enrollment": True}
        with TestClient(create_app(config=config, store=self.store, enrollment_verifier=lambda _token: "choigilung")) as client:
            first = client.post("/v1/enroll", json=body).json()
            second = client.post("/v1/enroll", json=body).json()
            self.assertNotEqual(first["automation_token"], second["automation_token"])
            self.assertFalse(second["enabled"])
            self.assertEqual(client.get("/v1/status", headers={"Authorization": "Bearer " + first["automation_token"]}).status_code, 401)
            self.assertEqual(client.get("/v1/status", headers={"Authorization": "Bearer " + second["automation_token"]}).status_code, 200)
            self.assertEqual(client.get("/v1/status", headers=self.headers("choigilung")).status_code, 401)
            self.assertEqual(client.get("/v1/status", headers=self.headers()).status_code, 200)
            self.assertNotIn(body["github_token"], str(self.store.status("jeongiryang")))

    def test_enrollment_cannot_impersonate_pm(self):
        with self.assertRaises(ControlError):
            self.store.enroll("jeongiryang")
        with self.assertRaises(ControlError):
            self.store.enroll("outsider")

    def test_enrollment_actual_github_checks_fixed_destinations_and_write(self):
        fake = Mock()
        fake.__enter__ = Mock(return_value=fake)
        fake.__exit__ = Mock(return_value=False)
        user = Mock(status_code=200)
        user.json.return_value = {"login": "choigilung"}
        repo = Mock(status_code=200)
        repo.json.return_value = {"full_name": REPO, "permissions": {"push": True}}
        fake.get.side_effect = [user, repo]
        with patch("services.automation.controller.httpx.Client", return_value=fake) as constructor:
            self.assertEqual(github_enrollment_identity("ghp_private-test-token-0123456789"), "choigilung")
            self.assertFalse(constructor.call_args.kwargs["trust_env"])
            self.assertFalse(constructor.call_args.kwargs["follow_redirects"])
            self.assertEqual(fake.get.call_args_list[0].args[0], "https://api.github.com/user")
            self.assertEqual(fake.get.call_args_list[1].args[0], f"https://api.github.com/repos/{REPO}")
        repo.json.return_value = {"full_name": REPO, "permissions": {"push": False}}
        fake.get.side_effect = [user, repo]
        with patch("services.automation.controller.httpx.Client", return_value=fake), self.assertRaises(ControlError):
            github_enrollment_identity("ghp_private-test-token-0123456789")

    def test_config_no_shared_credentials(self):
        import json
        path = Path(self.temp.name) / "private-config.json"
        invalid = copy.deepcopy(self.config)
        invalid["token_digests"]["choigilung"] = invalid["token_digests"]["jeongiryang"]
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(path)

    def test_pm_worker_credential_cannot_perform_operator_actions(self):
        worker_token = "private-PM-worker-not-operator-0123456789"
        self.config["worker_token_digests"] = {"jeongiryang": digest(worker_token)}
        worker_headers = {"Authorization": "Bearer " + worker_token}
        with TestClient(create_app(config=self.config, store=self.store)) as client:
            for path, body in (("/v1/jobs", self.packet()), ("/v1/mode", {"mode": "on"}),
                               ("/v1/mode", {"mode": "on", "member": "choigilung"}),
                               ("/v1/formal-snapshot", self.config["formal_snapshot"]),
                               ("/v1/jobs/anything/reconcile", {"action": "requeue", "reason": "test"})):
                with self.subTest(path=path):
                    self.assertEqual(client.post(path, json=body, headers=worker_headers).status_code, 403)
            self.assertEqual(client.get("/v1/status", headers=worker_headers).status_code, 200)
            self.assertEqual(client.post("/v1/mode", json={"mode": "on", "member": "jeongiryang"}, headers=worker_headers).status_code, 200)
            self.assertEqual(client.post("/v1/claim", json={}, headers=worker_headers).status_code, 200)

    def test_own_session_paths_allowed_other_person_forbidden(self):
        self.register(self.packet(allowed_paths=["docs/작업기록/세션/최길웅/run-1.md", "docs/작업근거/세션/최길웅/run-1.md"]))
        bad = self.packet("J2", allowed_paths=["docs/작업기록/세션/신진하/run-1.md"])
        self.assertEqual(self.post("/v1/jobs", bad).status_code, 422)

    def test_pm_reassignment_revokes_running_job_and_old_packet_cannot_restart(self):
        job = self.running()
        snapshot = copy.deepcopy(self.config["formal_snapshot"])
        snapshot["tasks"]["TASK-choigilung"]["owner"] = "unknownamed"
        self.post("/v1/formal-snapshot", snapshot)
        self.assertFalse(self.store.heartbeat("choigilung", "J1", job["lease_token"])["continue"])
        self.assertEqual(self.post("/v1/jobs/J1/authorize-publish", {"lease_token": job["lease_token"]}, "choigilung").status_code, 409)
        self.store.reconcile("jeongiryang", "J1", {"action": "requeue", "reason": "old process stopped", "runner_stopped": True})
        self.assertIsNone(self.claimed())

    def test_completed_formal_task_cannot_start_stale_implementation(self):
        self.register()
        self.enabled()
        snapshot = copy.deepcopy(self.config["formal_snapshot"])
        snapshot["tasks"]["TASK-choigilung"]["status"] = "done"
        self.post("/v1/formal-snapshot", snapshot)
        self.assertIsNone(self.claimed())

    def test_review_output_bounded_plain_data_and_obvious_credentials_rejected(self):
        valid = {"summary": "Inspection completed", "intent_interpretation": "Read only", "findings": [],
                 "limitations": ["Not an approval"], "next_action": "Wait for PM"}
        self.assertEqual(self.store._review_result(valid), valid)
        for values in ({"findings": ["x"] * 31}, {"findings": [{"command": "run"}]},
                       {"summary": "ghp_" + "s" * 30}, {"next_action": "Bearer " + "t" * 32},
                       {"summary": "x" * 4001}, {"unknown": "x"}, {"findings": ["x" * 2000] * 15}):
            with self.subTest(values=list(values)), self.assertRaises(ControlError):
                self.store._review_result({**valid, **values})
        with self.assertRaises(ControlError):
            self.store._review_result(None)


if __name__ == "__main__":
    unittest.main()
