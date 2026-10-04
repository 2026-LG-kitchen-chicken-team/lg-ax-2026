"""Read-only review dispatch, fixed-head publishing and restart-safe dedup tests."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from services.automation.controller import create_app
from services.automation.github_bridge import (
    STATUS_MARKER,
    Bridge,
    BridgeError,
    Controller,
    GitHub,
    exclusive_bridge_lock,
    related_task,
    review_comment,
)
from services.automation.state import REPO, Store, digest


def pr(number=73, author="choigilung", head="b" * 40, body="Closes #25"):
    return {"number": number, "state": "open", "draft": False, "user": {"login": author}, "body": body,
            "title": "Review this title", "head": {"sha": head, "repo": {"full_name": REPO}},
            "base": {"sha": "a" * 40, "ref": "main", "repo": {"full_name": REPO}}}


class FakeController:
    def __init__(self, mode="off"):
        self.status = {"global_mode": mode, "members": {"jeongiryang": False, "choigilung": False}, "jobs": [],
                       "formal_snapshot": {"approved_commit": "a" * 40, "tasks": {"P2-WEB-003": {"owner": "choigilung", "status": "doing"}}}}
        self.requests = []
        self.stop_before_publish = False
        self.fail = False

    def request(self, method, path, body=None):
        self.requests.append((method, path, copy.deepcopy(body)))
        if self.fail:
            raise BridgeError("private credential MUST NOT be included in returned diagnostics")
        if path == "/v1/status":
            status = copy.deepcopy(self.status)
            if self.stop_before_publish and len([r for r in self.requests if r[1] == "/v1/status"]) > 1:
                status["global_mode"] = "stop"
            return status
        if path == "/v1/jobs":
            self.status["jobs"].append({**body, "status": "pending"})
            return {"registered": True}
        if path == "/v1/model/api/tags":
            return {"models": [{"name": "qwen3:8b"}]}
        raise AssertionError((method, path))


class FakeGitHub:
    def __init__(self):
        self.account = "jeongiryang"
        self.prs = [pr()]
        self.comments = {28: [], 73: []}
        self.requests = []
        self.counter = 100

    def request(self, method, path, body=None):
        self.requests.append((method, path, copy.deepcopy(body)))
        base = f"/repos/{REPO}"
        if path == "/user":
            return {"login": self.account}
        if path.startswith(base + "/pulls?"):
            return copy.deepcopy(self.prs)
        if path.startswith(base + "/pulls/"):
            number = int(path.rsplit("/", 1)[1])
            return copy.deepcopy(next(item for item in self.prs if item["number"] == number))
        if "/issues/comments/" in path:
            cid = int(path.rsplit("/", 1)[1])
            found = next(c for values in self.comments.values() for c in values if c["id"] == cid)
            if method == "PATCH":
                found["body"] = body["body"]
            return copy.deepcopy(found)
        if "/issues/" in path and "/comments" in path:
            number = int(path.split("/issues/", 1)[1].split("/", 1)[0])
            if method == "GET":
                page = int(path.rsplit("page=", 1)[1])
                return copy.deepcopy(self.comments.get(number, [])[(page - 1) * 100:page * 100])
            if method == "POST":
                self.counter += 1
                comment = {"id": self.counter, "user": {"login": self.account}, "body": body["body"],
                           "html_url": f"https://github.com/{REPO}/issues/{number}#issuecomment-{self.counter}"}
                self.comments.setdefault(number, []).append(comment)
                return copy.deepcopy(comment)
        raise AssertionError((method, path))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = {"repo": REPO, "pm_account": "jeongiryang", "tasks": {
            "P2-WEB-003": {"account": "choigilung", "issue_number": 25},
            "P2-CORE-002": {"account": "unknownamed", "issue_number": 8}}}
        policy_path = self.root / "fixed-policy.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.config = {"policy_file": str(policy_path), "journal_file": str(self.root / "journal.json"),
                       "controller_url": "http://127.0.0.1:18871", "controller_token_file": str(self.root / "pm.token"),
                       "github_token_file": str(self.root / "github.token")}
        (self.root / "pm.token").write_text("private-controller-credential-0123456789", encoding="utf-8")
        (self.root / "github.token").write_text("ghp_private-token-for-test-0123456789", encoding="utf-8")
        self.controller = FakeController()
        self.github = FakeGitHub()
        self.bridge = Bridge(self.config, controller=self.controller, github=self.github, clock=lambda: 1000.0)

    def completed(self):
        return {"job_id": "review-pr73-" + "b" * 12, "kind": "review", "owner": "jeongiryang", "status": "completed_review",
                "task_id": "P2-WEB-003", "review_pr_url": f"https://github.com/{REPO}/pull/73", "review_head": "b" * 40,
                "result": {"review_result": {"summary": "Read-only inspection result", "intent_interpretation": "Check existing task",
                                             "findings": ["[P2] Check missing error branch"], "limitations": ["No tests executed"],
                                             "next_action": "Human PM should assess the finding", "changes": []}}}

    def mutations(self):
        return [call for call in self.github.requests if call[0] != "GET"]

    def test_off_default_mirrors_status_without_review_dispatch(self):
        result = self.bridge.tick()
        self.assertFalse(result["offline"])
        self.assertEqual(result["registered_reviews"], [])
        self.assertFalse(any(r[1] == "/v1/jobs" for r in self.controller.requests))
        self.assertEqual(len(self.github.comments[28]), 1)
        self.assertIn("OFF", self.github.comments[28][0]["body"])
        self.assertIn("수동 협업", self.github.comments[28][0]["body"])

    def test_on_known_owner_fixed_head_registers_readonly_job(self):
        self.controller.status["global_mode"] = "on"
        result = self.bridge.tick()
        self.assertEqual(result["registered_reviews"], ["review-pr73-" + "b" * 12])
        packet = next(r[2] for r in self.controller.requests if r[1] == "/v1/jobs")
        self.assertEqual(packet["owner"], "jeongiryang")
        self.assertEqual(packet["kind"], "review")
        self.assertEqual(packet["allowed_paths"], [])
        self.assertEqual(packet["review_head"], "b" * 40)
        self.assertEqual(packet["base_commit"], "a" * 40)
        self.assertEqual(packet["approved_snapshot_commit"], "a" * 40)
        self.assertNotIn("Closes #25", packet["prompt"])

    def test_events_deduplicated_across_restart(self):
        self.controller.status["global_mode"] = "on"
        self.bridge.tick()
        restarted = Bridge(self.config, controller=self.controller, github=self.github, clock=lambda: 1001)
        result = restarted.tick()
        self.assertEqual(result["registered_reviews"], [])
        self.assertEqual(len([r for r in self.controller.requests if r[1] == "/v1/jobs"]), 1)
        self.assertEqual(len(self.github.comments[28]), 1)

    def test_untrusted_fork_draft_wrong_base_missing_task_not_dispatched(self):
        self.controller.status["global_mode"] = "on"
        candidates = [pr(1, author="outsider"), {**pr(2), "draft": True}, pr(3, body="hello"), pr(4, body="Closes #8")]
        fork = pr(5)
        fork["head"]["repo"]["full_name"] = "outsider/fork"
        candidates.append(fork)
        wrong_base = pr(6)
        wrong_base["base"]["ref"] = "other"
        candidates.append(wrong_base)
        self.github.prs = candidates
        self.assertEqual(self.bridge.tick()["registered_reviews"], [])

    def test_related_task_supports_explicit_id_url_and_avoids_ambiguous_scope(self):
        self.assertEqual(related_task(pr(body="Task: P2-WEB-003"), self.policy), "P2-WEB-003")
        self.assertEqual(related_task(pr(body=f"Resolves https://github.com/{REPO}/issues/25"), self.policy), "P2-WEB-003")
        self.policy["tasks"]["P2-WEB-004"] = {"account": "choigilung", "issue_number": 26}
        self.assertIsNone(related_task(pr(body="Closes #25\nFixes #26"), self.policy))
        self.assertIsNone(related_task(pr(body="Closes https://github.com/other/repo/issues/25"), self.policy))

    def test_completed_review_publishes_once_off_allowed_never_approves(self):
        self.controller.status["jobs"] = [self.completed()]
        result = self.bridge.tick()
        self.assertEqual(result["posted_reviews"], [self.completed()["job_id"]])
        self.assertEqual(len(self.github.comments[73]), 1)
        self.assertIn("사람 PM 승인", self.github.comments[73][0]["body"])
        self.assertIn("b" * 40, self.github.comments[73][0]["body"])
        self.assertTrue(all("/comments" in request[1] for request in self.mutations()))
        self.bridge.tick()
        self.assertEqual(len(self.github.comments[73]), 1)
        self.assertFalse(any("/merge" in r[1] or "/reviews" in r[1] for r in self.github.requests))

    def test_stop_defers_review_publication_and_no_new_jobs(self):
        self.controller.status.update(global_mode="stop", jobs=[self.completed()])
        result = self.bridge.tick()
        self.assertEqual(result["posted_reviews"], [])
        self.assertEqual(result["registered_reviews"], [])
        self.assertEqual(len(self.github.comments[73]), 0)
        self.assertIn("STOP", self.github.comments[28][0]["body"])

    def test_stop_transition_rechecked_before_comment_mutation(self):
        self.controller.status["jobs"] = [self.completed()]
        self.controller.stop_before_publish = True
        self.assertEqual(self.bridge.tick()["posted_reviews"], [])
        self.assertEqual(len(self.github.comments[73]), 0)

    def test_changed_closed_or_draft_review_head_is_not_published(self):
        for change in ("changed", "closed", "draft"):
            with self.subTest(change=change):
                self.github.prs = [pr()]
                if change == "changed":
                    self.github.prs[0]["head"]["sha"] = "c" * 40
                elif change == "closed":
                    self.github.prs[0]["state"] = "closed"
                else:
                    self.github.prs[0]["draft"] = True
                self.controller.status["jobs"] = [self.completed()]
                self.assertEqual(self.bridge.tick()["posted_reviews"], [])
        self.assertEqual(len(self.github.comments[73]), 0)

    def test_existing_own_marker_recovers_crash_without_duplicate_comment(self):
        job = self.completed()
        marker, body = review_comment(job)
        self.github.comments[73] = [{"id": 77, "user": {"login": "jeongiryang"}, "body": marker + "\n" + body,
                                    "html_url": "https://example.invalid/already-posted"}]
        self.controller.status["jobs"] = [job]
        self.assertEqual(self.bridge.tick()["posted_reviews"], [job["job_id"]])
        self.assertEqual(len(self.github.comments[73]), 1)

    def test_marker_by_other_member_not_edited_or_trusted(self):
        self.github.comments[28] = [{"id": 55, "user": {"login": "choigilung"}, "body": STATUS_MARKER + " fake"}]
        self.bridge.tick()
        self.assertEqual(len(self.github.comments[28]), 2)
        self.assertFalse(any(request[0] == "PATCH" for request in self.mutations()))
        self.assertEqual(self.github.comments[28][0]["body"], STATUS_MARKER + " fake")

    def test_status_comment_updates_only_when_content_changes(self):
        self.bridge.tick()
        self.bridge.tick()
        self.assertEqual(len(self.mutations()), 1)
        self.controller.status["members"]["choigilung"] = True
        self.bridge.tick()
        self.assertEqual(len(self.github.comments[28]), 1)
        self.assertEqual(self.mutations()[-1][0], "PATCH")

    def test_foreign_status_comment_journal_reference_fails_closed(self):
        self.github.comments[28] = [{"id": 77, "user": {"login": "choigilung"}, "body": STATUS_MARKER}]
        self.bridge.journal["status_comment_id"] = 77
        self.assertTrue(self.bridge.tick()["offline"])
        self.assertFalse(self.mutations())

    def test_wrong_publisher_identity_refuses_all_mutations(self):
        self.github.account = "choigilung"
        result = self.bridge.tick()
        self.assertTrue(result["offline"])
        self.assertEqual(self.mutations(), [])
        self.assertEqual(self.controller.requests, [])

    def test_failure_backoff_and_sanitized_diagnostics_persist(self):
        self.controller.fail = True
        first = self.bridge.tick()
        second = self.bridge.tick()
        self.assertEqual(first["retry_after_seconds"], 15)
        self.assertEqual(second["retry_after_seconds"], 30)
        self.assertNotIn("credential", json.dumps(second))
        self.assertEqual(json.loads(self.bridge.journal_file.read_text())["failure_count"], 2)
        self.controller.fail = False
        self.assertFalse(self.bridge.tick()["offline"])
        self.assertEqual(self.bridge.journal["failure_count"], 0)

    def test_model_status_only_uses_tags_never_generate(self):
        self.bridge.config["model_gateway_enabled"] = True
        self.bridge.tick()
        self.assertTrue(any(r[1] == "/v1/model/api/tags" for r in self.controller.requests))
        self.assertFalse(any("generate" in r[1] for r in self.controller.requests))
        self.assertIn("조회 성공", self.github.comments[28][0]["body"])

    def test_review_comment_bounds_and_mentions_neutralized(self):
        job = self.completed()
        job["result"]["review_result"]["findings"] = ["@someone <!-- fake -->"]
        _, body = review_comment(job)
        self.assertNotIn("@someone", body)
        self.assertIn("＠someone", body)
        job["result"]["review_result"]["findings"] = ["x"] * 31
        with self.assertRaises(BridgeError):
            review_comment(job)

    def test_git_hub_transport_rejects_write_capabilities_and_redirects(self):
        seen = []

        def transport(request):
            seen.append(request)
            return httpx.Response(302, headers={"Location": "https://evil.invalid/steal"})

        github = GitHub(self.config, transport=httpx.MockTransport(transport))
        for method, route in (("PUT", f"/repos/{REPO}/pulls/73/merge"), ("POST", f"/repos/{REPO}/pulls/73/reviews"),
                              ("POST", "/repos/other/repo/issues/1/comments")):
            with self.assertRaises(BridgeError):
                github.request(method, route, {})
        with self.assertRaises(BridgeError):
            github.request("GET", "/user")
        self.assertEqual(len(seen), 1)
        self.assertEqual(str(seen[0].url), "https://api.github.com/user")

    def test_controller_http_requires_loopback_and_no_redirects(self):
        with self.assertRaises(BridgeError):
            Controller({**self.config, "controller_url": "http://remote.invalid"})
        with self.assertRaises(BridgeError):
            Controller({**self.config, "controller_url": "https://user:secret@host.invalid"})
        seen = []

        def transport(request):
            seen.append(request)
            return httpx.Response(302, headers={"Location": "https://evil.invalid"})

        controller = Controller(self.config, transport=httpx.MockTransport(transport))
        with self.assertRaises(BridgeError):
            controller.request("GET", "/v1/status")
        self.assertEqual(len(seen), 1)

    def test_disabled_dispatch_and_comment_publish_still_mirror(self):
        self.controller.status.update(global_mode="on", jobs=[self.completed()])
        self.bridge.config.update(enable_review_dispatch=False, enable_comment_publish=False)
        result = self.bridge.tick()
        self.assertEqual(result["registered_reviews"], [])
        self.assertEqual(result["posted_reviews"], [])
        self.assertEqual(len(self.github.comments[28]), 1)

    def test_invalid_fixed_policy_and_digest_fail_closed(self):
        bad = {**self.config, "policy_sha256": "f" * 64}
        with self.assertRaises(BridgeError):
            Bridge(bad, controller=self.controller, github=self.github)
        (self.root / "fixed-policy.json").write_text(json.dumps({**self.policy, "repo": "other/repo"}), encoding="utf-8")
        with self.assertRaises(BridgeError):
            Bridge(self.config, controller=self.controller, github=self.github)

    def test_real_controller_accepts_dispatch_packet_and_worker_opt_in_still_required(self):
        token = "operator-integration-test-private-0123456789"
        config = {"database": str(self.root / "actual.sqlite3"),
                  "token_digests": {"jeongiryang": digest(token)},
                  "formal_snapshot": self.controller.status["formal_snapshot"]}
        store = Store(config["database"], config)
        store.mode("jeongiryang", "on")
        with TestClient(create_app(config=config, store=store)) as client:
            class RealAdapter:
                def request(self, method, path, body=None):
                    response = client.request(method, path, json=body,
                                              headers={"Authorization": "Bearer " + token})
                    if response.status_code != 200:
                        raise BridgeError(f"controller rejected integration packet ({response.status_code})")
                    return response.json()

            bridge = Bridge({**self.config, "journal_file": str(self.root / "real-bridge.json")},
                            controller=RealAdapter(), github=self.github)
            result = bridge.tick()
            self.assertFalse(result["offline"])
            self.assertEqual(result["registered_reviews"], ["review-pr73-" + "b" * 12])
            self.assertIsNone(store.claim("jeongiryang")["job"])
            store.mode("jeongiryang", "on", "jeongiryang")
            job = store.claim("jeongiryang")["job"]
            self.assertEqual(job["kind"], "review")
            self.assertEqual(job["review_head"], "b" * 40)
            self.assertEqual(job["allowed_paths"], [])

    def test_bridge_singleton_lock_is_nonblocking_and_released(self):
        path = self.root / "journal.lock"
        with exclusive_bridge_lock(path), self.assertRaises(BridgeError), exclusive_bridge_lock(path):
            self.fail("second bridge process cannot own the same journal")
        with exclusive_bridge_lock(path):
            self.assertTrue(path.exists())

    def test_bridge_lock_blocks_another_process_and_recovers_after_exit(self):
        path = self.root / "cross-process.lock"
        code = (
            "import sys; from services.automation.github_bridge import exclusive_bridge_lock; "
            "guard=exclusive_bridge_lock(sys.argv[1]); guard.__enter__(); "
            "print('LOCKED',flush=True); sys.stdin.read(); guard.__exit__(None,None,None)"
        )
        child = subprocess.Popen([sys.executable, "-c", code, str(path)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(BridgeError), exclusive_bridge_lock(path):
                self.fail("second process must fail before metadata writes")
            child.communicate(input="exit", timeout=5)
            self.assertEqual(child.returncode, 0)
            with exclusive_bridge_lock(path):
                self.assertTrue(path.exists())
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
