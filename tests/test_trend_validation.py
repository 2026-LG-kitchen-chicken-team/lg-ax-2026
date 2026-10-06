"""Meaning checks for approved provider output; all dates below are unit fiction."""

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_api.trend_validation import (
    annotation_digest,
    trend_identity,
    trend_periods,
    trend_sample_warnings,
    validate_trend_collection,
    validate_trend_request,
)
from lgax_core.errors import DomainError


def canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fixture():
    dataset = json.loads((Path(__file__).resolve().parents[1] / "data/demo/dataset.json").read_text("utf-8"))
    template = dataset["reviews"][0]
    model = template["model_id"]
    other = next(product for product in dataset["products"] if product["model_id"] != model)
    reviews, annotations = [], []
    for number in range(1, 5):
        review = deepcopy(template)
        review.update({"id": f"TREND-REVIEW-{number}", "evidence_id": f"TREND-EV-{number}",
                       "source_id": "TEST-REVIEWS", "text": f"검사 전용 합성 리뷰 {number}"})
        if number == 4:
            review.update({"model_id": other["model_id"], "document_version": other["document_version"]})
        reviews.append(review)
        dataset["evidence"].append({"id": review["evidence_id"], "source_type": "review", "feature_ids": [],
                                    **{key: review[key] for key in ("model_id", "document_version", "source_kind",
                                                                  "source_id", "locator", "text")}})
        annotations.append({
            "review_id": review["id"], "evidence_id": review["evidence_id"],
            **{key: review[key] for key in ("model_id", "document_version", "source_kind", "source_id")},
            "text_sha256": hashlib.sha256(review["text"].encode("utf-8")).hexdigest(),
            "published_at": f"2026-10-{number + 4:02d}", "date_precision": "day",
            "date_provenance": {"source_id": review["source_id"], "locator": deepcopy(review["locator"]),
                                "source_sha256": "1" * 64},
            "topic_ids": [] if number == 3 else ["cleaning"],
            "classification_status": "unclassified" if number == 3 else "classified", "dedup_key": None,
        })
    dataset["reviews"] = reviews
    dataset["manifest"]["review_count"] = len(reviews)
    digest = canonical_hash(dataset)
    request = {"product_group": next(p["product_group"] for p in dataset["products"] if p["model_id"] == model),
               "target_customer": "검사 전용", "use_situation": "합성 날짜 검사", "improvement_task": "근거 조회",
               "exclusions": [], "model_ids": [model], "dataset_version": dataset["manifest"]["version"]}
    project = {"project": {"id": "project-trends", "name": "합성 동향 검사", "request": request,
                           "status": "draft", "dataset_version": request["dataset_version"]},
               "owner_id": "pm-trends", "document_versions": {model: template["document_version"]},
               "created_at": "2026-10-06T00:00:00Z", "dataset_sha256": digest}
    filters = {"project_id": "project-trends", "model_id": model, "source_ids": ["TEST-REVIEWS"],
               "dataset_version": request["dataset_version"], "start_date": "2026-10-01",
               "end_date_exclusive": "2026-12-01", "granularity": "month", "topic_ids": ["cleaning"],
               "source_kind": "synthetic", "timezone": "Asia/Seoul"}
    metadata = {"dataset_version": request["dataset_version"], "dataset_sha256": digest,
                "annotation_version": "fiction-v1", "annotation_sha256": "0" * 64,
                "topic_taxonomy_version": "fixture-topics-v1", "dedup_policy_version": "fixture-dedup-v1",
                "classification": {"method": "rule", "model_id": None, "revision": "fixture-rule-v1"},
                "rows": annotations}
    metadata["annotation_sha256"] = annotation_digest(metadata)
    aggregate = {
        "aggregate_id": trend_identity(filters, metadata, "fixture-aggregation-v1"),
        "project_id": filters["project_id"], **{key: metadata[key] for key in (
            "dataset_version", "dataset_sha256", "annotation_version", "annotation_sha256", "classification",
            "topic_taxonomy_version", "dedup_policy_version")},
        "trend_contract_version": "review-trends.v1", "filters": deepcopy(filters), "timezone": "Asia/Seoul",
        "aggregation_version": "fixture-aggregation-v1", "warnings": ["검사 전용 작은 합성 표본"],
        "counts": {"input_review_count": 4, "excluded_out_of_scope_count": 1, "in_scope_review_count": 3,
                   "excluded_undated_count": 0, "excluded_outside_period_count": 0, "duplicate_count": 0,
                   "eligible_unique_review_count": 3, "unclassified_review_count": 1},
        "buckets": [{"bucket_id": "MONTH-2026-10", "label": "2026년 10월", "period_start": "2026-10-01",
                     "period_end_exclusive": "2026-11-01", "partial_period": False, "total_reviews": 3,
                     "topics": [{"topic_id": "cleaning", "topic_review_count": 2, "ratio": 2 / 3,
                                 "evidence_count": 2, "evidence_ids": ["TREND-EV-1", "TREND-EV-2"],
                                 "evidence_ids_truncated": False}]},
                    {"bucket_id": "MONTH-2026-11", "label": "2026년 11월", "period_start": "2026-11-01",
                     "period_end_exclusive": "2026-12-01", "partial_period": False, "total_reviews": 0,
                     "topics": [{"topic_id": "cleaning", "topic_review_count": 0, "ratio": None,
                                 "evidence_count": 0, "evidence_ids": [], "evidence_ids_truncated": False}]}],
    }
    memberships = {"MONTH-2026-10": {"__all__": ["TREND-EV-1", "TREND-EV-2", "TREND-EV-3"],
                                       "cleaning": ["TREND-EV-1", "TREND-EV-2"]},
                   "MONTH-2026-11": {"__all__": [], "cleaning": []}}
    aggregate["warnings"].extend(trend_sample_warnings(aggregate["buckets"]))
    return dataset, digest, project, metadata, aggregate, memberships


class TrendValidationTests(unittest.TestCase):
    def setUp(self):
        self.dataset, self.digest, self.project, self.metadata, self.aggregate, self.memberships = fixture()

    def check(self):
        validate_trend_collection(self.aggregate, self.metadata, self.memberships,
                                  self.project, self.dataset, self.digest)

    def rebind(self):
        self.metadata["annotation_sha256"] = annotation_digest(self.metadata)
        for key in ("annotation_sha256", "annotation_version", "dataset_sha256", "dataset_version"):
            self.aggregate[key] = self.metadata[key]
        self.aggregate["aggregate_id"] = trend_identity(self.aggregate["filters"], self.metadata,
                                                       self.aggregate["aggregation_version"])
        self.aggregate["warnings"] = ["검사 전용 작은 합성 표본", *trend_sample_warnings(self.aggregate["buckets"])]

    def rejected(self, code="CONTRACT_MISMATCH"):
        with self.assertRaises(DomainError) as result:
            self.check()
        self.assertEqual(result.exception.code, code)

    def test_complete_sample_includes_unclassified_denominator_and_empty_month(self):
        before = deepcopy((self.aggregate, self.metadata, self.memberships, self.dataset, self.project))
        self.check()
        self.assertEqual(before, (self.aggregate, self.metadata, self.memberships, self.dataset, self.project))

    def test_small_and_empty_samples_require_explicit_canonical_warnings(self):
        required = trend_sample_warnings(self.aggregate["buckets"])
        self.assertEqual(required, ["표본이 적습니다: 2026년 10월 리뷰 3건(20건 미만).",
                                    "집계 가능한 리뷰가 없습니다: 2026년 11월."])
        self.aggregate["warnings"].remove(required[0])
        self.rejected()

    def test_source_allowlist_is_derived_from_real_model_document_evidence(self):
        filters = deepcopy(self.aggregate["filters"])
        for field, bad in [("source_ids", ["FOREIGN-SOURCE"]), ("model_id", "FOREIGN-MODEL"),
                           ("project_id", "project-other"), ("source_kind", "public")]:
            candidate = {**filters, field: bad}
            with self.assertRaises(DomainError) as result:
                validate_trend_request(candidate, self.project, self.dataset, self.digest)
            self.assertEqual(result.exception.code, "INVALID_INPUT")

    def test_changed_content_under_same_dataset_version_is_drift(self):
        self.dataset["reviews"][0]["text"] += " 원문 변조"
        self.rejected("DATASET_MISMATCH")

    def test_stale_project_digest_and_metadata_digest_are_drift(self):
        self.project["dataset_sha256"] = "f" * 64
        self.rejected("DATASET_MISMATCH")
        self.project["dataset_sha256"] = self.digest
        self.metadata["dataset_sha256"] = "f" * 64
        self.rejected("DATASET_MISMATCH")

    def test_unapproved_row_content_or_evidence_cannot_be_cited(self):
        for field, value in [("text_sha256", "f" * 64), ("evidence_id", "TREND-EV-4"),
                             ("model_id", "FOREIGN-MODEL"), ("document_version", "wrong")]:
            with self.subTest(field=field):
                saved = deepcopy(self.metadata)
                self.metadata["rows"][0][field] = value
                self.rebind()
                self.rejected()
                self.metadata = saved
                self.rebind()

    def test_missing_annotation_never_silently_shrinks_the_selected_scope(self):
        self.metadata["rows"].pop(2)
        self.rebind()
        self.rejected()

    def test_annotation_digest_and_identity_are_order_independent(self):
        other = deepcopy(self.metadata)
        other["rows"].reverse()
        self.assertEqual(annotation_digest(other), annotation_digest(self.metadata))
        before = deepcopy(self.aggregate["filters"])
        filters = {**before, "topic_ids": ["odor", "cleaning"]}
        reverse = {**filters, "topic_ids": ["cleaning", "odor"]}
        self.assertEqual(trend_identity(filters, self.metadata, "v1"), trend_identity(reverse, self.metadata, "v1"))
        self.assertNotEqual(trend_identity(filters, self.metadata, "v1"), trend_identity(filters, self.metadata, "v2"))
        self.assertNotEqual(trend_identity(filters, self.metadata, "v1"),
                            trend_identity({**filters, "project_id": "project-other"}, self.metadata, "v1"))

    def test_raw_annotation_tampering_cannot_keep_the_same_hash(self):
        self.metadata["rows"][0]["published_at"] = "2026-10-06"
        self.rejected("DATASET_MISMATCH")

    def test_date_provenance_is_bound_to_the_original_source(self):
        self.metadata["rows"][0]["date_provenance"]["source_id"] = "FOREIGN-SOURCE"
        self.rebind()
        self.rejected()

    def test_invalid_calendar_and_timezone_free_instant_are_rejected(self):
        for value, precision in [("2026-02-30", "day"), ("2026-10-05T12:00:00", "instant")]:
            with self.subTest(value=value):
                original = deepcopy(self.metadata)
                self.metadata["rows"][0].update({"published_at": value, "date_precision": precision})
                self.rejected()
                self.metadata = original
                self.rebind()

    def test_utc_instant_is_clipped_using_kst_half_open_dates(self):
        self.metadata["rows"][0].update({"published_at": "2026-09-30T15:00:00Z", "date_precision": "instant"})
        self.rebind()
        self.check()  # Exactly October 1 KST.
        self.metadata["rows"][0]["published_at"] = "2026-09-30T14:59:59Z"
        self.rebind()
        self.rejected()  # Same claimed counts now include a September record.

    def test_requested_topic_does_not_change_the_denominator(self):
        self.aggregate["filters"]["topic_ids"] = ["not-present"]
        for bucket in self.aggregate["buckets"]:
            old = bucket["topics"][0]
            bucket["topics"] = [{**old, "topic_id": "not-present", "topic_review_count": 0,
                                  "ratio": 0 if bucket["total_reviews"] else None,
                                  "evidence_count": 0, "evidence_ids": []}]
            membership = self.memberships[bucket["bucket_id"]]
            membership.pop("cleaning")
            membership["not-present"] = []
        self.rebind()
        self.check()
        self.aggregate["buckets"][0]["total_reviews"] = 0
        self.rejected()

    def test_ratio_zero_is_distinct_from_empty_denominator_null(self):
        self.aggregate["buckets"][1]["topics"][0]["ratio"] = 0
        self.rejected()
        self.aggregate["buckets"][1]["topics"][0]["ratio"] = None
        self.aggregate["buckets"][0]["topics"][0]["ratio"] = 1
        self.rejected()

    def test_forged_count_membership_and_unsorted_paging_are_rejected(self):
        self.aggregate["counts"]["unclassified_review_count"] = 0
        self.rejected()
        self.aggregate["counts"]["unclassified_review_count"] = 1
        self.memberships["MONTH-2026-10"]["__all__"].reverse()
        self.rejected()
        self.memberships["MONTH-2026-10"]["__all__"].sort()
        self.memberships["MONTH-2026-10"]["cleaning"] = ["TREND-EV-1", "TREND-EV-4"]
        self.rejected()

    def test_truncated_preview_still_requires_complete_membership_for_paging(self):
        # Fifty preview IDs cannot substitute for the full 51-review topic.
        original, annotation = self.dataset["reviews"][0], self.metadata["rows"][0]
        for number in range(49):
            review = {**deepcopy(original), "id": f"EXTRA-REVIEW-{number:03d}",
                      "evidence_id": f"EXTRA-EVIDENCE-{number:03d}"}
            self.dataset["reviews"].append(review)
            self.dataset["evidence"].append({"id": review["evidence_id"], "source_type": "review", "feature_ids": [],
                                            **{key: review[key] for key in ("model_id", "document_version", "source_kind",
                                                                          "source_id", "locator", "text")}})
            self.metadata["rows"].append({**deepcopy(annotation), "review_id": review["id"],
                                          "evidence_id": review["evidence_id"]})
        self.dataset["manifest"]["review_count"] = len(self.dataset["reviews"])
        self.digest = canonical_hash(self.dataset)
        self.project["dataset_sha256"] = self.digest
        self.metadata["dataset_sha256"] = self.digest
        all_ids = sorted(["TREND-EV-1", "TREND-EV-2", "TREND-EV-3",
                          *[f"EXTRA-EVIDENCE-{number:03d}" for number in range(49)]])
        topic_ids = sorted(set(all_ids) - {"TREND-EV-3"})
        self.aggregate["counts"].update({"input_review_count": 53, "in_scope_review_count": 52,
                                         "eligible_unique_review_count": 52})
        bucket = self.aggregate["buckets"][0]
        bucket["total_reviews"] = 52
        bucket["topics"][0].update({"topic_review_count": 51, "ratio": 51 / 52, "evidence_count": 51,
                                    "evidence_ids": topic_ids[:50], "evidence_ids_truncated": True})
        self.memberships["MONTH-2026-10"] = {"__all__": all_ids, "cleaning": topic_ids}
        self.rebind()
        self.check()
        self.memberships["MONTH-2026-10"]["cleaning"] = topic_ids[:50]
        self.rejected()

    def test_same_review_repeated_input_is_counted_once_after_date_filter(self):
        self.metadata["rows"].append(deepcopy(self.metadata["rows"][0]))
        self.aggregate["counts"].update({"input_review_count": 5, "in_scope_review_count": 4, "duplicate_count": 1})
        self.rebind()
        self.check()

    def test_conflicting_raw_text_cannot_share_a_dedup_key(self):
        for row in self.metadata["rows"][:2]:
            row["dedup_key"] = "same-key"
        self.rebind()
        self.rejected()

    def test_same_text_dedup_keeps_unclassified_denominator_and_scoped_counts(self):
        text = self.dataset["reviews"][0]["text"]
        self.dataset["reviews"][1]["text"] = text
        next(e for e in self.dataset["evidence"] if e["id"] == "TREND-EV-2")["text"] = text
        self.digest = canonical_hash(self.dataset)
        self.project["dataset_sha256"] = self.digest
        self.metadata["dataset_sha256"] = self.digest
        for row in self.metadata["rows"][:2]:
            row["dedup_key"] = "same-key"
            row["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.aggregate["counts"].update({"duplicate_count": 1, "eligible_unique_review_count": 2})
        self.aggregate["buckets"][0]["total_reviews"] = 2
        self.aggregate["buckets"][0]["topics"][0].update({"topic_review_count": 1, "ratio": 0.5,
                                                           "evidence_count": 1, "evidence_ids": ["TREND-EV-1"]})
        self.memberships["MONTH-2026-10"] = {"__all__": ["TREND-EV-1", "TREND-EV-3"], "cleaning": ["TREND-EV-1"]}
        self.rebind()
        self.check()

    def test_winter_crosses_year_and_partial_period_and_leap_day_are_explicit(self):
        filters = {**self.aggregate["filters"], "granularity": "season", "start_date": "2027-01-01",
                   "end_date_exclusive": "2027-03-01"}
        self.assertEqual(trend_periods(filters), [{"bucket_id": "SEASON-2026-WINTER", "label": "2026년 겨울",
                                                  "period_start": "2026-12-01", "period_end_exclusive": "2027-03-01",
                                                  "partial_period": True}])
        leap = {**filters, "granularity": "month", "start_date": "2028-02-29", "end_date_exclusive": "2028-03-01"}
        self.assertEqual(trend_periods(leap)[0]["period_end_exclusive"], "2028-03-01")
        self.assertTrue(trend_periods(leap)[0]["partial_period"])
        for start, end in [("2026-02-29", "2026-03-01"), ("2026-01-01", "2026-01-01"),
                           ("2026-01-01", "2036-01-02"), ("2026-01-15", "2036-01-15")]:
            with self.subTest(start=start, end=end), self.assertRaises(DomainError) as result:
                trend_periods({**filters, "start_date": start, "end_date_exclusive": end})
            self.assertEqual(result.exception.code, "INVALID_INPUT")

    def test_wrong_calendar_label_or_omitted_empty_bucket_is_rejected(self):
        self.aggregate["buckets"][0]["label"] = "2026년 겨울"
        self.rejected()
        self.aggregate["buckets"][0]["label"] = "2026년 10월"
        self.aggregate["buckets"].pop()
        self.memberships.pop("MONTH-2026-11")
        self.rejected()

    def test_no_date_is_not_invented_and_counts_exclusions_without_overlap(self):
        row = self.metadata["rows"][0]
        row.update({"published_at": None, "date_precision": "unknown", "date_provenance": None})
        self.aggregate["counts"].update({"excluded_undated_count": 1, "eligible_unique_review_count": 2})
        self.aggregate["buckets"][0]["total_reviews"] = 2
        self.aggregate["buckets"][0]["topics"][0].update({"topic_review_count": 1, "ratio": 0.5,
                                                           "evidence_count": 1, "evidence_ids": ["TREND-EV-2"]})
        self.memberships["MONTH-2026-10"] = {"__all__": ["TREND-EV-2", "TREND-EV-3"], "cleaning": ["TREND-EV-2"]}
        self.rebind()
        self.check()
        self.aggregate["counts"]["excluded_outside_period_count"] = 1
        self.rejected()


if __name__ == "__main__":
    unittest.main()
