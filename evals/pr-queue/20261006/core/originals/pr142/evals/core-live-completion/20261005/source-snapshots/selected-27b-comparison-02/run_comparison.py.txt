"""Run frozen six-case comparisons through one explicitly pinned Ollama model.

Never score semantic correctness or mark PM review complete. Preserve every
returned completion, failed attempt, and preflight rejection in a fresh folder.
"""
import argparse
import hashlib
import json
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, schema_for
from lgax_core.model_client import OllamaAdapter, StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore


def read(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class ObservedAdapter(OllamaAdapter):
    """Observe the SDK's single generation request, before result validation."""
    def __init__(self, config):
        super().__init__(config)
        self.calls = []
        self.pending = None

    def generate(self, prompt, schema):
        record = {"formatted_prompt": prompt, "schema": deepcopy(schema)}
        self.pending = record
        try:
            result = super().generate(prompt, schema)
            record["metadata"] = deepcopy(result["metadata"])
            return result
        except DomainError as error:
            record["error"] = error.response()["error"]
            raise
        finally:
            self.pending = None

    def _generate(self, prompt, schema, deadline):
        # Pin-only failures never reach this method and make no model request.
        record = self.pending
        self.calls.append(record)
        return super()._generate(prompt, schema, deadline)

    def _request(self, method, path, deadline, body=None):
        if method == "POST" and self.pending is not None:
            self.pending["api_path"] = path
            self.pending["transport_request"] = deepcopy(body)
        response = super()._request(method, path, deadline, body)
        if method == "POST" and self.pending is not None:
            self.pending["transport_response"] = deepcopy(response)
        return response


def measurements(calls, latency_ms, tool_calls):
    def total(name):
        values = [call.get("transport_response", {}).get(name) for call in calls]
        return sum(values) if all(type(value) is int for value in values) else None
    return {"latency_ms": round(latency_ms, 3), "input_tokens": total("prompt_eval_count"),
            "output_tokens": total("eval_count"), "model_calls": len(calls), "tool_calls": tool_calls,
            "cost": None, "modification_seconds": None}


def validate_frozen(suite, frozen):
    manifest = read(suite / "manifest.json")
    inventory = read(frozen / "inventory.json")
    cases = manifest["cases"]
    if len(cases) != 6 or len(inventory["cases"]) != 6:
        raise ValueError("Six frozen cases required")
    frozen_cases = {case["case_id"]: case for case in inventory["cases"]}
    prepared = []
    for case in cases:
        name = case["case_id"]
        entry = frozen_cases[name]
        input_path = frozen / f"{name}.model-input.json"
        baseline_path = frozen / f"{name}.baseline.txt"
        for path, field in ((suite / case["data_path"], "data_sha256"),
                            (suite / case["output_contract_path"], "output_contract_sha256"),
                            (input_path, "model_input_sha256"), (baseline_path, "baseline_file_sha256")):
            if digest(path) != entry[field]:
                raise ValueError(f"{name}: frozen material changed ({field})")
        payload = read(input_path)
        if (entry["baseline_contract_mode"] != "client_schema"
                or payload["materials"] != read(suite / case["data_path"])
                or payload["input"] != case["request"]
                or payload["output_contract"] != schema_for("output")
                or payload["input_sha256"] != input_digest(payload["input"])):
            raise ValueError(f"{name}: frozen scope/contract mismatch")
        prepared.append((case, entry, payload, baseline_path.read_text("utf-8")))
    return prepared


def run_comparison(suite, frozen, output_dir, config, *, gpu_identity,
                   environment_identity="existing-lg-lab-ollama"):
    prepared = validate_frozen(suite, frozen)
    if output_dir.exists():
        raise ValueError("Use a fresh output folder; never overwrite original executions")
    # Read only the approved forwarded service. No downloads or server lifecycle.
    version = httpx.get(config.endpoint + "/api/version", timeout=10).json()["version"]
    tags = httpx.get(config.endpoint + "/api/tags", timeout=10).json()["models"]
    model = next(item for item in tags if item["name"] == config.model_id)
    if model["digest"] != config.expected_digest:
        raise ValueError("Frozen model pin mismatch")
    root = Path(__file__).resolve().parents[2]
    source_hashes = {path.as_posix(): digest(root / path) for path in (
        Path("packages/core/src/lgax_core/planning_agent.py"),
        Path("packages/core/src/lgax_core/semantic_review.py"),
        Path("packages/core/src/lgax_core/no_candidate_review.py"),
        Path("packages/core/src/lgax_core/revision_guard.py"),
        Path("packages/core/src/lgax_core/correction_budget.py"),
        Path("packages/core/src/lgax_core/judgement_contract.py"),
        Path("packages/core/src/lgax_core/model_client.py"),
        Path("evals/core-semantic/run_comparison.py"))}
    output_dir.mkdir(parents=True)
    bundles = {name: {"schema_version": 1, "method": name, "records": []}
               for name in ("agent", "single_prompt_baseline")}
    summary = {"execution_kind": "live_model", "source_kind": "synthetic",
               "observed_at": datetime.now(UTC).isoformat(), "source_sha256": source_hashes,
               "semantic_scores": None, "evaluation_complete": False, "cases": [],
               "notice": "Execution success and planning hold differ from semantic correctness. "
                         "SEM06 current runs use the same current snapshot; prior execution is a separate experiment. "
                         "Measurements include every generation request/retry in each current request. "
                         "Tool count covers bootstrap/get_evidence and scoped revision reads, excluding model calls."}
    for case, entry, payload, baseline in prepared:
        name = case["case_id"]
        conditions = {
            "request_sha256": input_digest(case["request"]), "data_sha256": entry["data_sha256"],
            "output_contract_sha256": entry["output_contract_sha256"],
            "model": {"id": config.model_id, "revision": config.expected_digest, "digest": config.expected_digest},
            "sampling": {key: value for key, value in config.ollama_options().items()
                         if key not in {"num_ctx", "num_predict"}} | {"thinking": config.thinking},
            "output_budget": {"max_output_tokens_per_call": config.max_output_tokens,
                              "total_output_tokens_limit": None},
            "environment": {"provider": "ollama", "host": environment_identity,
                            "runtime": version, "context_tokens": config.context_tokens,
                            "adapter": "ollama", "constraint_mode": "native_schema_and_local_validation",
                            "api_mode": config.api_mode,
                            "model_quantization": model.get("details", {}).get("quantization_level"),
                            "gpu": gpu_identity},
            "data_access": {"pool": "entire_case_dataset", "availability": "all_materials_available",
                            "truncation": "none"},
            "measurement_scope": "whole_request_including_all_model_calls_and_retries"}
        for method in bundles:
            adapter = ObservedAdapter(config)
            started = time.monotonic()
            with StructuredModelClient(adapter) as client:
                if method == "agent":
                    result = PlanningAgent(client, DemoStore(payload["materials"]["dataset"])).run(payload["input"])
                    raw_output = result["output"]
                    success = result["decision"] is not None and result["status"] != "failed"
                    error = None if success else {
                        "status": result["status"], "errors": result["errors"], "decision": result["decision"]}
                    tools = sum(row["stage"] == "retrieve" for row in result["trace"])
                    tools += len(result.get("revision_session", {}).get("tool_audit", []))
                    prompts = [call["formatted_prompt"] for call in result["model_calls"]
                               if "formatted_prompt" in call]
                    actual_prompt = {"model_prompts": prompts, "preflight_input": payload["input"],
                                     "pipeline_source_sha256": source_hashes}
                else:
                    result = {"input": payload["input"], "output": None, "errors": [], "execution_kind": "live_model"}
                    try:
                        generated = client.generate(baseline, payload["output_contract"], config.model_id)
                        result["output"] = generated.data
                        result["metadata"] = generated.metadata
                        success, error = True, None
                    except DomainError as failure:
                        error = failure.response()["error"]
                        result["errors"].append(error)
                        success = False
                    raw_output, tools = result["output"], 0
                    actual_prompt = adapter.calls[0]["formatted_prompt"] if adapter.calls else baseline
            elapsed = (time.monotonic() - started) * 1000
            result["actual_generation_requests"] = adapter.calls
            result["source_sha256"] = source_hashes
            result["conditions"] = conditions
            write(output_dir / f"{name}.{method}.json", result)
            measured = measurements(adapter.calls, elapsed, tools)
            record = {
                "case_id": name, "execution_kind": "live_model", "status": "success" if success else "failure",
                "conditions": conditions,
                "method_setup": {"prompt": actual_prompt, "prompt_sha256": input_digest(actual_prompt),
                                 "instructions_complete": True,
                                 "material_delivery": "tool_access" if method == "agent" else "full_prompt",
                                 "call_policy": "agent_orchestration" if method == "agent" else "single_prompt"},
                "raw_output": raw_output, "raw_error": error,
                "execution_trace": result.get("trace", []) + adapter.calls,
                "measurements": measured}
            bundles[method]["records"].append(record)
            progress = {"case_id": name, "method": method, "execution_status": record["status"],
                        "planning_status": raw_output.get("status") if isinstance(raw_output, dict) else None,
                        "measurements": measured}
            summary["cases"].append(progress)
            print(json.dumps(progress, ensure_ascii=False), flush=True)
    for method, bundle in bundles.items():
        write(output_dir / f"{method}-results.json", bundle)
    write(output_dir / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--frozen-inputs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpu-identity", required=True, help="GPU assignment independently verified before this run")
    parser.add_argument("--environment-identity", default="existing-lg-lab-ollama")
    args = parser.parse_args()
    with StructuredModelClient.from_env() as configured:
        config = configured.adapter.config
        if not isinstance(configured.adapter, OllamaAdapter):
            raise TypeError("This runner requires the same explicitly configured Ollama adapter for both methods")
    run_comparison(args.suite, args.frozen_inputs, args.output_dir, config, gpu_identity=args.gpu_identity,
                   environment_identity=args.environment_identity)


if __name__ == "__main__":
    main()
