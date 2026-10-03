"""Small real CPU retrieval experiment; this is NOT the full submitted Agent evaluation."""

import argparse
import json
import math
import re
import statistics
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


def tokens(text):
    return re.findall(r"[\w]+", text.casefold())


def bm25(query, corpus):
    rows = [tokens(text) for text in corpus]
    average = sum(map(len, rows)) / len(rows)
    frequencies = Counter(token for row in rows for token in set(row))
    scores = []
    for row in rows:
        counts = Counter(row)
        score = 0.0
        for token in tokens(query):
            freq = counts[token]
            inverse = math.log(1 + (len(rows) - frequencies[token] + 0.5) / (frequencies[token] + 0.5))
            denominator = freq + 1.5 * (1 - 0.75 + 0.75 * len(row) / average)
            score += inverse * (freq * 2.5 / denominator)
        scores.append(score)
    return scores


def model_info(model_id, revision):
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{model_id}/revision/{revision}", timeout=30) as response:
        info = json.load(response)
    if info["sha"] != revision:
        raise ValueError("Model revision differs from the bootstrap lock")
    return {"model_id": model_id, "revision": info["sha"],
            "license": info.get("cardData", {}).get("license", "unverified"),
            "source": f"https://huggingface.co/{model_id}"}


def metrics(ranking, query, rows, k=3):
    selected = [rows[i] for i in ranking[:k]]
    relevant = set(query["relevant_evidence_ids"])
    hits = {row["id"] for row in selected} & relevant
    return {"recall_at_3": len(hits) / len(relevant),
            "model_mix_rate_at_3": sum(row["model_id"] != query["model_id"] for row in selected) / len(selected),
            "version_mix_rate_at_3": sum(row["document_version"] != query["document_version"] for row in selected) / len(selected),
            "evidence_ids": [row["id"] for row in selected]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/demo/dataset.json")
    parser.add_argument("--queries", default="evals/bootstrap-models/queries.json")
    parser.add_argument("--output", default="evals/bootstrap-models/retrieval-results.json")
    args = parser.parse_args()
    import torch
    import transformers
    from torch.nn import functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(4)
    dataset_path = Path(args.dataset)
    queries_path = Path(args.queries)
    dataset = json.loads(dataset_path.read_text("utf-8"))
    queries = json.loads(queries_path.read_text("utf-8"))
    evidence = dataset["evidence"]
    embed_info = model_info("BAAI/bge-m3", EMBEDDING_REVISION)
    rerank_info = model_info("BAAI/bge-reranker-v2-m3", RERANKER_REVISION)
    print(json.dumps({"stage": "loading", "models": [embed_info, rerank_info]}), flush=True)
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(embed_info["model_id"], revision=embed_info["revision"])
    # Official BGE-M3 revision publishes pytorch_model.bin, not model.safetensors.
    # Torch >=2.6 uses restricted weights_only loading; no trust_remote_code is enabled.
    encoder = AutoModel.from_pretrained(embed_info["model_id"], revision=embed_info["revision"], use_safetensors=False).eval()
    embed_load = time.perf_counter() - started

    def encode(texts):
        batches = []
        with torch.inference_mode():
            for offset in range(0, len(texts), 8):
                inputs = tokenizer(texts[offset:offset + 8], padding=True, truncation=True, max_length=256, return_tensors="pt")
                hidden = encoder(**inputs).last_hidden_state[:, 0]
                batches.append(functional.normalize(hidden, p=2, dim=1))
        return torch.cat(batches)

    started = time.perf_counter()
    corpus_embeddings = encode([item["text"] for item in evidence])
    index_seconds = time.perf_counter() - started
    started = time.perf_counter()
    rerank_tokenizer = AutoTokenizer.from_pretrained(rerank_info["model_id"], revision=rerank_info["revision"])
    reranker = AutoModelForSequenceClassification.from_pretrained(rerank_info["model_id"], revision=rerank_info["revision"], use_safetensors=True).eval()
    rerank_load = time.perf_counter() - started
    results = []
    for query in queries:
        print(json.dumps({"stage": "query", "id": query["id"]}), flush=True)
        methods = {}
        started = time.perf_counter()
        sparse_scores = bm25(query["query"], [item["text"] for item in evidence])
        sparse_rank = sorted(range(len(evidence)), key=lambda i: (-sparse_scores[i], evidence[i]["id"]))
        sparse_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        query_embedding = encode([query["query"]])
        dense_scores = (query_embedding @ corpus_embeddings.T)[0].tolist()
        dense_rank = sorted(range(len(evidence)), key=lambda i: (-dense_scores[i], evidence[i]["id"]))
        dense_ms = (time.perf_counter() - started) * 1000
        # Model/version filter is structural policy, not an embedding performance claim.
        filtered = [i for i in dense_rank if evidence[i]["model_id"] == query["model_id"] and evidence[i]["document_version"] == query["document_version"]]
        top = filtered[:10]
        started = time.perf_counter()
        inputs = rerank_tokenizer([[query["query"], evidence[i]["text"]] for i in top], padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.inference_mode():
            scores = reranker(**inputs).logits.view(-1).tolist()
        rerank_rank = [i for _, i in sorted(zip(scores, top), key=lambda pair: (-pair[0], evidence[pair[1]]["id"]))]
        rerank_ms = (time.perf_counter() - started) * 1000
        sparse_filtered = [i for i in sparse_rank if evidence[i]["model_id"] == query["model_id"] and evidence[i]["document_version"] == query["document_version"]]
        for name, rank, latency in [("bm25_unfiltered", sparse_rank, sparse_ms), ("bm25_filtered", sparse_filtered, sparse_ms),
                                    ("bge_m3_unfiltered", dense_rank, dense_ms), ("bge_m3_filtered", filtered, dense_ms),
                                    ("bge_m3_filtered_reranker", rerank_rank, dense_ms + rerank_ms)]:
            methods[name] = {**metrics(rank, query, evidence), "latency_ms": round(latency, 3)}
        results.append({"query": query, "methods": methods})
    summaries = {}
    for name in results[0]["methods"]:
        summaries[name] = {key: round(statistics.mean(row["methods"][name][key] for row in results), 5)
                           for key in ["recall_at_3", "model_mix_rate_at_3", "version_mix_rate_at_3", "latency_ms"]}
    output = {"status": "executed", "experiment_kind": "bootstrap_synthetic_retrieval", "timestamp_utc": datetime.now(UTC).isoformat(),
              "benchmark_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "device": "cpu", "torch_threads": 4, "torch_version": torch.__version__, "transformers_version": transformers.__version__,
              "models": [embed_info, rerank_info], "settings": {"max_length": 256, "batch_size": 8, "embedding": "normalized_cls_dense", "rerank_top": 10},
              "dataset_sha256": sha256(dataset_path.read_bytes()).hexdigest(), "queries_sha256": sha256(queries_path.read_bytes()).hexdigest(),
              "model_load_seconds": {"embedding": round(embed_load, 3), "reranker": round(rerank_load, 3)}, "index_seconds": round(index_seconds, 3),
              "query_count": len(queries), "summary": summaries, "results": results,
              "limits": ["6 hand-written synthetic queries; not independent full Agent evaluation", "No claimed market demand or time savings", "Model/version filtering removes mix by policy", "Cold load/download and indexing excluded from query latency", "CPU bootstrap does not demonstrate GPU BGE throughput"]}
    path = Path(args.output);path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"stage": "completed", "summary": summaries}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
