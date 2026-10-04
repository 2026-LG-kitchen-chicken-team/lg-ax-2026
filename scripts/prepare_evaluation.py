"""Validate external paired results and prepare label-blinded review files; never run models."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_CATEGORIES = (
    "normal", "duplicate_feature", "model_version_confusion", "conflicting_reviews",
    "missing_evidence", "specification_change",
)
MEASUREMENT_SCOPE = "whole_request_including_all_model_calls_and_retries"
MEASUREMENT_FIELDS = (
    "latency_ms", "input_tokens", "output_tokens", "model_calls", "tool_calls",
    "cost", "modification_seconds",
)
HASH = re.compile(r"[0-9a-f]{64}\Z")


class EvaluationError(ValueError):
    """Invalid or incomparable inputs; no evaluated performance is implied."""


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise EvaluationError("JSON contains duplicate field names")
        result[name] = value
    return result


def _read_json(path: Path):
    def invalid_constant(_value):
        raise EvaluationError("JSON contains a non-finite number")

    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object,
                            parse_constant=invalid_constant)
        json.dumps(result, allow_nan=False)
        return result
    except EvaluationError:
        raise
    except ValueError as exc:
        raise EvaluationError(f"Invalid finite JSON file: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read JSON file: {path.name}") from exc


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise EvaluationError(f"{label}: required fields do not match the contract")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label}: a nonempty string is required")


def _hash(value, label):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise EvaluationError(f"{label}: lowercase SHA256 is required")


def _number(value, label, integer=False):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationError(f"{label}: use a nonnegative measurement or null")
    finite = isinstance(value, int) or math.isfinite(value)
    if value < 0 or not finite or (integer and not isinstance(value, int)):
        raise EvaluationError(f"{label}: invalid measurement")


def _manifest(path: Path) -> dict:
    manifest = _read_json(path)
    _fields(manifest, ("schema_version", "independent_from_development", "cases"), "manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or (
        manifest["independent_from_development"] is not True
    ):
        raise EvaluationError("Manifest must explicitly declare independent cases, schema version 1")
    if not isinstance(manifest["cases"], list) or not manifest["cases"]:
        raise EvaluationError("Independent cases are required")
    cases = {}
    for case in manifest["cases"]:
        _fields(case, ("case_id", "category", "request", "data_path", "output_contract_path"), "case")
        _text(case["case_id"], "case_id")
        if case["case_id"] in cases:
            raise EvaluationError("Duplicate case ID")
        if case["category"] not in REQUIRED_CATEGORIES:
            raise EvaluationError("Unknown evaluation category")
        if not isinstance(case["request"], dict) or not case["request"]:
            raise EvaluationError("Case request must be a nonempty JSON object")
        checked = deepcopy(case)
        checked["request_sha256"] = canonical_sha256(case["request"])
        for source, target in (("data_path", "data_sha256"),
                               ("output_contract_path", "output_contract_sha256")):
            _text(case[source], source)
            try:
                checked[target] = hashlib.sha256((path.parent / case[source]).read_bytes()).hexdigest()
            except OSError as exc:
                raise EvaluationError(f"Case material is unreadable: {source}") from exc
        cases[case["case_id"]] = checked
    present = {case["category"] for case in cases.values()}
    missing = set(REQUIRED_CATEGORIES) - present
    if missing:
        raise EvaluationError("Missing independent case categories: " + ", ".join(sorted(missing)))
    return cases


def _conditions(record, case):
    conditions = record["conditions"]
    _fields(conditions, ("request_sha256", "data_sha256", "output_contract_sha256", "model",
                         "sampling", "output_budget", "environment", "data_access",
                         "measurement_scope"), "conditions")
    for name in ("request_sha256", "data_sha256", "output_contract_sha256"):
        _hash(conditions[name], name)
        if conditions[name] != case[name]:
            raise EvaluationError(f"{case['case_id']}: {name} does not match actual case material")
    model = conditions["model"]
    _fields(model, ("id", "revision", "digest"), "model")
    _text(model["id"], "model.id")
    for name in ("revision", "digest"):
        if model[name] is not None:
            _text(model[name], "model." + name)
    if model["revision"] is None and model["digest"] is None:
        raise EvaluationError("A pinned model revision or digest is required")
    for name in ("sampling", "environment"):
        if not isinstance(conditions[name], dict) or not conditions[name]:
            raise EvaluationError(f"{name}: declare the execution settings explicitly")
    budget = conditions["output_budget"]
    _fields(budget, ("max_output_tokens_per_call", "total_output_tokens_limit"), "output_budget")
    for name in budget:
        _number(budget[name], "output_budget." + name, integer=True)
    if not budget["max_output_tokens_per_call"]:
        raise EvaluationError("A positive per-call output budget is required")
    if budget["total_output_tokens_limit"] == 0:
        raise EvaluationError("An aggregate output cap must be positive or null (uncapped)")
    if conditions["data_access"] != {
        "pool": "entire_case_dataset", "availability": "all_materials_available", "truncation": "none",
    }:
        raise EvaluationError("Both methods must declare the entire case dataset available without truncation")
    if conditions["measurement_scope"] != MEASUREMENT_SCOPE:
        raise EvaluationError("Measurements must include the entire request, all model calls and retries")


def _measurements(measurements):
    _fields(measurements, MEASUREMENT_FIELDS, "measurements")
    for name in MEASUREMENT_FIELDS:
        if name != "cost":
            _number(measurements[name], name, integer=name.endswith(("tokens", "calls")))
    cost = measurements["cost"]
    if cost is not None:
        _fields(cost, ("amount", "currency"), "cost")
        if cost["amount"] is None:
            raise EvaluationError("Unknown cost must be null, not an amount-null object")
        _number(cost["amount"], "cost.amount")
        if not isinstance(cost["currency"], str) or not re.fullmatch(r"[A-Z]{3}", cost["currency"]):
            raise EvaluationError("Cost currency must be a three-letter uppercase code")


def _bundle(path: Path, method: str, cases: dict) -> dict:
    bundle = _read_json(path)
    _fields(bundle, ("schema_version", "method", "records"), "result bundle")
    if type(bundle["schema_version"]) is not int or bundle["schema_version"] != 1 or bundle["method"] != method:
        raise EvaluationError("Bundle schema or method does not match its input role")
    if not isinstance(bundle["records"], list):
        raise EvaluationError("Result records must be a list")
    records = {}
    for record in bundle["records"]:
        _fields(record, ("case_id", "execution_kind", "status", "conditions", "method_setup",
                         "raw_output", "raw_error", "execution_trace", "measurements"), "result record")
        case_id = record["case_id"]
        if not isinstance(case_id, str) or case_id not in cases or case_id in records:
            raise EvaluationError("Unknown or duplicate case ID in result bundle")
        if record["execution_kind"] not in ("live_model", "fixture"):
            raise EvaluationError("Execution kind must be live_model or fixture")
        if record["status"] not in ("success", "failure"):
            raise EvaluationError("Result status must be success or failure")
        if record["status"] == "failure" and record["raw_error"] is None:
            raise EvaluationError("A failed execution must preserve its raw error")
        if record["status"] == "success" and record["raw_error"] is not None:
            raise EvaluationError("A successful execution cannot carry a failure error")
        if not isinstance(record["execution_trace"], list):
            raise EvaluationError("Preserve an execution trace list; use [] when unavailable")
        _conditions(record, cases[case_id])
        setup = record["method_setup"]
        _fields(setup, ("prompt", "prompt_sha256", "instructions_complete", "material_delivery", "call_policy"),
                "method_setup")
        _hash(setup["prompt_sha256"], "prompt_sha256")
        if not isinstance(setup["prompt"], (str, dict, list)) or not setup["prompt"]:
            raise EvaluationError("Preserve the actual nonempty prompt/messages for PM audit")
        if canonical_sha256(setup["prompt"]) != setup["prompt_sha256"]:
            raise EvaluationError("Prompt SHA256 does not match its recorded prompt/messages")
        expected = ("full_prompt", "single_prompt") if method == "single_prompt_baseline" else (
            "tool_access", "agent_orchestration")
        if setup["instructions_complete"] is not True or (
            setup["material_delivery"], setup["call_policy"]
        ) != expected:
            raise EvaluationError("Method setup must declare complete instructions and the intended data access")
        _measurements(record["measurements"])
        records[case_id] = record
    if set(records) != set(cases):
        raise EvaluationError("Each method must include every manifest case, including failures")
    return records


def prepare_evaluation(manifest_path: Path, agent_path: Path, baseline_path: Path,
                       output_dir: Path, key_path: Path, seed: int) -> dict:
    """Reject incomparable records before writing new immutable files; return preparation status only."""
    inputs = [Path(path).resolve() for path in (manifest_path, agent_path, baseline_path)]
    output_dir, key_path = Path(output_dir).resolve(), Path(key_path).resolve()
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise EvaluationError("Seed must be an integer")
    if key_path == output_dir or key_path.is_relative_to(output_dir):
        raise EvaluationError("The PM mapping key must be outside the reviewer output directory")
    if output_dir.exists() or key_path.exists():
        raise EvaluationError("Output directory and PM key must be new; overwriting is forbidden")
    if any(path.is_relative_to(output_dir) or path == key_path for path in inputs):
        raise EvaluationError("Output paths cannot contain or overwrite an input")
    cases = _manifest(inputs[0])
    agent = _bundle(inputs[1], "agent", cases)
    baseline = _bundle(inputs[2], "single_prompt_baseline", cases)
    kinds = set()
    for case_id in cases:
        first, second = agent[case_id], baseline[case_id]
        if canonical_sha256(first["conditions"]) != canonical_sha256(second["conditions"]):
            raise EvaluationError(f"{case_id}: model, request, data or execution conditions differ")
        if first["execution_kind"] != second["execution_kind"]:
            raise EvaluationError(f"{case_id}: fixture and live results cannot be compared")
        currencies = {record["measurements"]["cost"]["currency"] for record in (first, second)
                      if record["measurements"]["cost"] is not None}
        if len(currencies) > 1:
            raise EvaluationError(f"{case_id}: cost currencies differ")
        kinds.add(first["execution_kind"])
    if len(kinds) != 1:
        raise EvaluationError("Separate fixture-only and live-model batches")
    execution_kind = kinds.pop()
    status = "fixture_only" if execution_kind == "fixture" else "live_results_awaiting_independent_review"
    rng = random.Random(seed)
    order = sorted(cases)
    rng.shuffle(order)
    review_cases, scorecards, mapping = [], [], []
    for case_id in order:
        methods = ["agent", "single_prompt_baseline"]
        rng.shuffle(methods)
        outputs = {}
        labels = {}
        for label, method in zip(("A", "B"), methods, strict=True):
            record = agent[case_id] if method == "agent" else baseline[case_id]
            outputs[label] = {name: deepcopy(record[name]) for name in ("status", "raw_output", "raw_error")}
            labels[label] = method
            scorecards.append({"case_id": case_id, "label": label, "reviewer_id": None,
                               "citation_checks": {"checked": None, "correct": None},
                               "product_model_errors": None, "duplicate_feature_proposals": None,
                               "modification_seconds": None, "notes": None})
        case = cases[case_id]
        review_cases.append({"case_id": case_id, "category": case["category"],
                             "request": deepcopy(case["request"]), "data_sha256": case["data_sha256"],
                             "output_contract_sha256": case["output_contract_sha256"], "outputs": outputs})
        mapping.append({"case_id": case_id, "labels": labels})
    common = {"schema_version": 1, "preparation_status": status, "execution_kind": execution_kind,
              "evaluation_complete": False, "blinding": "method_labels_only",
              "independent_review_required": True, "execution_verified_by_tool": False,
              "comparability_check": "case_file_hashes_and_declared_conditions_only"}
    review = {**common, "cases": review_cases}
    scorecard = {**common, "scorecards": scorecards}
    summary = {**common, "case_count": len(cases), "categories": {
        category: sum(case["category"] == category for case in cases.values()) for category in REQUIRED_CATEGORIES
    }}
    key = {**common, "prepared_at": datetime.now(UTC).isoformat(), "seed": seed,
           "mapping": mapping, "records": {"agent": agent, "single_prompt_baseline": baseline},
           "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in
                            zip(("manifest", "agent", "single_prompt_baseline"), inputs, strict=True)},
           "independence_and_execution_declarations_verified": False}
    # Every check above runs before creation. Exclusive creates also prevent race-time overwrites.
    key_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    with key_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(key, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    for name, value in (("review.json", review), ("scorecard.json", scorecard), ("preparation.json", summary)):
        with (output_dir / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True, help="Independent six-category case manifest")
    parser.add_argument("--agent-results", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New reviewer-only directory")
    parser.add_argument("--key-file", type=Path, required=True, help="New separate PM-only mapping file")
    parser.add_argument("--seed", type=int, required=True, help="Recorded only in the private PM key")
    args = parser.parse_args()
    try:
        result = prepare_evaluation(args.cases, args.agent_results, args.baseline_results,
                                    args.output_dir, args.key_file, args.seed)
    except (EvaluationError, OSError) as exc:
        parser.exit(2, f"Evaluation preparation rejected: {exc}\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
