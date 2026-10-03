"""Bundle immutable bootstrap model evidence and check it without loading models."""

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

DIRECTORY = Path("evals/bootstrap-models")
TARGET = DIRECTORY / "models-manifest.json"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((DIRECTORY / name).read_text("utf-8"))


def validate_sources():
    pairs = [("retrieval-results.json", "scripts/model_benchmark.py", "benchmark_source_sha256"),
             ("generation-results.json", "services/inference/generation_benchmark.py", "benchmark_source_sha256"),
             ("ocr-results.json", "services/inference/ocr_benchmark.py", "benchmark_source_sha256"),
             ("service-smoke.json", "services/inference/service_smoke.py", "benchmark_source_sha256"),
             ("server-inventory.json", "services/inference/server_inventory.py", "inventory_source_sha256")]
    for name, source, key in pairs:
        if read(name)[key] != digest(source):
            raise ValueError(f"Executed source differs: {source}")
    dataset_digest = digest(DIRECTORY / "input-dataset.json")
    for name in ["retrieval-results.json", "generation-results.json"]:
        if read(name)["dataset_sha256"] != dataset_digest:
            raise ValueError(f"Executed dataset differs: {name}")
    if read("retrieval-results.json")["queries_sha256"] != digest(DIRECTORY / "input-queries.json"):
        raise ValueError("Executed queries differ")
    if read("service-smoke.json")["checks"]["health"]["body"]["source_sha256"] != digest("services/inference/server.py"):
        raise ValueError("Actual running API source differs")
    if read("service-smoke.json")["status"] != "passed":
        raise ValueError("Private API smoke failed")


def build():
    validate_sources()
    retrieval, generation, ocr = (read(name) for name in ["retrieval-results.json", "generation-results.json", "ocr-results.json"])
    models = []
    for model in retrieval["models"]:
        models.append({**model, "revision_kind": "huggingface_commit", "device": "cpu", "status": "executed_bootstrap_candidate",
                       "license": "MIT" if model["license"] == "mit" else "Apache-2.0", "evidence": "evals/bootstrap-models/retrieval-results.json"})
    models.append({**generation["model"], "device": "cuda:0", "status": "executed_bootstrap_candidate", "evidence": "evals/bootstrap-models/generation-results.json"})
    models.append({**ocr["model"], "license": "Apache-2.0", "revision_kind": "huggingface_commit", "device": "cpu", "status": "executed_bootstrap_candidate",
                   "evidence": "evals/bootstrap-models/ocr-results.json"})
    sources = ["scripts/model_benchmark.py", "services/inference/server.py", "services/inference/generation_benchmark.py",
               "services/inference/ocr_benchmark.py", "services/inference/service_smoke.py", "services/inference/server_inventory.py",
               "services/inference/lab_setup.sh", "services/inference/ocr_setup.sh", "services/inference/run_lab.sh",
               "services/inference/ollama_start.sh", "services/inference/lab_server_start.sh", "services/inference/requirements-cpu.txt"]
    artifacts = [DIRECTORY / name for name in ["input-dataset.json", "input-queries.json", "retrieval-results.json", "generation-results.json", "ocr-results.json",
                                               "service-smoke.json", "server-inventory.json", "ocr/korean-text-1.png", "ocr/korean-text-2.png"]]
    generation_checks = ["schema_shape_ok", "allowed_evidence_ids_only", "model_id_matches", "feature_presence_matches_fixture", "done"]
    return {"schema_version": "1.0", "status": "executed_bootstrap", "confirmed_at_utc": datetime.now(UTC).isoformat(),
            "scope": "Actual lab retrieval, Korean textline OCR, structured generation and private API smoke; not full Agent",
            "agent_requirements_complete": False, "production_model_adoption_decided": False,
            "models": models, "source_versions": {path: digest(path) for path in sources},
            "artifacts": [{"path": path.as_posix(), "sha256": digest(path)} for path in artifacts],
            "inputs": {"dataset_snapshot": "evals/bootstrap-models/input-dataset.json", "dataset_sha256": digest(DIRECTORY / "input-dataset.json"),
                       "query_snapshot": "evals/bootstrap-models/input-queries.json", "queries_sha256": digest(DIRECTORY / "input-queries.json"),
                       "current_dataset_matches_executed": digest("data/demo/dataset.json") == digest(DIRECTORY / "input-dataset.json"), "source_kind": "synthetic"},
            "runtime": {"inventory": "evals/bootstrap-models/server-inventory.json", "python": "3.11.17", "torch": "2.8.0+cpu", "ollama": generation["ollama_version"],
                        "ocr_versions": ocr["runtime_versions"], "model_cache_and_environment": "dedicated_tmpfs_lost_on_reboot", "root_disk_reserve_bytes": 5368709120},
            "services": {"ollama": {"host": "127.0.0.1", "port": 18864, "gpu": 0}, "private_lab_api": {"host": "127.0.0.1", "port": 18865, "authentication": "not_configured"},
                         "public_mcp_connected": False, "service_smoke": "evals/bootstrap-models/service-smoke.json"},
            "measurements": {"retrieval_query_count": retrieval["query_count"], "retrieval_summary": retrieval["summary"],
                             "generation_case_count": len(generation["results"]), "generation_fixture_checks_passed": sum(all(row[key] for key in generation_checks) for row in generation["results"]),
                             "generation_latency_ms": {row["case_id"]: row["latency_ms"] for row in generation["results"]},
                             "ocr_case_count": len(ocr["results"]), "ocr_exact_matches": sum(row["exact_match"] for row in ocr["results"]),
                             "ocr_latency_ms": [row["latency_ms"] for row in ocr["results"]]},
            "limits": ["Tiny synthetic fixtures; no market demand, general accuracy or user benefit conclusion",
                       "BM25 with model/version filters matched dense/reranker recall; no embedding superiority established",
                       "BGE CPU dense normalized CLS only; sparse/multi-vector and GPU throughput not tested",
                       "Qwen Ollama digest identifies the quantized distribution, not an upstream HF commit",
                       "OCR text-line recognition only; document detection/layout/table/PDF ingestion not implemented",
                       "API loopback boundary is not authentication; requires access controls before shared/public integration",
                       "No submitted 5-Skill, 31-requirement workflow or 3-case end-to-end completion claim"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        validate_sources()
        manifest = json.loads(TARGET.read_text("utf-8"))
        for path, expected in manifest["source_versions"].items():
            if digest(path) != expected:
                raise ValueError(f"Manifest source hash differs: {path}")
        for artifact in manifest["artifacts"]:
            if digest(artifact["path"]) != artifact["sha256"]:
                raise ValueError(f"Manifest artifact hash differs: {artifact['path']}")
        print("Model bootstrap source/input/output hashes verified; Agent completion is not asserted.")
        return
    TARGET.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.as_posix()}")


if __name__ == "__main__":
    main()
