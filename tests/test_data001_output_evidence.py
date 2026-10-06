import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "trace_tool", Path(__file__).resolve().parents[1] / "scripts/check_data001_output_evidence.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class EvidenceTraceTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "product": {"model_id": "A", "document_version": "v1", "source_kind": "synthetic"},
            "sources": [
                {
                    "id": "R1",
                    "model_id": "A",
                    "document_version": "v1",
                    "source_kind": "synthetic",
                    "source_type": "review",
                    "source_id": "CSV1",
                    "locator": {"row": 2},
                    "text": "원문 리뷰",
                },
                {
                    "id": "M1",
                    "model_id": "A",
                    "document_version": "v1",
                    "source_kind": "synthetic",
                    "source_type": "manual",
                    "source_id": "DOC1",
                    "locator": {"page": 4},
                    "text": "원문 설명서",
                },
            ],
        }
        self.output = {
            "model_id": "A",
            "document_version": "v1",
            "status": "held",
            "needs": [{"evidence_ids": ["R1"]}],
            "gaps": [{"evidence_ids": ["R1", "M1"]}],
        }

    def test_every_reference_maps_back_to_original_with_kind_and_position(self):
        r = tool.trace_output(self.payload, self.output, expected_kind="synthetic")
        self.assertEqual(r["status"], "references_traced")
        self.assertEqual(len(r["rows"]), 3)
        self.assertTrue(all(row["original_source_sha256"] for row in r["rows"]))
        self.assertEqual(r["rows"][-1]["locator"], {"page": 4})
        self.assertFalse(r["http_sqlite_resume_verified"])

    def test_wrong_model_version_kind_and_unknown_id_are_not_accepted(self):
        for field, value in [("model_id", "B"), ("document_version", "v2"), ("source_kind", "public")]:
            p = deepcopy(self.payload)
            p["sources"][0][field] = value
            self.assertEqual(tool.trace_output(p, self.output, expected_kind="synthetic")["status"], "failed")
        o = deepcopy(self.output)
        o["needs"][0]["evidence_ids"] = ["UNKNOWN"]
        self.assertEqual(tool.trace_output(self.payload, o)["status"], "failed")

    def test_missing_fixed_output_is_pending_not_a_success(self):
        r = tool.trace_output(self.payload, None)
        self.assertEqual(r["status"], "fixed_output_pending")
        self.assertEqual(r["rows"], [])

    def test_duplicate_original_id_is_refused(self):
        self.payload["sources"].append(deepcopy(self.payload["sources"][0]))
        with self.assertRaises(ValueError):
            tool.trace_output(self.payload, self.output)

    def test_product_kind_is_enforced_without_an_override(self):
        self.payload["sources"][0]["source_kind"] = "public"
        self.assertEqual(tool.trace_output(self.payload, self.output)["status"], "failed")

    def test_malformed_output_ids_are_reported_as_invalid(self):
        for value in [[{}], None]:
            output = deepcopy(self.output)
            output["needs"][0]["evidence_ids"] = value
            result = tool.trace_output(self.payload, output)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("INVALID_EVIDENCE_ID" in error for error in result["errors"]))

    def test_dataset_review_id_and_source_row_are_linked_and_tampering_is_refused(self):
        source = self.payload["sources"][0]
        review = {
            "id": "REVIEW1",
            "evidence_id": "R1",
            **{
                k: source[k]
                for k in ["model_id", "document_version", "source_kind", "source_id", "locator", "text"]
            },
        }
        dataset = {
            "dataset_version": "pack1",
            "evidence": deepcopy(self.payload["sources"]),
            "reviews": [review],
        }
        result = tool.trace_output(self.payload, self.output, dataset=dataset)
        self.assertEqual(result["rows"][0]["original_review_id"], "REVIEW1")
        self.assertTrue(result["rows"][0]["review_origin_verified"])
        self.assertEqual(result["dataset_version"], "pack1")
        payload = deepcopy(self.payload)
        payload["sources"][0]["text"] = "바뀐 원문"
        self.assertEqual(tool.trace_output(payload, self.output, dataset=dataset)["status"], "failed")

    def test_missing_review_record_cannot_prove_a_review_origin(self):
        dataset = {"dataset_version": "pack1", "evidence": deepcopy(self.payload["sources"]), "reviews": []}
        result = tool.trace_output(self.payload, self.output, dataset=dataset)
        self.assertEqual(result["status"], "failed")
        self.assertIn("REVIEW_RECORD_MISSING", result["rows"][0]["errors"])


if __name__ == "__main__":
    unittest.main()
