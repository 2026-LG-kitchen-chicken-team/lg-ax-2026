import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.harness import ROOT, gate, validate


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "harness/project.json").read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Isolate tests from future real completion records.
        for group in ("stages", "submission_checks"):
            for row in self.data[group]:
                row.update(status="pending")
                row.pop("evidence", None)
        for row in self.data["candidates"]:
            row["feasibility"] = "conditional"
        self.data["decision"].update(status="proposed", candidate_id="B1", confirmed_by=None, confirmed_at=None)

    def evidence(self):
        path = self.root / "review.md"
        path.write_text("Reviewed example", encoding="utf-8")
        return {"path":"review.md", "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_valid_record(self):
        self.assertEqual(validate(self.data, self.root), [])

    def test_duplicate_source_rejected(self):
        self.data["sources"].append(copy.deepcopy(self.data["sources"][0]))
        self.assertTrue(validate(self.data, self.root))

    def test_unknown_source_rejected(self):
        self.data["candidates"][0]["evidence"] = ["invented"]
        self.assertTrue(validate(self.data, self.root))

    def test_missing_completion_evidence_rejected(self):
        self.data["stages"][0]["status"] = "done"
        self.assertTrue(validate(self.data, self.root))

    def test_changed_evidence_rejected(self):
        self.data["stages"][0].update(status="done", evidence=self.evidence())
        self.assertEqual(validate(self.data, self.root), [])
        (self.root / "review.md").write_text("Changed after review", encoding="utf-8")
        self.assertTrue(validate(self.data, self.root))

    def test_path_escape_rejected(self):
        self.data["stages"][0].update(status="done", evidence={"path":"../outside.md", "sha256":"x"})
        self.assertTrue(validate(self.data, self.root))

    def test_pending_topic_blocked(self):
        self.assertTrue(gate(self.data, "topic", self.root))

    def test_confirmed_without_user_record_rejected(self):
        self.data["decision"]["status"] = "confirmed"
        self.assertTrue(validate(self.data, self.root))

    def test_topic_and_submission_are_separate(self):
        self.data["decision"].update(status="confirmed", confirmed_by="test user", confirmed_at="2026-09-27", rationale="test")
        candidate = next(c for c in self.data["candidates"] if c["id"] == self.data["decision"]["candidate_id"])
        candidate.update(feasibility="reviewed", feasibility_evidence=self.evidence())
        self.assertEqual(gate(self.data, "topic", self.root), [])
        self.assertTrue(gate(self.data, "submission", self.root))

    def test_checklist_cannot_be_emptied(self):
        self.data["submission_checks"] = []
        self.assertTrue(validate(self.data, self.root))

    def test_timezone_required(self):
        self.data["deadline"] = "2026-09-28T18:00:00"
        self.assertTrue(validate(self.data, self.root))

    def test_workflow_stage_cannot_be_removed(self):
        self.data["stages"].pop()
        self.assertTrue(validate(self.data, self.root))

    def test_exploration_without_selection_is_valid_but_not_ready(self):
        self.data["decision"].update(status="exploring", candidate_id=None)
        self.assertEqual(validate(self.data, self.root), [])
        self.assertTrue(gate(self.data, "topic", self.root))


if __name__ == "__main__":
    unittest.main()
