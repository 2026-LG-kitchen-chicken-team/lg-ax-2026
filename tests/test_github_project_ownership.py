"""Separate a board's organization owner from the authenticated human PM."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bootstrap_github as bootstrap
import sync_github_phase2 as sync

HEAD = "a" * 40


class ProjectOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.phase = self.root / "harness/phase2"
        (self.phase / "tasks").mkdir(parents=True)
        self.owner = "fixture-organization"
        self.login = "jeongiryang"
        self.board = {"owner": {"login": self.owner, "type": "Organization"}, "number": 8,
                      "id": "fixture-project-id", "title": bootstrap.TITLE, "closed": False,
                      "url": f"https://github.com/orgs/{self.owner}/projects/8"}
        self.links = {"project": self.board, "tasks": {}, "items": []}
        self.write("github.json", self.links)
        self.write("requirements.json", {"requirements": []})
        self.write("project-reports.policy.json", {})
        self.policy = {"governance_issue_number": 28, "accept_reports_after": "2026-10-04T00:00:00Z"}
        self.comments = []
        self.api_calls, self.gh_calls = [], []
        self.created_issues = []
        self.fields = [{"name": name, "id": "fixture-field-" + str(i), "options": []}
                       for i, name in enumerate(("담당자", "요구사항", "의존 작업", "실행 증빙", "목표일",
                                                 "우선순위", "진행상태", "Status", "팀원 보고"))]

    def write(self, name, value):
        (self.phase / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def api(self, path, data=None, method=None):
        self.api_calls.append((path, data, method))
        if path == "user":
            return {"login": self.login}
        if path.endswith("/branches/main"):
            return {"commit": {"sha": HEAD}}
        if "/collaborators" in path:
            return [{"login": "jeongiryang"}]
        if method == "POST":
            if path.endswith("/issues"):
                self.created_issues.append(data)
                number = len(self.created_issues)
                return {"number": number, "node_id": "fixture-issue-" + str(number),
                        "html_url": f"https://github.com/{bootstrap.REPO}/issues/{number}",
                        "title": data["title"]}
            return {}
        if "/issues?" in path or "/labels?" in path:
            return []
        raise AssertionError(f"Unexpected mocked API call: {path}")

    def gh(self, *args, data=None):
        self.gh_calls.append((args, data))
        if args[:2] == ("project", "list"):
            return {"projects": [self.board]}
        if args[:2] == ("project", "field-list"):
            return {"fields": self.fields}
        if args[:2] == ("project", "item-add"):
            return {"id": "fixture-item-" + str(len(self.gh_calls))}
        if args[:2] in (("project", "link"), ("project", "item-edit")):
            return None
        raise AssertionError(f"Unexpected mocked CLI call: {args}")

    def git(self, command, **_kwargs):
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(command, 0, stdout=(HEAD + "\n").encode())
        if command[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(command, 0, stdout=b"")
        raise AssertionError(f"Unexpected mocked local command: {command}")

    def run_bootstrap(self):
        with (patch.object(bootstrap, "ROOT", self.root), patch.object(bootstrap, "api", self.api),
              patch.object(bootstrap, "gh", self.gh),
              patch.object(bootstrap, "TEAM", {"정이량": ("jeongiryang", "fixture PM role", "PM")}),
              patch.object(sys, "argv", ["bootstrap_github.py", "--apply"]), redirect_stdout(io.StringIO())):
            bootstrap.main()

    def run_sync(self):
        with (patch.object(sync, "ROOT", self.root), patch.object(sync, "api", self.api),
              patch.object(sync, "gh", self.gh), patch.object(sync, "load", return_value={}),
              patch.object(sync, "ready_tasks", return_value=[]), patch.object(sync, "validate", return_value=[]),
              patch.object(sync, "load_policy", return_value=self.policy),
              patch.object(sync, "GitHub", return_value=SimpleNamespace(pages=lambda _path: self.comments)),
              patch.object(sync.subprocess, "run", side_effect=self.git),
              patch.object(sys, "argv", ["sync_github_phase2.py", "--apply"]), redirect_stdout(io.StringIO())):
            sync.main()

    def test_missing_board_owner_defaults_to_organization_not_pm(self):
        self.assertEqual(bootstrap.configured_project_owner({}), "2026-LG-kitchen-chicken-team")
        self.assertNotEqual(bootstrap.PROJECT_OWNER, bootstrap.PM_ACCOUNT)
        with patch.object(bootstrap, "ROOT", self.root):
            (self.phase / "github.json").unlink()
            self.assertEqual(bootstrap.configured_project_owner(), bootstrap.PROJECT_OWNER)

    def test_recorded_board_owner_wins_without_changing_pm_identity(self):
        self.assertEqual(bootstrap.configured_project_owner(self.links), self.owner)
        self.assertEqual(bootstrap.configured_project_owner({"project": {"owner": {"login": "jeongiryang"}}}),
                         "jeongiryang")
        self.assertEqual(bootstrap.PM_ACCOUNT, "jeongiryang")

    def test_invalid_recorded_owner_is_rejected(self):
        for login in ("org/repo", " --owner other", 7):
            with self.subTest(login=login), self.assertRaisesRegex(ValueError, "Project owner"):
                bootstrap.configured_project_owner({"project": {"owner": {"login": login}}})

    def test_bootstrap_uses_board_owner_but_assigns_governance_to_pm(self):
        self.run_bootstrap()
        owner_calls = [args for args, _ in self.gh_calls if "--owner" in args]
        self.assertTrue(owner_calls)
        self.assertTrue(all(args[args.index("--owner") + 1] == self.owner for args in owner_calls))
        governance = next(issue for issue in self.created_issues if "팀 역할" in issue["title"])
        self.assertEqual(governance["assignees"], ["jeongiryang"])
        self.assertEqual(self.api_calls[0], ("user", None, None))

    def test_bootstrap_rejects_non_pm_before_any_mutation(self):
        self.login = self.owner
        original = (self.phase / "github.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "authenticated PM"):
            self.run_bootstrap()
        self.assertEqual(self.api_calls, [("user", None, None)])
        self.assertEqual(self.gh_calls, [])
        self.assertEqual((self.phase / "github.json").read_bytes(), original)

    def test_sync_uses_board_owner_and_reuses_only_the_pm_approval(self):
        self.comments = [{"user": {"login": "jeongiryang"},
                          "body": '/lgax-sync\n```json\n' + json.dumps({"commit": HEAD}) + '\n```',
                          "created_at": "2026-10-05T00:00:00Z"}]
        self.run_sync()
        fields_call = next(args for args, _ in self.gh_calls if args[:2] == ("project", "field-list"))
        self.assertEqual(fields_call[fields_call.index("--owner") + 1], self.owner)
        self.assertEqual(self.api_calls[0], ("user", None, None))
        self.assertFalse(any(method == "POST" for _, _, method in self.api_calls))

    def test_sync_does_not_accept_organization_as_approval_author(self):
        self.comments = [{"user": {"login": self.owner},
                          "body": '/lgax-sync\n```json\n' + json.dumps({"commit": HEAD}) + '\n```',
                          "created_at": "2026-10-05T00:00:00Z"}]
        self.run_sync()
        mutations = [(path, data) for path, data, method in self.api_calls if method == "POST"]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][0], f"repos/{bootstrap.REPO}/issues/28/comments")

    def test_sync_rejects_non_pm_before_any_mutation(self):
        self.login = self.owner
        original = (self.phase / "github.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "authenticated PM"):
            self.run_sync()
        self.assertEqual(self.api_calls, [("user", None, None)])
        self.assertEqual(self.gh_calls, [])
        self.assertEqual((self.phase / "github.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
