"""Read fixed artifacts and independently recheck bytes, membership and replay.

This is author self-verification, not an independent semantic scorer or Gold.
Run only in the authentication-free/network-free Docker validator.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

BASE = "data/research/r8-public-research-20261007/"
DELIVERY = BASE + "d1-d2-01a10600/"


def read(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for relative in ("apps/api/src", "packages/core/src", "packages/contracts/src"):
        sys.path.insert(0, str(args.source / "pm" / relative))
    from lgax_api.review_trends import build_review_trend_collection, canonical_dataset_sha256
    from lgax_api.trend_validation import annotation_digest
    from lgax_contracts import validate

    root = args.artifacts
    summary = read(root / "handoff-summary.json")
    for name, digest in summary["files"].items():
        assert sha((root / name).read_bytes()) == digest, name
    pins = read(root / "source-pins.json")
    assert pins == read(args.source / "source-pins.json")
    for pin in pins:
        assert sha((args.source / pin["kind"] / pin["path"]).read_bytes()) == pin["sha256"]
    records = {row["original_review_id"]: row for row in read(args.source / "data" / (BASE + "records.json"))}
    dev = {key: row for key, row in records.items() if row["split"] == "development"}
    assert len(records) == 238 and len(dev) == 141
    producer_members = read(args.source / "data" / (DELIVERY + "d1-membership.json"))
    partition = read(root / "partition-memberships.json")["original_review_id_memberships"]
    assert partition == {split: sorted(row["original_review_id"] for row in producer_members if row["split"] == split)
                         for split in sorted({row["split"] for row in producer_members})}
    assert len(set(key for ids in partition.values() for key in ids)) == 238
    assert {key for ids in partition.values() for key in ids} == set(records)
    assert partition["development"] == sorted(dev)
    assert {split: len(ids) for split, ids in partition.items()} == summary["sample"]["partition_counts"]
    assert sum(len(ids) for split, ids in partition.items() if split != "development") == 97
    incoming = {}
    for group in ("fridge", "dishwasher", "microwave"):
        bundle = read(args.source / "data" / (DELIVERY + f"agent-input/{group}/research-bundle.json"))
        for source in bundle["sources"]:
            if source["source_type"] == "review":
                key = source["metadata"]["original_review_id"]
                assert key not in incoming
                incoming[key] = source
    copied = read(root / "development-sources.json")["sources"]
    copied_index = {source["metadata"]["original_review_id"]: source for source in copied}
    assert len(copied) == len(copied_index) == 141 and copied_index == incoming
    assert set(copied_index) == set(dev)
    assert all(source["purchased_model"] is None and source["published_at"] is None for source in copied)
    assert all(source["metadata"]["split"] == "development" for source in copied)

    draft = read(root / "annotation.draft.json")
    assert draft["status"] == "draft" and draft["pm_approved"] is False and draft["gold"] is False
    assert draft["annotation_version"] == summary["annotation_version"]
    rows = draft["rows"]
    assert len(rows) == len({row["original_review_id"] for row in rows}) == 141
    assert {row["original_review_id"] for row in rows} == set(dev)
    quotes = 0
    for row in rows:
        original, source = dev[row["original_review_id"]], incoming[row["original_review_id"]]
        assert row["status"] == "draft" and not row["approved"]
        assert row["record_review_id"] == original.get("review_id")
        assert row["source_id"] == source["source_id"]
        assert row["source_url"] == source["url"] and row["source_locator"] == source["locator"]
        assert row["text_sha256"] == sha(source["text"].encode("utf-8"))
        assert row["research_source_sha256"] == sha(canonical(source))
        assert row["actual_purchased_model_id"] is None and row["published_at"] is None
        assert row["input_hold_reasons"] == original["input_hold_reasons"]
        assert row["reference_document_version"] == source["document_version"]
        assert row["record_document_version"] == original.get("document_version")
        assert row["record_original_text_sha256"] == original.get("original_text_sha256")
        assert row["raw_capture_verified_here"] is False
        for aspect in row["aspects"]:
            span = aspect["text_range"]
            assert span["end_exclusive"] is True and span["unit"] == "unicode_codepoint"
            assert 0 <= span["start"] < span["end"] <= len(source["text"])
            assert source["text"][span["start"]:span["end"]] == aspect["quote"]
            assert sha(aspect["quote"].encode("utf-8")) == aspect["quote_sha256"]
            quotes += 1
    membership = read(root / "draft-memberships.json")
    assert membership["selected_original_review_ids"] == sorted(dev)
    assert membership["overall_opinion_counts"] == dict(Counter(row["overall_opinion"] for row in rows))
    assert sum(membership["overall_opinion_counts"].values()) == 141
    for topic, polarities in membership["topic_polarity_memberships"].items():
        for polarity, ids in polarities.items():
            assert ids == sorted({row["original_review_id"] for row in rows
                                 if any(a["topic_id"] == topic and a["polarity"] == polarity for a in row["aspects"])})
    assert all(ratio is None for ratio in membership["topic_ratios"].values())
    row_index = {row["original_review_id"]: row for row in rows}
    for pair in draft["counterexample_pairs"]:
        left, right = [row_index[key] for key in pair["original_review_ids"]]
        assert left["product_group"] == right["product_group"]
        assert pair["topic_id"] in left["topic_ids"] and pair["topic_id"] in right["topic_ids"]
        assert pair["causal_or_same_sku_conclusion"] is False
        if pair["page_relation"] == "same_displayed_page_only":
            assert left["displayed_page_model"] == right["displayed_page_model"]
        else:
            assert left["displayed_page_model"] != right["displayed_page_model"]
    dataset = read(root / "projection.date-only.dataset.json")
    sidecar = read(root / "date-only.metadata.json")
    assert sidecar["dataset_sha256"] == canonical_dataset_sha256(dataset)
    assert sidecar["annotation_sha256"] == annotation_digest(sidecar)
    validate("ReviewTrendMetadata", sidecar)
    assert len(sidecar["rows"]) == 141
    assert all(row["topic_ids"] == [] and row["classification_status"] == "unclassified"
               and row["published_at"] is None and row["date_precision"] == "unknown"
               and row["date_provenance"] is None for row in sidecar["rows"])
    queries = read(root / "empty-collector-checks.json")
    assert queries["draft_topic_annotations_consumed"] is False
    assert queries["display_as_monthly_or_seasonal_trend"] is False
    assert len(queries["queries"]) == 36
    scope_totals = {"month": 0, "season": 0}
    for query in queries["queries"]:
        expected = build_review_trend_collection(query["project"], dataset, query["aggregate"]["filters"], sidecar)
        assert expected.aggregate == query["aggregate"] and expected.memberships == query["memberships"]
        validate("ReviewTrendAggregate", expected.aggregate)
        counts = expected.aggregate["counts"]
        assert counts["input_review_count"] == 141
        assert counts["in_scope_review_count"] == counts["excluded_undated_count"]
        scope_totals[query["aggregate"]["filters"]["granularity"]] += counts["in_scope_review_count"]
        for bucket in expected.aggregate["buckets"]:
            assert bucket["total_reviews"] == 0
            assert all(topic["ratio"] is None for topic in bucket["topics"])
    assert scope_totals == {"month": 141, "season": 141}
    assert summary["sample"]["ratio"] is None
    assert summary["sample"]["development_unknown_publication_date_count"] == 141
    report = {"status": "PASS", "source_pins_checked": len(pins), "development_rows": 141,
        "nondevelopment_excluded": 97, "quotes": quotes, "counterexample_pairs": len(draft["counterexample_pairs"]),
        "existing_collector_replays": 36, "unknown_date_exclusion_per_granularity": scope_totals,
        "all_dated_memberships_empty": True, "all_ratios_null": True,
        "annotation_file_sha256": sha((root / "annotation.draft.json").read_bytes()),
        "source_snapshot_file_sha256": sha((root / "development-sources.json").read_bytes()),
        "semantic_gold_or_independent_evaluation": False, "runtime_acceptance": False,
        "scope": "author self-verification; source bytes/binding/exclusions/deterministic output replay"}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
