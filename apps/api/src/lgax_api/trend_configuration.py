"""Explicit server-side trend wiring; requests never select sidecars or approve topics."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from lgax_contracts import validate
from lgax_core.store import DemoStore, default_store

from .review_trends import _bound_rows, canonical_dataset_sha256, create_review_trend_collector
from .trend_validation import annotation_digest
from .workspace_trends import TrendCollector

CANDIDATE_WARNING = "리뷰별 주제 연결은 합성 시연 후보입니다. 불만률이나 승인된 고객 분류가 아닙니다."
SYNTHETIC_WARNING = "합성 자료입니다. 날짜가 있는 경우에도 시연값이며 실제 고객 게시일·판매량·시장 수요의 증거가 아닙니다."


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate key in server-side JSON")
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError("Non-finite JSON values are not permitted")


def _read_json(path: Path) -> tuple[dict, bytes]:
    raw = Path(path).read_bytes()
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                       parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("Server-side JSON must be an object")
    return value, raw


def load_synthetic_store(dataset_path: Path | None = None) -> DemoStore:
    """The public/private demo path accepts only DemoStore's synthetic dataset policy."""
    return default_store() if dataset_path is None else DemoStore(_read_json(dataset_path)[0])


@dataclass(frozen=True)
class TrendRuntime:
    evidence_store: DemoStore
    collector: TrendCollector | None
    metadata_file_sha256: str | None


def load_trend_runtime(*, dataset_path: Path | None = None, metadata_path: Path | None = None,
                       metadata_sha256: str | None = None,
                       allow_candidate: bool = False) -> TrendRuntime:
    """Pin operator-selected file bytes before DB creation or serving requests.

    Candidate topic annotations are an explicit synthetic preview, never approval
    of customer data. A filename/digest is configuration, not a PM review receipt.
    Unknown source dates remain null and are excluded by the DATA collector.
    """
    if (metadata_path is None) != (metadata_sha256 is None):
        raise ValueError("A sidecar path and its exact file SHA256 are required together")
    if metadata_path is None:
        if allow_candidate:
            raise ValueError("Candidate preview requires an explicit pinned sidecar")
        return TrendRuntime(load_synthetic_store(dataset_path), None, None)
    if not isinstance(metadata_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", metadata_sha256):
        raise ValueError("The sidecar file SHA256 must contain 64 lowercase hexadecimal characters")
    metadata, raw = _read_json(metadata_path)
    if hashlib.sha256(raw).hexdigest() != metadata_sha256:
        raise ValueError("Sidecar file SHA256 mismatch")
    validate("ReviewTrendMetadata", metadata)
    store = load_synthetic_store(dataset_path)
    dataset = store.bootstrap()["data"]
    if (metadata["dataset_version"] != dataset["manifest"]["version"]
            or metadata["dataset_sha256"] != canonical_dataset_sha256(dataset)):
        raise ValueError("Sidecar dataset version/hash mismatch")
    if metadata["annotation_sha256"] != annotation_digest(metadata):
        raise ValueError("Sidecar annotation hash mismatch")
    reviews, rows = _bound_rows(dataset, metadata)
    if {row["review_id"] for row in rows} != set(reviews):
        raise ValueError("The pinned sidecar must cover every canonical review")
    candidate = any("candidate" in metadata[key].casefold()
                    for key in ("annotation_version", "topic_taxonomy_version"))
    if candidate:
        if not allow_candidate:
            raise ValueError("Candidate topic annotations require explicit synthetic preview")
        if any(row["source_kind"] != "synthetic" for row in rows):
            raise ValueError("Candidate annotations cannot be enabled for customer/source data")
    base_collector = create_review_trend_collector(metadata)

    def collect(project, fixed_dataset, filters):
        result = base_collector(project, fixed_dataset, filters)
        if filters["source_kind"] == "synthetic":
            result.aggregate["warnings"].append(SYNTHETIC_WARNING)
        if candidate:
            result.aggregate["warnings"].append(CANDIDATE_WARNING)
        return result

    return TrendRuntime(store, collect, metadata_sha256)
