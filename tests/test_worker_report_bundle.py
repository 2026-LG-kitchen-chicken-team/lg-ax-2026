import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_worker_report_bundle import ROOT, build


class ReportBundleTests(unittest.TestCase):
    def test_external_bundle_dependency_tamper_fails_before_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            info = build(output)
            script = output / "scripts/project_report_common.py"
            script.write_text("raise RuntimeError('must not execute')", encoding="utf-8")
            result = subprocess.run([__import__('sys').executable, info['trusted_report_script'], 'status'],
                                    capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('fixed report bundle changed', result.stderr)

    def test_in_repo_and_existing_directory_rejected(self):
        with self.assertRaises(ValueError):
            build(ROOT / "private/forbidden-report-hook")
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileExistsError):
            build(directory)

    def test_explicit_immutable_links_do_not_require_hook_directory_git_checkout(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import project_report
        policy = {'repo': '2026-LG-kitchen-chicken-team/lg-ax-2026',
                  'tasks': {'P2-DATA-001': {'name': '신진하'}}}
        argv = ['project_report.py', 'report', 'P2-DATA-001', '--status', 'doing',
                '--summary', 'testing', '--next-action', 'review', '--log-url', 'fixed-log', '--evidence-url', 'fixed-evidence']
        with patch.object(sys, 'argv', argv), patch.object(project_report, 'load_policy', return_value=policy), \
                patch.object(project_report, 'submit', return_value={'sent': False}) as submit, \
                patch.object(project_report.subprocess, 'run', side_effect=AssertionError('no local git required')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(project_report.main(), 0)
        self.assertEqual(submit.call_args.args[2]['log_url'], 'fixed-log')
        self.assertEqual(submit.call_args.args[2]['evidence_url'], 'fixed-evidence')
