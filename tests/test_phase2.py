import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase2 import (
    ROOT, BASE, adopt_extension, artifact_errors, cover_requirement, fingerprint, finish_task,
    gate, lifecycle, load, ready_tasks, record_check, validate, write,
)


class Phase2Tests(unittest.TestCase):
    """Tests use isolated fixtures; none are evidence of a live Agent/client."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        shutil.copytree(ROOT / BASE, self.root / BASE)
        original = load(ROOT)
        for row in original["archive"]["records"] + original["sources"]["sources"]:
            if row.get("private"):
                continue
            dst = self.root / row["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row["path"], dst)
        (self.root / "code.py").write_text("observed code\n", encoding="utf-8")
        (self.root / "source.txt").write_text("fixed fixture source\n", encoding="utf-8")
        (self.root / "output.txt").write_text("unit fixture observed output\n", encoding="utf-8")
        self.bundle = load(self.root)
        # Do not inherit future real completion records into unit test semantics.
        for task in self.bundle["tasks"].values():
            task.update(status="pending" if task["depends_on"] else "ready", individual_evidence=None,
                        pm_review=None, merge=None, integration=None, completion=None, history=[])
            if task.get("scope") == "proposed_extension":
                task["adoption"] = None
            write(self.root, f"{BASE}/tasks/{task['id']}.json", task)
        for row in self.bundle["requirements"]["requirements"]:
            row.update(status="pending", coverage=None)
        for row in self.bundle["checks"]["checks"]:
            row.update(status="pending", evidence=None)
        write(self.root, f"{BASE}/requirements.json", self.bundle["requirements"])
        write(self.root, f"{BASE}/checks.json", self.bundle["checks"])
        self.tid = "P2-CORE-001"

    def artifact(self, path="run.json", kind="fixture", **extras):
        data = {"task_id": self.tid, "owner": "황대겸", "result": "pass",
                "execution_kind": kind, "observations": ["unit test fixture, no live service"],
                "code_versions": [fingerprint(self.root, "code.py")],
                "source_versions": [fingerprint(self.root, "source.txt")],
                "checks": [{"name": "fixture assertion", "passed": True,
                            "evidence": fingerprint(self.root, "output.txt")}],
                "limitations": ["isolated fixture; does not demonstrate product execution"],
                "models": []}
        data.update(extras)
        write(self.root, path, data)
        return path

    def finished(self):
        finish_task(self.root, self.bundle, self.tid, self.artifact(), "unknownamed")
        self.bundle = load(self.root)
        return self.bundle["tasks"][self.tid]

    def review_artifact(self, path="review.json", **extras):
        task = self.bundle["tasks"][self.tid]
        data = {"task_id": self.tid, "pm": "정이량", "decision": "approved",
                "individual_evidence_sha256": task["individual_evidence"]["sha256"],
                "observations": ["PM unit fixture review"]}
        data.update(extras)
        write(self.root, path, data)
        return path

    def test_initial_structure_is_valid_not_product_completion(self):
        self.assertEqual(validate(self.root, self.bundle), [])
        self.assertTrue(gate(self.root, self.bundle, "setup_external"))
        self.assertTrue(gate(self.root, self.bundle, "integration"))
        self.assertFalse(any(t["status"] == "done" for t in self.bundle["tasks"].values()))

    def test_exact_31_requirement_contract(self):
        self.bundle["requirements"]["requirements"].pop()
        self.assertIn("exactly R01-R28/E01-E03 required", validate(self.root, self.bundle))

    def test_ready_for_all_four_members(self):
        for member in ("jeongiryang", "unknownamed", "ginaginaring", "choigilung"):
            self.assertTrue(ready_tasks(self.bundle, member))
        with self.assertRaises(ValueError):
            ready_tasks(self.bundle, "unconfigured")

    def test_dependency_cycle_rejected(self):
        t = self.bundle["tasks"][self.tid]
        t["depends_on"] = ["P2-CORE-002"]
        self.assertTrue(any("cycle" in e for e in validate(self.root, self.bundle)))

    def test_proposed_extension_stays_inactive_until_actual_pm_adoption(self):
        tid = "P2-DATA-005"
        task = self.bundle["tasks"][tid]
        # Only readiness is exercised here; these isolated dependency statuses
        # are not completion records and never touch the real project.
        for dep in task["depends_on"]:
            self.bundle["tasks"][dep]["status"] = "done"
        self.assertNotIn(tid, [t["id"] for t in ready_tasks(self.bundle, "ginaginaring")])
        with self.assertRaisesRegex(ValueError, "PM adoption"):
            finish_task(self.root, self.bundle, tid, "not-executed.json", "ginaginaring")
        task["status"] = "ready"
        self.assertTrue(any("adoption" in e for e in validate(self.root, self.bundle)))
        task["status"] = "pending"
        write(self.root, "adoption.json", {"task_id": tid, "pm": "정이량", "decision": "adopted",
             "instruction_source": "PM assignment", "instruction_quote": "unit fixture: PM explicitly assigns this extension",
             "observations": ["isolated PM adoption fixture; not a real assignment"]})
        with self.assertRaisesRegex(ValueError, "PM actor"):
            adopt_extension(self.root, self.bundle, tid, "adoption.json", "ginaginaring")
        adopt_extension(self.root, self.bundle, tid, "adoption.json", "jeongiryang")
        self.assertIn(tid, [t["id"] for t in ready_tasks(self.bundle, "ginaginaring")])

    def test_owner_finish_is_not_pm_completion(self):
        task = self.finished()
        self.assertEqual(task["status"], "individual_verified")
        self.assertIsNone(task["pm_review"])
        self.assertIsNone(task["completion"])
        self.assertEqual(validate(self.root, self.bundle), [])

    def test_other_owner_cannot_finish(self):
        with self.assertRaises(ValueError):
            finish_task(self.root, self.bundle, self.tid, self.artifact(), "ginaginaring")

    def test_cannot_finish_with_uncompleted_dependencies(self):
        with self.assertRaisesRegex(ValueError, "dependencies"):
            finish_task(self.root, self.bundle, "P2-CORE-002", self.artifact(), "unknownamed")

    def test_fixture_cannot_claim_live_model_task(self):
        a = self.artifact()
        data = json.loads((self.root / a).read_text(encoding="utf-8"))
        self.assertTrue(artifact_errors(self.root, data, ["live_model"]))

    def test_malformed_artifact_is_rejected_as_missing_evidence(self):
        self.assertTrue(artifact_errors(self.root, [], ["fixture"]))
        data = json.loads((self.root / self.artifact(checks=[None])).read_text(encoding="utf-8"))
        self.assertTrue(any("JSON object" in e for e in artifact_errors(self.root, data, ["fixture"])))

    def test_live_model_requires_revision_license_and_settings(self):
        data = json.loads((self.root / self.artifact(kind="live_model")).read_text(encoding="utf-8"))
        self.assertTrue(any("model ID/revision" in e for e in artifact_errors(self.root, data, ["live_model"])))

    def test_evidence_escape_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint(self.root, "../outside.json")

    def test_stale_tested_source_blocks_review(self):
        self.finished()
        path = self.review_artifact()
        (self.root / "code.py").write_text("modified since owner execution", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            lifecycle(self.root, self.bundle, "review", self.tid, path, "jeongiryang")

    def test_only_pm_can_record_review(self):
        self.finished()
        with self.assertRaisesRegex(ValueError, "PM actor"):
            lifecycle(self.root, self.bundle, "review", self.tid, self.review_artifact(), "unknownamed")

    def test_pm_approval_is_not_merge_or_done(self):
        self.finished()
        lifecycle(self.root, self.bundle, "review", self.tid, self.review_artifact(), "jeongiryang")
        self.bundle = load(self.root)
        self.assertEqual(self.bundle["tasks"][self.tid]["status"], "pm_approved")
        with self.assertRaises(ValueError):
            lifecycle(self.root, self.bundle, "complete", self.tid, "review.json", "jeongiryang")

    def test_merge_requires_real_commit_and_pr(self):
        self.finished()
        lifecycle(self.root, self.bundle, "review", self.tid, self.review_artifact(), "jeongiryang")
        self.bundle = load(self.root)
        path = self.review_artifact("merge.json", merge_commit="a" * 40, pull_request_url="https://github.com/example/repo/pull/1")
        with patch("scripts.phase2.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stdout = ""
            with self.assertRaisesRegex(ValueError, "real local Git"):
                lifecycle(self.root, self.bundle, "merge", self.tid, path, "jeongiryang")

    def test_manual_done_cannot_bypass_chain(self):
        self.bundle["tasks"][self.tid]["status"] = "done"
        errors = validate(self.root, self.bundle)
        for name in ("individual_evidence", "pm_review", "merge", "integration", "completion"):
            self.assertTrue(any(name in e for e in errors))

    def test_full_pm_chain_needs_exact_integration_version(self):
        self.finished()
        lifecycle(self.root, self.bundle, "review", self.tid, self.review_artifact(), "jeongiryang")
        self.bundle = load(self.root)
        path = self.review_artifact("merge.json", merge_commit="a" * 40, pull_request_url="https://github.com/example/repo/pull/1")
        with patch("scripts.phase2.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "commit\n"
            lifecycle(self.root, self.bundle, "merge", self.tid, path, "jeongiryang")
            self.bundle = load(self.root)
            stamp = self.bundle["tasks"][self.tid]["individual_evidence"]["sha256"]
            path = self.artifact("integration.json", pm="정이량", individual_evidence_sha256=stamp, tested_commit="b" * 40)
            with self.assertRaisesRegex(ValueError, "actual merge"):
                lifecycle(self.root, self.bundle, "verify", self.tid, path, "jeongiryang")
            path = self.artifact("integration.json", pm="정이량", individual_evidence_sha256=stamp, tested_commit="a" * 40)
            lifecycle(self.root, self.bundle, "verify", self.tid, path, "jeongiryang")
            self.bundle = load(self.root)
            task = self.bundle["tasks"][self.tid]
            path = self.review_artifact("complete.json", decision="complete", integration_evidence_sha256=task["integration"]["sha256"])
            lifecycle(self.root, self.bundle, "complete", self.tid, path, "jeongiryang")
            self.bundle = load(self.root)
            self.assertEqual(self.bundle["tasks"][self.tid]["status"], "done")
            self.assertEqual(validate(self.root, self.bundle), [])

    def test_tampered_pm_artifact_rejected_even_when_hash_matches(self):
        self.finished()
        task = self.bundle["tasks"][self.tid]
        path = self.review_artifact(pm="황대겸")
        task.update(status="pm_approved", pm_review=fingerprint(self.root, path))
        self.assertTrue(any("configured PM" in e for e in validate(self.root, self.bundle)))

    def test_external_gate_rejects_fixture_evidence(self):
        path = self.artifact(check_id="server_inventory")
        with self.assertRaisesRegex(ValueError, "execution_kind"):
            record_check(self.root, self.bundle, path, "jeongiryang")

    def test_verified_check_revalidated_not_boolean_only(self):
        row = next(c for c in self.bundle["checks"]["checks"] if c["id"] == "server_inventory")
        path = self.artifact(check_id="server_inventory")
        row.update(status="verified", evidence=fingerprint(self.root, path))
        self.assertTrue(any("execution_kind" in e for e in validate(self.root, self.bundle)))

    def test_requirement_coverage_rejects_mock(self):
        self.bundle["tasks"][self.tid]["status"] = "done"
        with self.assertRaisesRegex(ValueError, "actual execution"):
            cover_requirement(self.root, self.bundle, "R09", self.tid, self.artifact(requirement_ids=["R09"]), "jeongiryang")

    def test_phase1_archive_change_is_detected_without_rehashing(self):
        row = self.bundle["archive"]["records"][0]
        (self.root / row["path"]).write_text("changed historic artifact", encoding="utf-8")
        self.assertTrue(any("phase1 archive" in e for e in validate(self.root, self.bundle)))

    def test_framework_success_does_not_prove_external_connections(self):
        for row in self.bundle["checks"]["checks"]:
            if row["group"] == "setup_framework":
                path = self.artifact(f"{row['id']}.json", kind=row["allowed_execution_kinds"][0], check_id=row["id"])
                row.update(status="verified", evidence=fingerprint(self.root, path))
        self.assertEqual(gate(self.root, self.bundle, "setup_framework"), [])
        self.assertTrue(gate(self.root, self.bundle, "setup_external"))
        self.assertTrue(gate(self.root, self.bundle, "setup"))


if __name__ == "__main__":
    unittest.main()
