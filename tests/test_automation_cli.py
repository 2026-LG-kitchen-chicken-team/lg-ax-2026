"""Operator/enrollment contract checks; all credentials and transports are fixtures."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from services.automation.state import Store

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lgax_automation_cli_test", ROOT / "scripts/automation.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class AutomationCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.args = SimpleNamespace(state_dir=str(self.root / "member"),
                                    controller_url="https://controller.example.test/lgax", member="황대겸")
        # Build the same inert credential at runtime; keep issued-key patterns out of source.
        credential_parts = ("ghp", "fixture_not_a_real_credential_0123456789")
        self.github_credential = "_".join(credential_parts)

    def github_result(self):
        return subprocess.CompletedProcess(["gh", "auth", "token"], 0, self.github_credential + "\n", "")

    def test_setup_consumes_actual_controller_enrollment_key_and_keeps_tokens_private(self):
        store = Store(self.root / "controller.sqlite3", {})
        enrolled = store.enroll("unknownamed")
        response = httpx.Response(200, json=enrolled)
        with patch.object(CLI, "github_identity", return_value="unknownamed"), \
                patch.object(CLI.subprocess, "run", return_value=self.github_result()), \
                patch.object(CLI.httpx, "post", return_value=response) as request:
            result = CLI.setup(self.args)
        config = json.loads(Path(result["client_config"]).read_text(encoding="utf-8"))
        saved_token = Path(config["token_file"]).read_text(encoding="utf-8").strip()
        self.assertEqual(saved_token, enrolled["automation_token"])
        self.assertEqual(config["member"], "unknownamed")
        self.assertEqual(result["mode"], "off")
        self.assertFalse(result["credentials_printed"])
        self.assertNotIn(saved_token, json.dumps(result))
        self.assertNotIn(self.github_credential, json.dumps(result))
        for path in Path(self.args.state_dir).iterdir():
            self.assertNotIn(self.github_credential, path.read_text(encoding="utf-8"))
        self.assertEqual(request.call_args.args, (self.args.controller_url + "/v1/enroll",))
        self.assertFalse(request.call_args.kwargs["trust_env"])
        self.assertFalse(request.call_args.kwargs.get("follow_redirects", False))

    def test_setup_refuses_account_mismatch_before_reading_or_sending_github_token(self):
        with patch.object(CLI, "github_identity", return_value="ginaginaring"), \
                patch.object(CLI.subprocess, "run") as github, patch.object(CLI.httpx, "post") as request, \
                self.assertRaisesRegex(ValueError, "does not match"):
            CLI.setup(self.args)
        github.assert_not_called()
        request.assert_not_called()
        self.assertFalse(Path(self.args.state_dir).exists())

    def test_setup_wrong_controller_identity_does_not_save_credentials(self):
        response = httpx.Response(200, json={"account": "choigilung", "automation_token": "fixture"})
        with patch.object(CLI, "github_identity", return_value="unknownamed"), \
                patch.object(CLI.subprocess, "run", return_value=self.github_result()), \
                patch.object(CLI.httpx, "post", return_value=response), \
                self.assertRaisesRegex(ValueError, "identity mismatch"):
            CLI.setup(self.args)
        self.assertFalse(Path(self.args.state_dir).exists())

    def test_setup_rejection_does_not_echo_github_credential_or_create_config(self):
        response = httpx.Response(403, json={"error": self.github_credential})
        with patch.object(CLI, "github_identity", return_value="unknownamed"), \
                patch.object(CLI.subprocess, "run", return_value=self.github_result()), \
                patch.object(CLI.httpx, "post", return_value=response), self.assertRaises(ValueError) as failure:
            CLI.setup(self.args)
        self.assertNotIn(self.github_credential, str(failure.exception))
        self.assertFalse(Path(self.args.state_dir).exists())

    def test_existing_enrollment_is_preserved_without_rotating_remote_token(self):
        directory = Path(self.args.state_dir)
        directory.mkdir()
        original = b'{"member":"unknownamed","preserve":true}'
        (directory / "client.json").write_bytes(original)
        with patch.object(CLI, "github_identity", return_value="unknownamed"), \
                patch.object(CLI.subprocess, "run") as github, patch.object(CLI.httpx, "post") as request, \
                self.assertRaisesRegex(ValueError, "existing setup"):
            CLI.setup(self.args)
        github.assert_not_called()
        request.assert_not_called()
        self.assertEqual((directory / "client.json").read_bytes(), original)

    def test_setup_rejects_ambiguous_or_credential_bearing_url_before_token_read(self):
        for url in ("http://127.0.0.1:18871", "https://user@example.test", "https://example.test?redirect=other",
                    "https://example.test#fragment"):
            with self.subTest(url=url), patch.object(CLI, "github_identity", return_value="unknownamed"), \
                    patch.object(CLI.subprocess, "run") as github, patch.object(CLI.httpx, "post") as request:
                with self.assertRaises(ValueError):
                    CLI.setup(SimpleNamespace(**{**vars(self.args), "controller_url": url}))
                github.assert_not_called()
                request.assert_not_called()

    def test_operator_and_pm_worker_credentials_are_distinct_and_not_returned(self):
        args = SimpleNamespace(state_dir=str(self.root / "pm"), controller_url="http://127.0.0.1:18871")
        result = CLI.init(args)
        directory = Path(args.state_dir)
        config = json.loads((directory / "controller.json").read_text(encoding="utf-8"))
        operator = (directory / "pm.token").read_text(encoding="utf-8").strip()
        worker = (directory / "pm-worker.token").read_text(encoding="utf-8").strip()
        self.assertNotEqual(operator, worker)
        self.assertNotEqual(config["token_digests"]["jeongiryang"], config["worker_token_digests"]["jeongiryang"])
        self.assertNotIn(operator, json.dumps(result))
        self.assertNotIn(worker, json.dumps(result))
        self.assertEqual(Store(config["database"], config).status("jeongiryang")["global_mode"], "off")
        before = (directory / "pm.token").read_bytes()
        with self.assertRaises(ValueError):
            CLI.init(args)
        self.assertEqual((directory / "pm.token").read_bytes(), before)

    def client(self, url="https://controller.example.test/lgax"):
        token_file = self.root / "client.token"
        token_file.write_text("fixture_private_controller_0123456789", encoding="utf-8")
        return CLI.Client({"controller_url": url, "token_file": str(token_file)})

    def test_client_rejects_unsafe_urls(self):
        for url in ("https://user@example.test", "https://example.test?query=x", "https://example.test#fragment",
                    "http://example.test", "file:///tmp/controller"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.client(url)
        self.client("http://127.0.0.1:18871")

    def test_client_refuses_redirects_without_forwarding_private_bearer(self):
        response = httpx.Response(307, headers={"Location": "https://another.example.test"}, json={"ok": True})
        with patch.object(CLI.httpx, "request", return_value=response) as request, self.assertRaises(ValueError):
            self.client().request("POST", "/v1/mode", {"mode": "off"})
        self.assertEqual(request.call_count, 1)
        self.assertFalse(request.call_args.kwargs["trust_env"])
        self.assertFalse(request.call_args.kwargs.get("follow_redirects", False))


if __name__ == "__main__":
    unittest.main()
