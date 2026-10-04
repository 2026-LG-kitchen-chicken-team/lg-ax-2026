"""PM mail outbox/receipt invariants with isolated files and mocked external APIs."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import assign_task as assignments

REPO = "jeongiryang/lg-ax-2026"
TASK = "P2-CORE-001"
AID = "PM-20261004-core-start"
MESSAGE = "a1234567890abcdef"


class AssignmentAPI:
    def __init__(self):
        self.login = "jeongiryang"
        self.state = "open"
        self.pull_request = False
        self.comments = {}
        self.mutations = []
        self.fail_comment = False
        self.fail_after_comment = False
        self.fail_pages = False

    def api(self, path, data=None, method=None):
        if path == "user":
            return {"login": self.login}
        if "/issues/" not in path:
            raise AssertionError(f"Unexpected assignment fixture request: {path}")
        issue_number = int(path.split("/issues/")[1].split("/")[0])
        if method != "POST":
            issue = {"state": self.state, "html_url": f"https://github.com/{REPO}/issues/{issue_number}"}
            if self.pull_request:
                issue["pull_request"] = {}
            return issue
        self.mutations.append((path, copy.deepcopy(data)))
        if path.endswith("/assignees"):
            return {}
        if path.endswith("/comments"):
            if self.fail_comment:
                raise RuntimeError("fixture Issue transport failure")
            rows = self.comments.setdefault(issue_number, [])
            row = {"user": {"login": "jeongiryang"}, "body": data["body"],
                   "issue_url": f"https://api.github.com/repos/{REPO}/issues/{issue_number}",
                   "html_url": f"https://github.com/{REPO}/issues/{issue_number}#issuecomment-{100 + len(rows)}"}
            rows.append(row)
            if self.fail_after_comment:
                raise RuntimeError("fixture lost response after server accepted comment")
            return copy.deepcopy(row)
        raise AssertionError(f"Unexpected assignment fixture mutation: {path}")

    def pages(self, path):
        if self.fail_pages:
            raise RuntimeError("fixture Issue transport failure")
        if path == f"repos/{REPO}/issues/comments":
            return copy.deepcopy([c for rows in self.comments.values() for c in rows])
        issue_number = int(path.split("/issues/")[1].split("/")[0])
        return copy.deepcopy(self.comments.get(issue_number, []))


class AssignTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.public = self.root / "docs" / "assignments"
        self.private_patch = patch.object(assignments, "PRIVATE", self.private)
        self.public_patch = patch.object(assignments, "PUBLIC", self.public)
        self.field_patch = patch.object(assignments, "pm_field")
        self.private_patch.start()
        self.public_patch.start()
        self.update_field = self.field_patch.start()
        self.addCleanup(self.private_patch.stop)
        self.addCleanup(self.public_patch.stop)
        self.addCleanup(self.field_patch.stop)
        self.api = AssignmentAPI()
        self.policy = {"repo": REPO, "pm_account": "jeongiryang", "project_id": "fixture-project",
                       "project_url": "https://github.com/users/jeongiryang/projects/3",
                       "tasks": {TASK: {"name": "황대겸", "account": "unknownamed", "issue_number": 7, "item_id": "core-item"},
                                 "P2-DATA-001": {"name": "신진하", "account": "ginaginaring", "issue_number": 12, "item_id": "data-item"},
                                 "P2-PM-001": {"name": "정이량", "account": "jeongiryang", "issue_number": 17, "item_id": "pm-item"}}}
        self.assignment = {"assignment_id": AID, "task_id": TASK, "purpose": "핵심 판단 구현 착수",
                           "instructions": ["배정과 연결 규격을 읽는다.", "실제 모델 실행 근거를 남긴다."],
                           "acceptance": ["정상·오류·근거 부족 입력을 검증한다."],
                           "next_action": "자기 docs와 Issue에 의도 및 상태를 보고한다."}
        self.contacts = {"sender": {"name": "정이량", "email": "pm@example.test"},
                         "contacts": {"unknownamed": {"name": "황대겸", "email": "core@example.test",
                                                    "source": "private/fixture/contact-evidence.json", "verified_at": "2026-10-04T10:00:00Z"},
                                      "ginaginaring": {"name": "신진하", "email": "data@example.test",
                                                      "source": "private/fixture/contact-evidence.json", "verified_at": "2026-10-04T10:00:00Z"}}}

    def prepare(self, assignment=None, contacts=None, apply=True):
        result = assignments.prepare(self.api, self.policy, assignment or self.assignment, contacts or self.contacts, apply)
        if apply:
            assignments.write(self.private / "contacts.json", contacts or self.contacts)
        return result

    def outbox(self):
        return json.loads((self.private / "outbox" / (AID + ".json")).read_text(encoding="utf-8"))

    def save_outbox(self, row):
        assignments.write(self.private / "outbox" / (AID + ".json"), row)

    def receipt(self, **changes):
        return {"assignment_id": AID, "message_id": MESSAGE, "source": "Gmail send_email result",
                "recipient_email": "core@example.test", "sender_email": "pm@example.test",
                "subject": self.outbox()["subject"], "sent_observed": True, **changes}

    def sending(self):
        return assignments.record(self.api, self.policy, AID, "sending")

    def sent(self, receipt=None):
        return assignments.record(self.api, self.policy, AID, "sent", receipt or self.receipt())

    def test_only_authenticated_pm_can_prepare_or_record(self):
        self.prepare()
        before = len(self.api.mutations)
        for account in ("unknownamed", "ginaginaring", "choigilung", "unregistered"):
            self.api.login = account
            with self.subTest(account=account):
                with self.assertRaisesRegex(ValueError, "authenticated PM"):
                    self.prepare()
                with self.assertRaisesRegex(ValueError, "authenticated PM"):
                    self.sending()
        self.assertEqual(len(self.api.mutations), before)

    def test_fresh_pm_clone_cannot_reuse_assignment_id_on_another_issue(self):
        self.prepare()
        (self.private / "outbox" / (AID + ".json")).unlink()
        before = len(self.api.mutations)
        other = {**self.assignment, "task_id": "P2-DATA-001"}
        with self.assertRaisesRegex(ValueError, "another Issue/version"):
            self.prepare(assignment=other)
        self.assertEqual(len(self.api.mutations), before)

    def test_no_verified_contact_or_wrong_name_rejected_without_mutations(self):
        for contact in ({}, {"name": "다른 사람", "email": "core@example.test", "source": "fixture", "verified_at": "2026-10-04"},
                        {"name": "황대겸", "email": "core@example.test", "source": "fixture"},
                        {"name": "황대겸", "email": "core@example.test", "verified_at": "2026-10-04"}):
            with self.subTest(contact=contact), self.assertRaisesRegex(ValueError, "do not guess"):
                self.prepare(contacts={"contacts": {"unknownamed": contact}})
        self.assertEqual(self.api.mutations, [])
        self.assertFalse(self.private.exists())

    def test_noreply_malformed_or_header_injected_address_rejected(self):
        for address in ("12345+unknownamed@users.noreply.github.com", "not-an-email", "core@example.test\nBcc: other@example.test", "<core@example.test>"):
            contacts = copy.deepcopy(self.contacts)
            contacts["contacts"]["unknownamed"]["email"] = address
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, "deliverable"):
                self.prepare(contacts=contacts)
        self.assertEqual(self.api.mutations, [])

    def test_registered_teammate_open_issue_required(self):
        with self.assertRaisesRegex(ValueError, "registered task"):
            self.prepare({**self.assignment, "task_id": "P2-CORE-999"})
        with self.assertRaisesRegex(ValueError, "do not email the PM"):
            self.prepare({**self.assignment, "task_id": "P2-PM-001"})
        self.api.state = "closed"
        with self.assertRaisesRegex(ValueError, "open task Issue"):
            self.prepare()
        self.api.state = "open"
        self.api.pull_request = True
        with self.assertRaisesRegex(ValueError, "open task Issue"):
            self.prepare()
        self.assertEqual(self.api.mutations, [])

    def test_assignment_shape_and_id_reject_unknown_fields_and_path_traversal(self):
        for assignment in ({**self.assignment, "assignment_id": "../escape"},
                           {**self.assignment, "assignment_id": "PM-20261004-../escape"},
                           {**self.assignment, "instructions": []},
                           {**self.assignment, "acceptance": [False]},
                           {**self.assignment, "recipient_email": "other@example.test"}):
            with self.subTest(assignment=assignment), self.assertRaises(ValueError):
                self.prepare(assignment)
        self.assertEqual(self.api.mutations, [])

    def test_dry_run_does_not_write_issue_outbox_or_board(self):
        result = self.prepare(apply=False)
        self.assertTrue(result["ready"])
        self.assertFalse(result["applied"])
        self.assertEqual(self.api.mutations, [])
        self.update_field.assert_not_called()
        self.assertFalse(self.private.exists())
        self.assertNotIn("core@example.test", json.dumps(result))

    def test_prepare_records_assignment_without_claiming_mail_was_sent(self):
        result = self.prepare()
        row = self.outbox()
        self.assertEqual(result["mail_state"], "prepared")
        self.assertEqual(row["to"], "core@example.test")
        self.assertIsNone(row["message_id"])
        self.assertEqual(len(self.api.comments[7]), 1)
        self.assertTrue(self.api.comments[7][0]["body"].startswith("LGAX-ASSIGNMENT " + AID))
        for path in self.public.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("core@example.test", text)
            self.assertNotIn("private/fixture/contact-evidence.json", text)
        self.assertNotIn("core@example.test", json.dumps(result))
        self.assertIn("Do not infer send", result["next"])

    def test_repeated_prepare_reuses_same_comment_outbox_and_send_state(self):
        first = self.prepare()
        self.sending()
        self.sent()
        old = self.outbox()
        count = len(self.api.comments[7])
        second = self.prepare()
        self.assertEqual(second["assignment_url"], first["assignment_url"])
        self.assertEqual(second["mail_state"], "sent")
        self.assertEqual(self.outbox(), old)
        self.assertEqual(len(self.api.comments[7]), count)

    def test_public_assignment_file_roundtrip_preserves_sent_state_without_new_mail(self):
        first = self.prepare()
        self.sending()
        self.sent()
        count = len(self.api.comments[7])
        saved = json.loads((self.public / (AID + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(saved["assignment_url"], first["assignment_url"])
        second = self.prepare(saved)
        self.assertEqual(second["mail_state"], "sent")
        self.assertEqual(second["assignment_url"], first["assignment_url"])
        self.assertEqual(len(self.api.comments[7]), count)

    def test_public_assignment_metadata_cannot_change_pm_recipient_or_issue(self):
        for changed in ({"pm_account": "unknownamed"}, {"recipient_account": "ginaginaring"},
                        {"assignment_url": f"https://github.com/{REPO}/issues/12#issuecomment-100"},
                        {"assignment_url": "https://example.invalid/issues/7#issuecomment-100"}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "metadata mismatch"):
                self.prepare({**self.assignment, **changed})
        self.assertEqual(self.api.mutations, [])

    def test_remote_assignment_id_conflict_rejected_before_mutation(self):
        self.prepare()
        before = len(self.api.mutations)
        changed = {**self.assignment, "instructions": ["Different task request"]}
        with self.assertRaisesRegex(ValueError, "revision ID"):
            self.prepare(changed)
        self.assertEqual(len(self.api.mutations), before)

    def test_global_local_assignment_id_conflict_rejected_before_mutation(self):
        self.prepare()
        before = len(self.api.mutations)
        changed = {**self.assignment, "task_id": "P2-DATA-001"}
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.prepare(changed)
        self.assertEqual(len(self.api.mutations), before)
        self.assertNotIn(12, self.api.comments)

    def test_remote_sending_marker_prevents_guessing_new_send(self):
        self.api.comments[7] = [{"user": {"login": "jeongiryang"}, "body": f"LGAX-MAIL {AID} SENDING\nfixture pending result",
                                "html_url": f"https://github.com/{REPO}/issues/7#issuecomment-1"}]
        self.assertEqual(self.prepare()["mail_state"], "unknown")
        with self.assertRaisesRegex(ValueError, "check Gmail Sent"):
            self.sending()

    def test_remote_sent_marker_prevents_duplicate_send_with_missing_local_state(self):
        self.api.comments[7] = [{"user": {"login": "jeongiryang"}, "body": f"LGAX-MAIL {AID} SENT\nfixture actual send",
                                "html_url": f"https://github.com/{REPO}/issues/7#issuecomment-1"}]
        self.assertEqual(self.prepare()["mail_state"], "sent")
        with self.assertRaisesRegex(ValueError, "check Gmail Sent"):
            self.sending()

    def test_teammate_forged_mail_marker_is_not_pm_authority(self):
        self.api.comments[7] = [{"user": {"login": "unknownamed"}, "body": f"LGAX-MAIL {AID} SENT\nforged",
                                "html_url": f"https://github.com/{REPO}/issues/7#issuecomment-1"}]
        self.assertEqual(self.prepare()["mail_state"], "prepared")
        self.assertEqual(self.sending()["state"], "sending")

    def test_sending_gate_prevents_duplicate_sent_or_uncertain_mail(self):
        self.prepare()
        self.assertEqual(self.sending()["state"], "sending")
        with self.assertRaisesRegex(ValueError, "already sending"):
            self.sending()
        self.sent()
        with self.assertRaisesRegex(ValueError, "already sending"):
            self.sending()
        row = self.outbox()
        row["status"] = "unknown"
        self.save_outbox(row)
        with self.assertRaisesRegex(ValueError, "already sending"):
            self.sending()

    def test_sent_requires_prior_send_and_matching_actual_receipt(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "mark sending first"):
            self.sent()
        self.sending()
        for receipt in (self.receipt(message_id="invented"), self.receipt(assignment_id="PM-20261004-wrong"),
                        self.receipt(source="AI assumption"), self.receipt(recipient_email="wrong@example.test"),
                        self.receipt(sender_email="wrong@example.test"), self.receipt(subject="different assignment"),
                        self.receipt(sent_observed=False), None):
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                assignments.record(self.api, self.policy, AID, "sent", receipt)
        self.assertEqual(self.outbox()["status"], "sending")
        self.assertFalse((self.public / (AID + ".notification.json")).exists())

    def test_sent_receipt_is_durable_private_and_public_without_contact_address(self):
        self.prepare()
        self.sending()
        result = self.sent()
        self.assertEqual(result["state"], "sent")
        self.assertEqual(result["message_id"], MESSAGE)
        self.assertFalse(result["recipient_read_confirmed"])
        row = self.outbox()
        self.assertEqual(row["status"], "sent")
        receipt = json.loads((self.public / (AID + ".notification.json")).read_text(encoding="utf-8"))
        self.assertEqual(receipt["message_id"], MESSAGE)
        self.assertFalse(receipt["recipient_read_confirmed"])
        self.assertNotIn("core@example.test", json.dumps(receipt))
        self.assertEqual(sum(" SENT\n" in c["body"] for c in self.api.comments[7]), 1)

    def test_same_sent_receipt_is_idempotent_but_other_message_id_is_rejected(self):
        self.prepare()
        self.sending()
        self.sent()
        count = len(self.api.comments[7])
        self.sent()
        self.assertEqual(len(self.api.comments[7]), count)
        with self.assertRaisesRegex(ValueError, "different Gmail message ID"):
            self.sent(self.receipt(message_id="b" * 16))
        self.assertEqual(self.outbox()["message_id"], MESSAGE)

    def test_actual_sent_survives_issue_transport_failure_and_can_reconcile(self):
        self.prepare()
        self.sending()
        self.api.fail_pages = True
        with self.assertRaises(RuntimeError):
            self.sent()
        self.assertEqual(self.outbox()["status"], "sent")
        self.assertEqual(self.outbox()["message_id"], MESSAGE)
        self.assertTrue((self.public / (AID + ".notification.json")).exists())
        self.api.fail_pages = False
        self.assertEqual(self.sent()["state"], "sent")
        self.assertEqual(sum(" SENT\n" in c["body"] for c in self.api.comments[7]), 1)

    def test_actual_sent_survives_board_metadata_failure(self):
        self.prepare()
        self.sending()
        self.update_field.side_effect = RuntimeError("fixture board transport failure")
        with self.assertRaises(RuntimeError):
            self.sent()
        self.assertEqual(self.outbox()["status"], "sent")
        self.update_field.side_effect = None
        self.assertEqual(self.sent()["state"], "sent")
        self.assertEqual(sum(" SENT\n" in c["body"] for c in self.api.comments[7]), 1)

    def test_uncertain_sending_response_requires_sent_reconciliation(self):
        self.prepare()
        self.api.fail_after_comment = True
        with self.assertRaises(RuntimeError):
            self.sending()
        self.assertEqual(self.outbox()["status"], "prepared")
        self.api.fail_after_comment = False
        with self.assertRaisesRegex(ValueError, "check Gmail Sent"):
            self.sending()
        self.assertEqual(sum(" SENDING\n" in c["body"] for c in self.api.comments[7]), 1)

    def test_assignment_html_escapes_user_supplied_text(self):
        assignment = {**self.assignment, "purpose": "<script>unexpected</script>", "instructions": ['Use <b>literal</b> & "quoted" text']}
        self.prepare(assignment)
        text = self.outbox()["html"]
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("&lt;b&gt;literal&lt;/b&gt;", text)

    def test_pm_metadata_updater_rejects_any_non_metadata_field(self):
        self.field_patch.stop()
        for field in ("Status", "진행상태", "실행 증빙", "담당자", "우선순위"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "only assignment/mail"):
                assignments.pm_field(self.api, self.policy, self.policy["tasks"][TASK], {field: "changed"})


if __name__ == "__main__":
    unittest.main()
