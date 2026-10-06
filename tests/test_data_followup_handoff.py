"""Verify prepared DATA artifacts against preserved original bytes and scopes."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_api.review_trends import build_review_trend_collection, canonical_dataset_sha256
from lgax_api.trend_validation import annotation_digest
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/research/DATA-owner-followup-20261006-01a1100e"


class DataFollowupHandoffTests(unittest.TestCase):
    def test_dated_source_hash_and_original_texts_are_real_provenance(self):
        source_raw = (FOLDER / "source.synthetic-dated-demo.v1.json").read_bytes()
        source = json.loads(source_raw)
        dataset = json.loads((FOLDER / "dataset.synthetic-dated-demo.v1.json").read_bytes())
        metadata = json.loads((FOLDER / "annotation.synthetic-dated-demo.v1.json").read_bytes())
        DemoStore(dataset)
        self.assertEqual(metadata["dataset_sha256"], canonical_dataset_sha256(dataset))
        self.assertEqual(metadata["annotation_sha256"], annotation_digest(metadata))
        by_id = {row["id"]: row for row in source["rows"]}
        for row in metadata["rows"]:
            original = by_id[row["review_id"]]
            self.assertEqual(row["published_at"], original["published_at"])
            if row["published_at"] is not None:
                self.assertTrue(original["date_is_constructed"])
                self.assertEqual(row["date_provenance"]["source_sha256"], hashlib.sha256(source_raw).hexdigest())
                self.assertEqual(row["date_provenance"]["locator"], original["locator"])
        before = json.loads((ROOT / "data/demo/dataset.json").read_bytes())
        self.assertEqual([r["text"] for r in dataset["reviews"]], [r["text"] for r in before["reviews"]])
        handoff = json.loads((FOLDER / "demo-handoff.json").read_bytes())
        self.assertEqual(handoff["original_csv_file_sha256"],
            hashlib.sha256((ROOT / "data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv").read_bytes()).hexdigest())

    def test_nonempty_mentions_include_positive_review_without_claiming_pain(self):
        collection = json.loads((FOLDER / "demo-october.json").read_bytes())
        bucket = collection["aggregate"]["buckets"][0]
        cleaning = next(topic for topic in bucket["topics"] if topic["topic_id"] == "cleaning")
        self.assertEqual(bucket["total_reviews"], 4)
        self.assertEqual(cleaning["ratio"], 0.25)
        self.assertEqual(cleaning["evidence_ids"], ["SYNTH-DATED-REVIEW-EVIDENCE-006"])
        self.assertEqual(collection["aggregate"]["counts"]["excluded_undated_count"], 1)
        labels = json.loads((FOLDER / "topic-display-labels.preview.v1.json").read_bytes())
        self.assertEqual(labels["measure_label"], "주제 언급 비율")
        self.assertFalse(labels["polarity_labelled"])
        self.assertEqual(len(labels["topics"]), 7)

    def test_empty_ratios_and_winter_boundary(self):
        empty = json.loads((FOLDER / "demo-empty.json").read_bytes())["aggregate"]
        self.assertEqual(empty["counts"]["eligible_unique_review_count"], 0)
        self.assertTrue(all(t["ratio"] is None for b in empty["buckets"] for t in b["topics"]))
        winter = json.loads((FOLDER / "demo-winter.json").read_bytes())["aggregate"]
        self.assertEqual(winter["counts"]["eligible_unique_review_count"], 2)

    def test_changed_sidecar_dataset_binding_is_rejected(self):
        metadata = json.loads((FOLDER / "annotation.synthetic-dated-demo.v1.json").read_bytes())
        dataset = json.loads((FOLDER / "dataset.synthetic-dated-demo.v1.json").read_bytes())
        filters = json.loads((FOLDER / "demo-october.json").read_bytes())["aggregate"]["filters"]
        request = json.loads((ROOT / "data/demo/planning_requests.json").read_bytes())[0]
        request.update(model_ids=["FRIDGE-A"], dataset_version=dataset["manifest"]["version"])
        project = {"project": {"id": "data-dated-demo", "request": request}, "document_versions": {"FRIDGE-A": "1.0"}}
        for change in ({"dataset_sha256": "0" * 64}, {"annotation_sha256": "0" * 64}):
            with self.assertRaises(ValueError):
                build_review_trend_collection(project, dataset, filters, {**deepcopy(metadata), **change})

    def test_r4_output_bytes_and_questionless_failure_are_preserved(self):
        audit = json.loads((FOLDER / "r4-original-audit.json").read_bytes())
        self.assertEqual(audit["new_model_calls"], 0)
        self.assertEqual(len(audit["cases"]), 3)
        for case in audit["cases"]:
            self.assertEqual(hashlib.sha256((ROOT / case["output_path"]).read_bytes()).hexdigest(), case["output_sha256"])
            self.assertEqual(case["questions"], [])
            self.assertEqual(case["status"], "failed")
            self.assertEqual(case["feature_gap_concept_count"], [0, 0, 0])
            self.assertEqual(len(case["needs"]), 9)
