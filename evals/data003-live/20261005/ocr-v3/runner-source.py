"""Offline CPU DATA003 retrieval and manual-crop recognition using locked models."""

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import random
import re
import statistics
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from run_data003_bm25 import ROOT, digest, evaluate, machine_metrics, measure, percentile95, rank, read, save

PREP = ROOT / "evals/data003-preparation/20261005"
OCR = ROOT / "evals/data003-ocr-inputs/20261005-v2"
DOWNLOAD = ROOT / "evals/data003-live/20261005/downloaded-models.json"


def normalization(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def distance(left, right):
    previous = list(range(len(right) + 1))
    for index, first in enumerate(left, 1):
        row = [index]
        for offset, second in enumerate(right, 1):
            row.append(min(row[-1] + 1, previous[offset] + 1, previous[offset - 1] + (first != second)))
        previous = row
    return previous[-1]


def field_scores(region, recognized):
    target = region["field_target"]
    if target is None:
        return {"numeric_correct": None, "numeric_total": 0, "numeric_field_correct": None,
                "explicit_unit_correct": None, "unit_total": 0, "model_column_accuracy": None}
    text = normalization(recognized)
    # Only an explicit, source-preserved footnote is removed for typed-value scoring.
    # CER always uses the complete recognition, including that footnote.
    if "*" in region["gold_text"]:
        text = re.sub(r"\*\d+$", "", text)
    observed = [float(number) for number in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", text)]
    expected = target["value"] if isinstance(target["value"], list) else [target["value"]]
    correct = sum(index < len(observed) and value == observed[index] for index, value in enumerate(expected))
    unit_total = len(expected) if region["unit_in_crop"] else 0
    units = re.findall(r"[A-Za-z]+|인용", text)
    unit_correct = sum(unit == target["unit"] for unit in units) if unit_total else None
    if unit_total:
        unit_correct = min(unit_correct, unit_total)
    return {"observed_values": observed, "numeric_correct": correct, "numeric_total": len(expected),
            "numeric_field_correct": observed == expected, "observed_units": units,
            "explicit_unit_correct": unit_correct, "unit_total": unit_total,
            "manually_assigned_source_column": target.get("column"), "model_column_accuracy": None,
            "column_note": "manual fixed crop; recognizer does not predict table/model column"}


def checked_inputs():
    manifest = read(PREP / "manifest.json")
    for row in manifest["source_versions"] + manifest["output_versions"] + [manifest["generator"]]:
        if digest(ROOT / row["path"]) != row["sha256"]:
            raise ValueError(f"Frozen input mismatch: {row['path']}")
    validation = read(PREP / "validation.json")
    if validation["status"] != "pass" or validation["manifest_sha256"] != digest(PREP / "manifest.json"):
        raise ValueError("Preparation validation is stale")
    models = read(DOWNLOAD)
    if models["status"] != "verified":
        raise ValueError("Downloaded models have not been verified")
    for model in models["models"]:
        for file in model["files"]:
            if digest(ROOT / model["snapshot"] / file["name"]) != file["sha256"]:
                raise ValueError("Local model file changed")
    return models


def environment(distributions):
    return {"python": platform.python_version(), "os": platform.platform(), "cpu": platform.processor(),
            "logical_cpus": os.cpu_count(), "device": "CPU", "cpu_threads": 4,
            "versions": {name: importlib.metadata.version(name) for name in distributions},
            **machine_metrics(), "background_load": "shared PC external activity uncontrolled",
            "gpu_used": False}


def scoped(query, evidence):
    if not query["model_id"] or not query["document_version"]:
        return [], "request_document_version"
    found = [item for item in evidence if item["model_id"] == query["model_id"]
             and item["document_version"] == query["document_version"]]
    return found, "retrieved" if found else "no_evidence_for_scope"


def sorted_rows(rows, scores, k=3):
    ordered = sorted(zip(rows, scores), key=lambda pair: (-pair[1], pair[0]["id"]))
    return [{"id": item["id"], "score": float(score), "model_id": item["model_id"],
             "document_version": item["document_version"]} for item, score in ordered[:k]]


def run_retrieval(out, models):
    import torch
    from torch.nn import functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261005)
    corpus, queries, protocol = [read(PREP / name) for name in ("corpus.json", "queries.json", "protocol.json")]
    evidence = corpus["evidence"]
    runtime_inputs = read(ROOT / "evals/data003-execution/20261005-cpu-baseline-v3/runtime-inputs.json")
    runtime_map = {item["id"]: item for item in runtime_inputs}
    model_map = {model["model_id"]: model for model in models["models"]}
    embed_path = ROOT / model_map["BAAI/bge-m3"]["snapshot"]
    rerank_path = ROOT / model_map["BAAI/bge-reranker-v2-m3"]["snapshot"]
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(embed_path, local_files_only=True, trust_remote_code=False)
    encoder = AutoModel.from_pretrained(embed_path, local_files_only=True, use_safetensors=False,
                                       trust_remote_code=False).float().eval()
    embed_load_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    rerank_tokenizer = AutoTokenizer.from_pretrained(rerank_path, local_files_only=True, trust_remote_code=False)
    reranker = AutoModelForSequenceClassification.from_pretrained(
        rerank_path, local_files_only=True, use_safetensors=True, trust_remote_code=False).float().eval()
    rerank_load_ms = (time.perf_counter() - started) * 1000
    lengths = {"corpus": {item["id"]: len(tokenizer(item["text"])["input_ids"]) for item in evidence},
               "queries": {item["id"]: len(tokenizer(item["query"])["input_ids"]) for item in runtime_inputs},
               "reranker_pairs": {item["id"]: [len(rerank_tokenizer(item["query"], row["text"])["input_ids"])
                                                  for row in scoped(item, evidence)[0]] for item in runtime_inputs}}
    all_lengths = list(lengths["corpus"].values()) + list(lengths["queries"].values())
    all_lengths += [value for values in lengths["reranker_pairs"].values() for value in values]
    if max(all_lengths) > 256:
        save(out / "truncation-failure.json", lengths)
        raise ValueError("Protocol forbids unreported truncation; revise protocol and rerun all methods")

    def encode(texts):
        batches = []
        with torch.inference_mode():
            for offset in range(0, len(texts), 8):
                inputs = tokenizer(texts[offset:offset + 8], padding=True, truncation=True,
                                   max_length=256, return_tensors="pt")
                hidden = encoder(**inputs).last_hidden_state[:, 0]
                batches.append(functional.normalize(hidden, p=2, dim=1))
        return torch.cat(batches)

    started = time.perf_counter()
    embeddings = encode([row["text"] for row in evidence])
    index_ms = (time.perf_counter() - started) * 1000
    embedding_map = {row["id"]: embeddings[index] for index, row in enumerate(evidence)}

    def learned_rank(query_input, unused_evidence, rerank=False):
        rows, disposition = scoped(query_input, evidence)
        if not rows:
            return [], disposition
        query_embedding = encode([query_input["query"]])
        scoped_vectors = torch.stack([embedding_map[row["id"]] for row in rows])
        scores = (query_embedding @ scoped_vectors.T)[0].tolist()
        if not rerank:
            return sorted_rows(rows, scores), disposition
        candidates = [row for row, _ in sorted(zip(rows, scores), key=lambda pair: (-pair[1], pair[0]["id"]))[:10]]
        inputs = rerank_tokenizer([[query_input["query"], row["text"]] for row in candidates],
                                 padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.inference_mode():
            reranked_scores = reranker(**inputs).logits.view(-1).tolist()
        return sorted_rows(candidates, reranked_scores), disposition

    methods = [("bm25_filtered", rank), ("bge_m3_filtered", learned_rank),
               ("bge_m3_filtered_reranker", lambda query, rows: learned_rank(query, rows, rerank=True))]
    order = list(runtime_map)
    random.Random(protocol["retrieval"]["latency"]["seed"]).shuffle(order)
    results, summaries, warmups = [], {}, {}
    for method, ranker in methods:
        print(json.dumps({"stage": "measure", "method": method}), flush=True)
        warmups[method] = [measure(runtime_map[qid], evidence, ranker) for qid in order[:2]]
        attempts = []
        for repeat in range(5):
            for qid in order:
                attempts.append({"query_id": qid, "repeat": repeat + 1,
                                 **measure(runtime_map[qid], evidence, ranker)})
        rows = []
        for query in queries:
            measured = [attempt for attempt in attempts if attempt["query_id"] == query["id"]]
            successful = [attempt for attempt in measured if attempt["status"] == "success"]
            observed = successful[0]["ranking"] if successful else []
            scores = [evaluate(attempt["ranking"], query) for attempt in measured]
            metrics = {key: statistics.mean(score[key] for score in scores) if query["relevant_evidence_ids"]
                       else None for key in ("hit_at_1", "recall_at_3", "mrr_at_3")}
            samples = [attempt["elapsed_ms"] for attempt in successful]
            rows.append({"query_id": query["id"], "method": method, "ranking": observed, **metrics,
                         "ranking_metric_applicable": bool(query["relevant_evidence_ids"]),
                         "scope_disposition": successful[0]["scope_disposition"] if successful else "failed",
                         "median_ms": statistics.median(samples) if samples else None, "p95_ms": percentile95(samples),
                         "failure_count": len(measured) - len(successful), "latency_attempts": measured,
                         "stable_ranking_across_repeats": all(attempt["ranking"] == observed for attempt in successful),
                         "semantic_response_evaluated": False})
        supported = [row for row in rows if row["ranking_metric_applicable"]]
        supported_ids = {row["query_id"] for row in supported}
        times = [attempt["elapsed_ms"] for attempt in attempts
                 if attempt["query_id"] in supported_ids and attempt["status"] == "success"]
        summaries[method] = {"macro_hit_at_1": statistics.mean(row["hit_at_1"] for row in supported),
                             "macro_recall_at_3": statistics.mean(row["recall_at_3"] for row in supported),
                             "macro_mrr_at_3": statistics.mean(row["mrr_at_3"] for row in supported),
                             "supported_questions": len(supported), "excluded_no_gold_questions": 4,
                             "measured_attempts": len(attempts), "failed_attempts": sum(a["status"] != "success" for a in attempts),
                             "median_ms": statistics.median(times) if times else None, "p95_ms": percentile95(times),
                             "foreign_model_ids": sum(item["model_id"] != runtime_map[row["query_id"]]["model_id"]
                                                      for row in rows for attempt in row["latency_attempts"] for item in attempt["ranking"]),
                             "wrong_version_ids": sum(item["document_version"] != runtime_map[row["query_id"]]["document_version"]
                                                      for row in rows for attempt in row["latency_attempts"] for item in attempt["ranking"])}
        results.extend(rows)
        save(out / "progress.json", {"summary": summaries, "results": results})
    return {"status": "executed", "execution_kind": "live_model", "split": "development",
            "task_id": "P2-DATA-003", "summary": summaries, "results": results, "warmups": warmups,
            "query_order": order, "runtime_inputs": runtime_inputs, "token_lengths": lengths,
            "environment": environment(["torch", "transformers", "huggingface-hub", "numpy", "safetensors"]),
            "precision": "BM25 Python double, BGE/reranker float32", "torch_interop_threads": 1,
            "timing": {"embedding_load_ms": embed_load_ms, "reranker_load_ms": rerank_load_ms,
                       "index_build_ms": index_ms, "boundary": "query embedding + exact scope/rank + optional reranker",
                       "rss_scope": "whole combined benchmark process; not method-specific memory",
                       "percentile": "nearest rank", "latency_denominator": "supported-query successful attempts only"},
            "limitations": ["27 summaries/15 authored queries, not full manuals or independent final evaluation",
                            "No semantic answers for four no-gold queries; FR-04 runtime revision null",
                            "Tiny corpus; shared CPU background load uncontrolled; sequential method order",
                            "Structural filtering is policy, not learned model quality",
                            "#13 integration and PM semantic gold/output review not executed"]}


def run_ocr(out, models):
    from paddleocr import TextRecognition

    manifest = read(OCR / "crop-manifest.json")
    if read(OCR / "visual-review.json")["status"] != "pass":
        raise ValueError("OCR input visual review missing")
    model_info = next(model for model in models["models"] if model["model_id"].startswith("PaddlePaddle/"))
    started = time.perf_counter()
    # Paddle's Windows native file reader cannot open this Unicode absolute path.
    # Same files and hashes are used through ASCII paths relative to the worktree.
    model = TextRecognition(model_name="korean_PP-OCRv5_mobile_rec", model_dir=model_info["snapshot"],
                            device="cpu", enable_mkldnn=False, cpu_threads=4)
    load_ms = (time.perf_counter() - started) * 1000
    regions = [(case, region) for case in manifest["cases"] for region in case["regions"]]
    for _, region in regions:
        if digest(ROOT / region["crop_path"]) != region["crop_sha256"]:
            raise ValueError("Frozen OCR crop changed")
    warmups = []
    for _, region in regions[:2]:
        started = time.perf_counter()
        prediction = next(iter(model.predict(input=region["crop_path"], batch_size=1)))
        warmups.append({"region_id": region["id"], "recognized": prediction["rec_text"],
                        "elapsed_ms": (time.perf_counter() - started) * 1000})
    results = []
    for case, region in regions:
        print(json.dumps({"stage": "recognize", "region_id": region["id"]}), flush=True)
        attempts = []
        for repeat in range(5):
            started = time.perf_counter()
            try:
                prediction = next(iter(model.predict(input=region["crop_path"], batch_size=1)))
                observed = prediction["rec_text"]
                attempts.append({"repeat": repeat + 1, "status": "success", "recognized": observed,
                                 "confidence": float(prediction["rec_score"]),
                                 "elapsed_ms": (time.perf_counter() - started) * 1000, "error": None})
            except (RuntimeError, ValueError, TypeError, LookupError, OSError, StopIteration) as error:
                attempts.append({"repeat": repeat + 1, "status": "failed", "recognized": "",
                                 "confidence": None, "elapsed_ms": (time.perf_counter() - started) * 1000,
                                 "error": f"{type(error).__name__}: {error}"})
        successful = [attempt for attempt in attempts if attempt["status"] == "success"]
        observed = successful[0]["recognized"] if successful else ""
        gold = normalization(region["gold_text"])
        edits = distance(gold, normalization(observed))
        samples = [attempt["elapsed_ms"] for attempt in successful]
        results.append({"case_id": case["id"], "region_id": region["id"], "status": "executed" if successful else "failed",
                        "source_model_id": case["model_id"], "document_version": case["document_version"], "page": case["page"],
                        "crop_sha256": region["crop_sha256"], "gold_text": region["gold_text"], "recognized": observed,
                        "normalized_gold_length": len(gold), "edit_distance": edits, "CER": edits / len(gold),
                        "normalized_exact_match": gold == normalization(observed), **field_scores(region, observed),
                        "median_ms": statistics.median(samples) if samples else None, "p95_ms": percentile95(samples),
                        "failure_count": len(attempts) - len(successful), "attempts": attempts,
                        "stable_text_across_repeats": all(a["recognized"] == observed for a in successful)})
        save(out / "progress.json", {"results": results})
    numeric_total = sum(row["numeric_total"] for row in results)
    unit_total = sum(row["unit_total"] for row in results)
    attempts = [attempt for row in results for attempt in row["attempts"]]
    timings = [attempt["elapsed_ms"] for attempt in attempts if attempt["status"] == "success"]
    summary = {"cases": len(manifest["cases"]), "regions": len(results), "measured_attempts": len(attempts),
               "failed_attempts": sum(attempt["status"] != "success" for attempt in attempts),
               "macro_CER": statistics.mean(row["CER"] for row in results),
               "micro_CER": sum(row["edit_distance"] for row in results) / sum(row["normalized_gold_length"] for row in results),
               "normalized_exact_matches": sum(row["normalized_exact_match"] for row in results),
               "numeric_correct": sum(row["numeric_correct"] or 0 for row in results), "numeric_total": numeric_total,
               "numeric_value_accuracy": sum(row["numeric_correct"] or 0 for row in results) / numeric_total,
               "numeric_fields_correct": sum(row["numeric_field_correct"] is True for row in results),
               "numeric_fields_total": sum(row["numeric_total"] > 0 for row in results),
               "explicit_unit_correct": sum(row["explicit_unit_correct"] or 0 for row in results), "unit_total": unit_total,
               "explicit_unit_accuracy": sum(row["explicit_unit_correct"] or 0 for row in results) / unit_total,
               "model_column_accuracy": None, "median_ms": statistics.median(timings), "p95_ms": percentile95(timings)}
    return {"status": "executed", "execution_kind": "live_model", "split": "development", "task_id": "P2-DATA-003",
            "method": "paddle_manual_crop_recognition", "summary": summary, "results": results, "warmups": warmups,
            "model_load_ms": load_ms, "environment": environment(["paddlepaddle", "paddleocr", "paddlex", "pillow", "numpy"]),
            "settings": {"enable_mkldnn": False, "cpu_threads": 4, "dpi": 300, "batch_size": 1,
                         "rotation": 0, "denoise": False, "normalization": "NFC and whitespace collapse only for CER"},
            "crop_manifest_sha256": digest(OCR / "crop-manifest.json"), "visual_review_sha256": digest(OCR / "visual-review.json"),
            "comparison": read(OCR / "text-extraction-comparison.json"),
            "limitations": ["Manual crop segmentation/column assignment, not automatic page layout or column prediction",
                            "Model column accuracy remains null; correct value from a manually assigned column is not layout accuracy",
                            "MW dimensions unit outside crop: excluded from explicit unit score; original table context preserves mm",
                            "PDF baseline checks phrase availability only; does not claim field/CER equivalence",
                            "Real text PDFs rendered as images, not newly collected scans; no rotation/noise robustness tested",
                            "Confidence is model output, not verified semantic accuracy; #13 integration/PM review pending"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["retrieval", "ocr"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "evals") or out.exists():
        raise ValueError("Choose a fresh output directory under this worktree's evals")
    os.chdir(ROOT)
    task_cache = ROOT / "private/model-runtime"
    os.environ.update(HF_HOME=str(task_cache / "huggingface"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4",
                      PADDLE_PDX_CACHE_HOME=str(task_cache / "paddlex"), PADDLE_HOME=str(task_cache / "paddle"),
                      PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True", CUDA_VISIBLE_DEVICES="")
    models = checked_inputs()
    out.mkdir(parents=True)
    if args.kind == "retrieval":
        result = run_retrieval(out, models)
    else:
        # Paddle 3.0's legacy dataset import ignores PADDLE_HOME and calls
        # expanduser('~/.cache/paddle'). Redirect tilde paths only for this call;
        # do not alter system HOME/USERPROFILE, shared caches or installed code.
        task_legacy_home = task_cache / "legacy-home"
        task_legacy_home.mkdir(parents=True, exist_ok=True)
        original_expanduser = os.path.expanduser

        def task_expanduser(path):
            value = os.fspath(path)
            if isinstance(value, str) and (value == "~" or value.startswith(("~/", "~\\"))):
                return str(task_legacy_home / value[2:]) if value != "~" else str(task_legacy_home)
            return original_expanduser(path)

        with patch("os.path.expanduser", task_expanduser):
            result = run_ocr(out, models)
        result["legacy_cache_isolation"] = "process-local tilde expansion redirected to private/model-runtime/legacy-home"
    result.update(models=models["models"], script_sha256=digest(__file__),
                  protocol_sha256=digest(PREP / "protocol.json"), corpus_sha256=digest(PREP / "corpus.json"),
                  queries_sha256=digest(PREP / "queries.json"), downloaded_manifest_sha256=digest(DOWNLOAD),
                  created_at_kst=datetime.now(timezone(timedelta(hours=9))).isoformat(), formal_state_changed=False)
    save(out / "results.json", result)
    (out / "runner-source.py").write_bytes(Path(__file__).read_bytes())
    fields = list(result["results"][0])
    fields = [field for field in fields if field not in ("ranking", "attempts", "latency_attempts")]
    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in result["results"])
    print(json.dumps({"stage": "complete", "kind": args.kind, "summary": result["summary"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
