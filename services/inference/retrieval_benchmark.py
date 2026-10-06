"""Same-input development comparison; never launches dense/reranker models.

BM25 is measured here. Optional externally supplied response artifacts must pin
the exact cases, catalog, query/scope, model/revision/config and measurements.
Missing artifacts remain null. Development labels are not independent answers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from lgax_core.evidence_catalog import EvidenceCatalog
from lgax_core.retrieval import TOKENIZER_VERSION, bm25_search


def fingerprint(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def scope(case):
    return {key: case[key] for key in ("model_id", "document_version", "dataset_version", "source_kind")}


def metrics(cases, rankings, k):
    recalls, reciprocal, normalized = [], [], []
    for case in cases:
        relevant = set(case["relevant_evidence_ids"])
        if not relevant:
            continue
        ranked = rankings[case["case_id"]][:k]
        hits = [index + 1 for index, eid in enumerate(ranked) if eid in relevant]
        recalls.append(len(hits) / len(relevant))
        reciprocal.append(1 / hits[0] if hits else 0.0)
        dcg = sum(1 / math.log2(position + 1) for position in hits)
        ideal = sum(1 / math.log2(position + 1) for position in range(1, min(k, len(relevant)) + 1))
        normalized.append(dcg / ideal)
    return {"labelled_cases": len(recalls), "recall_at_k": sum(recalls) / len(recalls) if recalls else None,
            "mrr_at_k": sum(reciprocal) / len(reciprocal) if reciprocal else None,
            "ndcg_at_k": sum(normalized) / len(normalized) if normalized else None,
            "empty_query_results": sum(not ranked for ranked in rankings.values())}


def compare_retrievers(catalog, case_pack, *, responses=(), k=3):
    if (case_pack.get("artifact_kind") != "development_retrieval_cases"
            or case_pack.get("development_only") is not True
            or case_pack.get("independent_evaluation") is not False):
        raise ValueError("Explicit development cases required; heldout answers are not accepted")
    cases = case_pack["cases"]
    if type(k) is not int or not 1 <= k <= 50 or not 1 <= len(cases) <= 1000:
        raise ValueError("Bounded cases and top-k required")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case ID")
    for case in cases:
        selected_ids = {item["id"] for item in catalog.select(**scope(case))}
        if (len(case["relevant_evidence_ids"]) != len(set(case["relevant_evidence_ids"]))
                or not set(case["relevant_evidence_ids"]) <= selected_ids):
            raise ValueError("Relevant IDs must belong to the same approved case scope")
    input_sha256 = fingerprint(case_pack)
    catalog_sha256 = fingerprint(catalog.select())
    rankings, measurements = {}, []
    for case in cases:
        started = time.perf_counter()
        result = bm25_search(catalog, case["query"], **scope(case), limit=k)
        elapsed_ms = (time.perf_counter() - started) * 1000
        rankings[case["case_id"]] = [match["evidence"]["id"] for match in result["items"]]
        measurements.append({"case_id": case["case_id"], "query": case["query"], "filters": scope(case),
                             "latency_ms": elapsed_ms, "model_calls": 0,
                             "ranked_evidence_ids": rankings[case["case_id"]]})
    results = [{"method": "bm25", "execution_kind": "measured_here_cpu", "model": None, "revision": None,
                "config": {"k1": 1.2, "b": 0.75, "tokenizer_version": TOKENIZER_VERSION},
                "input_sha256": input_sha256, "catalog_sha256": catalog_sha256,
                "model_calls": 0, "latency_ms": sum(m["latency_ms"] for m in measurements),
                "metrics": metrics(cases, rankings, k), "responses": measurements}]
    received = {}
    for artifact in responses:
        method = artifact.get("method")
        if method not in {"bge-m3", "reranker"} or method in received:
            raise ValueError("Unique supplied BGE-M3/reranker artifacts required")
        if (artifact.get("input_sha256") != input_sha256 or artifact.get("catalog_sha256") != catalog_sha256
                or not isinstance(artifact.get("model"), str) or not artifact["model"].strip()
                or not isinstance(artifact.get("revision"), str) or not artifact["revision"].strip()
                or not isinstance(artifact.get("config"), dict)
                or type(artifact.get("model_calls")) is not int or artifact["model_calls"] <= 0
                or type(artifact.get("latency_ms")) not in (int, float)
                or not math.isfinite(artifact["latency_ms"]) or artifact["latency_ms"] < 0):
            raise ValueError("Supplied execution needs identical inputs/catalog and pinned model measurements")
        records = artifact.get("responses", [])
        if len(records) != len(cases) or len({r["case_id"] for r in records}) != len(records):
            raise ValueError("Supplied response case set is incomplete or duplicated")
        mapped = {r["case_id"]: r for r in records}
        supplied_rankings = {}
        for case in cases:
            record = mapped.get(case["case_id"])
            if record is None or record.get("query") != case["query"] or record.get("filters") != scope(case):
                raise ValueError("A supplied query/model/version/filter differs")
            ids = record["ranked_evidence_ids"]
            selected_ids = {item["id"] for item in catalog.select(**scope(case))}
            if not isinstance(ids, list) or len(ids) != len(set(ids)) or not set(ids) <= selected_ids:
                raise ValueError("Supplied IDs are duplicated or outside the approved scope")
            supplied_rankings[case["case_id"]] = ids
        received[method] = {**artifact, "execution_kind": "provided_artifact_not_run_here",
                            "artifact_sha256": fingerprint(artifact), "metrics": metrics(cases, supplied_rankings, k)}
    for method in ("bge-m3", "reranker"):
        results.append(received.get(method, {"method": method, "execution_kind": "unrun", "model": None,
                       "revision": None, "config": None, "model_calls": None, "latency_ms": None,
                       "metrics": None, "responses": None, "input_sha256": input_sha256,
                       "catalog_sha256": catalog_sha256}))
    return {"development_only": True, "independent_evaluation": False, "k": k,
            "input_sha256": input_sha256, "catalog_sha256": catalog_sha256, "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--response", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_retrievers(EvidenceCatalog([json.loads(args.dataset.read_bytes())]),
        json.loads(args.cases.read_bytes()), responses=[json.loads(path.read_bytes()) for path in args.response])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
