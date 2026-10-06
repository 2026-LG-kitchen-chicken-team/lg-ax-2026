"""Compare captured trend responses with pinned DATA inputs; never fetch or deploy."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[1]
for folder in ("apps/api/src", "packages/core/src", "packages/contracts/src"):
    sys.path.insert(0, str(ROOT / folder))

from lgax_api.review_trends import (
    build_review_trend_collection,
    canonical_dataset_sha256,
)
from lgax_api.trend_validation import validate_trend_request
from lgax_core.errors import DomainError


def _same(left, right):
    # JSON distinguishes true/1 and preserves null; Python dict equality does not.
    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    return canonical(left) == canonical(right)


def compare_snapshot(snapshot, dataset, annotation, *, date_source_sha256=None):
    """Compare one query, including saved denominator membership and original text.

    A matching capture is not proof of its operating origin or PM approval.
    Missing capture fields stay unconfirmed rather than becoming empty results.
    """
    report = {"status": "unconfirmed", "mismatches": [], "unconfirmed": [],
              "operating_origin_verified": False, "PM_approval_verified": False,
              "new_model_calls": 0, "runtime_mutations": 0}
    bad, missing = report["mismatches"], report["unconfirmed"]
    if not isinstance(snapshot, dict):
        bad.append("snapshot:INVALID_OBJECT")
        return {**report, "status": "mismatch"}
    if not isinstance(snapshot.get("project"), dict) or not isinstance(snapshot.get("filters"), dict):
        missing.append("project_or_filters")
        return report
    try:
        query = validate_trend_request(snapshot["filters"], snapshot["project"], dataset,
                                       canonical_dataset_sha256(dataset))
        expected = build_review_trend_collection(snapshot["project"], dataset, query, annotation)
    except (DomainError, ValidationError, ValueError, KeyError, TypeError) as error:
        # DomainError/contract errors can include source text; record only the class.
        bad.append("fixed_scope:" + type(error).__name__)
        return {**report, "status": "mismatch"}
    report.update(expected_aggregate_id=expected.aggregate["aggregate_id"],
                  dataset_sha256=expected.aggregate["dataset_sha256"],
                  annotation_sha256=expected.aggregate["annotation_sha256"])

    date_hashes = {row["date_provenance"]["source_sha256"] for row in annotation["rows"]
                   if row.get("date_provenance") is not None}
    if date_hashes:
        if date_source_sha256 is None:
            missing.append("date_source_file_sha256")
        elif date_hashes != {date_source_sha256}:
            bad.append("date_source_file_sha256:MISMATCH")

    for key in ("api_aggregate", "mcp_aggregate", "restart_aggregate"):
        observed = snapshot.get(key)
        if observed is None:
            missing.append(key)
        elif not _same(observed, expected.aggregate):
            bad.append(key + ":MISMATCH")

    sources = {row["id"]: row for row in dataset["evidence"]}
    all_ids = {identifier for group in expected.memberships.values()
               for identifiers in group.values() for identifier in identifiers}
    frozen = {"aggregate": expected.aggregate, "metadata": expected.metadata,
              "memberships": expected.memberships,
              "evidence": {identifier: sources[identifier] for identifier in sorted(all_ids)}}
    for key in ("stored_snapshot", "restart_snapshot"):
        observed = snapshot.get(key)
        if observed is None:
            missing.append(key)
        elif not isinstance(observed, dict):
            bad.append(key + ":INVALID_OBJECT")
        else:
            for field, value in frozen.items():
                if field not in observed:
                    missing.append(key + "." + field)
                elif not _same(observed[field], value):
                    bad.append(key + "." + field + ":MISMATCH")
    _check_pages(snapshot.get("evidence_pages"), expected, sources, bad, missing)
    report["status"] = "mismatch" if bad else "unconfirmed" if missing else "match"
    return report


def _check_pages(pages, expected, sources, bad, missing):
    if pages is None:
        missing.append("evidence_pages")
        return
    if not isinstance(pages, list):
        bad.append("evidence_pages:INVALID_ARRAY")
        return
    groups = {(bucket, topic): [] for bucket, mapping in expected.memberships.items()
              for topic in mapping if topic != "__all__"}
    for index, page in enumerate(pages):
        prefix = f"evidence_pages[{index}]"
        if not isinstance(page, dict):
            bad.append(prefix + ":INVALID_OBJECT")
            continue
        if not isinstance(page.get("bucket_id"), str) or not isinstance(page.get("topic_id"), str):
            bad.append(prefix + ":INVALID_GROUP")
            continue
        key = (page["bucket_id"], page["topic_id"])
        if key not in groups:
            bad.append(prefix + ":UNREQUESTED_GROUP")
            continue
        if (page.get("project_id") != expected.aggregate["project_id"]
                or page.get("aggregate_id") != expected.aggregate["aggregate_id"]):
            bad.append(prefix + ":WRONG_PROJECT_OR_AGGREGATE")
        numeric = ("offset", "limit", "total")
        if (any(type(page.get(field)) is not int for field in numeric)
                or page["offset"] < 0 or not 1 <= page["limit"] <= 50 or page["total"] < 0
                or "next_offset" not in page or not isinstance(page.get("evidence"), list)):
            bad.append(prefix + ":INVALID_PAGE")
            continue
        groups[key].append((index, page))
    for (bucket, topic), captured in groups.items():
        label = f"pages.{bucket}.{topic}"
        ids = expected.memberships[bucket][topic]
        if not captured:
            missing.append(label)
            continue
        offset = 0
        seen_offsets = set()
        for index, page in sorted(captured, key=lambda pair: pair[1]["offset"]):
            prefix = f"evidence_pages[{index}]"
            if page["offset"] in seen_offsets:
                bad.append(prefix + ":DUPLICATE_PAGE_OFFSET")
            seen_offsets.add(page["offset"])
            if page["offset"] != offset or page["total"] != len(ids):
                bad.append(prefix + ":PAGE_GAP_OVERLAP_OR_TOTAL")
            selected = ids[page["offset"]:page["offset"] + page["limit"]]
            originals = [sources[identifier] for identifier in selected]
            if not _same(page["evidence"], originals):
                bad.append(prefix + ":ORIGINAL_TEXT_OR_SCOPE")
            next_offset = page["offset"] + page["limit"]
            expected_next = next_offset if next_offset < len(ids) else None
            if not _same(page["next_offset"], expected_next):
                bad.append(prefix + ":NEXT_OFFSET")
            offset = page["offset"] + len(selected)
        if offset != len(ids):
            missing.append(label + ":INCOMPLETE")


def _read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError("Require a regular JSON file up to 10 MB")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("Nonfinite JSON value")
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=constant), hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("snapshot", "dataset", "annotation"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--date-source", type=Path)
    args = parser.parse_args(argv)
    try:
        values, pins = {}, {}
        for key in ("snapshot", "dataset", "annotation"):
            values[key], pins[key + "_file_sha256"] = _read_json(getattr(args, key))
        date_hash = None
        if args.date_source is not None:
            _, date_hash = _read_json(args.date_source)
            pins["date_source_file_sha256"] = date_hash
        report = compare_snapshot(values["snapshot"], values["dataset"], values["annotation"],
                                  date_source_sha256=date_hash)
        report["file_pins"] = pins
    except (OSError, ValueError, TypeError, KeyError) as error:
        report = {"status": "mismatch", "mismatches": ["input:" + type(error).__name__],
                  "operating_origin_verified": False, "PM_approval_verified": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {"match": 0, "mismatch": 1, "unconfirmed": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
