"""Startup contention is free metadata waiting, never a model or auth fallback."""
import io
import json
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import automation_pm
from services.automation.pm import PMDriverBusy


class PMStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / "fixed-config.json"
        self.config.write_text(json.dumps({"poll_seconds": 10, "policy_file": "fixed-policy",
            "policy_sha256": "a" * 64, "journal_file": str(self.root / "journal.sqlite"),
            "state_dir": str(self.root / "state")}))

    def test_once_observe_and_preflight_report_busy_without_claiming_success_or_calling_model(self):
        for flag in ("--once", "--observe", "--preflight"):
            output = io.StringIO()
            with self.subTest(flag=flag), redirect_stdout(output), patch.object(
                    automation_pm, "TrustedPMBroker", side_effect=PMDriverBusy("fixture active Worker")), patch.object(
                    automation_pm, "AutonomousPM") as model, patch.object(automation_pm.time, "sleep") as sleep:
                self.assertEqual(automation_pm.main(["--config", str(self.config), flag]), 0)
            model.assert_not_called()
            sleep.assert_not_called()
            row = json.loads(output.getvalue())
            self.assertEqual(row["state"], "wait")
            self.assertFalse(row["model_called"])
            self.assertFalse(row["mutated"])
            self.assertNotIn("preflight", row)

    def test_background_retries_startup_at_bounded_interval_after_worker_releases_profile(self):
        output = io.StringIO()
        broker = SimpleNamespace(driver=object())
        pm = SimpleNamespace(tick=lambda: {"state": "off", "model_called": False, "mutated": False})
        with redirect_stdout(output), patch.object(automation_pm, "TrustedPMBroker",
                side_effect=[PMDriverBusy("fixture active Worker"), broker]) as create, patch.object(
                automation_pm, "AutonomousPM", return_value=pm) as model, patch.object(
                automation_pm, "exclusive_bridge_lock", return_value=nullcontext()), patch.object(
                automation_pm.time, "sleep", side_effect=[None, KeyboardInterrupt]) as sleep, \
                self.assertRaises(KeyboardInterrupt):
            automation_pm.main(["--config", str(self.config)])
        self.assertEqual(create.call_count, 2)
        self.assertEqual(model.call_count, 1)
        self.assertEqual([call.args for call in sleep.call_args_list], [(10,), (10,)])
        self.assertEqual([json.loads(line)["state"] for line in output.getvalue().splitlines()], ["wait", "off"])


if __name__ == "__main__":
    unittest.main()
