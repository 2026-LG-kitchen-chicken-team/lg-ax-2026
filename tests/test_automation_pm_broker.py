"""Live-adapter routing, receipt recovery and isolated driver boundary tests.

These transport fixtures do not prove real GitHub mutations or a Docker login.
They regress the fixed adapter's authority decisions before the recorded pilot.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.pm import AutonomousPM, PMError, fingerprint, stable_observation
from services.automation.pm_broker import DockerPMDriver, LiveGitHub, TrustedPMBroker
from services.automation.state import ACCOUNTS, PM, REPO
from services.automation.worker import exclusive_lock, session_records

BASE, HEAD, MERGED = "a" * 40, "b" * 40, "c" * 40
TASK, CAP, ACTION = "P2-PM-003", "client-unit", "pm-" + "d" * 40


def policy():
    return {"schema_version": 1, "repo": REPO, "pm_account": PM, "enabled": True,
        "allow_auto_merge": True, "allow_admin_bypass": True, "delegation_reference": "user implementation request",
        "automatic_merge_delegation": "user requested routine autonomous PM merge",
        "admin_bypass_delegation": "scoped delegated PM bypass", "limits": {},
        "required_ci_contexts": ["python", "web"], "independent_reviewers": [PM],
        "tasks": {"P2-PM-001": {"owner": PM, "issue_number": 17, "scope": "required", "requirement_ids": ["R17"], "depends_on": []},
                  TASK: {"owner": PM, "issue_number": 19, "scope": "required", "requirement_ids": ["R17"], "depends_on": ["P2-PM-001"]}},
        "capabilities": {CAP: {"task_id": TASK, "requirement_ids": ["R17"], "title": "client unit", "purpose": "required client regression",
            "allowed_paths": ["tests/test_pilot.py"], "validation_commands": [["python", "-m", "unittest", "tests.test_pilot"]],
            "required_checks": ["client-unit"], "acceptance": ["Actual client behavior"], "shared_resources": [], "completes_task": False}}}


class FakeController:
    def __init__(self):
        self.operator = True
        self.calls = []
        self.status = {"global_mode": "on", "members": {account: account == PM for account in ACCOUNTS}, "jobs": [],
                       "formal_snapshot": {"approved_commit": BASE, "tasks": {
                           "P2-PM-001": {"owner": PM, "status": "done"}, TASK: {"owner": PM, "status": "blocked"}}}}

    def request(self, route, body=None):
        self.calls.append((route, deepcopy(body)))
        if route == "/v1/operator-status":
            return {"account": PM, "operator": self.operator}
        if route == "/v1/status":
            return deepcopy(self.status)
        if route == "/v1/jobs":
            self.status["jobs"].append({key: body[key] for key in
                ("job_id", "owner", "task_id", "assignment_id", "base_commit", "title", "kind", "priority")})
            self.status["jobs"][-1].update(status="pending", result=None)
            return {"registered": True, "job_id": body["job_id"]}
        if route == "/v1/formal-snapshot":
            self.status["formal_snapshot"] = deepcopy(body)
            return {"accepted": True}
        if route.endswith("/reconcile"):
            job = next(row for row in self.status["jobs"] if row["job_id"] == route.split("/")[-2])
            job["status"] = "accepted" if body["action"] == "accept" else "blocked"
            return {"accepted": True}
        raise AssertionError(route)


class FakeGitHub:
    def __init__(self):
        self.login = PM
        self.main = BASE
        self.parent = BASE
        self.comments = []
        self.calls = []
        self.merged = False
        self.changed_files = [{"filename": "tests/test_pilot.py"}]
        self.head = HEAD

    def request(self, method, route, body=None):
        self.calls.append((method, route, deepcopy(body)))
        prefix = f"repos/{REPO}/"
        if route == "user":
            return {"login": self.login}
        path = route.removeprefix(prefix)
        if path == "commits/main":
            return {"sha": self.main}
        if path == "commits/" + MERGED:
            return {"parents": [{"sha": self.parent}]}
        if path == "pulls/81":
            return {"number": 81, "user": {"login": PM}, "draft": False,
                    "head": {"sha": self.head, "repo": {"full_name": REPO}},
                    "base": {"sha": BASE, "ref": "main", "repo": {"full_name": REPO}},
                    "state": "closed" if self.merged else "open", "merged": self.merged,
                    "merge_commit_sha": MERGED if self.merged else None, "mergeable": True,
                    "changed_files": len(self.changed_files)}
        if path.startswith("commits/") and "/check-runs" in path:
            return {"total_count": 2, "check_runs": [{"id": index, "name": context, "head_sha": self.head,
                "status": "completed", "conclusion": "success", "app": {"id": 15368}}
                for index, context in enumerate(("python", "web"))]}
        if path == "compare/" + BASE + "..." + HEAD:
            return {"merge_base_commit": {"sha": BASE}}
        if method == "GET" and path.startswith("issues/") and path.endswith("/assignees"):
            return []
        if method == "GET" and path == "issues/19":
            return {"state": "open", "html_url": f"https://github.com/{REPO}/issues/19"}
        if method == "POST" and path.endswith("/assignees"):
            return {"assignees": body["assignees"]}
        if method == "POST" and path.endswith("/comments"):
            record = {"id": len(self.comments) + 1, "body": body["body"], "user": {"login": PM},
                      "route": path, "html_url": f"https://github.com/{REPO}/issues/28#issuecomment-{len(self.comments) + 1}"}
            self.comments.append(record)
            if body["body"].startswith("/lgax-sync\n"):
                commit = json.loads(body["body"].split("```json\n", 1)[1].split("\n```", 1)[0])["commit"]
                self.request("POST", route, {"body": f"LGAX-RECEIPT {record['id']} ACCEPTED\ncommit `{commit}`"})
            return deepcopy(record)
        if method == "PATCH" and path.startswith("issues/comments/"):
            record = next(row for row in self.comments if row["id"] == int(path.rsplit("/", 1)[1]))
            record["body"] = body["body"]
            return deepcopy(record)
        raise AssertionError((method, route))

    def pages(self, route, **_kwargs):
        if "/statuses" in route:
            return []
        if "/files" in route:
            return deepcopy(self.changed_files)
        return deepcopy([row for row in self.comments if row["route"] == route.removeprefix(f"repos/{REPO}/")])

    def command(self, args, **_kwargs):
        self.calls.append(("COMMAND", list(args)))
        if args[:2] == ["pr", "diff"]:
            return b"diff --git a/tests/test_pilot.py b/tests/test_pilot.py\n+fixed client regression\n"
        if args[:2] == ["pr", "merge"]:
            self.merged, self.main = True, MERGED
            return b""
        raise AssertionError(args)


class FakeExecutor:
    def __init__(self, root):
        auth_root = root / "auth"
        auth_root.mkdir()
        (auth_root / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "inert-fixture-only"}}))
        self.config = SimpleNamespace(workspace_root=root / "execution", auth_root=auth_root, engine="codex", image="sha256:" + "a" * 64)
        self.config.workspace_root.mkdir()
        self.last_boundary = {"backend": "docker", "publisher_credentials_mounted": False}
        self.calls = []
        self.fail = False

    def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if kwargs.get("role") == "model":
            (kwargs["artifacts"] / "result.json").write_text(json.dumps({"result": "metadata decision"}), encoding="utf-8")
            kwargs["output"].write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}}) + "\n")
        else:
            kwargs["output"].write_text("actual validator fixture output")
        return SimpleNamespace(returncode=1 if self.fail else 0, stopped_reason=None)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        path = self.root / "policy.json"
        path.write_text(json.dumps(policy()))
        repo = self.root / "clone"
        repo.mkdir()
        self.config = {"policy_file": str(path), "policy_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "state_dir": str(self.root / "state"), "repository": str(repo),
            "controller_url": "http://127.0.0.1:18871", "controller_token_file": str(self.root / "unused")}
        self.github, self.controller, self.executor = FakeGitHub(), FakeController(), FakeExecutor(self.root)
        self.driver = SimpleNamespace(call=lambda *_args, **_kwargs: {
            "session_id": "pm-review-independent-session", "usage": {"input_tokens": 20, "output_tokens": 4},
            "result": {"outcome": "approve", "reason": "Reviewed exact diff and acceptance", "findings": []}})
        self.broker = TrustedPMBroker(self.config, github=self.github, controller=self.controller,
                                     executor=self.executor, driver=self.driver)
        self.git_calls = []
        def fixed_git(args, **_kwargs):
            self.git_calls.append(args)
            if args[0] == "remote":
                return f"https://github.com/{REPO}.git"
            if args[0] == "fetch":
                return ""
            if args[0] == "diff":
                return b"diff --git a/tests/test_pilot.py b/tests/test_pilot.py\n+fixed client regression\n"
            raise AssertionError(args)
        self.broker._git = fixed_git
        self.broker._readiness = lambda: {PM: {key: True for key in
            ("execution_isolation_verified", "publisher_separation_verified", "login_verified")}}
        self.broker._formal_source_matches = lambda *_args: None
        self.broker._project_approval = lambda commit: {"approval_url": "fixture", "receipt_url": "fixture", "commit": commit}
        self.gate = object.__new__(AutonomousPM)
        self.gate.policy = self.broker.policy

    def tearDown(self):
        self.temp.cleanup()

    def action(self, kind):
        observation = self.broker.observe(collect=False)
        decision = {"action": kind, "task_id": TASK, "capability_id": CAP,
                    "pr_number": 81 if kind != "assign" else None,
                    "head_commit": HEAD if kind != "assign" else None,
                    "reason": "Fixed required client unit", "instructions": ["Implement fixed behavior"] if kind in {"assign", "request_changes"} else []}
        return self.gate.validate_action(decision, observation), fingerprint(stable_observation(observation))

    def add_unit(self, merged=False):
        self.broker.state["units"]["initial-job"] = {"job_id": "initial-job", "task_id": TASK,
            "capability_id": CAP, "base_commit": BASE, "implementation_session_id": "implementation-session",
            "head": HEAD, "pr_number": 81}
        if merged:
            self.github.merged, self.github.main = True, MERGED
            self.controller.status["jobs"] = [{"job_id": "initial-job", "owner": PM, "task_id": TASK,
                "status": "review_requested", "result": {"pr_url": f"https://github.com/{REPO}/pull/81", "head_commit": HEAD}}]

    def evidence(self):
        pr = self.broker.observe(collect=False)["prs"][0]
        capability = self.broker.policy["capabilities"][CAP]
        self.broker._review(pr, capability, self.broker._unit(pr["number"])["implementation_session_id"])
        key = fingerprint({"commit": HEAD, "head": HEAD, "base": BASE, "capability": capability, "postmerge": False})
        self.broker.state["proofs"][key] = {"verified": True, "collector": "trusted_pm", "head": HEAD, "base": BASE,
            "commit": HEAD, "result": "passed", "checks": ["client-unit"], "evidence_sha256": "e" * 64,
            "capability_fingerprint": fingerprint(capability)}

    def test_worker_token_is_not_operator(self):
        self.controller.operator = False
        with self.assertRaises(PMError):
            self.broker.authenticate()

    def test_wrong_github_account_rejected(self):
        self.github.login = "unknownamed"
        with self.assertRaises(PMError):
            self.broker.authenticate()

    def test_trusted_git_resets_helpers_and_uses_fixed_gh_without_global_config(self):
        response = SimpleNamespace(returncode=0, stdout=b"fixed metadata\n")
        with patch("services.automation.pm_broker.subprocess.run", return_value=response) as run:
            observed = TrustedPMBroker._git(self.broker, ["fetch", "--no-tags", "origin", HEAD])
        argv = run.call_args.args[0]
        reset = argv.index("credential.helper=")
        fixed = argv.index("credential.helper=!gh auth git-credential")
        self.assertLess(reset, fixed)
        self.assertEqual(argv[reset - 1], "-c")
        self.assertEqual(argv[fixed - 1], "-c")
        self.assertEqual(argv[-4:], ["fetch", "--no-tags", "origin", HEAD])
        self.assertEqual(run.call_args.kwargs["cwd"], self.broker.repository)
        self.assertEqual(run.call_args.kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(run.call_args.kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(observed, "fixed metadata")

    def test_off_observation_does_not_run_review(self):
        self.add_unit()
        self.controller.status["global_mode"] = "off"
        value = self.broker.observe()
        self.assertEqual(value["global_mode"], "off")
        self.assertNotIn("independent_review", value["prs"][0])

    def test_actual_ci_and_rename_both_paths_collected(self):
        self.add_unit()
        self.github.changed_files = [{"filename": "tests/test_pilot.py", "previous_filename": "private/secret.txt"}]
        pr = self.broker.observe(collect=False)["prs"][0]
        self.assertIn("private/secret.txt", pr["changed_paths"])
        self.assertEqual({row["context"] for row in pr["ci"]}, {"python", "web"})

    def test_review_diff_is_collected_from_immutable_shas(self):
        self.add_unit()
        self.evidence()
        diff = next(args for args in self.git_calls if args[0] == "diff")
        self.assertEqual(diff[-3:], [BASE, HEAD, "--"])
        self.assertIn("--no-ext-diff", diff)
        self.assertIn("--no-textconv", diff)
        self.assertFalse(any(row[0] == "COMMAND" and row[1][:2] == ["pr", "diff"] for row in self.github.calls))

    def test_trusted_external_usage_contains_actual_review_once(self):
        self.add_unit()
        self.evidence()
        self.evidence()
        usage = self.broker.observe(collect=False)["external_usage"]
        self.assertEqual(usage["day"], {"model_calls": 1, "tokens": 24})
        self.assertEqual(usage["tasks"][TASK], {"model_calls": 1, "tokens": 24})

    def test_review_task_budget_never_resets_at_new_day_or_head(self):
        self.add_unit()
        self.broker.state["budgets"]["2000-01-01"] = {"calls": 2, "tokens": 60,
            "tasks": {TASK: 60}, "task_calls": {TASK: 2}}
        self.evidence()
        usage = self.broker.observe(collect=False)["external_usage"]
        self.assertEqual(usage["day"], {"model_calls": 1, "tokens": 24})
        self.assertEqual(usage["tasks"][TASK], {"model_calls": 3, "tokens": 84})
        self.broker.policy["limits"]["max_model_calls_per_task"] = 3
        self.broker.state["proofs"].clear()
        pr = self.broker.observe(collect=False)["prs"][0]
        with self.assertRaisesRegex(PMError, "budget exhausted"):
            self.broker._review(pr, self.broker.policy["capabilities"][CAP], "implementation-session")

    def test_accepted_reconciliation_recovery_retires_completed_unit(self):
        self.add_unit(merged=True)
        action = {"action": "reconcile", "pr_number": 81, "head_commit": HEAD, "merged_commit": MERGED,
                  "formal_done": False, "integration_evidence_sha256": "e" * 64}
        self.github.request("POST", f"repos/{REPO}/issues/28/comments", {"body": self.broker._marker(ACTION) + "\n" +
            json.dumps({"phase": "intent", "action": action})})
        self.controller.status["jobs"][0]["status"] = "accepted"
        self.assertEqual(self.broker.lookup(ACTION)["outcome"], "applied")
        self.assertTrue(self.broker.state["units"]["initial-job"]["reconciled"])
        observed = self.broker.observe(collect=False)
        self.assertEqual(observed["prs"], [])
        self.assertNotIn(CAP, observed["capabilities_ready"])

    def test_assignment_posts_real_transport_then_enqueues_without_mail_claim(self):
        action, expected = self.action("assign")
        receipt = self.broker.execute(ACTION, action, expected)
        self.assertEqual(receipt["outcome"], "applied")
        self.assertEqual(len(self.controller.status["jobs"]), 1)
        self.assertEqual(self.controller.status["jobs"][0]["task_id"], TASK)
        self.assertEqual(self.broker.lookup(ACTION), receipt)
        final = json.loads(self.github.comments[0]["body"].split("\n", 1)[1])
        self.assertEqual(final["details"]["mail_state"], "not_required_self_assignment")

    def test_assignment_adds_only_fresh_exact_session_paths_without_changing_policy(self):
        action, expected = self.action("assign")
        original = deepcopy(action)
        self.broker.execute(ACTION, action, expected)
        packet = next(body for route, body in self.controller.calls if route == "/v1/jobs")
        records = session_records(packet, PM)
        self.assertEqual(packet["allowed_paths"], ["tests/test_pilot.py", *records])
        self.assertEqual(action, original)
        self.assertEqual(self.broker.policy["capabilities"][CAP]["allowed_paths"], ["tests/test_pilot.py"])
        self.assertEqual(records, [f"docs/{directory}/세션/정이량/auto-{'d' * 40}.md"
                                   for directory in ("작업기록", "작업근거")])

    def test_actual_publication_records_pass_broker_and_exact_pm_gate_together(self):
        action, expected = self.action("assign")
        self.broker.execute(ACTION, action, expected)
        packet = next(body for route, body in self.controller.calls if route == "/v1/jobs")
        records = session_records(packet, PM)
        self.controller.status["jobs"][0].update(status="review_requested", result={
            "pr_url": f"https://github.com/{REPO}/pull/81", "head_commit": HEAD})
        self.github.changed_files = [{"filename": path, "status": "added"}
                                    for path in packet["allowed_paths"]]
        self.evidence()
        observed = self.broker.observe(collect=False)
        pr = observed["prs"][0]
        self.assertEqual(pr["job_id"], packet["job_id"])
        self.assertTrue(set(records) <= set(pr["added_paths"]))
        self.assertEqual(self.action("merge")[0]["expected_head"], HEAD)
        # Existing, renamed and deleted current-session records cannot become
        # new artifacts merely because a trusted job ID is present.
        for status in ("modified", "renamed", "removed"):
            with self.subTest(status=status):
                self.github.changed_files[1]["status"] = status
                with self.assertRaisesRegex(PMError, "new immutable session"):
                    self.action("merge")

    def test_observation_takes_job_identity_only_from_registered_host_unit(self):
        self.add_unit()
        self.controller.status["jobs"] = [{"job_id": "initial-job", "owner": PM, "task_id": TASK,
            "status": "review_requested", "result": {"job_id": "branch-claim", "pr_url": f"https://github.com/{REPO}/pull/81",
                                                       "head_commit": HEAD}}]
        self.assertEqual(self.broker.observe(collect=False)["prs"][0]["job_id"], "initial-job")

    def test_off_after_decision_refuses_before_remote_intent(self):
        action, expected = self.action("assign")
        self.controller.status["global_mode"] = "off"
        receipt = self.broker.execute(ACTION, action, expected)
        self.assertEqual(receipt["outcome"], "rejected")
        self.assertEqual(self.github.comments, [])

    def test_duplicate_action_lookup_does_not_reenqueue(self):
        action, expected = self.action("assign")
        first = self.broker.execute(ACTION, action, expected)
        second = self.broker.execute(ACTION, action, expected)
        self.assertEqual(first, second)
        self.assertEqual(len(self.controller.status["jobs"]), 1)

    def test_remote_intent_unknown_never_replayed(self):
        action, expected = self.action("assign")
        body = {"phase": "intent", "action": action, "job_id": "absent"}
        self.github.request("POST", f"repos/{REPO}/issues/28/comments", {
            "body": self.broker._marker(ACTION) + "\n" + json.dumps(body)})
        result = self.broker.execute(ACTION, action, expected)
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(self.controller.status["jobs"], [])

    def test_conditional_merge_uses_actual_head_and_observed_parent(self):
        self.add_unit()
        self.evidence()
        action, expected = self.action("merge")
        receipt = self.broker.execute(ACTION, action, expected)
        self.assertEqual(receipt["merge_commit"], MERGED)
        merge = next(row[1] for row in self.github.calls if row[0] == "COMMAND" and row[1][:2] == ["pr", "merge"])
        self.assertIn("--admin", merge)
        self.assertEqual(merge[-1], HEAD)

    def test_merge_base_race_halts_without_success_receipt(self):
        self.add_unit()
        self.evidence()
        action, expected = self.action("merge")
        self.github.parent = "f" * 40
        with self.assertRaisesRegex(PMError, "merge base raced"):
            self.broker.execute(ACTION, action, expected)

    def test_integration_executes_only_zero_auth_readonly_container(self):
        self.add_unit()
        pr = self.broker.observe(collect=False)["prs"][0]
        work = self.executor.config.workspace_root / "source" / "workspace"
        artifacts = work.parent / "artifacts"
        work.mkdir(parents=True)
        artifacts.mkdir()
        with patch.object(self.broker, "_source", return_value=(work, artifacts)):
            proof = self.broker._integration(pr, self.broker.policy["capabilities"][CAP])
        self.assertEqual(proof["result"], "passed")
        self.assertEqual(self.executor.calls[0][1]["role"], "validator")
        self.assertTrue(self.executor.calls[0][1]["readonly_workspace"])
        self.assertEqual(self.executor.calls[0][1]["env"], {})

    def test_review_cached_once_and_session_not_implementation(self):
        self.add_unit()
        pr = self.broker.observe(collect=False)["prs"][0]
        cap = self.broker.policy["capabilities"][CAP]
        first = self.broker._review(pr, cap, "implementation-session")
        second = self.broker._review(pr, cap, "implementation-session")
        self.assertEqual(first, second)
        self.assertNotEqual(first["reviewer_session_id"], first["implementation_session_id"])
        self.assertEqual(sum(value["calls"] for value in self.broker.state["budgets"].values()), 1)

    def test_notification_without_hook_is_only_prepared(self):
        state = self.broker._notify(ACTION, {"owner": "unknownamed"}, {"assignment_id": "fixture"})
        self.assertEqual(state, "prepared_unconfigured")
        outbox = json.loads((self.broker.state_dir / "outbox" / (ACTION + ".json")).read_text())
        self.assertFalse(outbox["email_sent"])

    def test_no_implicit_parent_done_in_reconcile(self):
        self.add_unit(merged=True)
        cap = self.broker.policy["capabilities"][CAP]
        key = fingerprint({"commit": MERGED, "head": HEAD, "base": BASE, "capability": cap, "postmerge": True})
        self.broker.state["proofs"][key] = {"verified": True, "collector": "trusted_pm", "head": HEAD, "base": BASE,
            "commit": MERGED, "result": "passed", "checks": ["client-unit"], "evidence_sha256": "e" * 64,
            "capability_fingerprint": fingerprint(cap)}
        action, expected = self.action("reconcile")
        receipt = self.broker.execute(ACTION, action, expected)
        self.assertEqual(receipt["outcome"], "applied")
        self.assertEqual(self.controller.status["formal_snapshot"]["tasks"][TASK]["status"], "blocked")
        self.assertEqual(self.controller.status["jobs"][0]["status"], "accepted")

    def test_revision_releases_finished_lock_and_next_job_uses_fixed_inert_diff(self):
        self.add_unit()
        self.controller.status["jobs"] = [{"job_id": "initial-job", "owner": PM, "task_id": TASK,
            "status": "review_requested", "result": {"pr_url": f"https://github.com/{REPO}/pull/81", "head_commit": HEAD}}]
        action, expected = self.action("request_changes")
        result = self.broker.execute(ACTION, action, expected)
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(self.controller.status["jobs"][0]["status"], "blocked")
        self.assertEqual(self.broker.observe(collect=False)["prs"], [])
        new_action, new_expected = self.action("assign")
        self.broker.execute("pm-" + "e" * 40, new_action, new_expected)
        packet = next(body for route, body in reversed(self.controller.calls) if route == "/v1/jobs")
        self.assertIn("previous_head", packet["prompt"])
        self.assertIn(HEAD, packet["prompt"])
        self.assertEqual(packet["base_commit"], BASE)

    def test_recover_revision_comment_without_release_remains_unknown(self):
        self.add_unit()
        self.controller.status["jobs"] = [{"job_id": "initial-job", "owner": PM, "task_id": TASK,
                                           "status": "review_requested", "result": None}]
        action, _expected = self.action("request_changes")
        self.github.request("POST", f"repos/{REPO}/issues/28/comments", {"body": self.broker._marker(ACTION) + "\n" +
            json.dumps({"phase": "intent", "action": action})})
        self.github.request("POST", f"repos/{REPO}/issues/81/comments", {"body": self.broker._marker(ACTION) + ":effect\nreview"})
        self.assertIsNone(self.broker.lookup(ACTION))
        self.assertEqual(self.controller.status["jobs"][0]["status"], "review_requested")

    def test_canary_metadata_not_boolean_alone_controls_readiness(self):
        proof = {"collector": "trusted_pm", "account": PM, "verified_at": time.time(),
                 "execution_isolation_verified": True, "publisher_separation_verified": True, "login_verified": True,
                 "authentication": {"verified": True, "source": "actual_isolated_cli", "engine": "codex"},
                 "boundary": {"proof_kind": "actual_harmless_container_not_mounted_boundary", "publisher_readable": True,
                    "containers": {role: {"workspace_readable": True, "publisher_canary_readable": False,
                        "docker_socket_readable": False, "ai_profile_readable": role == "model",
                        "external_network_reachable": False,
                        "observed_boundary": {"backend": "docker", "image_id": self.executor.config.image,
                                              "publisher_credentials_mounted": False}} for role in ("model", "validator")}}}
        path = self.root / "readiness.json"
        path.write_text(json.dumps(proof))
        self.broker.config["readiness_files"] = {PM: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.assertTrue(TrustedPMBroker._readiness(self.broker)[PM]["login_verified"])
        proof["boundary"]["containers"]["validator"]["ai_profile_readable"] = True
        path.write_text(json.dumps(proof))
        self.broker.config["readiness_files"][PM]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertFalse(TrustedPMBroker._readiness(self.broker)[PM]["execution_isolation_verified"])

    def test_merge_recovery_does_not_hide_base_race(self):
        self.add_unit()
        self.evidence()
        action, _expected = self.action("merge")
        self.github.merged, self.github.main, self.github.parent = True, MERGED, "f" * 40
        self.github.request("POST", f"repos/{REPO}/issues/28/comments", {"body": self.broker._marker(ACTION) + "\n" +
            json.dumps({"phase": "intent", "action": action})})
        self.assertIsNone(self.broker.lookup(ACTION))

    def test_project_approval_has_actual_ack_and_no_duplicate_command(self):
        first = TrustedPMBroker._project_approval(self.broker, MERGED)
        second = TrustedPMBroker._project_approval(self.broker, MERGED)
        self.assertEqual(first, second)
        self.assertEqual(sum(row["body"].startswith("/lgax-sync\n") for row in self.github.comments), 1)
        self.assertIn("receipt_url", first)

    def test_project_pending_ack_does_not_mean_approved(self):
        self.broker.config["project_receipt_wait_seconds"] = 0
        self.github.request("POST", f"repos/{REPO}/issues/28/comments", {"body": '/lgax-sync\n```json\n' +
            json.dumps({"commit": MERGED}, separators=(",", ":")) + '\n```'})
        self.github.comments = [row for row in self.github.comments if row["body"].startswith("/lgax-sync")]
        with self.assertRaisesRegex(PMError, "pending"):
            TrustedPMBroker._project_approval(self.broker, MERGED)

    def test_formal_source_is_data_and_cannot_upgrade_parent_status(self):
        def fake_git(args, **_kwargs):
            if args[0] == "fetch":
                return ""
            task_id = args[1].rsplit("/", 1)[1].removesuffix(".json")
            return json.dumps({"id": task_id, "owner": "정이량", "status": "done"})
        with patch.object(self.broker, "_git", side_effect=fake_git), self.assertRaisesRegex(PMError, "ownership/status"):
            TrustedPMBroker._formal_source_matches(self.broker, MERGED, self.controller.status["formal_snapshot"])


class DriverTests(unittest.TestCase):
    def test_worker_profile_lock_blocks_pm_without_model_or_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = FakeExecutor(root)
            driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
            with (exclusive_lock(executor.config.auth_root / "lgax-worker.lock"),
                  self.assertRaisesRegex(PMError, "already held")):
                driver({}, {}, 30)
            self.assertEqual(executor.calls, [])
            self.assertEqual(list((root / "state").rglob("proof.json")), [])
            # A later explicit operator call after release works; the driver
            # never retries the rejected call itself.
            self.assertEqual(driver({}, {}, 30)["usage"]["output_tokens"], 3)
            self.assertEqual(len(executor.calls), 1)

    def test_pm_holds_profile_lock_for_complete_model_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = FakeExecutor(root)
            normal_run = executor.run
            observed_contention = []
            def check_lock(argv, **kwargs):
                with self.assertRaises(OSError), exclusive_lock(executor.config.auth_root / "lgax-worker.lock"):
                    self.fail("PM did not retain Worker-compatible profile lock")
                observed_contention.append(True)
                return normal_run(argv, **kwargs)
            executor.run = check_lock
            driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
            driver({}, {}, 30)
            self.assertEqual(observed_contention, [True])
            with exclusive_lock(executor.config.auth_root / "lgax-worker.lock"):
                pass

    def test_structured_output_rejects_opaque_own_auth_or_jwt_before_proof(self):
        for secret in ("opaque-refresh-fixture-" + "x" * 48, "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20):
            with self.subTest(secret_kind="opaque" if secret.startswith("opaque") else "jwt"), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                executor = FakeExecutor(root)
                (executor.config.auth_root / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt",
                    "tokens": {"access_token": "inert-fixture-only", "refresh_token": secret}}))
                normal_run = executor.run
                def disclose(argv, normal_run=normal_run, secret=secret, **kwargs):
                    observed = normal_run(argv, **kwargs)
                    (kwargs["artifacts"] / "result.json").write_text(json.dumps({"nested": {"note": secret}}))
                    return observed
                executor.run = disclose
                driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
                with self.assertRaisesRegex(PMError, "private credentials"):
                    driver({}, {}, 30)
                self.assertEqual(list((root / "state").rglob("proof.json")), [])

    def test_api_auth_is_rejected_before_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = FakeExecutor(root)
            (executor.config.auth_root / "auth.json").write_text(json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "inert fixture"}))
            driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
            with self.assertRaisesRegex(PMError, "API fallback"):
                driver({}, {}, 30)
            self.assertEqual(executor.calls, [])

    def test_metadata_only_workspace_and_real_usage_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = FakeExecutor(root)
            driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
            result = driver({"eligible_actions": []}, {"type": "object"}, 30)
            self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 3})
            argv, options = executor.calls[0]
            self.assertIn("--skip-git-repo-check", argv)
            self.assertEqual(options["role"], "model")
            self.assertTrue(options["readonly_workspace"])
            self.assertEqual(list(options["cwd"].iterdir()), [])

    def test_isolation_failure_is_not_a_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = FakeExecutor(root)
            executor.fail = True
            driver = DockerPMDriver(executor, state_dir=root / "state", heartbeat=lambda: True)
            with self.assertRaises(PMError):
                driver({}, {}, 30)


class DestinationTests(unittest.TestCase):
    def test_arbitrary_url_and_mutation_routes_refused(self):
        github = LiveGitHub()
        for method, route in (("GET", "https://evil.invalid"), ("PUT", f"repos/{REPO}/contents/anything"),
                              ("PATCH", f"repos/{REPO}/branches/main/protection")):
            with self.subTest(route=route), self.assertRaises(PMError):
                github.request(method, route)

    def test_fixed_compare_route_is_allowed(self):
        github = LiveGitHub()
        with patch.object(github, "command", return_value=b'{"merge_base_commit":{"sha":"aaaa"}}') as call:
            github.request("GET", f"repos/{REPO}/compare/{BASE}...{HEAD}")
        self.assertTrue(call.called)


if __name__ == "__main__":
    unittest.main()
