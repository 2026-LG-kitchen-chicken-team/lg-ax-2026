"""Isolated authorization/projection tests, not evidence of live board delivery."""
from __future__ import annotations

import base64
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_report as client
import project_report_common as common

from services.project_reports import worker

REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
TASK = "P2-CORE-001"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
AT = "2026-10-04T10:00:00Z"


class FixtureAPI:
    """No network; persists board writes and receipts to exercise retry behavior."""

    def __init__(self):
        self.login = "unknownamed"
        self.issue = {"state": "open", "assignees": [{"login": self.login}]}
        self.pr = {"state": "open", "draft": False, "user": {"login": self.login},
                   "base": {"ref": "main"},
                   "head": {"sha": COMMIT, "repo": {"full_name": REPO}}}
        self.file_text = "Recorded intent, changes, actual checks and limitations.\n"
        self.file_type = "file"
        self.comments = []
        self.posts = []
        self.calls = []
        self.mutations = []
        self.board = None
        self.fail_mutation = None
        self.fail_contents = False

    def api(self, path, data=None, method=None):
        self.calls.append((path, data, method))
        if path == "user":
            return {"login": self.login}
        if "/contents/" in path:
            if self.fail_contents:
                raise RuntimeError("fixture transport failure")
            return {"type": self.file_type, "sha": "c" * 40,
                    "content": base64.b64encode(self.file_text.encode()).decode()}
        if path.endswith("/issues/7"):
            return copy.deepcopy(self.issue)
        if "/pulls/" in path:
            return copy.deepcopy(self.pr)
        if path.endswith("/comments") and method == "POST":
            issue_number = int(path.split("/issues/")[1].split("/")[0])
            row = {"id": 1000 + len(self.posts), "user": {"login": "jeongiryang"},
                   "body": data["body"], "issue_number": issue_number,
                   "html_url": f"https://github.com/{REPO}/issues/{issue_number}#issuecomment-{1000 + len(self.posts)}"}
            self.posts.append(row)
            return copy.deepcopy(row)
        raise AssertionError(f"Unexpected fixture request: {path}")

    def pages(self, path):
        if "/issues/comments?" in path:
            return copy.deepcopy(self.comments)
        if match := re.search(r"/issues/(\d+)/comments$", path):
            return copy.deepcopy([p for p in self.posts if p.get("issue_number", 7) == int(match[1])])
        raise AssertionError(f"Unexpected fixture pagination: {path}")

    def graphql(self, query, variables):
        self.mutations.append(copy.deepcopy(variables))
        if self.fail_mutation == len(self.mutations):
            raise RuntimeError("fixture project transport failure")
        if self.board:
            name = next(name for name, value in self.board["fields"].items() if value["id"] == variables["field"])
            payload = variables["value"]
            value = payload.get("text")
            if "singleSelectOptionId" in payload:
                value = next(o["name"] for o in self.board["fields"][name]["options"]
                             if o["id"] == payload["singleSelectOptionId"])
            item = next(i for i in self.board["items"].values() if i["id"] == variables["item"])
            item["values"][name] = value
        return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": variables["item"]}}}


class ProjectReportTests(unittest.TestCase):
    def setUp(self):
        self.api = FixtureAPI()
        self.policy = {"repo": REPO, "project_id": "fixture-project", "project_url": "https://github.com/users/jeongiryang/projects/3",
                       "pm_account": "jeongiryang", "accept_reports_after": "2026-10-04T09:00:00Z",
                       "tasks": {TASK: {"name": "황대겸", "account": "unknownamed", "issue_number": 7, "item_id": "fixture-item"}}}
        self.tasks = {TASK: {"id": TASK, "title": "Core judgment", "owner": "황대겸", "status": "ready",
                             "scope": "required", "depends_on": [], "history": []}}
        self.policy.update(governance_issue_number=28, approved_main_commit=COMMIT,
                           approved_tasks=copy.deepcopy(self.tasks))
        self.main_commit = COMMIT
        self.report = {"task_id": TASK, "status": "doing", "summary": "구현 중; 실제 품질 검증은 남음",
                       "next_action": "실제 입력으로 검증 후 PR 요청",
                       "log_url": f"https://github.com/{REPO}/blob/{COMMIT}/docs/작업기록/황대겸.md",
                       "evidence_url": f"https://github.com/{REPO}/blob/{COMMIT}/docs/작업근거/황대겸.md"}

    def comment(self, report=None, **changes):
        value = {"id": 101, "body": common.report_body(report or self.report), "user": {"login": "unknownamed"},
                 "created_at": AT, "updated_at": AT, "issue_url": f"https://api.github.com/repos/{REPO}/issues/7",
                 "html_url": f"https://github.com/{REPO}/issues/7#issuecomment-101"}
        value.update(changes)
        return value

    def validate(self, report=None, **changes):
        return common.validate_submission(self.api, self.policy, self.comment(report, **changes), self.tasks)

    def board(self):
        fields = {name: {"id": "field-" + str(i), "name": name}
                  for i, name in enumerate(["Status", "팀원 보고", "최근 보고", "다음 행동", "진행상태", "실행 증빙"])}
        fields["Status"]["options"] = [{"id": "option-" + name, "name": name} for name in ("Todo", "In Progress", "Done")]
        fields["팀원 보고"]["options"] = [{"id": "report-" + name, "name": name} for name in common.REPORT_STATES.values()]
        return {"fields": fields, "items": {7: {"id": "fixture-item", "values": {"Status": "Todo", "진행상태": "Ready",
                                                                                     "실행 증빙": "PM-owned evidence"}}},
                "url": self.policy["project_url"], "at": AT}

    def test_valid_doing_is_authenticated_report_not_semantic_approval(self):
        result = self.validate()
        self.assertEqual(result["actor"], "unknownamed")
        self.assertEqual(result["comment_id"], 101)
        self.assertEqual(result["versions"]["log_url"]["commit"], COMMIT)
        self.assertEqual(result["versions"]["log_url"]["sha256"], common.digest(self.api.file_text))
        self.assertIn("not independently verified", result["meaning"])

    def test_valid_blocked_requires_reason(self):
        report = {**self.report, "status": "blocked", "reason": "자료 인수 대기"}
        self.assertEqual(self.validate(report)["report"]["status"], "blocked")
        del report["reason"]
        with self.assertRaisesRegex(ValueError, "blocked requires"):
            common.report_body(report)

    def test_valid_review_request_uses_exact_non_draft_pr_head(self):
        report = {**self.report, "status": "review_requested", "pr_url": f"https://github.com/{REPO}/pull/44"}
        self.assertEqual(self.validate(report)["report"]["status"], "review_requested")
        self.assertTrue(any("/pulls/44" in row[0] for row in self.api.calls))

    def test_other_account_cannot_report_owner_task(self):
        for actor in ("ginaginaring", "jeongiryang", "unregistered"):
            with self.subTest(actor=actor), self.assertRaisesRegex(ValueError, "registered task owner"):
                self.validate(user={"login": actor})
        self.assertEqual(self.api.calls, [])

    def test_unknown_task_rejected_before_fetch(self):
        with self.assertRaisesRegex(ValueError, "registered task owner"):
            self.validate({**self.report, "task_id": "P2-CORE-999"})
        self.assertEqual(self.api.calls, [])

    def test_wrong_issue_and_wrong_repository_are_rejected(self):
        for url in (f"https://api.github.com/repos/{REPO}/issues/8", "https://api.github.com/repos/other/repo/issues/7"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "registered task Issue"):
                self.validate(issue_url=url)

    def test_closed_pr_and_unassigned_issue_are_rejected(self):
        for issue in ({"state": "closed", "assignees": [{"login": "unknownamed"}]},
                      {"state": "open", "assignees": [{"login": "unknownamed"}], "pull_request": {}},
                      {"state": "open", "assignees": [{"login": "ginaginaring"}]}):
            self.api.issue = issue
            with self.subTest(issue=issue), self.assertRaisesRegex(ValueError, "open assigned"):
                self.validate()

    def test_edited_command_requires_new_report(self):
        with self.assertRaisesRegex(ValueError, "edited report"):
            self.validate(updated_at="2026-10-04T10:01:00Z")

    def test_self_report_cannot_set_done_or_pm_stages(self):
        for state in ("done", "pm_approved", "merged", "integration_verified", "individual_verified", "pm_review_requested"):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "only doing"):
                common.report_body({**self.report, "status": state})

    def test_formally_pm_approved_or_later_task_cannot_be_overwritten(self):
        for state in common.PM_STATES:
            self.tasks[TASK]["status"] = state
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "cannot be overwritten"):
                self.validate()

    def test_unadopted_extension_is_rejected_and_adopted_is_allowed(self):
        self.tasks[TASK]["scope"] = "proposed_extension"
        with self.assertRaisesRegex(ValueError, "not adopted"):
            self.validate()
        self.tasks[TASK]["adoption"] = {"pm": "정이량", "evidence": "fixture"}
        self.assertEqual(self.validate()["actor"], "unknownamed")

    def test_partial_work_can_report_with_dependencies_without_unlocking_completion(self):
        dependency = "P2-DATA-001"
        self.tasks[dependency] = {"status": "doing"}
        self.tasks[TASK]["depends_on"] = [dependency]
        for report in (self.report, {**self.report, "status": "review_requested", "pr_url": f"https://github.com/{REPO}/pull/44"}):
            with self.subTest(status=report["status"]):
                result = self.validate(report)
                self.assertEqual(result["waiting_for"], [dependency])
                self.assertEqual(self.tasks[TASK]["status"], "ready")
                self.assertEqual(self.tasks[dependency]["status"], "doing")

    def test_report_freshness_compares_actual_instants_not_timestamp_strings(self):
        accepted = self.validate()
        task = {**self.tasks[TASK], "history": [{"at": "2026-10-04T18:59:00+09:00"}]}
        self.assertTrue(common.latest_is_current(task, accepted))
        task["history"] = [{"at": "2026-10-04T10:00:00.100000+00:00"}]
        self.assertFalse(common.latest_is_current(task, accepted))

    def test_log_and_evidence_must_be_immutable_own_files(self):
        for key, url in (("log_url", self.report["log_url"].replace(COMMIT, "main")),
                         ("log_url", self.report["log_url"].replace("황대겸", "신진하")),
                         ("evidence_url", self.report["evidence_url"].replace("작업근거", "작업기록")),
                         ("log_url", self.report["log_url"].replace("github.com", "evil.example")),
                         ("log_url", self.report["log_url"] + "?token=abc")):
            with self.subTest(key=key, url=url), self.assertRaises(ValueError):
                self.validate({**self.report, key: url})

    def test_encoded_korean_links_retain_own_path_identity(self):
        from urllib.parse import quote
        report = {**self.report, "log_url": quote(self.report["log_url"], safe=":/"),
                  "evidence_url": quote(self.report["evidence_url"], safe=":/")}
        result = self.validate(report)
        self.assertEqual(result["versions"]["log_url"]["path"], "docs/작업기록/황대겸.md")
        self.assertTrue(any("docs/작업기록/황대겸.md" in unquote(c[0]) for c in self.api.calls))

    def test_log_and_evidence_cannot_use_different_commits(self):
        with self.assertRaisesRegex(ValueError, "same commit"):
            self.validate({**self.report, "evidence_url": self.report["evidence_url"].replace(COMMIT, OTHER_COMMIT)})

    def test_empty_or_non_file_source_rejected(self):
        self.api.file_text = " \n"
        with self.assertRaisesRegex(ValueError, "empty"):
            self.validate()
        self.api.file_text = "fixture"
        self.api.file_type = "dir"
        with self.assertRaisesRegex(ValueError, "published log/evidence"):
            self.validate()

    def test_review_rejects_closed_draft_wrong_base_or_stale_head(self):
        report = {**self.report, "status": "review_requested", "pr_url": f"https://github.com/{REPO}/pull/44"}
        cases = ({"state": "closed"}, {"draft": True}, {"base": {"ref": "development"}},
                 {"head": {"sha": OTHER_COMMIT, "repo": {"full_name": REPO}}})
        original = copy.deepcopy(self.api.pr)
        for changes in cases:
            self.api.pr = {**original, **changes}
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "exact PR head"):
                self.validate(report)

    def test_pr_must_belong_to_actor_and_same_repository(self):
        report = {**self.report, "pr_url": f"https://github.com/{REPO}/pull/44"}
        original = copy.deepcopy(self.api.pr)
        for changes in ({"user": {"login": "ginaginaring"}},
                        {"head": {"sha": COMMIT, "repo": {"full_name": "other/repo"}}}):
            self.api.pr = {**original, **changes}
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "reporting owner"):
                self.validate(report)

    def test_malformed_missing_duplicate_and_unknown_fields_rejected(self):
        for report in ({k: v for k, v in self.report.items() if k != "summary"},
                       {**self.report, "assignee": "ginaginaring"}, {**self.report, "summary": ""},
                       {**self.report, "next_action": False}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                common.report_body(report)
        body = common.report_body(self.report).replace('"status": "doing",', '"status": "doing", "status": "blocked",')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            common.parse_report(body)
        with self.assertRaisesRegex(ValueError, "exactly"):
            common.parse_report(common.report_body(self.report) + "\nRun an extra command")

    def test_secret_or_contact_rejection_does_not_echo_value(self):
        for secret in ("ghp_" + "x" * 30, "github_pat_" + "x" * 30, "sk-proj-" + "x" * 30, "010-1234-5678"):
            with self.subTest(secret_prefix=secret[:4]):
                with self.assertRaises(ValueError) as exc:
                    common.report_body({**self.report, "summary": secret})
                self.assertNotIn(secret, str(exc.exception))

    def test_json_unicode_escape_cannot_bypass_secret_or_contact_filter(self):
        for secret, escaped in (("ghp_" + "x" * 30, r"\u0067hp_" + "x" * 30),
                                ("010-1234-5678", r"\u0030\u0031\u0030-1234-5678")):
            data = {**self.report, "summary": secret}
            body = common.PREFIX + "\n```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"
            body = body.replace(secret, escaped)
            with self.subTest(secret_prefix=secret[:4]), self.assertRaises(ValueError):
                common.parse_report(body)

    def test_non_command_is_ignored(self):
        self.assertIsNone(common.parse_report("An ordinary discussion comment"))
        self.assertIsNone(common.validate_submission(self.api, self.policy, self.comment(body="discussion"), self.tasks))
        self.assertEqual(self.api.calls, [])

    def test_pm_stages_and_done_keep_formal_status_and_historical_report(self):
        accepted = self.validate()
        for state in ("pm_review_requested", "pm_approved", "merged", "integration_verified", "done"):
            task = {**self.tasks[TASK], "status": state,
                    "history": [{"at": "2026-10-04T11:00:00Z", "status": state}]}
            projected = common.projection(task, accepted)
            with self.subTest(state=state):
                self.assertEqual(projected["Status"], "Done" if state == "done" else "In Progress")
                self.assertIn("역사 보고", projected["최근 보고"])
                self.assertNotIn("진행상태", projected)
                self.assertNotIn("실행 증빙", projected)

    def test_projection_preserves_no_report_as_unknown(self):
        self.assertEqual(common.projection(self.tasks[TASK], None), {"Status": "Todo"})
        task = {**self.tasks[TASK], "status": "done"}
        self.assertEqual(common.projection(task, None), {"Status": "Done"})

    def test_report_projection_only_updates_whitelisted_fields(self):
        board = self.board()
        self.api.board = board
        accepted = self.validate()
        values = common.projection(self.tasks[TASK], accepted)
        self.assertEqual(set(values), common.REPORT_FIELDS)
        updated = common.update_fields(self.api, self.policy, board, board["items"][7], values)
        self.assertEqual(set(updated), common.REPORT_FIELDS)
        self.assertEqual(board["items"][7]["values"]["진행상태"], "Ready")
        self.assertEqual(board["items"][7]["values"]["실행 증빙"], "PM-owned evidence")
        self.assertEqual(common.update_fields(self.api, self.policy, board, board["items"][7], values), [])
        self.assertEqual(len(self.api.mutations), 4)

    def test_forbidden_field_rejected_before_any_mutation(self):
        for field in ("진행상태", "실행 증빙", "담당자", "우선순위", "목표일"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "only Status"):
                common.update_fields(self.api, self.policy, self.board(), self.board()["items"][7], {field: "changed"})
        self.assertEqual(self.api.mutations, [])

    def test_client_dry_run_and_send_authenticate_actual_account(self):
        with patch.object(client, "published_tasks", return_value=(self.tasks, COMMIT)):
            result = client.submit(self.api, self.policy, self.report)
            self.assertTrue(result["validated"])
            self.assertFalse(result["sent"])
            self.assertEqual(self.api.posts, [])
            result = client.submit(self.api, self.policy, self.report, send=True)
            self.assertTrue(result["sent"])
            self.assertFalse(result["project_updated"])
            self.assertEqual(len(self.api.posts), 1)
            self.api.login = "ginaginaring"
            with self.assertRaisesRegex(ValueError, "authenticated GitHub account"):
                client.submit(self.api, self.policy, self.report, send=True)
            self.assertEqual(len(self.api.posts), 1)

    def test_status_reconciles_board_and_formal_record_instead_of_inferred_completion(self):
        board = self.board()
        board["items"][7]["values"].update({"Status": "Done", "진행상태": "Done"})
        with patch.object(client, "published_tasks", return_value=(self.tasks, COMMIT)), \
                patch.object(client, "project_snapshot", return_value=board):
            result = client.status(self.api, self.policy, member="unknownamed")
            row = result["tasks"][0]
            self.assertEqual(row["formal_harness_status"], "ready")
            self.assertTrue(row["formal_display_mismatch"])
            self.assertEqual(row["self_report_status"], "No report")
            self.assertIsNone(row["latest_report"])
            self.assertFalse(row["may_start"])
            self.assertTrue(any("not proof of inactivity" in value for value in result["interpretation"]))
            with self.assertRaisesRegex(ValueError, "unknown member"):
                client.status(self.api, self.policy, member="unregistered")

    def test_status_identifies_waiting_dependencies_and_unadopted_extensions(self):
        dependency = "P2-DATA-001"
        self.tasks[dependency] = {"status": "doing"}
        self.tasks[TASK].update(depends_on=[dependency], scope="proposed_extension", adoption=None)
        with patch.object(client, "published_tasks", return_value=(self.tasks, COMMIT)), \
                patch.object(client, "project_snapshot", return_value=self.board()):
            row = client.status(self.api, self.policy)["tasks"][0]
            self.assertEqual(row["waiting_for"], [dependency])
            self.assertFalse(row["may_start"])
            self.assertTrue(row["adoption_required"])

    def tick(self, directory):
        with patch.object(worker, "published_tasks", return_value=(self.tasks, self.main_commit)), \
                patch.object(worker, "project_snapshot", side_effect=lambda *_: copy.deepcopy(self.api.board)):
            return worker.tick(self.api, self.policy, directory)

    def test_worker_accepts_once_and_receipt_is_after_projection(self):
        self.api.board = self.board()
        self.api.comments = [self.comment()]
        with tempfile.TemporaryDirectory() as directory:
            first = self.tick(directory)
            self.assertEqual(first["accepted"], 1)
            self.assertFalse(first["semantic_verification"])
            self.assertEqual(len(self.api.posts), 1)
            self.assertIn("LGAX-RECEIPT 101 ACCEPTED", self.api.posts[0]["body"])
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["latest"][TASK]["body_sha256"], common.digest(self.comment()["body"]))
            count = len(self.api.mutations)
            second = self.tick(directory)
            self.assertEqual(second["mutations"], [])
            self.assertEqual(len(self.api.mutations), count)
            self.assertEqual(len(self.api.posts), 1)

    def test_partial_projection_failure_retries_without_duplicate_report_or_receipt(self):
        self.api.board = self.board()
        self.api.comments = [self.comment()]
        self.api.fail_mutation = 2
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "transport failure"):
                self.tick(directory)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["seen"]["101"]["outcome"], "accepted")
            self.assertIsNone(state["seen"]["101"]["receipt_url"])
            self.assertEqual(self.api.posts, [])
            self.api.fail_mutation = None
            result = self.tick(directory)
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(len(self.api.posts), 1)
            # Status already written before failure; retry writes the other three fields.
            self.assertEqual(result["mutations"][0]["fields"], ["팀원 보고", "최근 보고", "다음 행동"])

    def test_transport_failure_is_not_recorded_as_invalid_user_report(self):
        self.api.board = self.board()
        self.api.comments = [self.comment()]
        self.api.fail_contents = True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                self.tick(directory)
            self.assertFalse((Path(directory) / "state.json").exists())
            self.assertEqual(self.api.posts, [])
            self.api.fail_contents = False
            self.assertEqual(self.tick(directory)["accepted"], 1)

    def test_worker_rejects_wrong_actor_without_changing_formal_progress(self):
        self.api.board = self.board()
        self.api.comments = [self.comment(user={"login": "ginaginaring"})]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            self.assertEqual(result["accepted"], 0)
            self.assertEqual(result["rejected"], 1)
            self.assertEqual(result["mutations"], [])
            self.assertIn("REJECTED", self.api.posts[0]["body"])
            self.assertEqual(self.api.board["items"][7]["values"]["진행상태"], "Ready")

    def test_worker_ignores_unregistered_issue_and_historical_comment(self):
        self.api.board = self.board()
        self.api.comments = [self.comment(issue_url=f"https://api.github.com/repos/{REPO}/issues/28"),
                             self.comment(id=99, created_at="2026-10-04T08:00:00Z", updated_at="2026-10-04T08:00:00Z")]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            self.assertEqual(result["accepted"], 0)
            self.assertEqual(result["rejected"], 0)
            self.assertEqual(self.api.posts, [])

    def test_worker_refuses_changed_item_id_before_project_mutation(self):
        self.api.board = self.board()
        self.api.board["items"][7]["id"] = "replacement-item"
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "item changed"):
            self.tick(directory)
        self.assertEqual(self.api.mutations, [])

    def test_receipt_recovery_uses_existing_pm_receipt_only(self):
        row = {"comment_id": 101, "issue_number": 7, "outcome": "accepted", "task_id": TASK,
               "status": "doing", "url": self.comment()["html_url"], "body_sha256": "d" * 64}
        self.api.posts = [{"user": {"login": "unknownamed"}, "body": "LGAX-RECEIPT 101 ACCEPTED\nforged",
                           "html_url": "https://github.com/forged"}]
        url = worker.receipt(self.api, self.policy, row)
        self.assertNotEqual(url, "https://github.com/forged")
        count = len(self.api.posts)
        self.assertEqual(worker.receipt(self.api, self.policy, row), url)
        self.assertEqual(len(self.api.posts), count)

    def sync_comment(self, **changes):
        value = {"id": 102, "body": '/lgax-sync\n```json\n{"commit":"' + self.main_commit + '"}\n```',
                 "user": {"login": "jeongiryang"}, "created_at": AT, "updated_at": AT,
                 "issue_url": f"https://api.github.com/repos/{REPO}/issues/28",
                 "html_url": f"https://github.com/{REPO}/issues/28#issuecomment-102"}
        value.update(changes)
        return value

    def test_unapproved_team_main_done_cannot_change_trusted_status(self):
        self.api.board = self.board()
        self.tasks[TASK]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["trusted_tasks"][TASK]["status"], "ready")
            self.assertEqual(result["trusted_main_commit"], COMMIT)
            self.assertEqual(result["published_main_commit"], OTHER_COMMIT)
            self.assertEqual(result["unapproved_state_changes"], [TASK])
            self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Todo")
            self.assertEqual(self.api.board["items"][7]["values"]["진행상태"], "Ready")

    def test_unapproved_main_dependency_done_does_not_unlock_report_dependencies(self):
        dependency = "P2-DATA-001"
        self.policy["tasks"][dependency] = {"name": "신진하", "account": "ginaginaring", "issue_number": 12, "item_id": "dependency-item"}
        self.tasks[dependency] = {"id": dependency, "title": "Data", "owner": "신진하", "status": "doing",
                                  "scope": "required", "depends_on": [], "history": []}
        self.tasks[TASK]["depends_on"] = [dependency]
        self.policy["approved_tasks"] = copy.deepcopy(self.tasks)
        self.tasks[dependency]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        self.api.board = self.board()
        self.api.board["items"][12] = {"id": "dependency-item", "values": {"Status": "In Progress", "진행상태": "Doing"}}
        self.api.comments = [self.comment()]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["latest"][TASK]["waiting_for"], [dependency])
            self.assertEqual(state["trusted_tasks"][dependency]["status"], "doing")
            self.assertEqual(self.api.board["items"][12]["values"]["Status"], "In Progress")
            self.assertEqual(result["unapproved_state_changes"], [dependency])

    def test_unapproved_main_extension_adoption_does_not_authorize_report(self):
        self.tasks[TASK].update(scope="proposed_extension", adoption=None)
        self.policy["approved_tasks"] = copy.deepcopy(self.tasks)
        self.tasks[TASK]["adoption"] = {"pm": "정이량", "evidence": "unapproved team main edit"}
        self.api.board = self.board()
        self.api.comments = [self.comment()]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            self.assertEqual(result["accepted"], 0)
            self.assertEqual(result["rejected"], 1)
            self.assertIn("not adopted", self.api.posts[0]["body"])

    def test_genuine_pm_sync_approves_exact_main_snapshot_and_survives_restart(self):
        self.tasks[TASK]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        self.api.board = self.board()
        self.api.comments = [self.sync_comment()]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(result["trusted_main_commit"], OTHER_COMMIT)
            self.assertEqual(result["unapproved_state_changes"], [])
            self.assertEqual(state["seen"]["102"]["type"], "formal_sync")
            self.assertEqual(state["trusted_tasks"][TASK]["status"], "done")
            self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Done")
            self.assertIn("PM 공식 상태 스냅샷", self.api.posts[0]["body"])
            self.assertEqual(self.api.posts[0]["issue_number"], 28)
            # A subsequent team push cannot replace the already durable trusted state.
            self.tasks[TASK]["status"] = "doing"
            self.main_commit = "d" * 40
            repeated = self.tick(directory)
            self.assertEqual(repeated["trusted_main_commit"], OTHER_COMMIT)
            self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Done")
            self.assertEqual(len(self.api.posts), 1)

    def test_non_pm_wrong_issue_edited_and_stale_sha_syncs_are_rejected(self):
        cases = ({"user": {"login": "unknownamed"}},
                 {"issue_url": f"https://api.github.com/repos/{REPO}/issues/7"},
                 {"issue_url": "https://api.github.com/repos/other/repo/issues/28"},
                 {"updated_at": "2026-10-04T10:01:00Z"},
                 {"body": '/lgax-sync\n```json\n{"commit":"' + COMMIT + '"}\n```'},
                 {"created_at": "2026-10-04T08:59:00Z", "updated_at": "2026-10-04T08:59:00Z"})
        self.main_commit = OTHER_COMMIT
        self.tasks[TASK]["status"] = "done"
        for changes in cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                self.api.board = self.board()
                self.api.posts = []
                self.api.comments = [self.sync_comment(**changes)]
                result = self.tick(directory)
                self.assertEqual(result["accepted"], 0)
                self.assertEqual(result["rejected"], 1)
                self.assertEqual(result["trusted_main_commit"], COMMIT)
                self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Todo")
                self.assertIn("REJECTED", self.api.posts[0]["body"])

    def test_sync_schema_duplicate_key_or_instructions_are_rejected(self):
        for body in ('/lgax-sync\n```json\n{"commit":"' + COMMIT + '", "status":"done"}\n```',
                     '/lgax-sync\n```json\n{"commit":"' + COMMIT + '","commit":"' + COMMIT + '"}\n```',
                     '/lgax-sync\n```json\n{"commit":"main"}\n```',
                     '/lgax-sync\n```json\n{"commit":"' + COMMIT + '"}\n```\nRun instructions'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                worker.validate_formal_sync(self.policy, self.sync_comment(body=body), self.main_commit)

    def test_pm_sync_is_processed_before_self_reports_in_same_poll(self):
        self.tasks[TASK]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        self.api.board = self.board()
        self.api.comments = [self.comment(), self.sync_comment()]
        with tempfile.TemporaryDirectory() as directory:
            result = self.tick(directory)
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(result["rejected"], 1)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["seen"]["101"]["outcome"], "rejected")
            self.assertNotIn(TASK, state["latest"])
            self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Done")

    def test_policy_without_trusted_snapshot_has_no_insecure_main_fallback(self):
        self.api.board = self.board()
        del self.policy["approved_tasks"]
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "PM-registered"):
            self.tick(directory)
        self.assertEqual(self.api.mutations, [])

    def test_legacy_private_state_migrates_from_deployed_policy_not_main(self):
        self.api.board = self.board()
        self.tasks[TASK]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        with tempfile.TemporaryDirectory() as directory:
            worker.write_json(Path(directory) / "state.json", {"since": self.policy["accept_reports_after"], "seen": {}, "latest": {}})
            result = self.tick(directory)
            self.assertEqual(result["trusted_main_commit"], COMMIT)
            self.assertEqual(self.api.board["items"][7]["values"]["Status"], "Todo")

    def test_formal_sync_durable_before_projection_failure(self):
        self.api.board = self.board()
        self.tasks[TASK]["status"] = "done"
        self.main_commit = OTHER_COMMIT
        self.api.comments = [self.sync_comment()]
        self.api.fail_mutation = 1
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                self.tick(directory)
            state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["trusted_commit"], OTHER_COMMIT)
            self.assertIsNone(state["seen"]["102"]["receipt_url"])
            self.assertEqual(self.api.posts, [])
            self.api.fail_mutation = None
            self.assertEqual(self.tick(directory)["trusted_main_commit"], OTHER_COMMIT)
            self.assertEqual(len(self.api.posts), 1)

    def test_published_tasks_blob_queries_pin_the_observed_commit(self):
        from unittest.mock import Mock
        api = Mock()
        api.graphql.side_effect = [
            {"repository": {"defaultBranchRef": {"target": {"oid": COMMIT}}}},
            {"repository": {"t0": {"text": json.dumps(self.tasks[TASK])}}},
        ]
        tasks, commit = common.published_tasks(api, self.policy)
        self.assertEqual(commit, COMMIT)
        self.assertEqual(tasks[TASK]["status"], "ready")
        query = api.graphql.call_args_list[1].args[0]
        self.assertIn(COMMIT + ":harness/phase2/tasks/", query)
        self.assertNotIn('expression:"main:', query)


if __name__ == "__main__":
    unittest.main()
