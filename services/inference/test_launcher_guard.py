"""Safety regression checks: never kill foreign processes or report failed binds as started."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher_guard as guard


class LauncherGuardTests(unittest.TestCase):
    def service(self, directory):
        return guard.Service("ollama", Path(directory), Path(directory) / "cache", Path(directory) / "ollama", 18864)

    def test_port_owner_must_be_visible_and_loopback(self):
        self.assertEqual(guard.parse_listeners('LISTEN 0 4096 127.0.0.1:18864 0.0.0.0:* users:(("ollama",pid=42,fd=3))', 18864), {42})
        for row in ["LISTEN 0 4096 127.0.0.1:18864 0.0.0.0:*", 'LISTEN 0 4096 0.0.0.0:18864 0.0.0.0:* users:(("x",pid=42))']:
            with self.subTest(row=row), self.assertRaises(guard.Blocked):
                guard.parse_listeners(row, 18864)

    def test_other_gpu_work_is_blocked(self):
        with patch.object(guard, "gpu_pids", return_value={42, 90}), patch.object(guard, "descendant", side_effect=lambda pid, ancestor: pid == ancestor), self.assertRaises(guard.Blocked):
            guard.assert_gpu_available(42)

    def test_cache_exe_and_cwd_are_independent_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            state = {"uid": 42, "executable": service.executable, "cwd": service.root, "arguments": [str(service.executable), "serve"],
                     "environment": {"OLLAMA_HOST": "127.0.0.1:18864", "OLLAMA_MODELS": str(service.cache / "ollama"), "OLLAMA_NO_CLOUD": "1", "OLLAMA_VULKAN": "false", "CUDA_VISIBLE_DEVICES": "0"}}
            with patch.object(guard.os, "getuid", return_value=42, create=True):
                guard.assert_identity(service, state)
                for key in ["executable", "cwd"]:
                    changed = {**state, key: Path(directory) / "foreign"}
                    with self.subTest(key=key), self.assertRaises(guard.Blocked):
                        guard.assert_identity(service, changed)
                changed = {**state, "environment": {**state["environment"], "OLLAMA_MODELS": "foreign-cache"}}
                with self.assertRaises(guard.Blocked):
                    guard.assert_identity(service, changed)

    def test_wrong_port_pid_is_never_killed(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            service.pid_file.parent.mkdir()
            service.pid_file.write_text("42\n")
            with patch.object(guard, "listeners", return_value={90}), patch.object(guard, "inspect_process", return_value={}), patch.object(guard, "assert_identity"), patch.object(guard.os, "kill") as kill:
                with self.assertRaises(guard.Blocked):
                    guard.prepare(service, True, 1)
                kill.assert_not_called()

    def test_unreleased_port_causes_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            with patch.object(guard.time, "monotonic", side_effect=[0, 0, 2]), patch.object(guard.time, "sleep"), patch.object(guard, "process_alive", return_value=False), patch.object(guard, "listeners", return_value={90}), self.assertRaises(guard.Blocked):
                guard.wait_released(service, 42, 1)

    def test_failed_bind_never_saves_pid_or_calls_health(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            with patch.object(guard.time, "monotonic", side_effect=[0, 0, 2]), patch.object(guard.time, "sleep"), patch.object(guard, "process_alive", return_value=True), patch.object(guard, "inspect_process", return_value={}), patch.object(guard, "assert_identity"), patch.object(guard, "listeners", return_value={90}), patch.object(guard, "read_health") as health:
                with self.assertRaises(guard.Blocked):
                    guard.ready(service, 42, 1)
                self.assertFalse(service.pid_file.exists())
                health.assert_not_called()


if __name__ == "__main__":
    unittest.main()
