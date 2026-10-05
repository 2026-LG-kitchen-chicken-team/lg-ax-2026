"""Offline provenance regressions; fixture calls never prove live model execution."""

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from lgax_contracts import load_schema
from lgax_core import DemoStore
from lgax_core.errors import DomainError
from lgax_core.skill_runner import SKILL_IDS, SkillRuntime, schema_for

ROOT = Path(__file__).resolve().parents[1]


def example(skill):
    return json.loads((ROOT / "skills" / skill / "examples/input.json").read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False).encode("utf-8")).hexdigest()


class SkillProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()
        self.request = {
            "product_group": "fridge", "target_customer": "개발용 합성 사용자",
            "use_situation": "선반 청소", "improvement_task": "불편과 기존 기능 대조",
            "exclusions": ["실제 수요로 해석 금지"], "model_ids": ["FRIDGE-A"],
            "dataset_version": self.store.bootstrap()["data"]["manifest"]["version"],
        }
        self.runtime = SkillRuntime(self.store, request=self.request)

    def install_fixtures(self):
        def extract(payload, _store):
            need = example("product_compare")["needs"][0]
            return {"needs": [need], "desired_outcomes": [
                {"need_id": need["id"], "desired_outcome": "식품 이동 감소 여부 검토"}], "unresolved": []}

        def compare(payload, _store):
            return {"gaps": example("concept_draft")["gaps"], "unresolved": []}

        def draft(payload, _store):
            return {"concepts": [], "hold_reasons": ["합성 근거의 한계 확인 필요"]}

        def revise(payload, _store):
            needs = deepcopy(payload["needs"])
            needs[0]["pain"] = "합성 입력에서 식품 이동 부담을 다시 검토"
            return {"needs": needs, "gaps": payload["gaps"], "concepts": payload["concepts"],
                    "revision_count": payload["revision_count"] + 1,
                    "changes": [{"field": "needs", "reason": "조건 변경에 따른 표현 검토",
                                 "evidence_ids": ["REVIEW-EVIDENCE-001"]}],
                    "unresolved": ["실제 수요 미검증"]}

        for skill, handler in zip(SKILL_IDS[1:], (extract, compare, draft, revise)):
            self.runtime.register_handler(skill, handler, backend_id="test:provenance-fixture-v1",
                                          execution_kind="fixture")

    def test_five_called_skills_share_request_contract_dataset_and_originals(self):
        self.install_fixtures()
        for skill in SKILL_IDS:
            response = self.runtime.execute(skill, example(skill))
            self.assertTrue(response["ok"], response)
            Draft202012Validator(schema_for(skill, "output")).validate(response)
        trace = self.runtime.trace
        self.assertEqual(trace["request"], self.request)
        self.assertEqual(trace["request_sha256"], digest(self.request))
        self.assertEqual(trace["contract_sha256"], digest(load_schema()))
        self.assertEqual(trace["dataset_sha256"], digest(self.store.bootstrap()["data"]))
        self.assertEqual([r["skill_id"] for r in trace["records"]], list(SKILL_IDS))
        prior = None
        for sequence, record in enumerate(trace["records"], 1):
            self.assertEqual(record["sequence"], sequence)
            self.assertEqual(record["previous_run_id"], prior)
            self.assertEqual(record["execution_id"], trace["execution_id"])
            self.assertEqual(record["request_sha256"], trace["request_sha256"])
            self.assertEqual(record["contract_sha256"], trace["contract_sha256"])
            self.assertTrue(record["tool"]["called"])
            kind = "deterministic" if sequence == 1 else "fixture"
            self.assertEqual(record["tool"]["execution_kind"], kind)
            self.assertIsNone(record["tool"]["model_call_count"])
            self.assertEqual(record["provenance"]["dataset_sha256"], trace["dataset_sha256"])
            self.assertEqual(record["provenance"]["manifest"]["source_kind"], "synthetic")
            for source in record["provenance"]["sources"]:
                self.assertEqual(source, self.store.get_evidence(source["id"])["data"]["evidence"])
                self.assertEqual((source["model_id"], source["document_version"]), ("FRIDGE-A", "1.0"))
            self.assertFalse(record["trusted_collector_verified"])
            prior = record["run_id"]
        revision = trace["records"][-1]
        self.assertEqual(revision["decision"]["status"], "held")
        self.assertEqual(revision["revision"]["before"]["needs"], example("review_revision")["needs"])
        self.assertNotEqual(revision["revision"]["before"]["needs"], revision["revision"]["after"]["needs"])
        self.assertEqual(revision["revision"]["after"]["revision_count"], 1)
        self.assertEqual(revision["revision"]["changes"], revision["output"]["data"]["result"]["changes"])

    def test_trace_request_sources_and_outputs_are_detached(self):
        self.runtime.execute("evidence_lookup", example("evidence_lookup"))
        original = self.runtime.trace
        self.request["exclusions"].append("caller mutation")
        changed = self.runtime.trace
        changed["request"].clear()
        changed["records"][0]["provenance"]["sources"][0]["text"] = "forged"
        changed["records"][0]["output"].clear()
        self.assertEqual(self.runtime.trace, original)

    def test_changed_input_links_before_after_without_rewriting_or_retrying(self):
        payload = example("evidence_lookup")
        self.runtime.execute("evidence_lookup", payload)
        before = self.runtime.records[-1]
        changed = {**payload, "query": "존재하지않는검색표현"}
        response = self.runtime.execute("evidence_lookup", changed, revision_of=before["run_id"])
        self.assertTrue(response["ok"], response)
        record = self.runtime.records[-1]
        self.assertEqual(record["change"], {"before_input": payload, "before_output": before["output"],
                                          "after_input": changed, "after_output": response})
        self.assertEqual(record["retry_count"], 0)
        self.assertIsNone(record["retry_of"])
        self.assertEqual(self.runtime.records[0], before)

    def test_changed_link_rejects_unknown_other_skill_scope_and_identical_input(self):
        payload = example("evidence_lookup")
        self.runtime.execute("evidence_lookup", payload)
        parent = self.runtime.records[-1]["run_id"]
        cases = [("evidence_lookup", payload, "unknown"),
                 ("evidence_lookup", payload, parent),
                 ("need_extract", example("need_extract"), parent),
                 ("evidence_lookup", {**payload, "model_id": "FRIDGE-B"}, parent),
                 ("evidence_lookup", {**payload, "document_version": "2.0"}, parent)]
        for skill, value, prior in cases:
            with self.subTest(skill=skill, value=value):
                response = self.runtime.execute(skill, value, revision_of=prior)
                self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
                self.assertFalse(self.runtime.records[-1]["tool"]["called"])
        response = self.runtime.execute("evidence_lookup", payload, revision_of=parent, retry_of=parent)
        self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")

    def test_failed_and_held_calls_keep_sources_and_explicit_retry_links(self):
        self.install_fixtures()
        def fail(_payload, _store):
            raise RuntimeError("provider-private-detail")
        self.runtime.register_handler("need_extract", fail, backend_id="test:failure",
                                      execution_kind="fixture", replace=True)
        payload = example("need_extract")
        self.runtime.execute("need_extract", payload)
        parent = self.runtime.records[-1]
        self.assertEqual(parent["decision"]["status"], "failed")
        self.assertEqual(parent["stage"], "handler_call")
        self.assertTrue(parent["provenance"]["sources"])
        self.assertNotIn("provider-private-detail", json.dumps(parent))
        self.runtime.execute("need_extract", payload, retry_of=parent["run_id"])
        retry = self.runtime.records[-1]
        self.assertEqual(retry["retry_count"], 1)
        self.assertEqual(retry["provenance"], parent["provenance"])
        self.assertEqual(self.runtime.records[0], parent)
        self.runtime.execute("review_revision", {**example("review_revision"), "revision_count": 2})
        held = self.runtime.records[-1]
        self.assertEqual(held["decision"]["status"], "held")
        self.assertFalse(held["tool"]["called"])
        self.assertTrue(held["provenance"]["sources"])
        self.assertNotIn("revision", held)

    def test_dataset_content_and_version_changes_are_blocked_before_retry(self):
        for change in ("version", "text"):
            with self.subTest(change=change):
                runtime = SkillRuntime(self.store)
                payload = example("need_extract")
                runtime.execute("need_extract", payload)
                prior = runtime.records[-1]
                dataset = deepcopy(self.store._dataset)
                if change == "version":
                    dataset["manifest"]["version"] = "changed-version"
                else:
                    for collection in ("evidence", "reviews"):
                        for item in dataset[collection]:
                            if item.get("evidence_id", item["id"]) == "REVIEW-EVIDENCE-001":
                                item["text"] += " 합성 문구 변경"
                runtime.store = DemoStore(dataset)
                response = runtime.execute("need_extract", payload, retry_of=prior["run_id"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
                record = runtime.records[-1]
                self.assertEqual(record["stage"], "provenance_validation")
                self.assertFalse(record["tool"]["called"])
                self.assertNotEqual(record["provenance"]["dataset_sha256"], prior["provenance"]["dataset_sha256"])
                self.assertEqual(runtime.trace["dataset_sha256"], prior["provenance"]["dataset_sha256"])

    def test_callback_cannot_change_dataset_and_report_success(self):
        def mutate(_payload, _store):
            dataset = deepcopy(self.store._dataset)
            dataset["manifest"]["version"] = "changed-in-callback"
            self.runtime.store = DemoStore(dataset)
            return {"needs": [], "desired_outcomes": [], "unresolved": ["fixture"]}
        self.runtime.register_handler("need_extract", mutate, backend_id="test:mutating-fixture",
                                      execution_kind="fixture")
        result = self.runtime.execute("need_extract", example("need_extract"))
        self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(self.runtime.records[-1]["stage"], "provenance_validation")
        self.assertTrue(self.runtime.records[-1]["tool"]["called"])

    def test_reader_cannot_diverge_from_recorded_original_text(self):
        self.install_fixtures()
        # Replace the index entry: in-place edits would also mutate bootstrap's
        # shared dictionary and would not exercise reader/snapshot divergence.
        self.store._evidence["REVIEW-EVIDENCE-001"] = {
            **self.store._evidence["REVIEW-EVIDENCE-001"], "text": "lookup differs from bootstrap"}
        result = self.runtime.execute("need_extract", example("need_extract"))
        self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        record = self.runtime.records[-1]
        self.assertEqual(record["stage"], "context_validation")
        self.assertFalse(record["tool"]["called"])

    def test_changed_review_cannot_reset_business_revision_counter(self):
        self.install_fixtures()
        payload = example("review_revision")
        self.assertTrue(self.runtime.execute("review_revision", payload)["ok"])
        parent = self.runtime.records[-1]["run_id"]
        changed = {**payload, "violations": ["새 변경 요청"]}
        result = self.runtime.execute("review_revision", changed, revision_of=parent)
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse(self.runtime.records[-1]["tool"]["called"])
        changed["revision_count"] = 1
        self.assertTrue(self.runtime.execute("review_revision", changed, revision_of=parent)["ok"])
        parent = self.runtime.records[-1]["run_id"]
        changed["revision_count"] = 2
        result = self.runtime.execute("review_revision", changed, revision_of=parent)
        self.assertEqual(result["error"]["code"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(self.runtime.records[-1]["tool"]["called"])
        self.assertEqual(self.runtime.records[-1]["decision"]["status"], "held")

    def test_non_synthetic_store_is_rejected_without_relabelling_sources(self):
        self.store._dataset["evidence"][0]["source_kind"] = "public"
        result = self.runtime.execute("evidence_lookup", example("evidence_lookup"))
        self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        self.assertFalse(self.runtime.records[-1]["tool"]["called"])

    def test_request_contract_and_scope_are_checked_without_backend_calls(self):
        for request in ({}, {**self.request, "unexpected": "not allowed"},
                        {**self.request, "improvement_task": "\ud800"}):
            with self.assertRaises(DomainError):
                SkillRuntime(self.store, request=request)
        for request in ({**self.request, "dataset_version": "missing"},
                        {**self.request, "model_ids": ["FRIDGE-B"]},
                        {**self.request, "product_group": "microwave"}):
            runtime = SkillRuntime(self.store, request=request)
            result = runtime.execute("evidence_lookup", example("evidence_lookup"))
            self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
            self.assertFalse(runtime.records[-1]["tool"]["called"])

    def test_legacy_caller_and_missing_backend_do_not_invent_request_or_calls(self):
        runtime = SkillRuntime(self.store)
        result = runtime.execute("need_extract", example("need_extract"))
        self.assertEqual(result["error"]["code"], "NOT_IMPLEMENTED")
        trace = runtime.trace
        self.assertIsNone(trace["request"])
        self.assertIsNone(trace["request_sha256"])
        self.assertFalse(trace["records"][0]["tool"]["called"])
        self.assertTrue(trace["records"][0]["provenance"]["sources"])

    def test_live_label_is_declaration_not_model_call_verification(self):
        # Intentionally a fake callback with a live declaration: the registry
        # cannot authenticate it and must never turn that label into proof.
        self.runtime.register_handler("need_extract", lambda _p, _s: {
            "needs": [], "desired_outcomes": [], "unresolved": ["실호출 증거 미확인"]},
            backend_id="declared-model@declared-revision", execution_kind="live_model")
        self.runtime.execute("need_extract", example("need_extract"))
        record = self.runtime.records[-1]
        self.assertEqual(record["tool"]["execution_kind"], "live_model")
        self.assertEqual(record["tool"]["backend_id"], "declared-model@declared-revision")
        self.assertEqual(record["tool"]["observation"], "handler_boundary")
        self.assertIsNone(record["tool"]["model_call_count"])
        self.assertFalse(record["trusted_collector_verified"])
        self.assertEqual(record["decision"]["status"], "held")

    def test_bad_output_and_invalid_input_keep_distinct_failure_stages(self):
        self.runtime.register_handler("need_extract", lambda _p, _s: {"needs": "invalid-result"},
                                      backend_id="test:invalid", execution_kind="fixture")
        result = self.runtime.execute("need_extract", example("need_extract"))
        self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        record = self.runtime.records[-1]
        self.assertEqual(record["stage"], "output_validation")
        self.assertTrue(record["provenance"]["sources"])
        self.assertNotIn("invalid-result", json.dumps(record))
        result = self.runtime.execute("need_extract", {"unexpected": "not-retained"})
        self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        record = self.runtime.records[-1]
        self.assertEqual(record["stage"], "input_validation")
        self.assertIsNone(record["provenance"])
        self.assertIsNone(record["input"])
        self.assertNotIn("not-retained", json.dumps(record))


if __name__ == "__main__":
    unittest.main()
