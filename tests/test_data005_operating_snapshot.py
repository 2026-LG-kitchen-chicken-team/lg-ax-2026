"""Read-only capture comparisons, including source substitution and incomplete receipts."""

import hashlib
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "data005_capture", ROOT / "scripts/check_data005_operating_snapshot.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

DATA_DIR = ROOT / "data/research/DATA-owner-followup-20261006-01a1100e"


def _fixture(original=False, *, project_id="project-operating-capture", limit=50):
    if original:
        dataset_path = ROOT / "data/demo/dataset.json"
        annotation_path = ROOT / "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json"
        date_hash = None
    else:
        dataset_path = DATA_DIR / "dataset.synthetic-dated-demo.v1.json"
        annotation_path = DATA_DIR / "annotation.synthetic-dated-demo.v1.json"
        date_hash = hashlib.sha256((DATA_DIR / "source.synthetic-dated-demo.v1.json").read_bytes()).hexdigest()
    dataset = json.loads(dataset_path.read_text("utf-8"))
    annotation = json.loads(annotation_path.read_text("utf-8"))
    request = json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))[0]
    request.update(model_ids=["FRIDGE-A"], dataset_version=dataset["manifest"]["version"])
    project = {"project": {"id": project_id, "name": "capture fixture", "request": request,
                          "status": "draft", "dataset_version": dataset["manifest"]["version"]},
               "owner_id": "fixture-owner", "document_versions": {"FRIDGE-A": next(
                   row["document_version"] for row in dataset["reviews"] if row["model_id"] == "FRIDGE-A")},
               "created_at": "2026-10-06T00:00:00Z",
               "dataset_sha256": TOOL.canonical_dataset_sha256(dataset)}
    query = {"project_id": project_id, "model_id": "FRIDGE-A",
             "source_ids": sorted({row["source_id"] for row in dataset["reviews"]
                                   if row["model_id"] == "FRIDGE-A"}),
             "dataset_version": dataset["manifest"]["version"],
             "start_date": "2026-10-01", "end_date_exclusive": "2026-11-01",
             "granularity": "month", "topic_ids": ["cleaning"],
             "source_kind": "synthetic", "timezone": "Asia/Seoul"}
    expected = TOOL.build_review_trend_collection(project, dataset, query, annotation)
    sources = {row["id"]: row for row in dataset["evidence"]}
    ids = {identifier for mapping in expected.memberships.values()
           for identifiers in mapping.values() for identifier in identifiers}
    saved = {"aggregate": expected.aggregate, "metadata": expected.metadata,
             "memberships": expected.memberships, "evidence": {key: sources[key] for key in ids}}
    pages = []
    for bucket, mapping in expected.memberships.items():
        for topic, identifiers in mapping.items():
            if topic == "__all__":
                continue
            for offset in range(0, max(1, len(identifiers)), limit):
                pages.append({"project_id": project_id, "aggregate_id": expected.aggregate["aggregate_id"],
                              "bucket_id": bucket, "topic_id": topic, "offset": offset, "limit": limit,
                              "total": len(identifiers),
                              "next_offset": offset + limit if offset + limit < len(identifiers) else None,
                              "evidence": [sources[key] for key in identifiers[offset:offset + limit]]})
    capture = deepcopy({"project": project, "filters": query, "api_aggregate": expected.aggregate,
                        "mcp_aggregate": expected.aggregate, "restart_aggregate": expected.aggregate,
                        "stored_snapshot": saved, "restart_snapshot": saved, "evidence_pages": pages})
    return capture, dataset, annotation, date_hash


class OperatingSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.capture, self.dataset, self.annotation, self.date_hash = _fixture()

    def report(self, capture=None, *, date_hash="default"):
        return TOOL.compare_snapshot(self.capture if capture is None else capture,
                                     self.dataset, self.annotation,
                                     date_source_sha256=self.date_hash if date_hash == "default" else date_hash)

    def test_complete_current_data_pack_matches_without_asserting_operating_origin(self):
        report = self.report()
        self.assertEqual(report["status"], "match")
        self.assertFalse(report["operating_origin_verified"])
        self.assertFalse(report["PM_approval_verified"])
        bucket = self.capture["api_aggregate"]["buckets"][0]
        self.assertEqual((bucket["total_reviews"], bucket["topics"][0]["ratio"]), (4, 0.25))

    def test_undated_original_keeps_zero_denominator_and_null_ratio(self):
        capture, dataset, annotation, date_hash = _fixture(original=True)
        self.assertEqual(TOOL.compare_snapshot(capture, dataset, annotation,
                         date_source_sha256=date_hash)["status"], "match")
        self.assertIsNone(capture["api_aggregate"]["buckets"][0]["topics"][0]["ratio"])

    def test_duplicate_empty_page_cannot_pass(self):
        capture, dataset, annotation, date_hash = _fixture(original=True)
        capture["evidence_pages"].append(deepcopy(capture["evidence_pages"][0]))
        self.assertEqual(TOOL.compare_snapshot(capture, dataset, annotation,
                         date_source_sha256=date_hash)["status"], "mismatch")

    def test_recomputes_identity_for_the_captured_project(self):
        capture, dataset, annotation, date_hash = _fixture(project_id="project-another-owner")
        self.assertNotEqual(capture["api_aggregate"]["aggregate_id"],
                            self.capture["api_aggregate"]["aggregate_id"])
        self.assertEqual(TOOL.compare_snapshot(capture, dataset, annotation,
                         date_source_sha256=date_hash)["status"], "match")

    def test_old_project_aggregate_cannot_be_reused(self):
        self.capture["api_aggregate"]["project_id"] = "project-old"
        self.assertEqual(self.report()["status"], "mismatch")

    def test_wrong_dataset_version_cannot_match(self):
        self.capture["filters"]["dataset_version"] = "wrong-version"
        self.assertEqual(self.report()["status"], "mismatch")

    def test_other_model_cannot_enter_scope(self):
        self.capture["filters"]["model_id"] = "MICROWAVE-A"
        self.assertEqual(self.report()["status"], "mismatch")

    def test_other_source_cannot_enter_scope(self):
        self.capture["filters"]["source_ids"] = ["unknown-source"]
        self.assertEqual(self.report()["status"], "mismatch")

    def test_equal_counts_with_wrong_evidence_are_rejected(self):
        self.capture["api_aggregate"]["buckets"][0]["topics"][0]["evidence_ids"] = ["other-review"]
        self.assertEqual(self.report()["status"], "mismatch")

    def test_missing_mcp_or_restart_is_unconfirmed(self):
        for field in ("api_aggregate", "mcp_aggregate", "restart_aggregate"):
            with self.subTest(field=field):
                capture = deepcopy(self.capture)
                del capture[field]
                self.assertEqual(self.report(capture)["status"], "unconfirmed")

    def test_mcp_or_restart_changed_counts_are_rejected(self):
        for field in ("mcp_aggregate", "restart_aggregate"):
            with self.subTest(field=field):
                capture = deepcopy(self.capture)
                capture[field]["buckets"][0]["total_reviews"] = 3
                self.assertEqual(self.report(capture)["status"], "mismatch")

    def test_boolean_cannot_replace_a_numeric_count(self):
        self.capture["api_aggregate"]["buckets"][0]["topics"][0]["topic_review_count"] = True
        self.assertEqual(self.report()["status"], "mismatch")

    def test_full_denominator_membership_is_required(self):
        self.capture["stored_snapshot"]["memberships"]["MONTH-2026-10"]["__all__"].pop()
        self.assertEqual(self.report()["status"], "mismatch")

    def test_denominator_original_text_is_preserved_after_restart(self):
        identifiers = self.capture["restart_snapshot"]["memberships"]["MONTH-2026-10"]["__all__"]
        self.capture["restart_snapshot"]["evidence"][identifiers[0]]["text"] += " changed"
        self.assertEqual(self.report()["status"], "mismatch")

    def test_restart_aggregate_alone_cannot_prove_original_preservation(self):
        del self.capture["restart_snapshot"]
        self.assertEqual(self.report()["status"], "unconfirmed")

    def test_missing_saved_metadata_stays_unconfirmed(self):
        del self.capture["stored_snapshot"]["metadata"]
        self.assertEqual(self.report()["status"], "unconfirmed")

    def test_original_page_text_and_model_are_compared(self):
        for field, value in (("text", "replacement text"), ("model_id", "MICROWAVE-A")):
            with self.subTest(field=field):
                capture = deepcopy(self.capture)
                capture["evidence_pages"][0]["evidence"][0][field] = value
                self.assertEqual(self.report(capture)["status"], "mismatch")

    def test_duplicate_page_and_page_gap_are_rejected(self):
        self.capture["evidence_pages"].append(deepcopy(self.capture["evidence_pages"][0]))
        self.assertEqual(self.report()["status"], "mismatch")
        self.capture["evidence_pages"] = self.capture["evidence_pages"][:1]
        self.capture["evidence_pages"][0]["offset"] = 1
        self.assertEqual(self.report()["status"], "mismatch")

    def test_wrong_aggregate_in_page_is_rejected(self):
        self.capture["evidence_pages"][0]["aggregate_id"] = "TREND-" + "0" * 64
        self.assertEqual(self.report()["status"], "mismatch")

    def test_missing_pages_stay_unconfirmed(self):
        self.capture["evidence_pages"] = []
        self.assertEqual(self.report()["status"], "unconfirmed")

    def test_invalid_page_fields_are_rejected(self):
        for field, value in (("next_offset", True), ("limit", 0), ("total", True), ("topic_id", [])):
            with self.subTest(field=field):
                capture = deepcopy(self.capture)
                capture["evidence_pages"][0][field] = value
                self.assertEqual(self.report(capture)["status"], "mismatch")

    def test_date_file_missing_or_substituted_cannot_pass(self):
        self.assertEqual(self.report(date_hash=None)["status"], "unconfirmed")
        self.assertEqual(self.report(date_hash="0" * 64)["status"], "mismatch")

    def test_self_declared_approval_does_not_approve_a_capture(self):
        self.capture.update(production_verified=True, PM_approval_verified=True)
        report = self.report()
        self.assertFalse(report["PM_approval_verified"])
        self.assertFalse(report["operating_origin_verified"])

    def test_duplicate_keys_and_nonfinite_json_are_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "capture.json"
            for raw in ('{"aggregate":1,"aggregate":2}', '{"count":NaN}'):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError):
                    TOOL._read_json(path)


if __name__ == "__main__":
    unittest.main()
