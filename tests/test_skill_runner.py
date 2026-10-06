"""Actual lookup, deferred reasoning and isolated backend contract failures."""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from lgax_core import DemoStore
from lgax_core.skill_runner import SKILL_IDS, SkillRuntime, schema_for

ROOT = Path(__file__).resolve().parents[1]


class SkillRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()
        self.runtime = SkillRuntime(self.store)

    @staticmethod
    def example(skill):
        return json.loads((ROOT / "skills" / skill / "examples/input.json").read_text(encoding="utf-8"))

    def fixture(self, skill, result):
        self.runtime.register_handler(skill, lambda _payload, _store: deepcopy(result),
                                      backend_id="test-only:fixture-v1", execution_kind="fixture")

    def test_lookup_is_actual_store_and_preserves_original_sources(self):
        payload = self.example("evidence_lookup")
        response = self.runtime.execute("evidence_lookup", payload)
        expected = self.store.search_evidence(payload["query"], payload["model_id"],
                                              payload["document_version"], payload["limit"])["data"]
        self.assertTrue(response["ok"], response)
        self.assertTrue(response["data"]["result"]["items"])
        self.assertEqual(response["data"]["result"]["items"], expected["items"])
        self.assertEqual(response["data"]["execution_kind"], "deterministic")
        for source in response["data"]["sources"]:
            self.assertEqual(source, self.store.get_evidence(source["id"])["data"]["evidence"])

    def test_valid_empty_lookup_is_success(self):
        payload = {**self.example("evidence_lookup"), "query": "절대존재하지않는표현"}
        response = self.runtime.execute("evidence_lookup", payload)
        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["result"]["total"], 0)
        self.assertEqual(response["data"]["result"]["items"], [])
        self.assertEqual(response["data"]["sources"], [])

    def test_bad_model_and_version_differ_from_empty_search(self):
        for field, value, error in [("model_id", "MISSING", "INVALID_MODEL_ID"),
                                    ("document_version", "9.0", "INVALID_DOCUMENT_VERSION")]:
            response = self.runtime.execute("evidence_lookup", {**self.example("evidence_lookup"), field: value})
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], error)

    def test_four_unimplemented_backends_are_not_successful_prompt_generation(self):
        for skill in SKILL_IDS[1:]:
            with self.subTest(skill=skill):
                response = self.runtime.execute(skill, self.example(skill))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")
                self.assertFalse(response["error"]["details"]["handler_registered"])
        self.assertEqual([item["skill_id"] for item in self.runtime.catalog() if item["handler_registered"]],
                         ["evidence_lookup"])

    def test_schema_checks_before_backend_and_never_echoes_raw_secret_values(self):
        payload = {**self.example("need_extract"), "api_key": "must-not-appear"}
        response = self.runtime.execute("need_extract", payload)
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
        self.assertNotIn("must-not-appear", json.dumps(response))
        for invalid in [None, [], {"model_id": "FRIDGE-A"}]:
            self.assertEqual(self.runtime.execute("evidence_lookup", invalid)["error"]["code"],
                             "VALIDATION_FAILED")

    def test_invalid_original_id_and_manual_used_as_review_are_rejected(self):
        payload = self.example("need_extract")
        response = self.runtime.execute("need_extract", {**payload, "review_evidence_ids": ["MISSING"]})
        self.assertEqual(response["error"]["code"], "INVALID_EVIDENCE_ID")
        response = self.runtime.execute("need_extract", {**payload, "review_evidence_ids": ["MANUAL-001"]})
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_wrong_model_and_wrong_version_references_are_rejected(self):
        examples = [item for item in self.store.bootstrap()["data"]["evidence"]
                    if item["model_id"] != "FRIDGE-A" or item["document_version"] != "1.0"]
        self.assertTrue(any(item["model_id"] == "FRIDGE-A" for item in examples))
        self.assertTrue(any(item["model_id"] != "FRIDGE-A" for item in examples))
        for evidence in examples:
            response = self.runtime.execute("need_extract", {**self.example("need_extract"),
                                            "review_evidence_ids": [evidence["id"]]})
            self.assertEqual(response["error"]["code"], "VALIDATION_FAILED", evidence["id"])
            self.assertEqual(response["error"]["details"]["field"],
                             "model_id" if evidence["model_id"] != "FRIDGE-A" else "document_version")

    def test_injected_fixture_is_distinguished_and_references_checked(self):
        need = self.example("product_compare")["needs"][0]
        self.fixture("need_extract", {"needs": [need], "desired_outcomes": [
            {"need_id": need["id"], "desired_outcome": "청소할 때 식품 이동을 줄이기"}], "unresolved": []})
        response = self.runtime.execute("need_extract", self.example("need_extract"))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["execution_kind"], "fixture")
        self.assertEqual(response["data"]["backend_id"], "test-only:fixture-v1")
        self.assertEqual(response["data"]["sources"][0]["id"], "REVIEW-EVIDENCE-001")
        self.assertEqual(self.runtime.store.bootstrap(), self.store.bootstrap())

    def test_injected_handler_cannot_add_an_undeclared_source(self):
        need = self.example("product_compare")["needs"][0]
        need["evidence_ids"] = ["REVIEW-EVIDENCE-003"]
        self.fixture("need_extract", {"needs": [need], "desired_outcomes": [
            {"need_id": need["id"], "desired_outcome": "검토"}], "unresolved": []})
        response = self.runtime.execute("need_extract", self.example("need_extract"))
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_backend_output_schema_is_validated(self):
        self.fixture("need_extract", {"needs": "invented success"})
        response = self.runtime.execute("need_extract", self.example("need_extract"))
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(response["error"]["details"]["direction"], "output")

    def test_need_outcomes_are_complete_and_have_no_duplicate_ids(self):
        need = self.example("product_compare")["needs"][0]
        self.fixture("need_extract", {"needs": [need], "desired_outcomes": [], "unresolved": []})
        error = self.runtime.execute("need_extract", self.example("need_extract"))["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["missing_need_ids"], [need["id"]])
        self.assertEqual(error["details"]["expected_count"], 1)
        outcome = {"need_id": need["id"], "desired_outcome": "개발 검증"}
        self.runtime = SkillRuntime(self.store)
        self.fixture("need_extract", {"needs": [need], "desired_outcomes": [outcome, outcome], "unresolved": []})
        error = self.runtime.execute("need_extract", self.example("need_extract"))["error"]
        self.assertEqual(error["details"]["duplicate_need_ids"], [need["id"]])

    def test_original_text_and_locator_cannot_be_forged(self):
        payload = self.example("evidence_lookup")
        original = self.store.search_evidence(payload["query"], "FRIDGE-A", "1.0", payload["limit"])["data"]
        for field in ("text", "locator"):
            result = {key: deepcopy(original[key]) for key in ("query", "items", "total", "search_method")}
            result["items"][0][field] = "forged" if field == "text" else {"page": 999, "section": "위조 위치"}
            runtime = SkillRuntime()
            runtime.register_handler("evidence_lookup", lambda _payload, _store, result=result: result,
                                     backend_id="test-only:forged-source", execution_kind="fixture", replace=True)
            response = runtime.execute("evidence_lookup", payload)
            self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_gap_references_and_each_need_comparison_are_checked(self):
        payload = self.example("product_compare")
        gap = self.example("concept_draft")["gaps"][0]
        self.fixture("product_compare", {"gaps": [gap], "unresolved": []})
        response = self.runtime.execute("product_compare", payload)
        self.assertTrue(response["ok"], response)
        self.assertEqual({item["id"] for item in response["data"]["sources"]},
                         {"MANUAL-001", "REVIEW-EVIDENCE-001"})
        runtime = SkillRuntime()
        gap["need_id"] = "UNKNOWN-NEED"
        runtime.register_handler("product_compare", lambda _payload, _store: {"gaps": [gap], "unresolved": []},
                                 backend_id="test-only:bad-gap", execution_kind="fixture")
        self.assertEqual(runtime.execute("product_compare", payload)["error"]["code"], "VALIDATION_FAILED")

    def test_concept_zero_is_allowed_only_with_hold_reason(self):
        self.fixture("concept_draft", {"concepts": [], "hold_reasons": ["충분한 신규성 근거 없음"]})
        response = self.runtime.execute("concept_draft", self.example("concept_draft"))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["result"]["concepts"], [])
        runtime = SkillRuntime()
        runtime.register_handler("concept_draft", lambda _p, _s: {"concepts": [], "hold_reasons": []},
                                 backend_id="test-only:empty", execution_kind="fixture")
        self.assertEqual(runtime.execute("concept_draft", self.example("concept_draft"))["error"]["code"],
                         "VALIDATION_FAILED")

    def test_concept_reference_and_requested_candidate_limit_are_checked(self):
        payload = {**self.example("concept_draft"), "max_concepts": 1}
        concept = {"id": "CONCEPT-FIXTURE-001", "title": "테스트 후보", "kind": "feature",
                   "gap_ids": [payload["gaps"][0]["id"]], "evidence_ids": ["REVIEW-EVIDENCE-001"],
                   "differentiation": "의미 정확성 미검증 fixture", "requirements": ["후속 전문가 검토"],
                   "assumptions": ["합성 fixture"], "status": "needs_review"}
        for concepts in [[{**concept, "gap_ids": ["MISSING-GAP"]}],
                         [concept, {**concept, "id": "CONCEPT-FIXTURE-002"}]]:
            runtime = SkillRuntime()
            runtime.register_handler("concept_draft", lambda _p, _s, concepts=concepts:
                                     {"concepts": concepts, "hold_reasons": []},
                                     backend_id="test-only:invalid-concept", execution_kind="fixture")
            self.assertEqual(runtime.execute("concept_draft", payload)["error"]["code"], "VALIDATION_FAILED")

    def test_review_limit_and_increment_are_enforced_without_extra_handler_call(self):
        calls = []
        payload = self.example("review_revision")
        def handler(value, _store):
            calls.append(value)
            return {"needs": value["needs"], "gaps": value["gaps"], "concepts": value["concepts"],
                    "changes": [], "unresolved": ["fixture 검토"], "revision_count": value["revision_count"] + 1}
        self.runtime.register_handler("review_revision", handler,
                                      backend_id="test-only:revision", execution_kind="fixture")
        response = self.runtime.execute("review_revision", payload)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["result"]["revision_count"], 1)
        response = self.runtime.execute("review_revision", {**payload, "revision_count": 2})
        self.assertEqual(response["error"]["code"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(len(calls), 1)
        runtime = SkillRuntime()
        runtime.register_handler("review_revision", lambda value, _s: {
            "needs": value["needs"], "gaps": value["gaps"], "concepts": value["concepts"],
            "changes": [], "unresolved": [], "revision_count": value["revision_count"]},
            backend_id="test-only:bad-count", execution_kind="fixture")
        response = runtime.execute("review_revision", {**payload, "revision_count": 1})
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_handler_failure_has_no_raw_provider_exception_or_secret(self):
        def handler(_payload, _store):
            raise RuntimeError("secret-api-key-sample")
        self.runtime.register_handler("need_extract", handler, backend_id="test-only:failure", execution_kind="fixture")
        response = self.runtime.execute("need_extract", self.example("need_extract"))
        self.assertEqual(response["error"]["code"], "MODEL_UNAVAILABLE")
        self.assertNotIn("secret-api-key-sample", json.dumps(response))

    def test_registration_requires_explicit_replacement_and_fixture_metadata(self):
        with self.assertRaises(ValueError):
            self.runtime.register_handler("evidence_lookup", lambda _p, _s: {},
                                          backend_id="fixture", execution_kind="fixture")
        with self.assertRaises(ValueError):
            self.runtime.register_handler("unknown", lambda _p, _s: {}, backend_id="fixture", execution_kind="fixture")
        self.assertEqual(self.runtime.execute("unknown", {})["error"]["code"], "INVALID_ARGUMENT")

    def test_standalone_schema_packages_validate_actual_current_outputs(self):
        for skill in SKILL_IDS:
            payload = self.example(skill)
            for direction, value in [("input", payload), ("output", self.runtime.execute(skill, payload))]:
                packaged = json.loads((ROOT / "skills" / skill / f"schemas/{direction}.json").read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(packaged)
                Draft202012Validator(packaged).validate(value)
                Draft202012Validator(schema_for(skill, direction)).validate(value)

    def test_repeatable_cli_writes_success_and_explicit_unimplemented_error(self):
        with tempfile.TemporaryDirectory(prefix="lgax-skill-cli-") as dirname:
            for skill, expected_code in [("evidence_lookup", 0), ("need_extract", 2)]:
                output = Path(dirname) / f"{skill}.json"
                result = subprocess.run([sys.executable, str(ROOT / "skills" / skill / "scripts/run.py"),
                                         "--input", str(ROOT / "skills" / skill / "examples/input.json"),
                                         "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, expected_code, result.stderr)
                response = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(response["ok"], skill == "evidence_lookup")
                if expected_code:
                    self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")

    def test_cli_cannot_overwrite_its_input_source(self):
        with tempfile.TemporaryDirectory(prefix="lgax-skill-source-") as dirname:
            source = Path(dirname) / "input.json"
            original = json.dumps(self.example("evidence_lookup")).encode("utf-8")
            source.write_bytes(original)
            process = subprocess.run([sys.executable, str(ROOT / "skills/evidence_lookup/scripts/run.py"),
                                      "--input", str(source), "--output", str(source)],
                                     cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(json.loads(process.stderr)["error"]["code"], "INVALID_ARGUMENT")

    def test_all_skills_trace_detached_inputs_outputs_and_calls(self):
        for skill in SKILL_IDS:
            payload = self.example(skill)
            response = self.runtime.execute(skill, payload)
            record = self.runtime.records[-1]
            self.assertEqual(record["input"], payload)
            self.assertEqual(record["output"], response)
            self.assertEqual(record["tool"]["called"], skill == "evidence_lookup")
            self.assertEqual(record["decision"]["status"], "succeeded" if response["ok"] else "failed")
            self.assertEqual(len(record["input_sha256"]), 64)
            self.assertEqual(record["automatic_retries"], 0)
            self.assertFalse(record["trusted_collector_verified"])
            payload.clear()
            response.clear()
            record.clear()
            self.assertIn("model_id", self.runtime.records[-1]["input"])
            self.assertIn("ok", self.runtime.records[-1]["output"])
        self.assertEqual(len({r["run_id"] for r in self.runtime.records}), 5)

    def test_surrogate_input_is_explicit_error_with_run_record(self):
        for surrogate in ("\ud800", "\udfff"):
            payload = {**self.example("evidence_lookup"), "query": surrogate}
            response = self.runtime.execute("evidence_lookup", payload)
            self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
            self.assertEqual(response["error"]["details"]["error_type"], "UnicodeEncodeError")
            record = self.runtime.records[-1]
            self.assertTrue(record["run_id"].startswith("skill-"))
            self.assertEqual(record["output"], response)
            self.assertEqual(record["error"], response["error"])
            self.assertEqual(record["stage"], "input_validation")
            self.assertEqual(record["decision"]["status"], "failed")
            self.assertFalse(record["tool"]["called"])
            self.assertIsNone(record["input"])
            self.assertIsNone(record["input_sha256"])
            json.dumps(record, ensure_ascii=False).encode("utf-8")
        self.assertNotEqual(self.runtime.records[0]["run_id"], self.runtime.records[1]["run_id"])
        self.assertTrue(self.runtime.execute("evidence_lookup", self.example("evidence_lookup"))["ok"])

    def test_serialization_failure_keeps_failed_record(self):
        from unittest.mock import patch
        for error in (TypeError("private"), ValueError("private")):
            with patch("lgax_core.skill_runner.json.dumps", side_effect=error):
                response = self.runtime.execute("evidence_lookup", self.example("evidence_lookup"))
            self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
            record = self.runtime.records[-1]
            self.assertEqual(record["output"], response)
            self.assertIsNone(record["input"])
            self.assertNotIn("private", json.dumps(record))

    def test_invalid_schema_input_is_not_retained(self):
        self.runtime.execute("need_extract", {**self.example("need_extract"), "secret": "do-not-retain"})
        record = self.runtime.records[-1]
        self.assertIsNone(record["input"])
        self.assertFalse(record["tool"]["called"])
        self.assertNotIn("do-not-retain", json.dumps(record))

    def test_successful_unresolved_and_gap_results_are_held(self):
        self.fixture("need_extract", {"needs": [], "desired_outcomes": [], "unresolved": ["자료 부족"]})
        self.assertTrue(self.runtime.execute("need_extract", self.example("need_extract"))["ok"])
        self.assertEqual(self.runtime.records[-1]["decision"], {"status": "held", "hold_reasons": ["자료 부족"]})
        gap = self.example("concept_draft")["gaps"][0]
        gap["support_status"] = "insufficient_evidence"
        self.fixture("product_compare", {"gaps": [gap], "unresolved": []})
        self.assertTrue(self.runtime.execute("product_compare", self.example("product_compare"))["ok"])
        self.assertEqual(self.runtime.records[-1]["decision"]["status"], "held")

    def test_retry_limits_and_rejected_parent_do_not_reset_budget(self):
        payload = self.example("need_extract")
        parent = None
        for count in range(3):
            self.runtime.execute("need_extract", payload, retry_of=parent)
            record = self.runtime.records[-1]
            self.assertEqual(record["retry_count"], count)
            self.assertEqual(record["retry_of"], parent)
            parent = record["run_id"]
        for _ in range(2):
            response = self.runtime.execute("need_extract", payload, retry_of=parent)
            self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
            self.assertFalse(self.runtime.records[-1]["tool"]["called"])
            parent = self.runtime.records[-1]["run_id"]

    def test_retry_rejects_changed_input_unknown_success_and_fork(self):
        payload = self.example("need_extract")
        self.runtime.execute("need_extract", payload)
        parent = self.runtime.records[-1]["run_id"]
        for prior, value in [("unknown", payload), (parent, {**payload, "document_version": "9.0"})]:
            self.assertEqual(self.runtime.execute("need_extract", value, retry_of=prior)["error"]["code"],
                             "INVALID_ARGUMENT")
        self.runtime.execute("need_extract", payload, retry_of=parent)
        self.assertEqual(self.runtime.execute("need_extract", payload, retry_of=parent)["error"]["code"],
                         "INVALID_ARGUMENT")
        lookup = self.example("evidence_lookup")
        self.runtime.execute("evidence_lookup", lookup)
        parent = self.runtime.records[-1]["run_id"]
        self.assertEqual(self.runtime.execute("evidence_lookup", lookup, retry_of=parent)["error"]["code"],
                         "INVALID_ARGUMENT")

    def test_failed_handler_recovery_preserves_original_record(self):
        calls = []
        def handler(payload, store):
            calls.append(payload)
            if len(calls) == 1:
                raise RuntimeError("private-provider-error")
            need = self.example("product_compare")["needs"][0]
            return {"needs": [need], "desired_outcomes": [{"need_id": need["id"], "desired_outcome": "개발 예시"}],
                    "unresolved": []}
        self.runtime.register_handler("need_extract", handler, backend_id="test:recovery", execution_kind="fixture")
        payload = self.example("need_extract")
        self.runtime.execute("need_extract", payload)
        original = self.runtime.records[-1]
        self.assertEqual(original["stage"], "handler_call")
        self.assertTrue(original["tool"]["called"])
        self.assertNotIn("private-provider-error", json.dumps(original))
        self.assertTrue(self.runtime.execute("need_extract", payload, retry_of=original["run_id"])["ok"])
        self.assertEqual(self.runtime.records[0], original)
        self.assertEqual(self.runtime.records[-1]["retry_count"], 1)
        self.assertEqual(len(calls), 2)

    def test_revision_budget_and_output_failure_stages(self):
        self.fixture("review_revision", {})
        payload = {**self.example("review_revision"), "revision_count": 2}
        self.runtime.execute("review_revision", payload)
        record = self.runtime.records[-1]
        self.assertEqual(record["decision"]["status"], "held")
        self.assertFalse(record["tool"]["called"])
        self.fixture("need_extract", {"needs": "bad output"})
        self.runtime.execute("need_extract", self.example("need_extract"))
        record = self.runtime.records[-1]
        self.assertEqual(record["stage"], "output_validation")
        self.assertTrue(record["tool"]["called"])
        self.assertEqual(record["decision"]["status"], "failed")
        self.assertNotIn("bad output", json.dumps(record))

    def test_cli_surrogate_retains_execution_record_not_read_error(self):
        with tempfile.TemporaryDirectory() as dirname:
            source, output = Path(dirname) / "in.json", Path(dirname) / "out.json"
            source.write_text(json.dumps({**self.example("evidence_lookup"), "query": "\ud800"}), encoding="utf-8")
            process = subprocess.run([sys.executable, str(ROOT / "skills/evidence_lookup/scripts/run.py"),
                                      "--input", str(source), "--output", str(output)],
                                     cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(process.stderr, "")
            response = json.loads(output.read_text(encoding="utf-8"))
            trace = json.loads(Path(str(output) + ".trace.json").read_text(encoding="utf-8"))
            self.assertIsNone(trace["cli_error"])
            self.assertEqual(len(trace["records"]), 1)
            record = trace["records"][0]
            self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
            self.assertEqual(response["error"]["details"]["error_type"], "UnicodeEncodeError")
            self.assertEqual(record["output"], response)
            self.assertEqual(record["error"], response["error"])
            self.assertEqual(record["decision"]["status"], "failed")
            self.assertTrue(record["run_id"].startswith("skill-"))
            self.assertFalse(record["tool"]["called"])
            self.assertIsNone(record["input"])

    def test_cli_all_skills_trace_and_existing_file_preservation(self):
        with tempfile.TemporaryDirectory() as dirname:
            for skill in SKILL_IDS:
                output = Path(dirname) / f"{skill}.json"
                command = [sys.executable, str(ROOT / "skills" / skill / "scripts/run.py"),
                           "--input", str(ROOT / "skills" / skill / "examples/input.json"), "--output", str(output)]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0 if skill == "evidence_lookup" else 2, result.stderr)
                trace = Path(str(output) + ".trace.json")
                original = trace.read_bytes()
                record = json.loads(original)["records"][0]
                self.assertEqual(record["output"], json.loads(output.read_text(encoding="utf-8")))
                self.assertEqual(record["skill_id"], skill)
                rerun = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
                self.assertEqual(rerun.returncode, 2)
                self.assertEqual(trace.read_bytes(), original)

    def test_cli_parse_failure_has_no_invented_execution(self):
        with tempfile.TemporaryDirectory() as dirname:
            source, output = Path(dirname) / "in.json", Path(dirname) / "out.json"
            source.write_text("not json", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "skills/evidence_lookup/scripts/run.py"),
                                     "--input", str(source), "--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            trace = json.loads(Path(str(output) + ".trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["records"], [])
            self.assertEqual(trace["cli_error"]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
