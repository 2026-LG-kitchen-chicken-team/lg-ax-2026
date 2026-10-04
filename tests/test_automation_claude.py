"""Claude driver policy/stream tests. Fixtures do not prove a paid model run."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.build_worker_runtime import build
from services.automation import claude
from services.automation.worker import (
    RESULT_SCHEMA,
    WorkerConfig,
    execute_job,
    isolated_environment,
    load_result,
)


class ClaudeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run = self.root / "run"
        self.run.mkdir()
        self.config = WorkerConfig(account="choigilung", repository=self.repo,
            state_dir=self.root / "state", controller_url="http://127.0.0.1:18871",
            token_file=self.root / "worker.token", engine="claude", claude_home=self.root / "claude-auth",
            isolation_acknowledged=True)
        self.result = {"summary": "fixture only", "intent_interpretation": "assigned web work",
                       "changes": [], "limitations": ["no live model"], "findings": [],
                       "next_action": "PM review"}
        self.event = {"type": "result", "subtype": "success", "is_error": False,
                      "structured_output": self.result, "num_turns": 3, "total_cost_usd": 0.02,
                      "usage": {"input_tokens": 123, "output_tokens": 10}, "permission_denials": []}

    def write_config(self, **overrides):
        example = json.loads((Path(__file__).resolve().parents[1] /
                              "services/automation/worker.claude.example.json").read_text())
        example.update(repository=str(self.repo), state_dir=str(self.config.state_dir),
                       token_file=str(self.config.token_file), claude_home=str(self.config.claude_home),
                       isolation_acknowledged=True)
        example.update(overrides)
        path = self.root / "config.json"
        path.write_text(json.dumps(example))
        return path

    def status(self, **overrides):
        return {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
                "configDirectory": str(self.config.claude_home), "email": "fixture-private",
                **overrides}

    def probe_auth(self, status=None, version="2.1.289", help_text=None):
        values = [f"{version} (Claude Code)\n", help_text if help_text is not None else
                  " ".join(claude.REQUIRED_FLAGS), json.dumps(status or self.status())]
        with patch("services.automation.claude.executable", return_value="claude.exe"), \
                patch("services.automation.claude._probe", side_effect=values):
            return claude.validate_auth(self.config, {}, self.run)

    def stream(self, *events):
        path = self.run / "agent.jsonl"
        path.write_text("CLI diagnostic\n" + "\n".join(json.dumps(event) for event in events) + "\n")
        return path

    def test_claude_config_needs_no_codex_directory_or_subscription(self):
        actual = WorkerConfig.load(self.write_config())
        self.assertIsNone(actual.codex_home)
        self.assertEqual(actual.agent_home, self.config.claude_home)
        self.assertEqual(actual.engine, "claude")

    def test_codex_default_remains_backward_compatible(self):
        path = self.write_config(engine="codex", codex_home=str(self.root / "codex-auth"))
        actual = WorkerConfig.load(path)
        self.assertEqual(actual.agent_home, self.root / "codex-auth")

    def test_metadata_preflight_preserves_unacknowledged_isolation_without_permitting_execution(self):
        path = self.write_config(isolation_acknowledged=False)
        actual = WorkerConfig.load(path, require_isolation=False)
        self.assertIs(actual.isolation_acknowledged, False)
        with self.assertRaisesRegex(ValueError, "deployment boundary"):
            WorkerConfig.load(path)

    def test_invalid_engine_home_turns_model_or_unacknowledged_deployment_refused(self):
        for overrides in ({"engine": "chat"}, {"claude_home": None}, {"claude_home": "relative"},
                          {"claude_home": str(self.repo / "auth")}, {"claude_max_turns": True},
                          {"claude_max_turns": 101}, {"claude_model": "unapproved"},
                          {"claude_version": "latest"}, {"claude_version": "2.1.250"},
                          {"isolation_acknowledged": "false"},
                          {"isolation_acknowledged": False}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                WorkerConfig.load(self.write_config(**overrides))

    def test_inherited_provider_auth_and_config_are_scrubbed(self):
        source = {"PATH": "fixture", "ANTHROPIC_API_KEY": "private", "CLAUDE_CODE_OAUTH_TOKEN": "private",
                  "CLAUDE_CONFIG_DIR": "wrong", "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_SIMPLE": "1",
                  "CLAUDE_CODE_PROCESS_WRAPPER": "evil", "CODEX_HOME": "wrong", "GH_TOKEN": "private",
                  "CLAUDE_CODE_USE_VERTEX": "1", "ANTHROPIC_BASE_URL": "http://wrong"}
        env = isolated_environment(self.config, self.run, source)
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(self.config.claude_home))
        self.assertEqual(env["CLAUDE_CODE_SAFE_MODE"], "1")
        for key in set(source) - {"PATH", "CLAUDE_CONFIG_DIR"}:
            self.assertNotIn(key, env)

    def test_auth_metadata_verifies_private_profile_without_exposing_email(self):
        metadata = self.probe_auth()
        self.assertEqual(metadata["auth_method"], "claude.ai")
        self.assertNotIn("fixture-private", json.dumps(metadata))
        self.assertIs(metadata["model_executed"], False)

    def test_api_oauth_token_third_party_and_wrong_profile_are_refused(self):
        for overrides in ({"loggedIn": False}, {"authMethod": "api_key"}, {"authMethod": "api_key_helper"},
                          {"authMethod": "oauth_token"}, {"apiProvider": "bedrock"},
                          {"configDirectory": str(self.root / "other")}, {"configDirectory": None}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.probe_auth(self.status(**overrides))

    def test_version_change_or_missing_capabilities_block_before_claim(self):
        with self.assertRaises(ValueError):
            self.probe_auth(version="2.1.290")
        with self.assertRaises(ValueError):
            self.probe_auth(help_text="--json-schema only")

    def test_auth_errors_do_not_echo_cli_or_credentials(self):
        with patch("services.automation.claude.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 1, "private-email", "private-token")), \
                self.assertRaises(ValueError) as caught:
            claude._probe(["claude.exe", "auth", "status"], {}, self.run)
        self.assertNotIn("private", str(caught.exception))

    def test_write_driver_has_file_tools_and_no_shell_network_mcp_or_bypass(self):
        with patch("services.automation.claude.executable", return_value="claude.exe"):
            argv = claude.argv(self.config, {"kind": "implementation"}, self.run, RESULT_SCHEMA)
        tools = argv[argv.index("--tools") + 1].split(",")
        self.assertEqual(set(tools), {"Read", "Glob", "Grep", "Edit", "Write"})
        self.assertIn("--restricted", argv)
        self.assertIn("--safe-mode", argv)
        self.assertNotIn("--bare", argv)  # Bare disables subscription login.
        self.assertNotIn("--dangerously-skip-permissions", argv)
        self.assertEqual(argv[argv.index("--permission-prompts") + 1], "none")
        self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), RESULT_SCHEMA)
        self.assertEqual(json.loads((self.run / "empty-mcp.json").read_text()), {"mcpServers": {}})

    def test_review_driver_cannot_edit_or_execute(self):
        with patch("services.automation.claude.executable", return_value="claude.exe"):
            argv = claude.argv(self.config, {"kind": "review"}, self.run, RESULT_SCHEMA)
        self.assertEqual(argv[argv.index("--tools") + 1], "Read,Glob,Grep")

    def test_success_final_event_uses_existing_result_contract_and_cost_is_estimate(self):
        metadata = claude.extract_result(self.stream({"type": "system"}, self.event), self.run / "result.json")
        self.assertEqual(load_result(self.run / "result.json"), self.result)
        self.assertEqual(metadata["estimated_cost_usd"], 0.02)
        self.assertNotIn("total_cost_usd", metadata)

    def test_error_success_subtype_limit_missing_schema_or_denied_tool_never_succeed(self):
        for changes in ({"is_error": True}, {"subtype": "error_max_turns"}, {"structured_output": None},
                        {"permission_denials": [{"tool_name": "Bash"}]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                claude.extract_result(self.stream({**self.event, **changes}), self.run / "result.json")

    def test_duplicate_or_nonfinal_result_and_assistant_prose_refused(self):
        for events in ((self.event, self.event), (self.event, {"type": "assistant"}),
                       ({"type": "assistant", "message": self.result},)):
            with self.subTest(events=events), self.assertRaises(ValueError):
                claude.extract_result(self.stream(*events), self.run / "result.json")

    def test_existing_secret_and_schema_checks_apply_to_claude_result(self):
        for result in ({"summary": "not a full schema"}, {**self.result, "summary": "sk-" + "a" * 40}):
            claude.extract_result(self.stream({**self.event, "structured_output": result}), self.run / "result.json")
            with self.assertRaises(ValueError):
                load_result(self.run / "result.json")

    def test_common_executor_dispatches_claude_review_with_fixed_validation_and_receipt(self):
        job = {"job_id": "REVIEW-CLAUDE-1", "owner": "choigilung", "kind": "review",
               "base_commit": "a" * 40, "review_head": "b" * 40, "lease_token": "fixture",
               "timeout_seconds": 120, "prompt": "fixed review", "allowed_paths": []}
        receipts = []
        client = SimpleNamespace(heartbeat=lambda job: True,
                                 request=lambda route, payload: receipts.append(payload) or {})

        def run(argv, **kwargs):
            self.assertIn("--restricted", argv)
            self.assertEqual(argv[argv.index("--tools") + 1], "Read,Glob,Grep")
            kwargs["output"].write_text(json.dumps(self.event) + "\n")
            return SimpleNamespace(returncode=0, elapsed_seconds=0.1, stopped_reason=None)

        with patch("services.automation.worker.github_identity"), \
                patch("services.automation.worker.validate_auth", return_value={"engine": "claude"}), \
                patch("services.automation.worker.prepare_worktree",
                      return_value=(self.repo, "codex/fixture", "b" * 40, [], [])), \
                patch("services.automation.claude.executable", return_value="claude.exe"), \
                patch("services.automation.worker.run_bounded", side_effect=run), \
                patch("services.automation.worker.git", return_value="b" * 40), \
                patch("services.automation.worker.check_scope", return_value=[]), \
                patch("services.automation.worker.check_review_head"), \
                patch("services.automation.worker.publish") as publish:
            observed = execute_job(self.config, client, job)
        self.assertEqual(observed["state"], "completed_review")
        self.assertEqual(observed["engine"], "claude")
        self.assertEqual(observed["controller_receipt"], "accepted")
        self.assertEqual(receipts[-1]["outcome"], "completed_review")
        publish.assert_not_called()

    def test_claude_off_before_model_never_dispatches_or_publishes(self):
        job = {"job_id": "REVIEW-OFF", "owner": "choigilung", "kind": "review",
               "base_commit": "a" * 40, "review_head": "b" * 40, "lease_token": "fixture",
               "timeout_seconds": 120}
        client = SimpleNamespace(heartbeat=lambda job: False, request=lambda *args: {})
        with patch("services.automation.worker.github_identity"), \
                patch("services.automation.worker.validate_auth", return_value=None), \
                patch("services.automation.worker.run_bounded") as run, \
                patch("services.automation.worker.publish") as publish:
            observed = execute_job(self.config, client, job)
        self.assertEqual(observed["state"], "blocked")
        run.assert_not_called()
        publish.assert_not_called()

    def test_expired_authentication_halts_member_instead_of_draining_approved_queue(self):
        job = {"job_id": "REVIEW-EXPIRED", "owner": "choigilung", "kind": "review",
               "base_commit": "a" * 40, "review_head": "b" * 40, "lease_token": "fixture",
               "timeout_seconds": 120}
        client = SimpleNamespace(heartbeat=lambda job: True, request=lambda *args: {})
        with patch("services.automation.worker.github_identity"), \
                patch("services.automation.worker.validate_auth", side_effect=ValueError("login expired")), \
                patch("services.automation.worker.run_bounded") as run:
            observed = execute_job(self.config, client, job)
        self.assertIs(observed["halt_worker"], True)
        self.assertEqual(observed["state"], "blocked")
        run.assert_not_called()

    def test_external_runtime_includes_both_engines_and_refuses_module_tamper(self):
        bundle = build(self.root / "fixed-runtime")
        self.assertEqual(set(bundle["dependency_manifest"]), {"worker.py", "process.py", "claude.py"})
        self.assertIs(bundle["automation_enabled"], False)
        help_result = subprocess.run([sys.executable, bundle["worker_path"], "--help"],
                                     capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        path = Path(bundle["worker_path"]).parent / "claude.py"
        path.write_text("raise Exception('untrusted changed module')\n")
        refused = subprocess.run([sys.executable, bundle["worker_path"], "--help"],
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("fixed worker runtime changed", refused.stderr)
        self.assertNotIn("untrusted changed module", refused.stderr)

    def test_runtime_does_not_overwrite_deployed_bundle_or_copy_inside_repo(self):
        target = self.root / "existing-bundle"
        target.mkdir()
        (target / "keep.txt").write_text("existing deployment")
        with self.assertRaises(FileExistsError):
            build(target)
        self.assertEqual((target / "keep.txt").read_text(), "existing deployment")
        with self.assertRaises(ValueError):
            build(Path(__file__).resolve().parents[1] / "private/forbidden-runtime")


if __name__ == "__main__":
    unittest.main()
