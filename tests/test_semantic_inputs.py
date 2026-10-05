"""Keep reviewer answers out of model inputs and preserve existing execution files."""
import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

import httpx
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient

ROOT = Path(__file__).resolve().parents[1]
prepare_inputs = runpy.run_path(str(ROOT / "evals/core-semantic/prepare_inputs.py"))["prepare_inputs"]
validate_frozen = runpy.run_path(str(ROOT / "evals/core-semantic/run_comparison.py"))["validate_frozen"]


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
            self.assertIn(payload["input_sha256"], prompt)
        self.assertTrue(result["cases"][2]["preflight_violations"])
        changed_prompt = (self.output / "SEM-06.baseline.txt").read_text("utf-8")
        self.assertNotIn('"previous_dataset"', changed_prompt)
        self.assertNotIn('"previous_input"', changed_prompt)

    def test_extra_material_answer_field_rejected_before_any_input_files_written(self):
        self.edit("materials/SEM-01.json", lambda v: v.update(correct_answer="leaked expected answer"))
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertFalse(self.output.exists())

    def test_full_six_case_baseline_reaches_model_without_truncating_materials(self):
        prepare_inputs(self.suite, self.output, baseline_contract_mode="client_schema")
        model = "qwen3:8b"
        digest = "a" * 64
        response = json.loads((ROOT / "evals/core-contract/development/normal.fixture-output.json").read_text("utf-8"))
        for path in sorted(self.output.glob("*.model-input.json")):
            payload = json.loads(path.read_text("utf-8"))
            prompt = path.with_name(path.name.replace(".model-input.json", ".baseline.txt")).read_text("utf-8")
            sent = []

            def transport(request, sent=sent):
                if request.url.path == "/api/tags":
                    value = {"models": [{"name": model, "digest": digest}]}
                else:
                    sent.append(json.loads(request.content))
                    value = {"model": model, "response": json.dumps(response),
                             "done": True, "done_reason": "stop"}
                return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value).encode()),
                                      headers={"Content-Type": "application/json"})

            config = ModelConfig("http://127.0.0.1:18864", model, digest,
                                 max_output_tokens=8192, context_tokens=16384)
            with StructuredModelClient(OllamaAdapter(config, transport=httpx.MockTransport(transport))) as client:
                client.generate(prompt, payload["output_contract"], model)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["format"], payload["output_contract"])
            current = {"input": payload["materials"]["input"], "dataset": payload["materials"]["dataset"]}
            self.assertIn(json.dumps(current, ensure_ascii=False, separators=(",", ":")), sent[0]["prompt"])
            for source in current["input"]["sources"]:
                self.assertIn(source["text"], sent[0]["prompt"])
            self.assertNotIn('"review_checks"', sent[0]["prompt"])

    def test_existing_output_directory_and_record_are_preserved(self):
        self.output.mkdir()
        original = self.output / "actual-run.json"
        original.write_text("record to preserve", "utf-8")
        with self.assertRaises(ValueError):
            prepare_inputs(self.suite, self.output)
        self.assertEqual(original.read_text("utf-8"), "record to preserve")

    def test_comparison_refuses_modified_frozen_prompt_and_original_material(self):
        prepare_inputs(self.suite, self.output, baseline_contract_mode="client_schema")
        self.assertEqual(len(validate_frozen(self.suite, self.output)), 6)
        prompt = self.output / "SEM-01.baseline.txt"
        original = prompt.read_bytes()
        prompt.write_bytes(original + b"changed")
        with self.assertRaises(ValueError):
            validate_frozen(self.suite, self.output)
        prompt.write_bytes(original)
        self.edit("materials/SEM-01.json", lambda value: value["dataset"]["evidence"][0].update(text="changed"))
        with self.assertRaises(ValueError):
            validate_frozen(self.suite, self.output)

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

    def test_previous_dataset_version_or_original_change_is_rejected_before_export(self):
        for field in ("version", "text"):
            with self.subTest(field=field):
                source = self.suite / "materials/SEM-06.json"
                original = source.read_text("utf-8")
                def mutate(value, field=field):
                    if field == "version":
                        value["previous_dataset"]["manifest"]["version"] = "wrong-version"
                    else:
                        value["previous_dataset"]["evidence"][0]["text"] = "changed-original"
                self.edit("materials/SEM-06.json", mutate)
                with self.assertRaises(ValueError):
                    prepare_inputs(self.suite, self.output)
                self.assertFalse(self.output.exists())
                source.write_text(original, "utf-8")


if __name__ == "__main__":
    unittest.main()
