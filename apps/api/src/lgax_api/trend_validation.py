"""Validate trusted trend-provider results, never produce a research aggregate.

Date provenance identifies an approved source and locator. DemoDataset does not
contain original source-file bytes: its declared source SHA is a trusted sidecar
pin, not a claim that this module independently verified the publication date.
"""

import calendar
import hashlib
import json
import math
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from jsonschema import ValidationError
from lgax_contracts import validate
from lgax_core.errors import DomainError

_KST = timezone(timedelta(hours=9))
_CONTRACT = "review-trends.v1"


def _fail(code="CONTRACT_MISMATCH"):
    messages = {
        "INVALID_INPUT": "동향 조회 입력과 허용 범위를 확인해 주세요.",
        "DATASET_MISMATCH": "작업실과 동향 자료의 고정 버전이 다릅니다.",
        "CONTRACT_MISMATCH": "동향 자료 또는 집계 결과가 공통 규격과 다릅니다.",
    }
    raise DomainError(code, messages[code])


def _schema(name, value, code="CONTRACT_MISMATCH"):
    try:
        validate(name, value)
    except (ValidationError, TypeError, ValueError):
        _fail(code)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _canonical_filters(filters):
    result = deepcopy(filters)
    result["source_ids"] = sorted(result["source_ids"])
    result["topic_ids"] = sorted(result["topic_ids"])
    return result


def canonical_annotation(metadata) -> dict:
    """Keep annotation identity and stored snapshots insensitive to row order."""
    value = deepcopy(metadata)
    for row in value["rows"]:
        row["topic_ids"] = sorted(row["topic_ids"])
    value["rows"].sort(key=_json)
    return value


def annotation_digest(metadata) -> str:
    """Canonical v1: sort row topics and rows; exclude only the digest field.

    Identical repeated rows remain present, so duplicate input accounting is
    preserved. Callers use this helper while constructing a trusted sidecar.
    """
    value = canonical_annotation(metadata)
    value.pop("annotation_sha256", None)
    return _digest(value)


def trend_identity(filters, metadata, aggregation_version) -> str:
    """Client type and request time never participate in the shared identity."""
    _schema("ReviewTrendRequest", filters, "INVALID_INPUT")
    _schema("ReviewTrendMetadata", metadata)
    _schema("ReviewTrendVersion", aggregation_version)
    return "TREND-" + _digest({
        "trend_contract_version": _CONTRACT,
        "filters": _canonical_filters(filters),
        "aggregation_version": aggregation_version,
        **{key: metadata[key] for key in (
            "dataset_version", "dataset_sha256", "annotation_version", "annotation_sha256",
            "classification", "topic_taxonomy_version", "dedup_policy_version",
        )},
    })


def _dataset(dataset, dataset_sha256):
    value = deepcopy(dataset)
    if isinstance(value, dict):
        value.pop("contract_version", None)
    _schema("DemoDataset", value)
    if _digest(value) != dataset_sha256:
        _fail("DATASET_MISMATCH")
    return value


def _period_start(day, granularity):
    if granularity == "month":
        return day.replace(day=1)
    if granularity == "year":
        return date(day.year, 1, 1)
    if day.month < 3:
        return date(day.year - 1, 12, 1)
    return date(day.year, 3 + 3 * ((day.month - 3) // 3), 1)


def _next_period(start, granularity):
    months = {"month": 1, "season": 3, "year": 12}[granularity]
    index = start.year * 12 + start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _periods(filters):
    """Whole calendar boundaries; provider counts are clipped to the request."""
    try:
        start = date.fromisoformat(filters["start_date"])
        end = date.fromisoformat(filters["end_date_exclusive"])
        anniversary_year = min(start.year + 10, 9999)
        anniversary = date(anniversary_year, start.month,
                           min(start.day, calendar.monthrange(anniversary_year, start.month)[1]))
        if start >= end or end > anniversary:
            _fail("INVALID_INPUT")
        month = start.replace(day=1)
        count = 0
        while month < end:
            count += 1
            if count > 120:
                _fail("INVALID_INPUT")
            month = _next_period(month, "month")
        cursor = _period_start(start, filters["granularity"])
        result = []
        while cursor < end:
            following = _next_period(cursor, filters["granularity"])
            result.append((cursor, following, start > cursor or end < following))
            cursor = following
        return result
    except (ValueError, OverflowError):
        _fail("INVALID_INPUT")


def trend_periods(filters) -> list[dict]:
    """Canonical v1 IDs/labels; January belongs to the prior winter year."""
    _schema("ReviewTrendRequest", filters, "INVALID_INPUT")
    result = []
    seasons = {3: ("SPRING", "봄"), 6: ("SUMMER", "여름"),
               9: ("AUTUMN", "가을"), 12: ("WINTER", "겨울")}
    for start, end, partial in _periods(filters):
        if filters["granularity"] == "month":
            identifier, label = f"MONTH-{start.year:04d}-{start.month:02d}", f"{start.year}년 {start.month}월"
        elif filters["granularity"] == "year":
            identifier, label = f"YEAR-{start.year:04d}", f"{start.year}년"
        else:
            identifier, name = seasons[start.month]
            identifier, label = f"SEASON-{start.year:04d}-{identifier}", f"{start.year}년 {name}"
        result.append({"bucket_id": identifier, "label": label,
                       "period_start": start.isoformat(), "period_end_exclusive": end.isoformat(),
                       "partial_period": partial})
    return result


def trend_sample_warnings(buckets) -> list[str]:
    """Required deterministic sample context, without significance claims."""
    result = []
    for bucket in buckets:
        _schema("ReviewTrendBucket", bucket)
        count, label = bucket["total_reviews"], bucket["label"]
        if count == 0:
            result.append(f"집계 가능한 리뷰가 없습니다: {label}.")
        elif count < 20:
            result.append(f"표본이 적습니다: {label} 리뷰 {count}건(20건 미만).")
    return result


def validate_trend_request(filters, project, dataset, dataset_sha256) -> dict:
    """Validate a query against the actual frozen model/document/source join."""
    _schema("ReviewTrendRequest", filters, "INVALID_INPUT")
    _schema("WorkspaceProjectSnapshot", project)
    data = _dataset(dataset, dataset_sha256)
    version = data["manifest"]["version"]
    if (project["dataset_sha256"] != dataset_sha256
            or project["project"]["dataset_version"] != version
            or filters["dataset_version"] != version):
        _fail("DATASET_MISMATCH")
    if (filters["project_id"] != project["project"]["id"]
            or filters["model_id"] not in project["project"]["request"]["model_ids"]
            or filters["model_id"] not in project["document_versions"]):
        _fail("INVALID_INPUT")
    model = filters["model_id"]
    version = project["document_versions"][model]
    allowed_sources = {item["source_id"] for item in data["evidence"]
                       if item["model_id"] == model and item["document_version"] == version
                       and item["source_kind"] == filters["source_kind"]}
    if not set(filters["source_ids"]).issubset(allowed_sources):
        _fail("INVALID_INPUT")
    result = _canonical_filters(filters)
    _periods(result)
    return result


def _indices(dataset):
    reviews = {row["id"]: row for row in dataset["reviews"]}
    evidence = {row["id"]: row for row in dataset["evidence"]}
    if (len(reviews) != len(dataset["reviews"]) or len(evidence) != len(dataset["evidence"])
            or len({row["evidence_id"] for row in reviews.values()}) != len(reviews)):
        _fail()
    for review in reviews.values():
        source = evidence.get(review["evidence_id"])
        if source is None or source["source_type"] != "review":
            _fail()
        if any(source[key] != review[key] for key in (
                "model_id", "document_version", "source_kind", "source_id", "locator", "text")):
            _fail()
    return reviews, evidence


def _day(row):
    if row["published_at"] is None:
        return None
    try:
        if row["date_precision"] == "day":
            return date.fromisoformat(row["published_at"])
        value = datetime.fromisoformat(row["published_at"])
        if value.utcoffset() is None:
            _fail()
        return value.astimezone(_KST).date()
    except (ValueError, OverflowError):
        _fail()


def _in_scope(row, filters, project):
    return (row["model_id"] == filters["model_id"]
            and row["document_version"] == project["document_versions"][filters["model_id"]]
            and row["source_kind"] == filters["source_kind"]
            and row["source_id"] in filters["source_ids"])


def _bound_rows(metadata, dataset):
    reviews, _ = _indices(dataset)
    repeated = {}
    provenance_hashes = {}
    for row in metadata["rows"]:
        original = reviews.get(row["review_id"])
        if original is None or any(row[key] != original[key] for key in (
                "model_id", "document_version", "source_kind", "source_id", "evidence_id")):
            _fail()
        if row["text_sha256"] != hashlib.sha256(original["text"].encode("utf-8")).hexdigest():
            _fail()
        canonical = deepcopy(row)
        canonical["topic_ids"] = sorted(canonical["topic_ids"])
        previous = repeated.setdefault(row["review_id"], canonical)
        if previous != canonical:
            _fail()
        origin = row["date_provenance"]
        if origin is not None:
            # Source bytes are not available here. The digest is an approved
            # source pin; validate the same-source join and consistent pin.
            if origin["source_id"] != original["source_id"]:
                _fail()
            key = (row["source_id"], row["source_kind"], row["model_id"], row["document_version"])
            if provenance_hashes.setdefault(key, origin["source_sha256"]) != origin["source_sha256"]:
                _fail()
        if metadata["classification"]["method"] == "unclassified" and row["classification_status"] != "unclassified":
            _fail()
        _day(row)
    return reviews


def _expected_rows(metadata, filters, project, reviews):
    rows = deepcopy(metadata["rows"])
    for row in rows:
        row["topic_ids"] = sorted(row["topic_ids"])
    scoped = [row for row in rows if _in_scope(row, filters, project)]
    required = {review["id"] for review in reviews.values() if _in_scope(review, filters, project)}
    if {row["review_id"] for row in scoped} != required:
        _fail()  # Omitting an in-scope review must never shrink the denominator.
    start, end = date.fromisoformat(filters["start_date"]), date.fromisoformat(filters["end_date_exclusive"])
    known = [row for row in scoped if _day(row) is not None]
    eligible = [row for row in known if start <= _day(row) < end]
    content_by_key = {}
    for row in scoped:
        if row["dedup_key"] is not None:
            key = (row["model_id"], row["document_version"], row["source_kind"], row["source_id"], row["dedup_key"])
            if content_by_key.setdefault(key, row["text_sha256"]) != row["text_sha256"]:
                _fail()
    unique = {}
    for row in sorted(eligible, key=lambda item: (_day(item), item["review_id"], item["evidence_id"])):
        key = (("review", row["review_id"]) if row["dedup_key"] is None else
               ("dedup", row["model_id"], row["document_version"], row["source_kind"], row["source_id"], row["dedup_key"]))
        if key in unique:
            previous = unique[key]
            if (previous["topic_ids"] != row["topic_ids"]
                    or previous["classification_status"] != row["classification_status"]):
                _fail()
        else:
            unique[key] = row
    values = list(unique.values())
    counts = {
        "input_review_count": len(rows), "excluded_out_of_scope_count": len(rows) - len(scoped),
        "in_scope_review_count": len(scoped), "excluded_undated_count": len(scoped) - len(known),
        "excluded_outside_period_count": len(known) - len(eligible), "duplicate_count": len(eligible) - len(values),
        "eligible_unique_review_count": len(values),
        "unclassified_review_count": sum(row["classification_status"] == "unclassified" for row in values),
    }
    topics = filters["topic_ids"] or sorted({topic for row in scoped for topic in row["topic_ids"]})
    return values, counts, topics


def validate_trend_collection(aggregate, metadata, memberships, project, dataset, dataset_sha256) -> None:
    """Reject a provider's false counts, citations, ranges, or frozen identity."""
    _schema("ReviewTrendAggregate", aggregate)
    _schema("ReviewTrendMetadata", metadata)
    data = _dataset(dataset, dataset_sha256)
    try:
        filters = validate_trend_request(aggregate["filters"], project, data, dataset_sha256)
    except DomainError as error:
        if error.code == "DATASET_MISMATCH":
            raise
        _fail()
    if (metadata["dataset_sha256"] != dataset_sha256
            or metadata["dataset_version"] != data["manifest"]["version"]):
        _fail("DATASET_MISMATCH")
    if metadata["annotation_sha256"] != annotation_digest(metadata):
        _fail("DATASET_MISMATCH")
    if (aggregate["filters"] != filters or aggregate["project_id"] != filters["project_id"]
            or aggregate["aggregate_id"] != trend_identity(filters, metadata, aggregate["aggregation_version"])):
        _fail()
    for field in ("dataset_version", "dataset_sha256", "annotation_version", "annotation_sha256",
                  "classification", "topic_taxonomy_version", "dedup_policy_version"):
        if aggregate[field] != metadata[field]:
            _fail("DATASET_MISMATCH" if field != "classification" else "CONTRACT_MISMATCH")
    reviews = _bound_rows(metadata, data)
    unique, counts, topics = _expected_rows(metadata, filters, project, reviews)
    if aggregate["counts"] != counts or not isinstance(memberships, dict):
        _fail()
    periods = trend_periods(filters)
    buckets = aggregate["buckets"]
    if len(buckets) != len(periods) or len({bucket["bucket_id"] for bucket in buckets}) != len(buckets):
        _fail()
    if set(memberships) != {bucket["bucket_id"] for bucket in buckets}:
        _fail()
    all_seen = set()
    for bucket, period in zip(buckets, periods, strict=True):
        if any(bucket[key] != value for key, value in period.items()):
            _fail()
        start, end = date.fromisoformat(period["period_start"]), date.fromisoformat(period["period_end_exclusive"])
        included = [row for row in unique if start <= _day(row) < end]
        expected_all = {row["evidence_id"] for row in included}
        mapping = memberships[bucket["bucket_id"]]
        if not isinstance(mapping, dict) or set(mapping) != {"__all__", *topics}:
            _fail()
        for ids in mapping.values():
            if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids) or len(ids) != len(set(ids)):
                _fail()
        if (mapping["__all__"] != sorted(expected_all) or all_seen & expected_all
                or bucket["total_reviews"] != len(expected_all)):
            _fail()
        all_seen.update(expected_all)
        topic_rows = bucket["topics"]
        if [row["topic_id"] for row in topic_rows] != topics:
            _fail()
        for topic in topic_rows:
            ids = {row["evidence_id"] for row in included if topic["topic_id"] in row["topic_ids"]}
            denominator = len(expected_all)
            ratio = len(ids) / denominator if denominator else None
            actual_ratio = topic["ratio"]
            if ratio is None:
                if actual_ratio is not None:
                    _fail()
            elif (not isinstance(actual_ratio, (int, float)) or isinstance(actual_ratio, bool)
                  or not math.isclose(actual_ratio, ratio, rel_tol=0, abs_tol=1e-12)):
                _fail()
            preview = sorted(ids)[:50]
            if (mapping[topic["topic_id"]] != sorted(ids) or topic["topic_review_count"] != len(ids)
                    or topic["evidence_count"] != len(ids) or topic["evidence_ids"] != preview
                    or topic["evidence_ids_truncated"] != (len(ids) > 50)):
                _fail()
    if len(all_seen) != counts["eligible_unique_review_count"]:
        _fail()
    if not set(trend_sample_warnings(buckets)).issubset(aggregate["warnings"]):
        _fail()
