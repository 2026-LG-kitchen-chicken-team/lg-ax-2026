"""Offline synthetic cases: actual boundary execution, no model-quality claims."""
import unittest
from copy import deepcopy

from jsonschema import Draft202012Validator
from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.feature_scope import select_feature_scope
from lgax_core.judgement_contract import schema_for
from lgax_core.store import DemoStore


def fixture():
    request = {"product_group": "fridge", "target_customer": "사용자", "use_situation": "청소",
               "improvement_task": "청소 개선", "exclusions": [], "model_ids": ["A"], "dataset_version": "pack-1"}
    data = {"artifact_kind": "document_dataset", "dataset_version": "pack-1", "products": [],
            "features": [], "evidence": [], "reviews": []}
    for model, version, text in (("A", "v1", "자동 세척을 지원합니다. 빈 상태에서만 사용합니다."),
                                 ("B", "v1", "자동 세척을 지원하지 않습니다."),
                                 ("A", "v2", "자동 세척을 지원하지 않습니다. 수동 세척하세요.")):
        suffix = model + version
        data["products"].append({"model_id": model, "name": "가상 냉장고 " + model, "product_group": "fridge",
                                 "document_version": version, "source_kind": "synthetic"})
        data["features"].append({"id": "F-" + suffix, "model_id": model, "document_version": version,
                                 "name": "자동 세척", "description": text, "conditions": ["빈 상태"],
                                 "evidence_ids": ["E-" + suffix]})
        data["evidence"].append({"id": "E-" + suffix, "model_id": model, "document_version": version,
                                 "source_kind": "synthetic", "source_type": "manual", "source_id": "DOC-" + suffix,
                                 "locator": {"page": 1, "section": "청소"}, "text": text,
                                 "feature_ids": ["F-" + suffix]})
    return request, {"A": "v1"}, data


class FeatureScopeTests(unittest.TestCase):
    def setUp(self):
        self.request, self.versions, self.data = fixture()

    def select(self):
        return select_feature_scope(self.request, self.versions, self.data)

    def fails(self, code, reason):
        with self.assertRaises(DomainError) as caught:
            self.select()
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.details["reason"], reason)
        self.assertTrue(error.details["question"])
        validate("ErrorResponse", error.response())

    def test_same_feature_name_does_not_mix_models_or_versions(self):
        result = self.select()["inputs"][0]
        self.assertEqual([s["id"] for s in result["sources"]], ["E-Av1"])
        self.assertEqual([f["id"] for f in result["features"]], ["F-Av1"])
        self.assertEqual(result["sources"][0], self.data["evidence"][0])
        Draft202012Validator(schema_for("input")).validate(result)

    def test_changed_model_then_changed_version_reselect_originals(self):
        self.request["model_ids"] = ["B"]
        self.versions = {"B": "v1"}
        self.assertEqual(self.select()["inputs"][0]["sources"][0]["id"], "E-Bv1")
        self.request["model_ids"] = ["A"]
        self.versions = {"A": "v2"}
        self.assertEqual(self.select()["inputs"][0]["sources"][0]["id"], "E-Av2")

    def test_multiple_models_stay_separate_and_support_statements_unchanged(self):
        self.request["model_ids"] = ["B", "A"]
        self.versions = {"A": "v1", "B": "v1"}
        results = self.select()["inputs"]
        self.assertEqual([p["product"]["model_id"] for p in results], ["B", "A"])
        self.assertIn("지원하지 않습니다", results[0]["sources"][0]["text"])
        self.assertIn("지원합니다", results[1]["sources"][0]["text"])
        for result in results:
            Draft202012Validator(schema_for("input")).validate(result)

    def test_unmentioned_is_not_unsupported(self):
        self.data["features"] = self.data["features"][1:]
        self.data["evidence"][0].update(text="전원 버튼은 오른쪽에 있습니다.", feature_ids=[])
        result = self.select()["inputs"][0]
        self.assertEqual(result["features"], [])
        self.assertEqual(result["sources"][0]["text"], "전원 버튼은 오른쪽에 있습니다.")
        self.assertNotIn("support", result)
        self.assertNotIn("unsupported", str(result))

    def test_missing_requested_version_never_falls_back(self):
        for value in (None, "", "   ", 1):
            with self.subTest(value=value):
                self.versions["A"] = value
                self.fails("INVALID_DOCUMENT_VERSION", "missing_document_version")
        self.versions = {}
        self.fails("INVALID_DOCUMENT_VERSION", "missing_document_version")

    def test_missing_original_version_is_question_not_absence(self):
        del self.data["evidence"][0]["document_version"]
        self.fails("INVALID_DOCUMENT_VERSION", "missing_source_version")

    def test_unknown_model_differs_from_unknown_version(self):
        self.request["model_ids"] = ["UNKNOWN"]
        self.versions = {"UNKNOWN": "v1"}
        self.fails("INVALID_MODEL_ID", "model_not_found")
        self.request["model_ids"] = ["A"]
        self.versions = {"A": "unknown"}
        self.fails("INVALID_DOCUMENT_VERSION", "document_version_not_found")

    def test_dataset_mismatch(self):
        self.request["dataset_version"] = "pack-2"
        self.fails("DATASET_MISMATCH", "dataset_version_mismatch")

    def test_extra_version_scope_and_wrong_product_group(self):
        self.versions["B"] = "v1"
        self.fails("INVALID_ARGUMENT", "version_scope_mismatch")
        del self.versions["B"]
        self.request["product_group"] = "microwave"
        self.fails("INVALID_ARGUMENT", "product_group_mismatch")

    def test_cross_model_and_cross_version_feature_links_fail(self):
        for eid in ("E-Bv1", "E-Av2"):
            with self.subTest(eid=eid):
                self.data["features"][0]["evidence_ids"] = ["E-Av1", eid]
                self.fails("VALIDATION_FAILED", "feature_evidence_scope_mismatch")

    def test_source_cannot_smuggle_another_models_feature(self):
        self.data["evidence"][0]["feature_ids"].append("F-Bv1")
        self.fails("VALIDATION_FAILED", "source_feature_scope_mismatch")

    def test_missing_evidence_and_nonreciprocal_links(self):
        self.data["features"][0]["evidence_ids"].append("MISSING")
        self.fails("VALIDATION_FAILED", "missing_evidence")
        self.data["features"][0]["evidence_ids"] = ["E-Bv1"]
        self.fails("VALIDATION_FAILED", "nonreciprocal_link")

    def test_review_is_not_manual_support(self):
        self.data["evidence"][0]["source_type"] = "review"
        self.fails("VALIDATION_FAILED", "invalid_manual_link")

    def test_no_originals_is_insufficient_evidence(self):
        self.data["evidence"] = self.data["evidence"][1:]
        self.fails("INSUFFICIENT_EVIDENCE", "no_scoped_evidence")

    def test_duplicate_ids_fail_instead_of_last_record_wins(self):
        self.data["evidence"].append(deepcopy(self.data["evidence"][0]))
        self.fails("VALIDATION_FAILED", "duplicate_identity")

    def test_source_kind_and_original_metadata_preserved(self):
        # Public is a metadata mutation fixture, not a claim of real-source testing.
        self.data["products"][0]["source_kind"] = "public"
        self.fails("VALIDATION_FAILED", "source_kind_mismatch")
        self.data["evidence"][0]["source_kind"] = "public"
        result = self.select()["inputs"][0]
        self.assertEqual(result["product"], self.data["products"][0])
        self.assertEqual(result["sources"][0], self.data["evidence"][0])
        self.assertEqual(result["features"][0], self.data["features"][0])

    def test_invalid_canonical_input_and_missing_locator(self):
        self.request["model_ids"] = []
        self.fails("INVALID_ARGUMENT", "invalid_contract")
        self.request["model_ids"] = ["A"]
        self.data["evidence"][0]["locator"] = {}
        self.fails("INVALID_ARGUMENT", "invalid_contract")

    def test_copies_do_not_mutate_originals_or_sibling_requests(self):
        self.request["model_ids"] = ["A", "B"]
        self.versions["B"] = "v1"
        before = deepcopy((self.request, self.versions, self.data))
        result = self.select()
        self.assertEqual(before, (self.request, self.versions, self.data))
        result["inputs"][0]["sources"][0]["locator"]["page"] = 999
        result["inputs"][0]["features"][0]["conditions"].append("변경")
        result["inputs"][0]["request"]["exclusions"].append("변경")
        self.assertEqual(result["inputs"][1]["request"]["exclusions"], [])
        self.assertEqual(before, (self.request, self.versions, self.data))

    def test_demo_store_container_and_dataset_metadata(self):
        self.data = DemoStore().bootstrap()["data"]
        product = self.data["products"][0]
        self.request["model_ids"] = [product["model_id"]]
        self.request["dataset_version"] = self.data["manifest"]["version"]
        self.versions = {product["model_id"]: product["document_version"]}
        result = self.select()
        self.assertEqual(result["manifest"], self.data["manifest"])
        Draft202012Validator(schema_for("input")).validate(result["inputs"][0])
        self.data["dataset_version"] = "different"
        self.fails("DATASET_MISMATCH", "ambiguous_dataset_version")

    def test_all_or_nothing_if_second_model_has_no_originals(self):
        self.request["model_ids"] = ["A", "B"]
        self.versions["B"] = "v1"
        self.data["evidence"] = [e for e in self.data["evidence"] if e["model_id"] != "B"]
        self.fails("INSUFFICIENT_EVIDENCE", "no_scoped_evidence")


if __name__ == "__main__":
    unittest.main()
