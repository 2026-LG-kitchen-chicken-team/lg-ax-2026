"""DATA review-trend collection tests: source-bound, synthetic dates are isolated."""

import csv
import hashlib
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "packages/core/src"))

from lgax_api.review_trends import (  # noqa: E402
    build_review_trend_collection,
    canonical_dataset_sha256,
)
from lgax_api.trend_validation import (  # noqa: E402
    canonical_annotation,
    validate_trend_collection,
)

DATASET_PATH = ROOT / "data/demo/dataset.json"
CSV_PATH = ROOT / "data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv"
SIDECAR_PATH = ROOT / "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json"
CSV_SHA256 = "3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9"
DATASET_FILE_SHA256 = "97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _load_original():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _filters(dataset, *, start="2026-10-01", end="2026-11-01", granularity="month", topics=None):
    source_ids = sorted({row["source_id"] for row in dataset["reviews"]
                         if row["model_id"] == "FRIDGE-A"})
    return {
        "project_id": "project-data-trends-test",
        "model_id": "FRIDGE-A",
        "source_ids": source_ids,
        "dataset_version": dataset["manifest"]["version"],
        "start_date": start,
        "end_date_exclusive": end,
        "granularity": granularity,
        "topic_ids": list(topics or ["cleaning"]),
        "source_kind": "synthetic",
        "timezone": "Asia/Seoul",
    }


def _project(dataset):
    digest = canonical_dataset_sha256(dataset)
    request = json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))[0]
    request["model_ids"] = ["FRIDGE-A"]
    request["dataset_version"] = dataset["manifest"]["version"]
    return {
        "project": {
            "id": "project-data-trends-test", "name": "DATA trend test",
            "request": request, "status": "draft",
            "dataset_version": dataset["manifest"]["version"],
        },
        "owner_id": "pm-data-trends-test",
        "document_versions": {"FRIDGE-A": next(
            row["document_version"] for row in dataset["reviews"] if row["model_id"] == "FRIDGE-A")},
        "created_at": "2026-10-06T00:00:00Z",
        "dataset_sha256": digest,
    }


def _rehash(metadata):
    metadata["annotation_sha256"] = "0" * 64
    unsigned = canonical_annotation(metadata)
    unsigned.pop("annotation_sha256")
    metadata["annotation_sha256"] = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
    return metadata


def _dated_synthetic_dataset_and_sidecar(*, conflicting_duplicate_text=False):
    """Build an isolated in-memory test version; never edits the 36-source fixture."""
    dataset = _load_original()
    dataset["manifest"].update(
        dataset_id="kitchen-trend-dated-test",
        version="synthetic-dated-test.v1",
        description="Test-only dated copy; dates and duplicate are invented for calculation checks.",
    )
    original_reviews = dataset["reviews"]
    evidence_by_id = {item["id"]: item for item in dataset["evidence"]}
    source_id = "TREND-DATED-SYNTHETIC-v1"
    for review in original_reviews:
        old_evidence_id = review["evidence_id"]
        review["id"] = "TREND-" + review["id"]
        review["evidence_id"] = "TREND-EVIDENCE-" + old_evidence_id.removeprefix("REVIEW-EVIDENCE-")
        review["source_id"] = source_id
        review["document_version"] = "synthetic.v1"
        review["locator"] = {"row": int(review["id"].rsplit("-", 1)[1])}
        evidence = evidence_by_id.pop(old_evidence_id)
        evidence["id"] = review["evidence_id"]
        evidence["source_id"] = source_id
        evidence["document_version"] = "synthetic.v1"
        evidence["locator"] = deepcopy(review["locator"])
        evidence["text"] = review["text"]
    dataset["evidence"] = list(evidence_by_id.values())
    # Re-append the rewritten review Evidence items, kept outside the old-id index.
    dataset["evidence"].extend({
        "id": review["evidence_id"], "source_type": "review", "feature_ids": [],
        **{key: review[key] for key in (
            "model_id", "document_version", "source_kind", "source_id", "locator", "text")},
    } for review in original_reviews)
    dataset["manifest"]["review_count"] = len(original_reviews)

    review_1 = next(row for row in original_reviews if row["id"] == "TREND-REVIEW-001")
    review_2 = next(row for row in original_reviews if row["id"] == "TREND-REVIEW-002")
    review_2["text"] = ("합성 중복 충돌 문장" if conflicting_duplicate_text else review_1["text"])
    review_2_evidence = next(row for row in dataset["evidence"] if row["id"] == review_2["evidence_id"])
    review_2_evidence["text"] = review_2["text"]

    base = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    source_topics = {row["review_id"]: row["topic_ids"] for row in base["rows"]}
    dates = {
        "TREND-REVIEW-001": ("2026-11-30T15:00:00Z", "instant"),  # 12/1 00:00 KST
        "TREND-REVIEW-002": ("2026-12-31T15:00:00Z", "instant"),  # 1/1 00:00 KST
        "TREND-REVIEW-003": ("2028-02-29", "day"),
        "TREND-REVIEW-004": (None, "unknown"),
        "TREND-REVIEW-005": ("2026-11-30", "day"),  # outside winter 2026
    }
    rows = []
    for review in original_reviews:
        original_id = review["id"].removeprefix("TREND-")
        published_at, precision = dates.get(review["id"], (None, "unknown"))
        if review["id"] in {"TREND-REVIEW-001", "TREND-REVIEW-002"}:
            topic_ids = ["cleaning"]
        elif review["id"] == "TREND-REVIEW-003":
            topic_ids = ["cleaning", "food_findability"]
        else:
            topic_ids = deepcopy(source_topics[original_id])
        row = {
            "review_id": review["id"], "evidence_id": review["evidence_id"],
            "source_id": review["source_id"], "model_id": review["model_id"],
            "document_version": review["document_version"], "source_kind": review["source_kind"],
            "text_sha256": hashlib.sha256(review["text"].encode("utf-8")).hexdigest(),
            "published_at": published_at, "date_precision": precision,
            "date_provenance": (None if published_at is None else {
                "source_id": source_id, "locator": deepcopy(review["locator"]),
                "source_sha256": "a" * 64,
            }),
            "topic_ids": topic_ids, "classification_status": "classified",
            "dedup_key": ("synthetic-cross-winter-duplicate" if review["id"] in {
                "TREND-REVIEW-001", "TREND-REVIEW-002"} else
                "exact-text:" + hashlib.sha256(review["text"].encode("utf-8")).hexdigest()),
        }
        rows.append(row)
    metadata = {
        "dataset_version": dataset["manifest"]["version"],
        "dataset_sha256": canonical_dataset_sha256(dataset),
        "annotation_version": "synthetic-dated-test.v1",
        "annotation_sha256": "0" * 64,
        "topic_taxonomy_version": "synthetic-dated-test-topics.v1",
        "dedup_policy_version": "synthetic-test-dedup.v1",
        "classification": {"method": "human", "model_id": None, "revision": None},
        "rows": rows,
    }
    return dataset, _rehash(metadata)


class ReviewTrendCollectorTests(unittest.TestCase):
    def _collect(self, dataset, metadata, filters):
        project = _project(dataset)
        result = build_review_trend_collection(project, dataset, filters, metadata)
        validate_trend_collection(result.aggregate, result.metadata, result.memberships,
                                  project, dataset, canonical_dataset_sha256(dataset))
        return result

    def test_existing_36_reviews_remain_undated_and_csv_stays_unchanged(self):
        dataset = _load_original()
        metadata = json.loads(SIDECAR_PATH.read_text("utf-8"))
        original_bytes = DATASET_PATH.read_bytes()
        csv_bytes = CSV_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(original_bytes).hexdigest(), DATASET_FILE_SHA256)
        self.assertEqual(hashlib.sha256(csv_bytes).hexdigest(), CSV_SHA256)
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(len(reader.fieldnames), 8)
            self.assertEqual(len(list(reader)), 36)

        result = self._collect(dataset, metadata, _filters(dataset))
        counts = result.aggregate["counts"]
        self.assertEqual(counts, {
            "input_review_count": 36, "excluded_out_of_scope_count": 26,
            "in_scope_review_count": 10, "excluded_undated_count": 10,
            "excluded_outside_period_count": 0, "duplicate_count": 0,
            "eligible_unique_review_count": 0, "unclassified_review_count": 0,
        })
        bucket = result.aggregate["buckets"][0]
        self.assertEqual(bucket["total_reviews"], 0)
        self.assertIsNone(bucket["topics"][0]["ratio"])
        self.assertEqual(result.memberships[bucket["bucket_id"]], {
            "__all__": [], "cleaning": [],
        })
        self.assertTrue(any("집계 가능한 리뷰가 없습니다" in warning
                            for warning in result.aggregate["warnings"]))
        self.assertEqual(DATASET_PATH.read_bytes(), original_bytes)
        self.assertEqual(CSV_PATH.read_bytes(), csv_bytes)

    def test_kst_winter_dedup_multitopic_and_leap_day(self):
        dataset, metadata = _dated_synthetic_dataset_and_sidecar()
        winter = self._collect(dataset, metadata, _filters(
            dataset, start="2026-12-01", end="2027-03-01", granularity="season",
            topics=["cleaning", "food_findability", "no_matching_topic"],
        ))
        counts = winter.aggregate["counts"]
        self.assertEqual(counts["in_scope_review_count"], 10)
        self.assertEqual(counts["excluded_undated_count"], 6)
        self.assertEqual(counts["excluded_outside_period_count"], 2)
        self.assertEqual(counts["duplicate_count"], 1)
        self.assertEqual(counts["eligible_unique_review_count"], 1)
        bucket = winter.aggregate["buckets"][0]
        self.assertEqual(bucket["bucket_id"], "SEASON-2026-WINTER")
        self.assertEqual(bucket["total_reviews"], 1)
        self.assertEqual(bucket["topics"][0]["topic_review_count"], 1)
        self.assertEqual(bucket["topics"][0]["ratio"], 1)
        self.assertEqual(bucket["topics"][1]["topic_review_count"], 0)
        self.assertEqual(bucket["topics"][1]["ratio"], 0)
        self.assertEqual(bucket["topics"][2]["ratio"], 0)
        self.assertEqual(winter.memberships[bucket["bucket_id"]]["__all__"],
                         ["TREND-EVIDENCE-001"])

        leap = self._collect(dataset, metadata, _filters(
            dataset, start="2028-02-01", end="2028-03-01", topics=["cleaning", "food_findability"],
        ))
        leap_bucket = leap.aggregate["buckets"][0]
        self.assertEqual(leap_bucket["bucket_id"], "MONTH-2028-02")
        self.assertEqual(leap_bucket["total_reviews"], 1)
        self.assertEqual([topic["ratio"] for topic in leap_bucket["topics"]], [1, 1])
        self.assertEqual(leap.memberships[leap_bucket["bucket_id"]]["food_findability"],
                         ["TREND-EVIDENCE-003"])

    def test_wrong_source_model_version_and_conflicting_duplicate_text_fail(self):
        dataset = _load_original()
        metadata = json.loads(SIDECAR_PATH.read_text("utf-8"))
        filters = _filters(dataset)

        for field, value in (("source_id", "WRONG-SOURCE"),
                             ("model_id", "DISHWASHER-A"),
                             ("document_version", "2.0")):
            altered = deepcopy(metadata)
            altered["rows"][0][field] = value
            _rehash(altered)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "binding mismatch"):
                build_review_trend_collection(_project(dataset), dataset, filters, altered)

        conflicting_dataset, conflicting_metadata = _dated_synthetic_dataset_and_sidecar(
            conflicting_duplicate_text=True)
        with self.assertRaisesRegex(ValueError, "different review text"):
            build_review_trend_collection(_project(conflicting_dataset), conflicting_dataset,
                                          _filters(conflicting_dataset, start="2026-12-01",
                                                   end="2027-03-01", granularity="season"),
                                          conflicting_metadata)


if __name__ == "__main__":
    unittest.main()
