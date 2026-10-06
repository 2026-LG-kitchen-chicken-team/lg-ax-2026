"""Run the locked DATA003 BM25 development baseline; no learned model calls."""

import argparse
import csv
import ctypes
import hashlib
import json
import math
import os
import platform
import random
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from model_benchmark import bm25

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "evals/data003-preparation/20261005"
DEFAULT_OUT = ROOT / "evals/data003-execution/20261005-cpu-baseline"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rank(query_input, evidence):
    """Only runtime input is accepted here; gold answers never enter ranking."""
    if not query_input["model_id"] or not query_input["document_version"]:
        return [], "request_document_version"
    scoped = [e for e in evidence if e["model_id"] == query_input["model_id"]
              and e["document_version"] == query_input["document_version"]]
    if not scoped:
        return [], "no_evidence_for_scope"
    scores = bm25(query_input["query"], [e["text"] for e in scoped])
    result = sorted(zip(scoped, scores), key=lambda pair: (-pair[1], pair[0]["id"]))
    return [{"id": e["id"], "score": score, "model_id": e["model_id"],
             "document_version": e["document_version"]} for e, score in result[:3]], "retrieved"


def evaluate(ranking, query):
    relevant = set(query["relevant_evidence_ids"])
    ids = [e["id"] for e in ranking[:3]]
    first = next((i + 1 for i, eid in enumerate(ids) if eid in relevant), None)
    return {
        "hit_at_1": int(bool(ids) and ids[0] in relevant) if relevant else None,
        "recall_at_3": len(set(ids) & relevant) / len(relevant) if relevant else None,
        "mrr_at_3": (1 / first if first else 0) if relevant else None,
        "model_mix_rate_at_3": sum(e["model_id"] != query["model_id"] for e in ranking) / len(ranking) if ranking else None,
        "version_mix_rate_at_3": sum(e["document_version"] != query["document_version"] for e in ranking) / len(ranking) if ranking else None,
    }


def percentile95(values):
    return sorted(values)[math.ceil(len(values) * 0.95) - 1] if values else None


def measure(query_input, evidence, ranker=rank):
    started = time.perf_counter_ns()
    try:
        ranking, disposition = ranker(query_input, evidence)
        return {"status": "success", "ranking": ranking, "scope_disposition": disposition,
                "error": None, "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000}
    except (ArithmeticError, LookupError, RuntimeError, TypeError, ValueError) as exc:
        return {"status": "failed", "ranking": [], "scope_disposition": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000}


def machine_metrics():
    result = {"peak_rss_mb": None, "ram_gb": None, "memory_probe": "unavailable"}
    if os.name != "nt":
        return result
    from ctypes import wintypes

    class ProcessMemory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in (
                "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile", "ullTotalVirtual",
                "ullAvailVirtual", "ullAvailExtendedVirtual")]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
    memory = ProcessMemory()
    memory.cb = ctypes.sizeof(memory)
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(memory), memory.cb):
        result["peak_rss_mb"] = memory.PeakWorkingSetSize / 1024**2
    if kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        result["ram_gb"] = status.ullTotalPhys / 1024**3
    result["memory_probe"] = "Windows process PeakWorkingSetSize and GlobalMemoryStatusEx"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--preflight-metadata", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "evals") or out.exists():
        raise ValueError("Use a fresh output directory under this worktree's evals")
    manifest = read(PREP / "manifest.json")
    for row in manifest["source_versions"] + manifest["output_versions"] + [manifest["generator"]]:
        if digest(ROOT / row["path"]) != row["sha256"]:
            raise ValueError(f"Prepared input hash mismatch: {row['path']}")
    validation = read(PREP / "validation.json")
    if validation["status"] != "pass" or validation["manifest_sha256"] != digest(PREP / "manifest.json"):
        raise ValueError("Preparation validation is missing or stale")
    load_started = time.perf_counter_ns()
    corpus, queries, protocol = [read(PREP / name) for name in ("corpus.json", "queries.json", "protocol.json")]
    input_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000
    runtime_inputs = [{"id": q["id"], "query": q["query"], "model_id": q["model_id"],
                       "document_version": q["document_version"]} for q in queries]
    # Explicit runtime scope for an authored request about an unidentified older revision.
    # This is recorded input, not a classifier or a generated semantic answer.
    for row in runtime_inputs:
        if row["id"] == "FR-04":
            row["document_version"] = None
    runtime_map = {q["id"]: q for q in runtime_inputs}
    order = list(runtime_map)
    random.Random(protocol["retrieval"]["latency"]["seed"]).shuffle(order)
    warmups = [measure(runtime_map[qid], corpus["evidence"]) for qid in order[:2]]
    attempts = []
    for repeat in range(protocol["retrieval"]["latency"]["measured_repeats_per_query"]):
        for qid in order:
            attempts.append({"query_id": qid, "repeat": repeat + 1, **measure(runtime_map[qid], corpus["evidence"])})
    rows = []
    for query in queries:
        measured = [a for a in attempts if a["query_id"] == query["id"]]
        successful = [a for a in measured if a["status"] == "success"]
        observed = successful[0]["ranking"] if successful else []
        metrics = evaluate(observed, query)
        samples = [a["elapsed_ms"] for a in successful]
        rows.append({"query_id": query["id"], "method": "bm25_filtered",
                     "status": "executed" if successful else "failed", **metrics,
                     "returned_evidence_ids": [e["id"] for e in observed],
                     "ranking": observed, "ranking_metric_applicable": bool(query["relevant_evidence_ids"]),
                     "scope_disposition": successful[0]["scope_disposition"] if successful else "failed",
                     "response_disposition": "not_evaluated_retrieval_only", "response_check_passed": None,
                     "median_ms": statistics.median(samples) if samples else None,
                     "p95_ms": percentile95(samples), "failure_count": len(measured) - len(successful),
                     "stable_ranking_across_repeats": all(a["ranking"] == observed for a in successful),
                     "latency_attempts": measured})
    scored = [r for r in rows if r["ranking_metric_applicable"]]
    timings = [a["elapsed_ms"] for a in attempts if a["query_id"] in {r["query_id"] for r in scored}
               and a["status"] == "success"]
    summary = {"supported_questions": len(scored), "excluded_no_gold_questions": len(rows) - len(scored),
               "macro_hit_at_1": statistics.mean(r["hit_at_1"] for r in scored),
               "macro_recall_at_3": statistics.mean(r["recall_at_3"] for r in scored),
               "macro_mrr_at_3": statistics.mean(r["mrr_at_3"] for r in scored),
               "foreign_model_ids_returned": sum(e["model_id"] != runtime_map[r["query_id"]]["model_id"]
                                                  for r in rows for e in r["ranking"]),
               "wrong_version_ids_returned": sum(e["document_version"] != runtime_map[r["query_id"]]["document_version"]
                                                  for r in rows for e in r["ranking"]),
               "measured_attempts": len(attempts), "failed_attempts": sum(a["status"] != "success" for a in attempts),
               "warmup_attempts": len(warmups), "median_ms_supported_attempts": statistics.median(timings) if timings else None,
               "p95_ms_supported_attempts": percentile95(timings)}
    result = {"status": "executed", "execution_kind": "deterministic", "method": "bm25_filtered",
              "split": "development", "task_id": "P2-DATA-003", "summary": summary,
              "protocol_sha256": digest(PREP / "protocol.json"), "queries_sha256": digest(PREP / "queries.json"),
              "corpus_sha256": digest(PREP / "corpus.json"), "script_sha256": digest(__file__),
              "legacy_bm25_sha256": digest(ROOT / "scripts/model_benchmark.py"),
              "query_order": order, "warmups": warmups, "results": rows,
              "environment": {"python": platform.python_version(), "os": platform.platform(),
                              "cpu": platform.processor(), "logical_cpus": os.cpu_count(), "device": "CPU",
                              "bm25_execution_threads": 1, "configured_model_threads_for_future": 4,
                              "numeric_precision": "Python float (double), BM25 has no FP32 tensor",
                              **machine_metrics()},
              "preflight": {"metadata": read(args.preflight_metadata) if args.preflight_metadata else None,
                            "metadata_sha256": digest(args.preflight_metadata) if args.preflight_metadata else None,
                            "isolation": "No other work is launched by this runner; shared host background load is uncontrolled"},
              "timing": {"input_load_ms": input_load_ms, "index_build_ms": None, "cold_model_load_ms": None,
                         "note": "Legacy BM25 recomputes tokens/IDF on scoped corpus per query; included in timed query, no persistent index",
                         "percentile": "nearest rank", "latency_denominator": "55 supported-query successful attempts"},
              "created_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "learned_model_calls": 0, "ocr_calls": 0, "formal_state_changed": False,
              "limitations": ["27 curated fact summaries and 15 authored queries; no independent final evaluation",
                              "11 gold queries score retrieval only; four scope/unknown cases do not score semantic answers",
                              "FR-04 explicitly has missing runtime version; current version is not silently substituted",
                              "Single-thread Python BM25; future tensor methods must record actual device/threads/precision separately",
                              "Tiny corpus latency is noisy and is not full-system performance",
                              "No BGE/reranker/Paddle, generation, #13 integration or PM semantic gold review executed"]}
    out.mkdir(parents=True)
    save(out / "runtime-inputs.json", runtime_inputs)
    save(out / "results.json", result)
    (out / "runner-source.py").write_bytes(Path(__file__).read_bytes())
    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["query_id", "method", "status", "hit_at_1", "recall_at_3", "mrr_at_3",
                  "model_mix_rate_at_3", "version_mix_rate_at_3", "median_ms", "p95_ms", "failure_count", "scope_disposition"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in rows)
    table = ["# BM25 개발 기준선 실제 실행", "", "기존 27개 사실 요약, 15문항 중 근거가 있는 11문항의 검색 지표다.", "",
             f"- Hit@1: {summary['macro_hit_at_1']:.4f}", f"- Recall@3: {summary['macro_recall_at_3']:.4f}",
             f"- MRR@3: {summary['macro_mrr_at_3']:.4f}",
             f"- 실제 측정: {len(attempts)}회, 실패 {summary['failed_attempts']}회; warmup {len(warmups)}회 별도",
             f"- 모델/버전 혼입 ID: {summary['foreign_model_ids_returned']}/{summary['wrong_version_ids_returned']}개",
             "", "| 질문 | Hit@1 | Recall@3 | MRR@3 | 반환 근거 |", "|---|---|---|---|---|"]
    for r in rows:
        table.append(f"| {r['query_id']} | {r['hit_at_1']} | {r['recall_at_3']} | {r['mrr_at_3']} | {' / '.join(r['returned_evidence_ids']) or '없음'} |")
    table += ["", "None은 순위 평가 제외다. 무정답 질의의 최종 답변·추가 조건 요청·금지 주장 준수는 미평가다.",
              "FR-04의 미지정 과거 문서 버전은 별도 runtime input에서 null로 고정해 현재 문서 검색을 하지 않았다.",
              "기존 tokenizer/BM25 공식과 점수 ID 순 정렬을 유지했다. 형태소 분석·질문/정답 기반 튜닝은 없다.",
              "실패·반환 점수·질문별 반복 시간은 results.json에 있다. 개발 기준선이며 실제 고객 수요나 독립 평가 우위를 뜻하지 않는다.",
              "Python BM25는 한 스레드/float64로 실행했다. FP32/4threads는 이후 tensor 모델 설정이며 두 종류를 동일하다고 표시하지 않는다.",
              "새 출력 폴더 인자로 scripts/run_data003_bm25.py를 실행해 재현한다. 기존 준비/기존 bootstrap 결과를 덮어쓰지 않는다."]
    (out / "README.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(json.dumps({"status": "executed", "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
