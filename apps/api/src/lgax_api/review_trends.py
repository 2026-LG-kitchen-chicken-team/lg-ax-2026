"""Deterministic DATA collector for the private review-trends contract.

This module consumes a trusted, versioned sidecar. It does not infer dates,
classify text at request time, edit source reviews, or connect itself to the
workspace server. The server-side injection remains an explicit PM action.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .trend_validation import (
    annotation_digest,
    canonical_annotation,
    trend_identity,
    trend_periods,
    trend_sample_warnings,
)
from .workspace_trends import TrendCollection

_KST = timezone(timedelta(hours=9))
_AGGREGATION_VERSION = "data-review-trends.v1"
_CONTRACT_VERSION = "review-trends.v1"


def canonical_dataset_sha256(dataset: dict) -> str:
    """Match WorkspaceStore's canonical dataset hash (not the file-byte hash)."""
    value = deepcopy(dataset)
    value.pop("contract_version", None)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_trend_metadata(path: str | Path) -> dict:
    """Load a pre-reviewed sidecar without changing or normalizing its source."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _review_indices(dataset: dict) -> tuple[dict, dict]:
    reviews = {row["id"]: row for row in dataset["reviews"]}
    evidence = {row["id"]: row for row in dataset["evidence"]}
    if (len(reviews) != len(dataset["reviews"]) or len(evidence) != len(dataset["evidence"])
            or len({row["evidence_id"] for row in reviews.values()}) != len(reviews)):
        raise ValueError("review/evidence identifiers must be unique")
    for review in reviews.values():
        source = evidence.get(review["evidence_id"])
        if source is None or source.get("source_type") != "review":
            raise ValueError(f"missing review evidence for {review['id']}")
        for key in ("model_id", "document_version", "source_kind", "source_id", "locator", "text"):
            if source.get(key) != review.get(key):
                raise ValueError(f"review/evidence binding mismatch for {review['id']}")
    return reviews, evidence


def _local_day(row: dict) -> date | None:
    value = row["published_at"]
    if value is None:
        if row["date_precision"] != "unknown" or row["date_provenance"] is not None:
            raise ValueError("unknown dates must be explicit and have no provenance")
        return None
    if row["date_precision"] == "day":
        return date.fromisoformat(value)
    if row["date_precision"] != "instant":
        raise ValueError("known dates require day or instant precision")
    instant = datetime.fromisoformat(value)
    if instant.utcoffset() is None:
        raise ValueError("instant dates require an explicit timezone")
    return instant.astimezone(_KST).date()


def _bound_rows(dataset: dict, metadata: dict) -> tuple[dict, list[dict]]:
    reviews, _ = _review_indices(dataset)
    canonical = canonical_annotation(metadata)
    prior_by_review: dict[str, dict] = {}
    provenance_hashes: dict[tuple, str] = {}
    for row in canonical["rows"]:
        original = reviews.get(row["review_id"])
        if original is None:
            raise ValueError(f"unknown review id {row['review_id']}")
        expected = {
            "evidence_id": original["evidence_id"],
            "source_id": original["source_id"],
            "model_id": original["model_id"],
            "document_version": original["document_version"],
            "source_kind": original["source_kind"],
            "text_sha256": hashlib.sha256(original["text"].encode("utf-8")).hexdigest(),
        }
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"source/model/version/text binding mismatch for {row['review_id']}")
        previous = prior_by_review.setdefault(row["review_id"], row)
        if previous != row:
            raise ValueError(f"conflicting duplicate annotation for {row['review_id']}")
        origin = row["date_provenance"]
        if origin is not None:
            if origin["source_id"] != original["source_id"]:
                raise ValueError(f"date provenance source mismatch for {row['review_id']}")
            scope = (row["source_kind"], row["source_id"], row["model_id"], row["document_version"])
            if provenance_hashes.setdefault(scope, origin["source_sha256"]) != origin["source_sha256"]:
                raise ValueError("one pinned source scope cannot have multiple source hashes")
        _local_day(row)
    return reviews, canonical["rows"]


def build_review_trend_collection(project: dict, dataset: dict, filters: dict,
                                  metadata: dict) -> TrendCollection:
    """Calculate counts and complete Evidence-ID memberships for one request.

    ``metadata`` must already be bound to the immutable dataset and carry its
    ``annotation_sha256``. No row is accepted from the request itself.
    """
    filters = deepcopy(filters)
    filters["source_ids"] = sorted(filters["source_ids"])
    filters["topic_ids"] = sorted(filters["topic_ids"])
    data = deepcopy(dataset)
    data.pop("contract_version", None)
    digest = canonical_dataset_sha256(data)
    if (metadata.get("dataset_sha256") != digest
            or metadata.get("dataset_version") != data.get("manifest", {}).get("version")):
        raise ValueError("sidecar does not match the frozen dataset")
    sidecar = canonical_annotation(metadata)
    if sidecar.get("annotation_sha256") != annotation_digest(sidecar):
        raise ValueError("sidecar annotation hash mismatch")

    project_data = project.get("project", {})
    request = project_data.get("request", {})
    project_id = project_data.get("id")
    model_id = filters["model_id"]
    if (filters["project_id"] != project_id
            or filters["dataset_version"] != data["manifest"]["version"]
            or model_id not in request.get("model_ids", [])
            or model_id not in project.get("document_versions", {})):
        raise ValueError("request does not match the fixed project/dataset scope")
    document_version = project["document_versions"][model_id]

    reviews, rows = _bound_rows(data, sidecar)
    scoped = [row for row in rows if (
        row["model_id"] == model_id
        and row["document_version"] == document_version
        and row["source_kind"] == filters["source_kind"]
        and row["source_id"] in filters["source_ids"]
    )]
    required = {row["id"] for row in reviews.values() if (
        row["model_id"] == model_id
        and row["document_version"] == document_version
        and row["source_kind"] == filters["source_kind"]
        and row["source_id"] in filters["source_ids"]
    )}
    if {row["review_id"] for row in scoped} != required:
        raise ValueError("sidecar omits one or more in-scope reviews")

    start = date.fromisoformat(filters["start_date"])
    end = date.fromisoformat(filters["end_date_exclusive"])
    known = [row for row in scoped if _local_day(row) is not None]
    in_period = [row for row in known if start <= _local_day(row) < end]

    contents_by_dedup_key = {}
    for row in scoped:
        if row["dedup_key"] is not None:
            key = (row["model_id"], row["document_version"], row["source_kind"],
                   row["source_id"], row["dedup_key"])
            previous_hash = contents_by_dedup_key.setdefault(key, row["text_sha256"])
            if previous_hash != row["text_sha256"]:
                raise ValueError("a deduplication key cannot bind different review text")

    unique_by_key = {}
    for row in sorted(in_period, key=lambda item: (
            _local_day(item), item["review_id"], item["evidence_id"])):
        key = (("review", row["review_id"]) if row["dedup_key"] is None else
               ("dedup", row["model_id"], row["document_version"], row["source_kind"],
                row["source_id"], row["dedup_key"]))
        previous = unique_by_key.get(key)
        if previous is not None:
            if (previous["topic_ids"] != row["topic_ids"]
                    or previous["classification_status"] != row["classification_status"]):
                raise ValueError("duplicate reviews have conflicting topic annotations")
        else:
            unique_by_key[key] = row
    unique = list(unique_by_key.values())

    topics = filters["topic_ids"] or sorted({topic for row in scoped for topic in row["topic_ids"]})
    if "__all__" in topics:
        raise ValueError("__all__ is a reserved membership key")
    periods = trend_periods(filters)
    memberships = {}
    buckets = []
    for period in periods:
        period_start = date.fromisoformat(period["period_start"])
        period_end = date.fromisoformat(period["period_end_exclusive"])
        included = [row for row in unique if period_start <= _local_day(row) < period_end]
        all_ids = sorted(row["evidence_id"] for row in included)
        topic_members = {}
        topic_values = []
        denominator = len(all_ids)
        for topic_id in topics:
            ids = sorted(row["evidence_id"] for row in included if topic_id in row["topic_ids"])
            topic_members[topic_id] = ids
            topic_values.append({
                "topic_id": topic_id,
                "topic_review_count": len(ids),
                "ratio": len(ids) / denominator if denominator else None,
                "evidence_count": len(ids),
                "evidence_ids": ids[:50],
                "evidence_ids_truncated": len(ids) > 50,
            })
        memberships[period["bucket_id"]] = {"__all__": all_ids, **topic_members}
        buckets.append({**period, "total_reviews": denominator, "topics": topic_values})

    counts = {
        "input_review_count": len(rows),
        "excluded_out_of_scope_count": len(rows) - len(scoped),
        "in_scope_review_count": len(scoped),
        "excluded_undated_count": len(scoped) - len(known),
        "excluded_outside_period_count": len(known) - len(in_period),
        "duplicate_count": len(in_period) - len(unique),
        "eligible_unique_review_count": len(unique),
        "unclassified_review_count": sum(row["classification_status"] == "unclassified" for row in unique),
    }
    aggregate = {
        "aggregate_id": trend_identity(filters, sidecar, _AGGREGATION_VERSION),
        "project_id": project_id,
        "dataset_version": sidecar["dataset_version"],
        "dataset_sha256": sidecar["dataset_sha256"],
        "annotation_version": sidecar["annotation_version"],
        "annotation_sha256": sidecar["annotation_sha256"],
        "trend_contract_version": _CONTRACT_VERSION,
        "filters": deepcopy(filters),
        "timezone": "Asia/Seoul",
        "aggregation_version": _AGGREGATION_VERSION,
        "classification": deepcopy(sidecar["classification"]),
        "topic_taxonomy_version": sidecar["topic_taxonomy_version"],
        "dedup_policy_version": sidecar["dedup_policy_version"],
        "counts": counts,
        "buckets": buckets,
        "warnings": trend_sample_warnings(buckets),
        "notes": (f"자료 성격: {filters['source_kind']}. 주제별 수치는 리뷰 주제 등장 비율입니다. "
                  "감정·불편 비율이나 판매량·시장 수요를 뜻하지 않습니다. "
                  "날짜가 없는 원문은 분모에서 빼고 제외 건수로 보고합니다."),
    }
    return TrendCollection(aggregate=aggregate, metadata=sidecar, memberships=memberships)


def create_review_trend_collector(metadata: dict):
    """Return an explicit trusted injection callable for PM-controlled wiring."""
    frozen_metadata = deepcopy(metadata)

    def collect(project: dict, dataset: dict, filters: dict) -> TrendCollection:
        return build_review_trend_collection(project, dataset, filters, frozen_metadata)

    return collect
