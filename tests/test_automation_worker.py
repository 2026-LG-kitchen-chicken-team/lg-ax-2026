"""Isolated policy/process tests; they do not prove live model or runner operation."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from services.automation.process import run_bounded
from services.automation.worker import (
    REPO,
    ControllerClient,
    WorkerConfig,
    allowed_path,
    check_scope,
    codex_argv,
    exclusive_lock,
    execute_job,
    isolated_environment,
    load_result,
    normalized_path,
    prepare_worktree,
    publish,
    send_project_report,
    session_records,
    validate_auth,
    validate_commands,
    validate_job,
)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repository = self.root / "repo"
        self.repository.mkdir()
        self.config = WorkerConfig(account="unknownamed", repository=self.repository,
            state_dir=self.root / "state", codex_home=self.root / "codex-private",
            controller_url="http://127.0.0.1:18875", token_file=self.root / "controller-token",
            isolation_acknowledged=True)
        self.job = {"job_id": "CORE-1", "owner": "unknownamed", "task_id": "P2-CORE-002",
            "assignment_id": "A1", "base_commit": "a" * 40, "kind": "implementation",
            "title": "Implement input validation", "prompt": "bounded task", "lease_token": "test-only",
            "timeout_seconds": 120, "attempt": 1, "allowed_paths": ["packages/core/", "tests/",
                "docs/작업기록/황대겸.md", "docs/작업근거/황대겸.md",
                "docs/작업기록/세션/황대겸/CORE-1.md", "docs/작업근거/세션/황대겸/CORE-1.md"],
            "validation_commands": [["python", "-m", "unittest", "discover", "-s", "tests"]]}

    def init_git(self):
        self.git_env = {**os.environ, "GIT_CONFIG_GLOBAL": str(self.root / "empty-config"),
                        "GIT_CONFIG_NOSYSTEM": "1"}
        (self.root / "empty-config").touch()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for name in ("packages/core/a.py", "packages/core/removed.py", "AGENTS.md"):
            path = self.repository / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "isolated fixture")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repository, env=self.git_env,
                              capture_output=True, check=True, timeout=10)

    def test_unowned_or_unbounded_jobs_refused(self):
        validate_job(self.job, "unknownamed")
        for update in ({"owner": "jeongiryang"}, {"base_commit": "main"},
                       {"job_id": "../../escape"}, {"timeout_seconds": 99999},
                       {"validation_commands": []}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_job({**self.job, **update}, "unknownamed")

    def test_codex_container_uses_outer_boundary_native_keeps_inner_sandbox(self):
        stage = self.root / "argv-artifacts"
        stage.mkdir()
        for kind, native_mode in (("implementation", "workspace-write"), ("review", "read-only")):
            job = {**self.job, "kind": kind}
            with patch("services.automation.worker.shutil.which", return_value="codex"):
                native = codex_argv(self.config, job, stage)
            self.assertEqual(native[native.index("--sandbox") + 1], native_mode)
            container = codex_argv(replace(self.config, executor_image="sha256:" + "a" * 64), job, stage)
            self.assertEqual(container[container.index("--sandbox") + 1], "danger-full-access")
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", container)

    def test_review_requires_fixed_head(self):
        with self.assertRaises(ValueError):
            validate_job({**self.job, "kind": "review"}, "unknownamed")
        validate_job({**self.job, "kind": "review", "review_head": "b" * 40}, "unknownamed")

    def test_moved_main_blocks_implementation_but_not_fixed_head_readonly_review(self):
        self.init_git()
        review = {**self.job, "kind": "review", "review_head": "c" * 40,
                  "review_pr_url": f"https://github.com/{REPO}/pull/999"}
        run = self.root / "stale-test"
        run.mkdir()
        calls = []

        def fake_git(config, argv, cwd=None):
            calls.append(argv)
            if argv == ["remote", "get-url", "origin"]:
                return f"https://github.com/{REPO}.git"
            if argv == ["rev-parse", "origin/main"]:
                return "b" * 40  # Main advanced while this task was waiting.
            if argv[:2] == ["rev-parse", "--verify"]:
                return review["review_head"]
            if argv[:2] == ["worktree", "add"]:
                Path(argv[-2]).mkdir()
            if argv in (["rev-parse", "--git-common-dir"], ["rev-parse", "--git-dir"]):
                return str(self.repository / ".git")
            return ""

        with patch("services.automation.worker.git", side_effect=fake_git), self.assertRaisesRegex(ValueError, "stale"):
            prepare_worktree(self.config, self.job, run)
        calls.clear()
        with patch("services.automation.worker.git", side_effect=fake_git), \
                patch("services.automation.worker.check_review_head") as verify:
            workspace, branch, head, _paths, _digests = prepare_worktree(self.config, review, run)
        self.assertEqual(head, review["review_head"])
        self.assertTrue(workspace.is_dir())
        self.assertTrue(branch.endswith("-a1-g1"))
        self.assertNotIn(["rev-parse", "origin/main"], calls)
        verify.assert_called_once_with(self.config, review)

    def review_git_fixture(self):
        self.init_git()
        self.git("branch", "-M", "main")
        (self.repository / "packages/core/a.py").write_text("review\n", encoding="utf-8")
        self.git("commit", "-qam", "approved review fixture")
        review_head = self.git("rev-parse", "HEAD").stdout.decode().strip()
        (self.repository / "packages/core/a.py").write_text("main\n", encoding="utf-8")
        self.git("commit", "-qam", "unrelated main fixture")
        main_head = self.git("rev-parse", "HEAD").stdout.decode().strip()
        remote = self.root / "remote.git"
        self.git("clone", "--bare", str(self.repository), str(remote))
        self.git("--git-dir", str(remote), "update-ref", "refs/pull/999/head", review_head)
        self.git("remote", "add", "origin", f"https://github.com/{REPO}.git")
        review = {**self.job, "kind": "review", "review_head": review_head,
                  "review_pr_url": f"https://github.com/{REPO}/pull/999",
                  "attempt": 2, "lease_generation": 3}
        return review, remote, main_head

    def test_review_fetch_is_pinned_while_concurrent_fetch_changes_fetch_head(self):
        review, remote, main_head = self.review_git_fixture()
        run = self.root / "concurrent-fetch"
        run.mkdir()
        calls, concurrent_errors = [], []
        before_other_fetch, allow_other_fetch, other_fetch_finished = (
            threading.Event(), threading.Event(), threading.Event())

        def metadata_fetch():
            try:
                if not allow_other_fetch.wait(10):
                    raise TimeoutError("review fetch did not complete")
                self.git("fetch", "--no-tags", str(remote), "main")
            except (OSError, subprocess.SubprocessError) as exc:
                concurrent_errors.append(exc)
            finally:
                other_fetch_finished.set()

        metadata = threading.Thread(target=metadata_fetch)
        metadata.start()
        self.addCleanup(metadata.join, 10)

        def fixture_git(config, argv, cwd=None):
            calls.append(argv)
            actual = list(argv)
            if actual[0] == "fetch":
                actual[actual.index("origin")] = str(remote)
            result = subprocess.run(["git", *actual], cwd=cwd or self.repository,
                                    env=self.git_env, capture_output=True, check=True, timeout=10)
            if argv[0] == "fetch" and argv[-1].startswith("refs/pull/999/head"):
                # The review fetch must preserve a different caller's FETCH_HEAD.
                before_other_fetch.set()
                if "--no-write-fetch-head" in argv:
                    self.assertEqual(self.git("rev-parse", "FETCH_HEAD").stdout.decode().strip(), main_head)
                self.git("update-ref", "FETCH_HEAD", review["review_head"])
                allow_other_fetch.set()
                self.assertTrue(other_fetch_finished.wait(10))
                self.assertFalse(concurrent_errors)
            return result.stdout.decode().strip()

        metadata_response = json.dumps({"headRefOid": review["review_head"],
                                        "baseRefName": "main", "state": "OPEN"})
        try:
            with patch("services.automation.worker.git", side_effect=fixture_git), \
                    patch("services.automation.worker.command", return_value=metadata_response) as remote_guard:
                workspace, branch, head, _paths, _digests = prepare_worktree(self.config, review, run)
        finally:
            allow_other_fetch.set()
            metadata.join(10)
        self.assertFalse(metadata.is_alive())
        self.assertFalse(concurrent_errors)
        self.assertTrue(before_other_fetch.is_set())
        self.assertEqual(self.git("rev-parse", "FETCH_HEAD").stdout.decode().strip(), main_head)
        review_ref = "refs/lgax/reviews/unknownamed/CORE-1/a2-g3"
        self.assertEqual(self.git("rev-parse", "--verify", review_ref).stdout.decode().strip(), head)
        self.assertEqual(self.git("cat-file", "-t", head).stdout.decode().strip(), "commit")
        checked_out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace,
                                     env=self.git_env, capture_output=True, check=True, timeout=10)
        self.assertEqual(checked_out.stdout.decode().strip(), review["review_head"])
        self.assertEqual(head, review["review_head"])
        self.assertTrue(branch.endswith("-a2-g3"))
        self.assertIn(["fetch", "--no-tags", "--no-write-fetch-head", "origin",
                       f"refs/pull/999/head:{review_ref}"], calls)
        self.assertNotIn(["rev-parse", "FETCH_HEAD"], calls)
        remote_guard.assert_called_once()

    def test_stale_remote_review_head_is_rejected_before_review_fetch(self):
        review, _remote, main_head = self.review_git_fixture()
        run = self.root / "stale-remote"
        run.mkdir()
        calls = []

        def fixture_git(config, argv, cwd=None):
            calls.append(argv)
            if argv == ["remote", "get-url", "origin"]:
                return f"https://github.com/{REPO}.git"
            return ""

        metadata_response = json.dumps({"headRefOid": main_head, "baseRefName": "main", "state": "OPEN"})
        with patch("services.automation.worker.git", side_effect=fixture_git), \
                patch("services.automation.worker.command", return_value=metadata_response), \
                self.assertRaisesRegex(ValueError, "review head changed"):
            prepare_worktree(self.config, review, run)
        self.assertFalse(any(argv[0] == "worktree" or "--no-write-fetch-head" in argv for argv in calls))
        self.assertFalse((run / "worktree").exists())

    def test_fetched_review_head_must_match_approved_head(self):
        review, remote, main_head = self.review_git_fixture()
        self.git("--git-dir", str(remote), "update-ref", "refs/pull/999/head", main_head)
        run = self.root / "changed-during-fetch"
        run.mkdir()

        def fixture_git(config, argv, cwd=None):
            actual = list(argv)
            if actual[0] == "fetch":
                actual[actual.index("origin")] = str(remote)
            result = subprocess.run(["git", *actual], cwd=cwd or self.repository,
                                    env=self.git_env, capture_output=True, check=True, timeout=10)
            return result.stdout.decode().strip()

        metadata_response = json.dumps({"headRefOid": review["review_head"],
                                        "baseRefName": "main", "state": "OPEN"})
        with patch("services.automation.worker.git", side_effect=fixture_git), \
                patch("services.automation.worker.command", return_value=metadata_response), \
                self.assertRaisesRegex(ValueError, "fetch no longer matches approved"):
            prepare_worktree(self.config, review, run)
        self.assertFalse((run / "worktree").exists())

    def test_public_worker_example_has_supported_fields_and_safe_offline_default(self):
        source = Path(__file__).resolve().parents[1] / "services/automation/worker.example.json"
        example = json.loads(source.read_text(encoding="utf-8"))
        self.assertLessEqual(set(example), set(WorkerConfig.__dataclass_fields__))
        self.assertIs(example["isolation_acknowledged"], False)
        for field, value in (("repository", self.repository), ("state_dir", self.config.state_dir),
                             ("codex_home", self.config.codex_home), ("token_file", self.config.token_file),
                             ("execution_root", self.root / "execution")):
            example[field] = str(value)
        # The example intentionally cannot be deployed by merely copying it.
        config_file = self.root / "worker-config.json"
        config_file.write_text(json.dumps(example))
        with self.assertRaisesRegex(ValueError, "no native fallback"):
            WorkerConfig.load(config_file)
        example["isolation_acknowledged"] = True
        example["executor_image"] = "sha256:" + "a" * 64
        example["execution_root"] = str(self.root / "execution")
        config_file.write_text(json.dumps(example))
        actual = WorkerConfig.load(config_file)
        self.assertEqual(actual.model_gateway_url, "http://127.0.0.1:18873")
        self.assertEqual(actual.repository, self.repository)

    def test_sensitive_and_other_member_paths_are_denied(self):
        paths = ["docs/", "packages/", "tests/", "AGENTS.md", "private/", "scripts/", "services/"]
        for name in ("AGENTS.md", "CLAUDE.md", ".github/workflows/a.yml", "private/key",
                     "packages/contracts/schema.json", "harness/phase2/tasks.json", "scripts/main.py",
                     "services/automation/state.py", "data/.env.local", "docs/pm/assignments/a.json",
                     "docs/작업기록/정이량.md", "DOCS/작업근거/신진하.md", "tests/AGENTS.md"):
            with self.subTest(name=name):
                self.assertFalse(allowed_path(name, paths, "unknownamed"))
        self.assertTrue(allowed_path("packages/core/a.py", paths, "unknownamed"))
        self.assertTrue(allowed_path("docs/작업기록/황대겸.md", paths, "unknownamed"))

    def test_paths_are_bounded_at_directory_boundary(self):
        self.assertTrue(allowed_path("packages/core/a.py", ["packages/core"], "unknownamed"))
        self.assertFalse(allowed_path("packages/core-extra/a.py", ["packages/core"], "unknownamed"))
        for name in ("../secret", "/secret", "C:/secret", "a\\b", "a/.git/config"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                normalized_path(name)

    def test_staged_and_untracked_protected_changes_refused(self):
        self.init_git()
        (self.repository / "AGENTS.md").write_text("changed", encoding="utf-8")
        self.git("add", "AGENTS.md")
        with self.assertRaises(ValueError):
            check_scope(self.repository, self.job, "unknownamed", require_records=False)

    def test_deletion_and_both_rename_sides_are_checked(self):
        self.init_git()
        (self.repository / "packages/core/removed.py").unlink()
        (self.repository / "packages/core/a.py").rename(self.repository / "outside.py")
        with self.assertRaises(ValueError):
            check_scope(self.repository, self.job, "unknownamed", require_records=False)
        (self.repository / "outside.py").rename(self.repository / "packages/core/renamed.py")
        paths = check_scope(self.repository, self.job, "unknownamed", require_records=False)
        self.assertEqual(set(paths), {"packages/core/removed.py", "packages/core/a.py", "packages/core/renamed.py"})

    @unittest.skipIf(os.name == "nt", "Windows symlink creation depends on developer mode")
    def test_symlink_to_external_content_is_refused(self):
        self.init_git()
        external = self.root / "outside.txt"
        external.write_text("private fixture")
        (self.repository / "packages/core/link.py").symlink_to(external)
        with self.assertRaises(ValueError):
            check_scope(self.repository, self.job, "unknownamed", require_records=False)

    def test_required_detailed_records_cannot_be_skipped(self):
        self.init_git()
        (self.repository / "packages/core/a.py").write_text("change")
        with self.assertRaisesRegex(ValueError, "detailed session"):
            check_scope(self.repository, self.job, "unknownamed")
        for record in session_records(self.job, "unknownamed"):
            path = self.repository / record
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("CORE-1: Original request; interpretation; actual changes; actual check conditions; "
                            "observed failures; remaining limits; PM review pending; explicit next action")
        self.assertEqual(len(check_scope(self.repository, self.job, "unknownamed")), 3)

    def test_existing_session_history_cannot_be_overwritten(self):
        self.init_git()
        records = session_records(self.job, "unknownamed")
        for record in records:
            path = self.repository / record
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("CORE-1 immutable request and actual evidence, " * 5)
        self.git("add", ".")
        self.git("commit", "-qm", "preserved fixture history")
        for record in records:
            (self.repository / record).write_text("CORE-1 rewritten request and fabricated evidence, " * 5)
        with self.assertRaisesRegex(ValueError, "history"):
            check_scope(self.repository, self.job, "unknownamed")

    def test_broad_own_session_scope_cannot_rewrite_another_session(self):
        self.init_git()
        path = self.repository / "docs/작업기록/세션/황대겸/OLDER-JOB.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserve a different session")
        job = {**self.job, "allowed_paths": self.job["allowed_paths"] + ["docs/작업기록/세션/황대겸/"]}
        with self.assertRaisesRegex(ValueError, "another immutable session"):
            check_scope(self.repository, job, "unknownamed", require_records=False)

    def test_indexed_symlink_and_submodule_refused_without_os_symlink_privilege(self):
        self.init_git()
        target = self.root / "blob.txt"
        target.write_text("../../private/fixture")
        blob = self.git("hash-object", "-w", str(target)).stdout.decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{blob},packages/core/link.py")
        with self.assertRaisesRegex(ValueError, "indexed symlink"):
            check_scope(self.repository, self.job, "unknownamed", require_records=False)
        self.git("update-index", "--force-remove", "packages/core/link.py")
        head = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},packages/core/submodule")
        with self.assertRaisesRegex(ValueError, "submodule"):
            check_scope(self.repository, self.job, "unknownamed", require_records=False)

    def test_review_cannot_modify_files(self):
        self.init_git()
        (self.repository / "packages/core/a.py").write_text("change")
        with self.assertRaisesRegex(ValueError, "read-only"):
            check_scope(self.repository, {**self.job, "kind": "review"}, "unknownamed")

    def test_model_and_tests_do_not_receive_publisher_credentials(self):
        run = self.root / "run"
        run.mkdir()
        source = {"PATH": "fixture", "GH_TOKEN": "fixture", "GITHUB_TOKEN": "fixture",
                  "OPENAI_API_KEY": "fixture", "CODEX_API_KEY": "fixture", "LGAX_AUTH": "fixture",
                  "SSH_AUTH_SOCK": "fixture", "ANTHROPIC_API_KEY": "fixture", "MAIL_PASSWORD": "fixture",
                  "AUTOMATION_TOKEN": "fixture", "HF_TOKEN": "fixture"}
        env = isolated_environment(self.config, run, source)
        for key in source:
            if key != "PATH":
                self.assertNotIn(key, env)
        self.assertEqual(env["CODEX_HOME"], str(self.config.codex_home))
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertNotEqual(env["GH_CONFIG_DIR"], os.environ.get("GH_CONFIG_DIR"))

    def test_child_gateway_environment_is_consumed_by_actual_structured_model_client(self):
        from lgax_core.model_client import StructuredModelClient

        from services.automation.model_gateway import DIGEST, MODEL

        run = self.root / "model-run"
        run.mkdir()
        config = replace(self.config, model_gateway_url="http://127.0.0.1:18873")
        source = {"LGAX_MODEL_ENDPOINT": "https://unapproved.example", "LGAX_MODEL_ID": "wrong-model",
                  "LGAX_MODEL_DIGEST": "wrong-digest", "LGAX_MODEL_API_KEY": "fixture-private",
                  "LGAX_MODEL_MAX_OUTPUT_TOKENS": "99999", "GITHUB_TOKEN": "fixture-private"}
        env = isolated_environment(config, run, source)
        self.assertNotIn("LGAX_MODEL_API_KEY", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env["LGAX_MODEL_ADAPTER"], "ollama")
        self.assertEqual(env["LGAX_MODEL_ID"], MODEL)
        self.assertEqual(env["LGAX_MODEL_DIGEST"], DIGEST)
        # Configuration construction makes no real model request.
        with StructuredModelClient.from_env(env) as client:
            self.assertEqual(client.adapter.config.endpoint, "http://127.0.0.1:18873")
            self.assertEqual(client.adapter.config.max_output_tokens, 256)
            self.assertEqual(client.adapter.config.context_tokens, 4096)

    def test_gateway_settings_cannot_override_model_pin_or_inherit_unsafe_budgets(self):
        source = Path(__file__).resolve().parents[1] / "services/automation/worker.example.json"
        example = json.loads(source.read_text(encoding="utf-8"))
        for field, value in (("repository", self.repository), ("state_dir", self.config.state_dir),
                             ("codex_home", self.config.codex_home), ("token_file", self.config.token_file)):
            example[field] = str(value)
        example["isolation_acknowledged"] = True
        config_file = self.root / "unsafe-gateway-config.json"
        for unsafe in ({"model_gateway_url": "http://localhost:18873"},
                       {"model_gateway_url": "http://127.0.0.1:9999"},
                       {"model_max_output_tokens": 8192, "model_context_tokens": 4096},
                       {"model_max_output_tokens": True}):
            config_file.write_text(json.dumps({**example, **unsafe}))
            with self.assertRaises(ValueError):
                WorkerConfig.load(config_file)

    def test_authentication_is_chatgpt_only_without_secret_echo(self):
        self.config.codex_home.mkdir()
        auth = self.config.codex_home / "auth.json"
        auth.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "fixture-only"}}))
        validate_auth(self.config)
        auth.write_text(json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "fixture-key"}))
        with self.assertRaises(ValueError) as caught:
            validate_auth(self.config)
        self.assertNotIn("fixture-key", str(caught.exception))

    def test_custom_provider_is_not_silently_used(self):
        self.config.codex_home.mkdir()
        (self.config.codex_home / "auth.json").write_text(json.dumps({
            "auth_mode": "chatgpt", "tokens": {"access_token": "fixture"}}))
        (self.config.codex_home / "config.toml").write_text('model_provider = "other"\n')
        with self.assertRaises(ValueError):
            validate_auth(self.config)

    def test_actual_exclusive_lock_prevents_duplicate_worker(self):
        with exclusive_lock(self.root / "worker.lock"), self.assertRaises(OSError):  # noqa: SIM117
            with exclusive_lock(self.root / "worker.lock"):
                self.fail("duplicate worker acquired same lock")
        with exclusive_lock(self.root / "worker.lock"):
            pass

    def test_controller_rejects_credentials_in_url_or_remote_plain_http(self):
        for url in ("http://example.com", "https://user:password@example.com", "file:///tmp/a",
                    "https://example.com?token=fixture", "https://example.com#fragment"):
            with self.assertRaises(ValueError):
                ControllerClient(url, self.config.token_file)
        ControllerClient("http://127.0.0.1:18875", self.config.token_file)

    def test_validation_is_argv_not_shell(self):
        validate_commands([["python", "-m", "unittest"], ["npm", "run", "test"]])
        for commands in (["npm test"], [["cmd", "/c", "echo"]], [["../../python", "test"]]):
            with self.assertRaises(ValueError):
                validate_commands(commands)

    def test_structured_result_validation(self):
        path = self.root / "result.json"
        path.write_text(json.dumps({"summary": "observed", "intent_interpretation": "task",
            "changes": [], "limitations": ["actual model not tested"], "next_action": "PM review", "findings": []}))
        self.assertEqual(load_result(path)["summary"], "observed")
        path.write_text('{"summary":"claims only"}')
        with self.assertRaises(ValueError):
            load_result(path)

    def test_structured_result_never_exports_own_opaque_login_or_jwt(self):
        path = self.root / "result.json"
        output = {"summary": "observed", "intent_interpretation": "task", "changes": [],
                  "limitations": [], "next_action": "PM review", "findings": []}
        opaque = b"private-opaque-refresh-canary-123456789"
        for secret in (opaque.decode(), "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20,
                       "-----BEGIN PRIVATE KEY-----"):
            output["limitations"] = [secret]
            path.write_text(json.dumps(output))
            with self.assertRaises(ValueError) as error:
                load_result(path, [opaque])
            self.assertNotIn(secret, str(error.exception))

    def test_off_before_model_retains_checkpoint_and_does_not_execute(self):
        class Client:
            def heartbeat(self, job):
                return False

            def request(self, route, payload):
                return {"job": {"state": "blocked"}}

        with patch("services.automation.worker.github_identity"), patch("services.automation.worker.validate_auth", return_value=None), \
                patch("services.automation.worker.DockerExecutor") as execution:
            observed = execute_job(self.config, Client(), self.job)
        execution.assert_not_called()
        self.assertEqual(observed["state"], "blocked")
        self.assertEqual(observed["controller_receipt"], "accepted")
        self.assertTrue((self.config.state_dir / "runs/CORE-1-attempt1-g1/checkpoint.json").is_file())

    def test_existing_attempt_never_overwrites_partial_workspace(self):
        run = self.config.state_dir / "runs/CORE-1-attempt1-g1"
        run.mkdir(parents=True)
        (run / "keep.txt").write_text("checkpoint")
        with self.assertRaisesRegex(ValueError, "reconciled"):
            execute_job(self.config, object(), self.job)
        self.assertEqual((run / "keep.txt").read_text(), "checkpoint")

    def test_publish_is_branch_only_and_authorizes_each_remote_mutation(self):
        self.config.state_dir.mkdir()
        publication_dir = self.root / "publish"
        publication_dir.mkdir()
        calls = []

        def fake_git(config, argv, cwd=None):
            calls.append(argv)
            return self.job["base_commit"] if argv == ["rev-parse", "HEAD"] else ""

        class Client:
            authorizations = 0

            def heartbeat(self, job):
                return True

            def request(self, route, payload):
                self.authorizations += 1
                return {"publish_token": f"fixture-{self.authorizations}"}

        client = Client()
        result = {"summary": "actual observed change", "limitations": []}
        branch = "codex/auto-unknownamed-CORE-1-a1-g1"
        def fake_command(argv, cwd, **kwargs):
            if argv[:3] == ["gh", "pr", "view"]:
                return json.dumps({"headRefOid": self.job["base_commit"], "headRefName": branch,
                                   "baseRefName": "main", "state": "OPEN", "author": {"login": "unknownamed"}})
            return f"https://github.com/{REPO}/pull/999"

        with patch("services.automation.worker.github_identity"), \
                patch("services.automation.worker.git", side_effect=fake_git), \
                patch("services.automation.worker.command", side_effect=fake_command):
            publication = publish(self.config, client, self.job, self.repository,
                branch, publication_dir, result, [], ["packages/core/a.py"])
        self.assertEqual(client.authorizations, 3)
        push = [argv for argv in calls if argv[0] == "push"]
        self.assertEqual(push, [["push", "origin", f"HEAD:refs/heads/{branch}"]])
        self.assertEqual(publication["publish_token"], "fixture-3")
        self.assertFalse(any("--force" in argv or "merge" in argv for argv in calls))

    def test_configured_trusted_report_hook_executes_and_requires_accepted_receipt(self):
        script = self.root / "fixed-report.py"
        receipt = {"sent": True, "project_updated": True, "receipt": "LGAX-RECEIPT fixture ACCEPTED\n"}
        script.write_text("import json\nprint(json.dumps(" + repr(receipt) + "))\n")
        config = replace(self.config, trusted_report_script=str(script),
                         trusted_report_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        run = self.root / "report-run"
        run.mkdir()
        publication = {"head_commit": "a" * 40, "pr_url": f"https://github.com/{REPO}/pull/999"}
        with patch("services.automation.worker.github_identity"):
            result = send_project_report(config, self.job, publication, run)
        self.assertEqual(result["state"], "accepted")
        self.assertTrue((run / "project-report-receipt.txt").is_file())
        script.write_text("raise Exception('modified untrusted hook must not execute')")
        with patch("services.automation.worker.github_identity"):
            rejected = send_project_report(config, self.job, publication, run)
        self.assertEqual(rejected["state"], "failed")
        self.assertIn("hash mismatch", rejected["remaining"])

    def test_result_secrets_and_excessive_fields_cannot_be_published(self):
        path = self.root / "result.json"
        result = {"summary": "observed", "intent_interpretation": "task", "changes": [],
                  "limitations": [], "next_action": "PM review", "findings": []}
        for change in ({"findings": ["x"] * 31}, {"summary": "x" * 4001},
                       {"findings": ["github_pat_" + "x" * 32]}):
            path.write_text(json.dumps({**result, **change}))
            with self.assertRaises(ValueError):
                load_result(path)


class OwnedProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_process(self, program, heartbeat=lambda: True, timeout=3, **extra):
        return run_bounded([sys.executable, "-c", program], cwd=self.root, env=dict(os.environ),
            output=self.root / "child.log", timeout_seconds=timeout, heartbeat=heartbeat,
            heartbeat_interval=0.1, poll_interval=0.02, **extra)

    def test_off_prevents_process_start(self):
        result = self.run_process("raise Exception('must not execute')", heartbeat=lambda: False)
        self.assertIsNotNone(result.stopped_reason)
        self.assertFalse((self.root / "child.log").exists())

    def test_actual_process_timeout_retains_output(self):
        result = self.run_process("import time; print('checkpoint', flush=True); time.sleep(10)", timeout=0.3)
        self.assertEqual(result.stopped_reason, "bounded execution timeout")
        self.assertIn("checkpoint", (self.root / "child.log").read_text())
        self.assertLess(result.elapsed_seconds, 3)

    def test_controller_off_stops_owned_child(self):
        count = 0

        def heartbeat():
            nonlocal count
            count += 1
            return count == 1

        result = self.run_process("import time; time.sleep(10)", heartbeat=heartbeat)
        self.assertIn("OFF/STOP", result.stopped_reason)

    def test_unreachable_controller_stops_owned_child(self):
        count = 0

        def heartbeat():
            nonlocal count
            count += 1
            if count == 1:
                return True
            raise RuntimeError("fixture offline")

        result = self.run_process("import time; time.sleep(10)", heartbeat=heartbeat)
        self.assertIn("connection unavailable", result.stopped_reason)

    def test_actual_process_normal_exit_is_observed(self):
        result = self.run_process("print('observed')")
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(result.stopped_reason)

    def test_timeout_stops_descendant_and_keeps_checkpoint(self):
        import time
        descendant = "import pathlib,time; time.sleep(1); pathlib.Path('escaped-child.txt').write_text('alive')"
        program = ("import subprocess,sys,time; "
                   f"subprocess.Popen([sys.executable,'-c',{descendant!r}]); "
                   "print('parent checkpoint',flush=True); time.sleep(10)")
        result = self.run_process(program, timeout=0.3)
        time.sleep(1.1)
        self.assertEqual(result.stopped_reason, "bounded execution timeout")
        self.assertFalse((self.root / "escaped-child.txt").exists())

    def test_output_storage_is_bounded(self):
        result = self.run_process("import time; print('a' * 5000, flush=True); time.sleep(10)", max_output_bytes=1000)
        self.assertEqual(result.stopped_reason, "bounded output storage exceeded")


if __name__ == "__main__":
    unittest.main()
