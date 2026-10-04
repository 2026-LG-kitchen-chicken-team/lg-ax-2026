"""Keep reviewer answers out of model inputs and preserve existing execution files."""
import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
prepare_inputs = runpy.run_path(str(ROOT / "evals/core-semantic/prepare_inputs.py"))["prepare_inputs"]


class SemanticInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.suite = self.root / "suite"
        shutil.copytree(ROOT / "evals/core-semantic", self.suite)
        schema = self.root / "core-contract/schemas"
        schema.mkdir(parents=True)
        shutil.copy(ROOT / "evals/core-contract/schemas/output.json", schema / "output.json")
        self.output = self.root / "frozen-inputs"

    def edit(self, relative, mutation):
        path = self.suite / relative
        value = json.loads(path.read_text("utf-8"))
        mutation(value)
        path.write_text(json.dumps(value, ensure_ascii=False), "utf-8")

    def test_real_pack_freezes_six_inputs_with_no_reviewer_answers_or_model_results(self):
        result = prepare_inputs(self.suite, self.output)
        self.assertEqual(len(result["cases"]), 6)
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["evaluation_complete"])
        self.assertFalse(result["live_results_created"])
        rubric = json.loads((self.suite / "reviewer-only.json").read_text("utf-8"))
        for case in rubric["cases"]:
            prompt = (self.output / f"{case['case_id']}.baseline.txt").read_text("utf-8")
            payload = json.loads((self.output / f"{case['case_id']}.model-input.json").read_text("utf-8"))
            self.assertNotIn("review_checks", prompt)
            for check in case["review_checks"]:
                self.assertNotIn(check, prompt)
            self.assertEqual(set(payload), {"input", "materials", "input_sha256", "output_contract"})
        self.assertTrue(result["cases"][2]["preflight_violations"])

    def test_extra_material_answer_field_rejected_before_any_input_files_written(self):
        self.edit("materials/SEM-01.json", lambda v: v.update(correct_answer="leaked expected answer"))
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_directory_and_record_are_preserved(self):
        self.output.mkdir()
        original = self.output / "actual-run.json"
        original.write_text("record to preserve", "utf-8")
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertEqual(original.read_text("utf-8"), "record to preserve")

    def test_manifest_request_and_material_scope_mismatch_are_rejected(self):
        self.edit("materials/SEM-01.json", lambda v: v["input"]["request"].update(improvement_task="changed"))
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_category_cannot_be_called_six_category_input_preparation(self):
        self.edit("manifest.json", lambda v: v["cases"].pop())
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertFalse(self.output.exists())

    def test_raw_dataset_change_cannot_be_hidden_by_matching_manifest_request(self):
        self.edit("materials/SEM-01.json", lambda v: v["dataset"]["evidence"][0].update(text="tampered"))
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
