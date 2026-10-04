"""Preparation tests use marked fixtures, not model-performance evidence."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_evaluation", ROOT / "scripts/prepare_evaluation.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class EvaluationPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = b'{"materials": "independent-test-only"}'
        self.contract = b'{"output": "planning-result-test-contract"}'
        (self.root / "data.json").write_bytes(self.data)
        (self.root / "output-contract.json").write_bytes(self.contract)
        cases = []
        for index, category in enumerate(evaluation.REQUIRED_CATEGORIES):
            cases.append({"case_id": f"CASE-{index + 1:02d}", "category": category,
                          "request": {"task": "청소 요구 " + str(index)}, "data_path": "data.json",
                          "output_contract_path": "output-contract.json"})
        self.manifest = {"schema_version": 1, "independent_from_development": True, "cases": cases}
        self.bundles = {}
        for method in ("agent", "single_prompt_baseline"):
            records = []
            for case in cases:
                records.append({
                    "case_id": case["case_id"], "execution_kind": "fixture", "status": "success",
                    "conditions": {
                        "request_sha256": evaluation.canonical_sha256(case["request"]),
                        "data_sha256": hashlib.sha256(self.data).hexdigest(),
                        "output_contract_sha256": hashlib.sha256(self.contract).hexdigest(),
                        "model": {"id": "test-only-model", "revision": "test-r1", "digest": None},
                        "sampling": {"temperature": 0, "seed": 10},
                        "output_budget": {"max_output_tokens_per_call": 4096, "total_output_tokens_limit": None},
                        "environment": {"host": "test-only", "provider": "fixture"},
                        "data_access": {"pool": "entire_case_dataset", "availability": "all_materials_available",
                                        "truncation": "none"},
                        "measurement_scope": evaluation.MEASUREMENT_SCOPE,
                    },
                    "method_setup": {"prompt": "test-only recorded prompt: " + method,
                                     "prompt_sha256": evaluation.canonical_sha256("test-only recorded prompt: " + method),
                                     "instructions_complete": True,
                                     "material_delivery": "tool_access" if method == "agent" else "full_prompt",
                                     "call_policy": "agent_orchestration" if method == "agent" else "single_prompt"},
                    "raw_output": {"text": "원문 그대로 " + case["case_id"]}, "raw_error": None,
                    "execution_trace": [], "measurements": dict.fromkeys(evaluation.MEASUREMENT_FIELDS),
                })
            self.bundles[method] = {"schema_version": 1, "method": method, "records": records}
        self.write_inputs()

    def write_inputs(self):
        for name, value in (("cases", self.manifest), ("agent", self.bundles["agent"]),
                            ("baseline", self.bundles["single_prompt_baseline"])):
            (self.root / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def prepare(self, suffix="one", seed=42):
        self.write_inputs()
        return evaluation.prepare_evaluation(self.root / "cases.json", self.root / "agent.json",
                                             self.root / "baseline.json", self.root / ("review-" + suffix),
                                             self.root / ("pm-key-" + suffix + ".json"), seed)

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def test_fixture_nulls_seed_blinding_and_failure_raw_are_preserved(self):
        failed = self.bundles["agent"]["records"][0]
        failed.update(status="failure", raw_output="partial\n원문", raw_error={"code": "NOT_IMPLEMENTED"})
        failed["measurements"]["model_calls"] = 0  # Actual zero is distinct from unmeasured null.
        summary = self.prepare()
        self.assertEqual(summary["preparation_status"], "fixture_only")
        self.assertFalse(summary["evaluation_complete"])
        self.assertEqual(sum(summary["categories"].values()), 6)
        key = self.read("pm-key-one.json")
        self.assertIsNone(key["records"]["agent"]["CASE-01"]["measurements"]["latency_ms"])
        self.assertEqual(key["records"]["agent"]["CASE-01"]["measurements"]["model_calls"], 0)
        review = self.read("review-one/review.json")
        case = next(item for item in review["cases"] if item["case_id"] == "CASE-01")
        labels = next(item["labels"] for item in key["mapping"] if item["case_id"] == "CASE-01")
        label = next(label for label, method in labels.items() if method == "agent")
        self.assertEqual(case["outputs"][label]["raw_output"], "partial\n원문")
        self.assertEqual(case["outputs"][label]["raw_error"], {"code": "NOT_IMPLEMENTED"})
        self.assertNotIn("seed", review)
        self.assertNotIn("measurements", json.dumps(review))
        self.assertNotIn("method_setup", json.dumps(review))
        for item in self.read("review-one/scorecard.json")["scorecards"]:
            self.assertIsNone(item["citation_checks"]["correct"])
            self.assertIsNone(item["product_model_errors"])
            self.assertIsNone(item["duplicate_feature_proposals"])
        self.prepare("two", 42)
        self.assertEqual(review, self.read("review-two/review.json"))
        self.assertEqual(key["mapping"], self.read("pm-key-two.json")["mapping"])

    def test_every_condition_difference_is_rejected_before_creating_outputs(self):
        original = deepcopy(self.bundles["single_prompt_baseline"])
        changes = [
            ("request_sha256", "0" * 64), ("data_sha256", "1" * 64),
            ("output_contract_sha256", "2" * 64),
            ("model", {"id": "different", "revision": "r1", "digest": None}),
            ("sampling", {"temperature": 1, "seed": 10}),
            ("output_budget", {"max_output_tokens_per_call": 256, "total_output_tokens_limit": None}),
            ("environment", {"host": "different"}),
            ("data_access", {"pool": "subset", "availability": "all_materials_available", "truncation": "none"}),
            ("measurement_scope", "final_call_only"),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                self.bundles["single_prompt_baseline"] = deepcopy(original)
                self.bundles["single_prompt_baseline"]["records"][0]["conditions"][field] = value
                with self.assertRaises(evaluation.EvaluationError):
                    self.prepare()
                self.assertFalse((self.root / "review-one").exists())
                self.assertFalse((self.root / "pm-key-one.json").exists())

    def test_missing_type_missing_case_duplicate_case_and_mixed_execution_are_rejected(self):
        original_manifest, original_bundles = deepcopy(self.manifest), deepcopy(self.bundles)
        for mutation in ("type", "case", "duplicate", "mixed_pair", "mixed_batch", "not_independent"):
            with self.subTest(mutation=mutation):
                self.manifest, self.bundles = deepcopy(original_manifest), deepcopy(original_bundles)
                if mutation == "type":
                    self.manifest["cases"][0]["category"] = "duplicate_feature"
                elif mutation == "case":
                    self.bundles["agent"]["records"].pop()
                elif mutation == "duplicate":
                    self.bundles["agent"]["records"].append(deepcopy(self.bundles["agent"]["records"][0]))
                elif mutation == "mixed_pair":
                    self.bundles["agent"]["records"][0]["execution_kind"] = "live_model"
                elif mutation == "mixed_batch":
                    for bundle in self.bundles.values():
                        bundle["records"][0]["execution_kind"] = "live_model"
                else:
                    self.manifest["independent_from_development"] = False
                with self.assertRaises(evaluation.EvaluationError):
                    self.prepare()

    def test_invalid_metrics_unpinned_model_and_weak_baseline_setup_are_rejected(self):
        original = deepcopy(self.bundles)
        for mutation in ("negative", "bool", "fractional_calls", "unpinned", "weak_baseline", "prompt_hash", "currency"):
            with self.subTest(mutation=mutation):
                self.bundles = deepcopy(original)
                record = self.bundles["single_prompt_baseline"]["records"][0]
                if mutation == "negative":
                    record["measurements"]["latency_ms"] = -1
                elif mutation == "bool":
                    record["measurements"]["input_tokens"] = False
                elif mutation == "fractional_calls":
                    record["measurements"]["model_calls"] = 1.5
                elif mutation == "unpinned":
                    record["conditions"]["model"] = {"id": "alias", "revision": None, "digest": None}
                elif mutation == "weak_baseline":
                    record["method_setup"]["material_delivery"] = "tool_access"
                elif mutation == "prompt_hash":
                    record["method_setup"]["prompt"] = "changed prompt"
                else:
                    record["measurements"]["cost"] = {"amount": 2, "currency": "USD"}
                    self.bundles["agent"]["records"][0]["measurements"]["cost"] = {"amount": 2, "currency": "KRW"}
                with self.assertRaises(evaluation.EvaluationError):
                    self.prepare()

    def test_actual_material_change_rejected_and_no_overwrite_or_shared_key(self):
        (self.root / "data.json").write_bytes(b"changed data")
        with self.assertRaises(evaluation.EvaluationError):
            self.prepare()
        (self.root / "data.json").write_bytes(self.data)
        self.prepare()
        before = (self.root / "review-one/review.json").read_bytes()
        with self.assertRaises(evaluation.EvaluationError):
            self.prepare()
        self.assertEqual(before, (self.root / "review-one/review.json").read_bytes())
        with self.assertRaises(evaluation.EvaluationError):
            evaluation.prepare_evaluation(self.root / "cases.json", self.root / "agent.json",
                                           self.root / "baseline.json", self.root / "new-review",
                                           self.root / "new-review/pm-key.json", 42)
        self.assertFalse((self.root / "new-review").exists())

    def test_cli_does_not_promote_declared_live_results_to_completed_evaluation(self):
        for bundle in self.bundles.values():
            for record in bundle["records"]:
                record["execution_kind"] = "live_model"  # Test declaration only; no model is called.
        self.write_inputs()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_evaluation.py"),
                                 "--cases", str(self.root / "cases.json"), "--agent-results", str(self.root / "agent.json"),
                                 "--baseline-results", str(self.root / "baseline.json"),
                                 "--output-dir", str(self.root / "review-cli"),
                                 "--key-file", str(self.root / "pm-key-cli.json"), "--seed", "45"],
                                capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = json.loads(result.stdout)
        self.assertEqual(result["preparation_status"], "live_results_awaiting_independent_review")
        self.assertFalse(result["evaluation_complete"])


if __name__ == "__main__":
    unittest.main()
