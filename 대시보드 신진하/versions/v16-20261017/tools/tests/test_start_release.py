"""Launcher contract tests: fake children and synthetic paths, no native session."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "start_release.py"
SPEC = importlib.util.spec_from_file_location("ax_start_release_under_test", SOURCE)
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)
TEST_TOKEN = "synthetic-view-token-only-012345678901234567890"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "codex"
        self.dist = self.root / "dist"
        (self.workspace / ".venv/Scripts").mkdir(parents=True)
        (self.workspace / ".venv/Scripts/python.exe").write_bytes(b"synthetic-not-executable")
        (self.workspace / "web/prototypes/agent-office").mkdir(parents=True)
        (self.workspace / "web/prototypes/agent-office/office.py").write_text("# synthetic", encoding="utf-8")
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<html><head></head></html>", encoding="utf-8")
        self.verify = patch.object(launcher.ReleaseReader, "_verify", return_value=("codex", "synthetic"))
        self.verify_mock = self.verify.start()

    def tearDown(self):
        self.verify.stop()
        self.temp.cleanup()

    def plan(self, **kwargs):
        return launcher.prepare(self.workspace, self.dist, **kwargs)

    def fake_process(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        process.returncode = None
        return process

    def test_verify_source_only_before_start_and_reject_relative_or_invalid_port(self):
        with patch.object(launcher.ReleaseReader, "snapshot", side_effect=AssertionError("must not read observations")):
            self.assertEqual("codex", self.plan().engine)
        self.verify_mock.assert_called_once_with()
        for workspace, dist, port in ((Path("relative"), self.dist, 8033), (self.workspace, Path("relative"), 8033), (self.workspace, self.dist, 0)):
            with self.assertRaises(launcher.StartError):
                launcher.prepare(workspace, dist, port)

    def test_failed_pin_prevents_child_spawn(self):
        self.verify_mock.side_effect = launcher.ReleaseReadError("release_mismatch")
        with patch.object(launcher, "spawn") as spawn:
            with self.assertRaises(launcher.StartError):
                self.plan()
        spawn.assert_not_called()

    def test_wait_is_default_and_latest_requires_explicit_option(self):
        server, observer = launcher.child_specs(self.plan(), TEST_TOKEN)
        self.assertEqual(["-u", "-m", "backend.release_server", "--port", "8033"], server[0][1:])
        self.assertEqual("--wait", observer[0][-1])
        self.assertNotIn("--latest", observer[0])
        self.assertEqual(str(self.workspace.resolve()), observer[0][-2])
        self.assertTrue(observer[0][2].endswith("office.py"))
        self.assertEqual("--latest", launcher.child_specs(self.plan(latest=True), TEST_TOKEN)[1][0][-1])
        self.assertNotIn("codex.exe", observer[0])

    def test_secret_only_server_environment_and_no_public_origins(self):
        with patch.dict(os.environ, {"AX_HARNESS_VIEW_TOKEN": "old-secret", "AX_HARNESS_ALLOWED_ORIGINS": "https://public.example", "AX_HARNESS_DB": "private-old-db"}):
            server, observer = launcher.child_specs(self.plan(), TEST_TOKEN)
        self.assertEqual(TEST_TOKEN, server[2]["AX_HARNESS_VIEW_TOKEN"])
        for spec in (server, observer):
            self.assertNotIn(TEST_TOKEN, " ".join(spec[0]))
            self.assertNotIn("AX_HARNESS_ALLOWED_ORIGINS", spec[2])
            self.assertNotIn("AX_HARNESS_DB", spec[2])
            self.assertEqual("1", spec[2]["PYTHONDONTWRITEBYTECODE"])
        self.assertNotIn("AX_HARNESS_VIEW_TOKEN", observer[2])
        self.assertNotIn("AX_RELEASE_UI_DIST", observer[2])

    def test_spawn_uses_no_shell_hidden_helpers_and_devnull(self):
        spec = launcher.child_specs(self.plan(), TEST_TOKEN)[0]
        with patch.object(launcher.subprocess, "Popen") as popen:
            launcher.spawn(spec)
        args, kwargs = popen.call_args
        self.assertEqual(spec[0], args[0])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(subprocess.DEVNULL, kwargs["stdin"])
        self.assertEqual(subprocess.DEVNULL, kwargs["stdout"])
        self.assertEqual(subprocess.DEVNULL, kwargs["stderr"])
        self.assertEqual(getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0, kwargs["creationflags"])

    def run_mocked(self, *, no_open=False, readiness_error=None, supervisor_error=None):
        plan = self.plan(no_open=no_open)
        children = [self.fake_process(), self.fake_process()]
        output, errors = io.StringIO(), io.StringIO()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(launcher, "check_port_available") as check, patch.object(launcher.secrets, "token_urlsafe", return_value=TEST_TOKEN), patch.object(launcher, "spawn", side_effect=children) as spawn, patch.object(launcher, "wait_ready", side_effect=readiness_error) as ready, patch.object(launcher, "supervise", side_effect=supervisor_error, return_value=0), patch.object(launcher.webbrowser, "open", return_value=True) as browser, contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            if readiness_error:
                with self.assertRaises(launcher.StartError):
                    launcher.launch(plan)
            else:
                self.assertEqual(0, launcher.launch(plan))
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn(TEST_TOKEN, output.getvalue() + errors.getvalue())
        check.assert_called_once_with(8033)
        ready.assert_called_once_with(children[0], plan, TEST_TOKEN)
        return plan, children, spawn, browser

    def test_no_open_does_not_launch_browser_or_write_token(self):
        _plan, children, spawn, browser = self.run_mocked(no_open=True)
        self.assertEqual(2, spawn.call_count)
        browser.assert_not_called()
        for child in children:
            child.terminate.assert_called_once_with()

    def test_browser_receives_only_plain_local_url(self):
        plan, _children, _spawn, browser = self.run_mocked()
        browser.assert_called_once_with(plan.url, new=2)
        self.assertNotIn("?", plan.url)

    def test_failed_readiness_stops_only_own_server_and_never_starts_observer(self):
        _plan, children, spawn, browser = self.run_mocked(readiness_error=launcher.StartError("synthetic failure"))
        self.assertEqual(1, spawn.call_count)
        children[0].terminate.assert_called_once_with()
        children[1].terminate.assert_not_called()
        browser.assert_not_called()

    def test_ctrl_c_terminates_only_returned_child_handles(self):
        _plan, children, _spawn, _browser = self.run_mocked(supervisor_error=KeyboardInterrupt())
        for child in children:
            child.terminate.assert_called_once_with()
            child.kill.assert_not_called()

    def test_port_collision_does_not_spawn_anything(self):
        with patch.object(launcher, "check_port_available", side_effect=launcher.StartError("busy")), patch.object(launcher, "spawn") as spawn:
            with self.assertRaises(launcher.StartError):
                launcher.launch(self.plan())
        spawn.assert_not_called()

    def test_claude_does_not_start_codex_or_change_hook_settings(self):
        self.verify_mock.return_value = ("claude", "synthetic")
        plan = self.plan()
        self.assertIsNone(launcher.child_specs(plan, TEST_TOKEN)[1])
        with self.assertRaises(launcher.StartError):
            self.plan(latest=True)

    def test_readiness_checks_own_bootstrap_without_sending_token(self):
        plan = self.plan()
        process = self.fake_process()
        payload = {"kind": "lgax_local_release_connection", "url": plan.url.rstrip("/"), "token": TEST_TOKEN}
        html = '<html><script type="application/json" id="ax-release-bootstrap">' + json.dumps(payload) + '</script></html>'
        responses = [Mock(), Mock()]
        for response, raw in zip(responses, (b'{"service":"kitchen-ax-harness-reader","ok":true}', html.encode())):
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = raw
        opener = Mock()
        opener.open.side_effect = responses
        with patch.object(launcher.urllib.request, "build_opener", return_value=opener):
            launcher.wait_ready(process, plan, TEST_TOKEN)
        self.assertEqual([plan.url + "health", plan.url], [call.args[0] for call in opener.open.call_args_list])
        for call in opener.open.call_args_list:
            self.assertNotIn(TEST_TOKEN, str(call.args))

    def test_foreign_bootstrap_cannot_pass_port_ownership_check(self):
        plan = self.plan()
        health, page = Mock(), Mock()
        for response, raw in ((health, b'{"service":"kitchen-ax-harness-reader","ok":true}'), (page, b'<html>another server</html>')):
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = raw
        opener = Mock()
        opener.open.side_effect = [health, page]
        with patch.object(launcher.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(launcher.StartError):
                launcher.wait_ready(self.fake_process(), plan, TEST_TOKEN)


if __name__ == "__main__":
    unittest.main()
