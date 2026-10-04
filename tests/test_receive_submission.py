"""Isolated Git/API fixtures; these tests do not prove real owner execution."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.phase2 import fingerprint, intake_errors, read, task_path, write
from scripts.receive_submission import REPO, receive


class FakeAPI:
    def __init__(self, pr):
        self.login = "jeongiryang"
        self.pr = pr
        self.calls = []

    def api(self, path):
        self.calls.append(path)
        if path == "user":
            return {"login": self.login}
        if path == f"repos/{REPO}/pulls/36":
            return copy.deepcopy(self.pr)
        raise AssertionError("unexpected API request; never mutate remote state")


class SubmissionIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Intake fixture")
        self.git("config", "user.email", "fixture@example.test")
        self.git("config", "core.autocrlf", "false")
        self.tid = "P2-WEB-001"
        self.task = {
            "id": self.tid, "owner": "최길웅", "title": "isolated intake fixture",
            "status": "ready", "scope": "required", "depends_on": [],
            "allowed_execution_kinds": ["fixture"], "individual_evidence": None,
            "pm_review": None, "merge": None, "integration": None, "completion": None,
            "block_reason": None, "history": [],
        }
        self.bundle = {
            "workflow": {"pm": {"name": "정이량", "account": "jeongiryang"},
                         "roles": [{"name": "정이량", "account": "jeongiryang"},
                                   {"name": "최길웅", "account": "choigilung"}]},
            "tasks": {self.tid: self.task},
        }
        (self.root / "harness/phase2/tasks").mkdir(parents=True)
        write(self.root, task_path(self.tid), self.task)
        for path, content in [("code.py", "# isolated fixture code\n"),
                              ("source.txt", "fixture source\n"), ("output.txt", "fixture observed output\n")]:
            (self.root / path).write_text(content, encoding="utf-8")
        tested = self.commit()
        self.evidence = "evals/owner/individual.json"
        (self.root / "evals/owner").mkdir(parents=True)
        self.artifact = {
            "task_id": self.tid, "owner": "최길웅", "tested_commit": tested,
            "execution_kind": "fixture", "result": "pass",
            "observations": ["isolated fixture; no actual service or owner involved"],
            "limitations": ["API identity is simulated in this unit test"],
            "code_versions": [{**fingerprint(self.root, "code.py"), "git_commit": tested}],
            "source_versions": [{**fingerprint(self.root, "source.txt"), "git_commit": tested}],
            "checks": [{"name": "fixture output check", "passed": True,
                        "evidence": fingerprint(self.root, "output.txt")}], "models": [],
        }
        write(self.root, self.evidence, self.artifact)
        head = self.commit()
        self.api = FakeAPI({
            "number": 36, "user": {"login": "choigilung"}, "state": "open", "merged": False,
            "draft": False, "html_url": f"https://github.com/{REPO}/pull/36",
            "head": {"sha": head, "repo": {"full_name": REPO}},
            "base": {"ref": "main", "repo": {"full_name": REPO}},
        })
        self.receipt = "evals/pm/intake.json"

    def git(self, *args):
        return subprocess.run(["git", "--no-replace-objects", *args], cwd=self.root,
                              capture_output=True, check=True).stdout

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-q", "-m", "isolated intake fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def intake(self, apply=False):
        return receive(self.root, self.bundle, self.tid, 36, self.evidence, self.receipt,
                       self.api, apply=apply)

    def publish_artifact(self):
        write(self.root, self.evidence, self.artifact)
        self.api.pr["head"]["sha"] = self.commit()

    def test_preview_reads_source_without_local_or_remote_mutation(self):
        before = (self.root / task_path(self.tid)).read_bytes()
        result = self.intake()
        self.assertFalse(result["applied"])
        self.assertEqual((self.root / task_path(self.tid)).read_bytes(), before)
        self.assertFalse((self.root / self.receipt).exists())
        self.assertEqual(self.bundle["tasks"][self.tid]["status"], "ready")
        self.assertEqual(self.api.calls, ["user", f"repos/{REPO}/pulls/36"])

    def test_pm_intake_never_forges_owner_finish_or_final_completion(self):
        result = self.intake(apply=True)
        task = read(self.root, task_path(self.tid))
        self.assertTrue(result["applied"])
        self.assertEqual(task["status"], "individual_verified")
        self.assertEqual([r["action"] for r in task["history"]], ["PM_receive_submission"])
        self.assertEqual(task["individual_evidence"], fingerprint(self.root, self.evidence))
        self.assertIn("pm_intake", task)
        for key in ("pm_review", "merge", "integration", "completion"):
            self.assertIsNone(task[key])
        receipt = read(self.root, self.receipt)
        self.assertEqual(receipt["authenticated_pm"], "jeongiryang")
        self.assertEqual(receipt["submitted_by"], "choigilung")
        self.assertNotIn("body", receipt["source"])

    def test_harness_accepts_matching_intake_without_network_identity_claim(self):
        self.intake(apply=True)
        self.assertEqual(intake_errors(self.root, self.bundle, self.bundle["tasks"][self.tid]), [])

    def test_harness_detects_receipt_byte_tampering(self):
        self.intake(apply=True)
        with (self.root / self.receipt).open("ab") as output:
            output.write(b"\n")
        errors = intake_errors(self.root, self.bundle, self.bundle["tasks"][self.tid])
        self.assertTrue(any("changed" in error for error in errors))

    def test_harness_rejects_removed_receipt_reference_from_pm_intake_history(self):
        self.intake(apply=True)
        self.bundle["tasks"][self.tid].pop("pm_intake")
        errors = intake_errors(self.root, self.bundle, self.bundle["tasks"][self.tid])
        self.assertTrue(any("requires its receipt" in error for error in errors))

    def test_harness_rejects_rehashed_account_task_pr_and_owner_evidence_tampering(self):
        self.intake(apply=True)
        original = read(self.root, self.receipt)
        cases = [
            ("task_id", "P2-WEB-999", "task/owner/PM"),
            ("owner", "황대겸", "task/owner/PM"),
            ("pm", "최길웅", "task/owner/PM"),
            ("authenticated_pm", "choigilung", "task/owner/PM"),
            ("submitted_by", "unknownamed", "task/owner/PM"),
            ("source.author", "unknownamed", "PR/repository/owner"),
            ("source.pull_request_url", f"https://github.com/{REPO}/pull/999", "PR/repository/owner"),
            ("source.base_ref", "codex/other", "PR/repository/owner"),
            ("individual_evidence.sha256", "0" * 64, "original owner evidence"),
            ("owner_tested_commit", "f" * 40, "tested commit"),
            ("observed_at", "not-a-date", "timestamp"),
        ]
        for key, value, expected in cases:
            with self.subTest(field=key):
                changed = copy.deepcopy(original)
                if "." in key:
                    parent, child = key.split(".")
                    changed[parent][child] = value
                else:
                    changed[key] = value
                write(self.root, self.receipt, changed)
                self.bundle["tasks"][self.tid]["pm_intake"] = fingerprint(self.root, self.receipt)
                errors = intake_errors(self.root, self.bundle, self.bundle["tasks"][self.tid])
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_already_recorded_owner_evidence_and_history_are_preserved(self):
        self.task.update(status="individual_verified", individual_evidence=fingerprint(self.root, self.evidence))
        self.task["history"] = [{"action": "owner_finish", "status": "individual_verified"}]
        write(self.root, task_path(self.tid), self.task)
        self.intake(apply=True)
        task = read(self.root, task_path(self.tid))
        self.assertEqual(task["history"][0]["action"], "owner_finish")
        self.assertEqual(task["history"][1]["action"], "PM_receive_submission")

    def test_wrong_authenticated_account_is_rejected(self):
        self.api.login = "choigilung"
        with self.assertRaisesRegex(ValueError, "authenticated"):
            self.intake(apply=True)
        self.assertFalse((self.root / self.receipt).exists())

    def test_wrong_owner_pr_is_rejected(self):
        self.api.pr["user"]["login"] = "unknownamed"
        with self.assertRaisesRegex(ValueError, "owner"):
            self.intake()

    def test_fork_or_stacked_pr_is_not_silently_treated_as_main(self):
        self.api.pr["head"]["repo"]["full_name"] = "someone/lg-ax-2026"
        with self.assertRaisesRegex(ValueError, "same-repository"):
            self.intake()
        self.api.pr["head"]["repo"]["full_name"] = REPO
        self.api.pr["base"]["ref"] = "codex/owner-predecessor"
        with self.assertRaisesRegex(ValueError, "stacked"):
            self.intake()

    def test_closed_unmerged_and_draft_pr_are_rejected(self):
        self.api.pr["state"] = "closed"
        with self.assertRaisesRegex(ValueError, "actually merged"):
            self.intake()
        self.api.pr.update(state="open", draft=True)
        with self.assertRaisesRegex(ValueError, "non-draft"):
            self.intake()

    def test_actual_merged_pr_source_can_be_received_without_marking_task_merged(self):
        self.api.pr.update(state="closed", merged=True)
        self.intake(apply=True)
        self.assertEqual(read(self.root, task_path(self.tid))["status"], "individual_verified")

    def test_artifact_owner_mismatch_rejected_even_in_owner_pr(self):
        self.artifact["owner"] = "황대겸"
        self.publish_artifact()
        with self.assertRaisesRegex(ValueError, "artifact task/owner"):
            self.intake()

    def test_unpublished_local_artifact_bytes_are_rejected(self):
        self.artifact["observations"] = ["local-only unsubmitted revision"]
        write(self.root, self.evidence, self.artifact)
        with self.assertRaisesRegex(ValueError, "PR head blob"):
            self.intake()

    def test_tested_commit_can_precede_head_when_tested_files_did_not_change(self):
        self.assertNotEqual(self.artifact["tested_commit"], self.api.pr["head"]["sha"])
        self.assertTrue(self.intake()["validated"])

    def test_code_changed_after_owner_test_is_rejected(self):
        (self.root / "code.py").write_text("# changed after owner fixture test\n", encoding="utf-8")
        self.api.pr["head"]["sha"] = self.commit()
        with self.assertRaisesRegex(ValueError, "tested code/source changed"):
            self.intake()

    def test_later_code_version_cannot_be_claimed_under_an_earlier_tested_commit(self):
        (self.root / "code.py").write_text("# new code, not tested at claimed commit\n", encoding="utf-8")
        newer = self.commit()
        self.artifact["code_versions"][0] = {**fingerprint(self.root, "code.py"), "git_commit": newer}
        self.publish_artifact()
        with self.assertRaisesRegex(ValueError, "claimed owner tested commit"):
            self.intake()

    def test_bad_fixed_commit_and_output_hash_are_rejected(self):
        self.artifact["tested_commit"] = "not-a-commit"
        self.publish_artifact()
        with self.assertRaisesRegex(ValueError, "full tested commit"):
            self.intake()
        self.artifact["tested_commit"] = self.artifact["code_versions"][0]["git_commit"]
        self.artifact["checks"][0]["evidence"]["sha256"] = "0" * 64
        self.publish_artifact()
        with self.assertRaisesRegex(ValueError, "output evidence hash"):
            self.intake()

    def test_dependency_wait_cannot_receive_or_change_task_status(self):
        self.task["depends_on"] = ["P2-WEB-000"]
        self.bundle["tasks"]["P2-WEB-000"] = {"status": "individual_verified"}
        write(self.root, task_path(self.tid), self.task)
        before = (self.root / task_path(self.tid)).read_bytes()
        with self.assertRaisesRegex(ValueError, "unfinished dependencies"):
            self.intake(apply=True)
        self.assertEqual((self.root / task_path(self.tid)).read_bytes(), before)
        self.assertFalse((self.root / self.receipt).exists())

    def test_receipt_cannot_overwrite_files_or_escape_repository(self):
        self.receipt = self.evidence
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            self.intake(apply=True)
        self.receipt = "../outside.json"
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.intake(apply=True)

    def test_task_race_rejected_before_receipt_write(self):
        newer = copy.deepcopy(self.task)
        newer["block_reason"] = "simulated concurrent update"
        write(self.root, task_path(self.tid), newer)
        with self.assertRaisesRegex(ValueError, "changed during intake"):
            self.intake(apply=True)
        self.assertFalse((self.root / self.receipt).exists())

    def test_final_pm_stages_cannot_be_reopened_by_intake(self):
        self.task["status"] = "done"
        with self.assertRaisesRegex(ValueError, "reopen"):
            self.intake(apply=True)

    def test_fixture_cannot_claim_live_service_contract(self):
        self.task["allowed_execution_kinds"] = ["live_service"]
        with self.assertRaisesRegex(ValueError, "execution_kind"):
            self.intake()

    def test_git_replacement_cannot_change_the_fixed_owner_proof(self):
        original = self.api.pr["head"]["sha"]
        (self.root / "output.txt").write_text("replacement output, not original\n", encoding="utf-8")
        replacement = self.commit()
        self.git("replace", original, replacement)
        (self.root / "output.txt").write_text("fixture observed output\n", encoding="utf-8")
        self.api.pr["head"]["sha"] = original
        # Normal git show would read replacement output under the original SHA.
        # Intake must still validate the untouched original proof/output bytes.
        result = self.intake()
        self.assertTrue(result["validated"])
        self.assertEqual(result["receipt"]["source"]["head_commit"], original)


if __name__ == "__main__":
    unittest.main()
