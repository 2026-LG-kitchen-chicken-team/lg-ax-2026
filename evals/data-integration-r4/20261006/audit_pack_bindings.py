"""Compare three pinned public synthetic packs without deploying or generating."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from lgax_api.review_trends import build_review_trend_collection, canonical_dataset_sha256
from lgax_api.trend_validation import annotation_digest, validate_trend_collection
from lgax_core.errors import DomainError
from lgax_core.retrieval import GroundedDemoStore

ROOT = Path(__file__).resolve().parents[3]
DATA = "data/research/DATA-owner-followup-20261006-01a1100e"
KST = timezone(timedelta(hours=9))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def local_day(row):
    if row["published_at"] is None:
        return None
    if row["date_precision"] == "day":
        return date.fromisoformat(row["published_at"])
    return datetime.fromisoformat(row["published_at"]).astimezone(KST).date()


def verify_source(dataset, metadata, source_raw, source_mode):
    """Read the pinned date artifact, not only the sidecar's declared hash."""
    reviews = {r["id"]: r for r in dataset["reviews"]}
    sources = json.loads(source_raw)["rows"] if source_raw else []
    sections = {r["id"]: r for r in sources} if source_mode == "section" else {}
    for row in metadata["rows"]:
        original = reviews.get(row["review_id"])
        if original is None:
            raise ValueError("unknown review id")
        expected = {"evidence_id": original["evidence_id"], "model_id": original["model_id"],
                    "document_version": original["document_version"], "source_id": original["source_id"],
                    "source_kind": original["source_kind"], "text_sha256": sha(original["text"].encode())}
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("review text/id/model/version/source binding mismatch")
        if row["published_at"] is None:
            if row["date_provenance"] is not None or row["date_precision"] != "unknown":
                raise ValueError("unknown date must have no provenance")
            continue
        provenance = row["date_provenance"]
        if not source_raw or provenance["source_sha256"] != sha(source_raw):
            raise ValueError("date artifact bytes do not match provenance")
        if provenance["source_id"] != original["source_id"]:
            raise ValueError("date provenance source mismatch")
        if source_mode == "section":
            source = sections[provenance["locator"]["section"]]
            if source["id"] != row["review_id"] or source["text"] != original["text"]:
                raise ValueError("date source section/text mismatch")
        else:
            source = sources[provenance["locator"]["row"] - 1]
            if source["review_id"] != row["review_id"]:
                raise ValueError("date source row mismatch")
        if (source["published_at"] != row["published_at"]
                or source["date_precision"] != row["date_precision"]):
            raise ValueError("date source value/precision mismatch")


def run(pm_ref, output):
    output.mkdir(parents=True, exist_ok=False)
    code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    pm = subprocess.check_output(["git", "rev-parse", pm_ref + "^{commit}"], cwd=ROOT, text=True).strip()
    specs = [
        ("original", code, "data/demo/dataset.json",
         "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json", None, None),
        ("pm", pm, "data/demo/review-trends-dated/dataset.json",
         "data/demo/review-trends-dated/annotation.candidate.json",
         "data/demo/review-trends-dated/date-schedule.json", "row"),
        ("data", code, DATA + "/dataset.synthetic-dated-demo.v1.json",
         DATA + "/annotation.synthetic-dated-demo.v1.json",
         DATA + "/source.synthetic-dated-demo.v1.json", "section"),
    ]
    packs = {}
    for name, commit, dataset_path, annotation_path, source_path, mode in specs:
        dataset_raw = git_bytes(commit, dataset_path)
        metadata_raw = git_bytes(commit, annotation_path)
        source_raw = git_bytes(commit, source_path) if source_path else None
        packs[name] = {"dataset": json.loads(dataset_raw), "metadata": json.loads(metadata_raw),
                       "source_raw": source_raw, "source_mode": mode, "commit": commit,
                       "dataset_path": dataset_path, "annotation_path": annotation_path,
                       "date_source_path": source_path, "dataset_bytes_sha256": sha(dataset_raw),
                       "annotation_bytes_sha256": sha(metadata_raw),
                       "date_source_bytes_sha256": sha(source_raw) if source_raw else None}
    original = packs["original"]["dataset"]
    original_metadata = {r["review_id"]: r for r in packs["original"]["metadata"]["rows"]}
    csv_raw = git_bytes(code, "data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv")
    reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig"), newline=""))
    csv_rows = list(reader)
    assert len(reader.fieldnames) == 8 and len(csv_rows) == 36
    assert sha(csv_raw) == "3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9"
    assert packs["original"]["dataset_bytes_sha256"] == "97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0"
    csv_by_id = {r["id"]: r for r in csv_rows}
    assert all(csv_by_id[r["id"]]["text"] == r["text"] for r in original["reviews"])
    queries, rejections, bindings, searches = [], [], [], []

    def rejected(name, operation):
        try:
            operation()
        except (ValueError, DomainError, KeyError) as error:
            rejections.append({"case": name, "rejected": True, "error_type": type(error).__name__,
                               "message": str(error)[:200]})
        else:
            raise AssertionError("not rejected: " + name)

    def collect(pack, filters=None, metadata=None):
        query = filters or pack["filters"]
        meta = metadata or pack["metadata"]
        collection = build_review_trend_collection(pack["project"], pack["dataset"], query, meta)
        validate_trend_collection(collection.aggregate, collection.metadata, collection.memberships,
                                  pack["project"], pack["dataset"], meta["dataset_sha256"])
        return collection

    for name, pack in packs.items():
        dataset, metadata = pack["dataset"], pack["metadata"]
        assert len(dataset["reviews"]) == len(metadata["rows"]) == 36
        assert metadata["dataset_sha256"] == canonical_dataset_sha256(dataset)
        assert metadata["annotation_sha256"] == annotation_digest(metadata)
        verify_source(dataset, metadata, pack["source_raw"], pack["source_mode"])
        store = GroundedDemoStore(dataset)
        rows = {r["review_id"]: r for r in metadata["rows"]}
        for old, review in zip(original["reviews"], dataset["reviews"], strict=True):
            for key in ("text", "model_id", "document_version", "source_kind"):
                assert review[key] == old[key]
            evidence = store.get_evidence(review["evidence_id"])["data"]["evidence"]
            assert evidence["text"] == old["text"] and evidence["locator"] == review["locator"]
            assert sorted(rows[review["id"]]["topic_ids"]) == sorted(original_metadata[old["id"]]["topic_ids"])
            bindings.append({"pack": name, "original_review_id": old["id"],
                             "review_id": review["id"], "evidence_id": review["evidence_id"],
                             "model_id": review["model_id"], "document_version": review["document_version"],
                             "source_id": review["source_id"], "locator": review["locator"],
                             "text_sha256": sha(review["text"].encode()),
                             "published_at": rows[review["id"]]["published_at"],
                             "local_day_kst": str(local_day(rows[review["id"]])) if local_day(rows[review["id"]]) else None,
                             "topic_ids": rows[review["id"]]["topic_ids"]})
        version = dataset["manifest"]["version"]
        source_id = dataset["reviews"][0]["source_id"]
        request = json.loads(git_bytes(code, "data/demo/planning_requests.json"))[0]
        request.update(model_ids=["FRIDGE-A"], dataset_version=version)
        pack["project"] = {"project": {"id": "data-r4-pack-binding", "name": "DATA R4 pack binding",
                                       "request": request, "status": "draft", "dataset_version": version},
                           "owner_id": "data-r4-owner", "created_at": "2026-10-06T00:00:00Z",
                           "dataset_sha256": metadata["dataset_sha256"],
                           "document_versions": {"FRIDGE-A": "1.0"}}
        pack["filters"] = {"project_id": "data-r4-pack-binding", "model_id": "FRIDGE-A",
                           "document_version": "1.0", "source_ids": [source_id], "dataset_version": version,
                           "start_date": "2026-10-01", "end_date_exclusive": "2026-11-01",
                           "granularity": "month", "topic_ids": ["cleaning"], "source_kind": "synthetic",
                           "timezone": "Asia/Seoul"}
        # document_version is fixed by the project, not a public TrendQuery field.
        pack["filters"].pop("document_version")
        periods = {"october": {}, "empty": {"start_date": "2026-01-01", "end_date_exclusive": "2026-02-01"},
                   "winter": {"start_date": "2026-12-01", "end_date_exclusive": "2027-03-01", "granularity": "season"},
                   "december": {"start_date": "2026-12-01", "end_date_exclusive": "2027-01-01"},
                   "january": {"start_date": "2027-01-01", "end_date_exclusive": "2027-02-01"}}
        for period, change in periods.items():
            filters = {**pack["filters"], **change}
            collection = collect(pack, filters)
            assert collection == collect(pack, filters)
            start, end = date.fromisoformat(filters["start_date"]), date.fromisoformat(filters["end_date_exclusive"])
            eligible = [row for row in metadata["rows"] if row["model_id"] == "FRIDGE-A"
                        and local_day(row) is not None and start <= local_day(row) < end]
            ids = sorted({r["evidence_id"] for r in eligible})
            cleaning = sorted({r["evidence_id"] for r in eligible if "cleaning" in r["topic_ids"]})
            assert collection.aggregate["counts"]["eligible_unique_review_count"] == len(ids)
            assert sum(b["total_reviews"] for b in collection.aggregate["buckets"]) == len(ids)
            assert sorted(e for m in collection.memberships.values() for e in m["cleaning"]) == cleaning
            for bucket in collection.aggregate["buckets"]:
                topic = bucket["topics"][0]
                expected_ratio = topic["topic_review_count"] / bucket["total_reviews"] if bucket["total_reviews"] else None
                assert topic["ratio"] == expected_ratio
                for evidence_id in topic["evidence_ids"]:
                    assert store.get_evidence(evidence_id)["data"]["evidence"]["model_id"] == "FRIDGE-A"
            if period == "empty":
                assert not ids and all(b["topics"][0]["ratio"] is None for b in collection.aggregate["buckets"])
            entry = {"pack": name, "period": period, "query": filters,
                     "aggregate": collection.aggregate, "memberships": collection.memberships,
                     "independent_denominator": len(ids), "independent_cleaning_count": len(cleaning)}
            queries.append(entry)
            if period == "october":
                pack["october"] = entry
        result = store.search_ranked_evidence("선반 청소", model_id="FRIDGE-A", document_version="1.0",
                                             dataset_version=version, source_kind="synthetic")
        assert result["items"] and result["search_method"] == "bm25"
        assert all(i["evidence"]["model_id"] == "FRIDGE-A" and i["evidence"]["document_version"] == "1.0"
                   for i in result["items"])
        assert result == store.search_ranked_evidence("선반 청소", model_id="FRIDGE-A", document_version="1.0",
                                                     dataset_version=version, source_kind="synthetic")
        rejected(name + ":search-wrong-model", lambda store=store, version=version:
                 store.search_ranked_evidence("선반 청소", model_id="WRONG-MODEL",
                                             document_version="1.0", dataset_version=version))
        rejected(name + ":search-wrong-version", lambda store=store, version=version:
                 store.search_ranked_evidence("선반 청소", model_id="FRIDGE-A",
                                             document_version="WRONG-VERSION", dataset_version=version))
        searches.append({"pack": name, "result": result, "replay_equal": True,
                         "wrong_model_rejected": True, "wrong_version_rejected": True, "public_method_changed": False})
        for field, value in [("review_id", "SWAPPED-ID"), ("evidence_id", "SWAPPED-EVIDENCE"),
                             ("model_id", "OTHER-MODEL"), ("document_version", "OTHER-EDITION"),
                             ("source_id", "OTHER-SOURCE"), ("text_sha256", "0" * 64)]:
            changed = deepcopy(metadata)
            changed["rows"][0][field] = value
            changed["annotation_sha256"] = annotation_digest(changed)
            rejected(name + ":changed-" + field,
                     lambda changed=changed, pack=pack: collect(pack, metadata=changed))
        if pack["source_raw"]:
            changed = deepcopy(metadata)
            for row in changed["rows"]:
                if row["date_provenance"]:
                    row["date_provenance"]["source_sha256"] = "0" * 64
            changed["annotation_sha256"] = annotation_digest(changed)
            rejected(name + ":all-date-hashes-swapped",
                     lambda changed=changed, dataset=dataset, pack=pack: verify_source(
                         dataset, changed, pack["source_raw"], pack["source_mode"]))
            eligible_id = pack["october"]["memberships"]["MONTH-2026-10"]["__all__"][0]
            duplicate = deepcopy(metadata)
            duplicate["rows"].append(deepcopy(next(r for r in metadata["rows"] if r["evidence_id"] == eligible_id)))
            duplicate["annotation_sha256"] = annotation_digest(duplicate)
            repeated = collect(pack, metadata=duplicate)
            assert repeated.memberships == pack["october"]["memberships"]
            assert repeated.aggregate["counts"]["duplicate_count"] == 1
            assert repeated.aggregate["counts"]["eligible_unique_review_count"] == pack["october"]["independent_denominator"]
            duplicate["rows"][-1]["topic_ids"] = ["conflicting-topic"]
            duplicate["annotation_sha256"] = annotation_digest(duplicate)
            rejected(name + ":conflicting-duplicate",
                     lambda pack=pack, duplicate=duplicate: collect(pack, metadata=duplicate))

    for left, pack in packs.items():
        for right, other in packs.items():
            if left == right:
                continue
            assert pack["metadata"]["dataset_version"] != other["metadata"]["dataset_version"]
            assert not ({r["id"] for r in pack["dataset"]["reviews"]} & {r["id"] for r in other["dataset"]["reviews"]})
            rejected(left + ":sidecar-from-" + right,
                     lambda pack=pack, other=other: collect(pack, metadata=other["metadata"]))
            store = GroundedDemoStore(pack["dataset"])
            rejected(left + ":evidence-from-" + right,
                     lambda store=store, other=other: store.get_evidence(other["dataset"]["reviews"][0]["evidence_id"]))
    assert [packs[n]["october"]["independent_denominator"] for n in packs] == [0, 3, 4]
    assert [packs[n]["october"]["independent_cleaning_count"] for n in packs] == [0, 1, 1]
    assert math.isclose(packs["pm"]["october"]["aggregate"]["buckets"][0]["topics"][0]["ratio"], 1 / 3)
    assert packs["data"]["october"]["aggregate"]["buckets"][0]["topics"][0]["ratio"] == 0.25
    summary = {"observed_at": datetime.now(KST).isoformat(), "code_commit": code, "pm_input_commit": pm,
               "pm_input_pr": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/188",
               "original_csv_sha256": sha(csv_raw), "original_csv_rows": 36, "original_csv_columns": 8,
               "exact_text_model_version_bindings": len(bindings), "queries_checked": len(queries),
               "rejections_checked": len(rejections), "model_calls": 0, "production_injected": False,
               "classification_status": "candidate preview; mention counts, no complaint polarity",
               "public_bm25_contract_changed": False, "independent_evaluation": False, "all_passed": True,
               "packs": [{k: pack[k] for k in ("commit", "dataset_path", "annotation_path", "date_source_path",
                           "dataset_bytes_sha256", "annotation_bytes_sha256", "date_source_bytes_sha256")}
                         | {"name": name, "dataset_version": pack["metadata"]["dataset_version"],
                            "dataset_canonical_sha256": pack["metadata"]["dataset_sha256"],
                            "annotation_canonical_sha256": pack["metadata"]["annotation_sha256"],
                            "dated_total": sum(r["published_at"] is not None for r in pack["metadata"]["rows"]),
                            "unknown_total": sum(r["published_at"] is None for r in pack["metadata"]["rows"]),
                            "source_ids": sorted({r["source_id"] for r in pack["metadata"]["rows"]}),
                            "october_query": pack["filters"], "october_counts": pack["october"]["aggregate"]["counts"]}
                         for name, pack in packs.items()]}
    assert [p["dated_total"] for p in summary["packs"]] == [0, 31, 9]
    write(output / "pack-audit.json", summary)
    write(output / "review-bindings.json", bindings)
    write(output / "queries.json", queries)
    write(output / "rejections.json", rejections)
    write(output / "searches.json", searches)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pm-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.pm_ref, args.output)
    print(json.dumps({k: result[k] for k in ("code_commit", "pm_input_commit", "exact_text_model_version_bindings",
                                           "queries_checked", "rejections_checked", "all_passed", "model_calls")}))
