"""Meaningful port isolation and success/failure cleanup checks, without a browser."""

import importlib.util
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_web_e2e", ROOT / "scripts" / "ci_web_e2e.py")
ci_web_e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_web_e2e)


class CiWebE2ETests(unittest.TestCase):
    def test_reserved_ports_are_distinct_and_preserve_existing_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
            existing.bind((ci_web_e2e.HOST, 0))
            existing.listen()
            occupied = existing.getsockname()[1]
            ports = ci_web_e2e.reserve_ports(3)
            self.assertEqual(len(set(ports)), 3)
            self.assertNotIn(occupied, ports)
            with socket.create_connection((ci_web_e2e.HOST, occupied), timeout=2):
                pass

    def test_active_listener_is_not_released(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((ci_web_e2e.HOST, 0))
            listener.listen()
            listener.settimeout(2)
            port = listener.getsockname()[1]
            self.assertFalse(ci_web_e2e.port_available(port))
            accepted, _ = listener.accept()
            accepted.close()

    def test_closed_listener_with_time_wait_is_released(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((ci_web_e2e.HOST, 0))
            listener.listen()
            listener.settimeout(2)
            port = listener.getsockname()[1]
            with socket.create_connection((ci_web_e2e.HOST, port), timeout=2) as client:
                accepted, _ = listener.accept()
                # Server closes first, making its local port enter TIME_WAIT when
                # the peer acknowledges the FIN and then closes its side.
                accepted.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1), b"")
                accepted.close()
        self.assertTrue(ci_web_e2e.port_available(port))

    def test_listener_timeout_does_not_count_as_released(self):
        with patch.object(socket, "create_connection", side_effect=TimeoutError):
            self.assertFalse(ci_web_e2e.port_available(19001))

    def test_browser_summary_drops_token_error_console_and_attachments(self):
        raw = {"suites": [{"specs": [{"title": "live: connect, save a request on server", "tests": [{
            "status": "unexpected", "results": [{"status": "failed", "error": {"message": "Bearer SECRET"},
            "stdout": ["private token"], "attachments": [{"body": "credential screenshot"}]}],
        }]}]}]}
        summary = ci_web_e2e.browser_cases(raw)
        self.assertEqual(summary, [{"case": "live_workspace", "outcome": "unexpected", "results": ["failed"]}])
        self.assertNotIn("SECRET", json.dumps(summary))
        self.assertNotIn("credential", json.dumps(summary))

    def test_actual_api_probe_auth_origin_and_cleanup(self):
        report = ci_web_e2e.run(probe=True)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(all(report["checks"].values()))
        self.assertIsNone(report["browser_stats"])
        self.assertFalse(report["credentials_retained"])
        self.assertFalse(report["planning_agent_executed"])

    def test_failed_auth_gate_reaps_children_and_removes_material(self):
        request = ci_web_e2e.request_json

        def fail_unauthenticated_gate(url, **kwargs):
            if url.endswith("/api/workspace/projects") and not kwargs.get("token"):
                return 200, {}  # The preflight must reject this insecure outcome.
            return request(url, **kwargs)

        with patch.object(ci_web_e2e, "request_json", side_effect=fail_unauthenticated_gate):
            report = ci_web_e2e.run(probe=True)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["failure"], "api_preflight_failed")
        self.assertFalse(report["checks"]["unauthenticated_denied"])
        for check in ("owned_children_reaped", "isolated_ports_released", "temporary_material_removed"):
            self.assertTrue(report["checks"][check])
        self.assertNotIn("Bearer", json.dumps(report))
        self.assertFalse(report["credentials_retained"])


if __name__ == "__main__":
    unittest.main()
