"""Replay recorded semantic declarations without generating, correcting, or scoring them."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest
from lgax_core.semantic_review import review_semantics

ROOT = Path(__file__).resolve().parents[4]
STAGES = ("need_extract", "product_compare", "concept_draft")
LIST_FIELDS = ("needs", "desired_outcomes", "gaps", "concepts", "review_assessments",
               "gap_assessments", "concept_assessments", "questions", "hold_reasons",
               "unresolved", "no_candidate_reasons")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON fields are not replayable")
            result[key] = value
        return result

    def invalid_number(_value):
        raise ValueError("Non-finite JSON is not replayable")

    return json.loads(path.read_text("utf-8-sig"), object_pairs_hook=unique_fields,
                      parse_constant=invalid_number)


def legacy_snapshots(execution: dict, call_index: int) -> tuple[dict, dict]:
    """Recover an old review's exact state from successful tool events, never failed retries.

    Older rejected reviews lack reviewed_output. The reconstruction is usable only
    when its complete canonical hash equals the original review's recorded hash.
    """
    call = execution["model_calls"][call_index]
    context = call["request_context"]
    states = {}
    for event in execution["trace"]:
        if event["operation"] in ("semantic_review", "semantic_review_error") and event["inputs"] == context:
            break
        if event["operation"] in STAGES and event["outputs"].get("ok") is True:
            states[event["operation"]] = event["outputs"]["data"]["result"]
    else:
        raise ValueError("The original semantic review event is missing")
    payload = deepcopy(execution["original_input"])
    payload["revision_count"] = context["revision_count"]
    output = {"input_sha256": input_digest(payload), "model_id": payload["product"]["model_id"],
              "document_version": payload["product"]["document_version"],
              "revision_count": payload["revision_count"], "status": "completed",
              **{key: [] for key in LIST_FIELDS}}
    for skill in STAGES:
        require(skill in states, "A successful original stage is missing")
        matches = [previous["generated"]["data"] for previous in execution["model_calls"][:call_index]
                   if previous["skill_id"] == skill and
                   previous.get("generated", {}).get("data", {}).get("result") == states[skill]]
        require(bool(matches), "Successful tool output has no matching original model declaration")
        declaration = matches[-1]
        for key, value in declaration["result"].items():
            if key in output:
                output[key] = deepcopy(value)
        for key in ("review_assessments", "gap_assessments", "concept_assessments"):
            if key in declaration:
                output[key] = deepcopy(declaration[key])
        for key in ("questions", "hold_reasons", "no_candidate_reasons"):
            output[key] = list(dict.fromkeys(output[key] + declaration[key]))
    require(not output["hold_reasons"] and not output["unresolved"],
            "Legacy reconstruction only supports a completed analysis entering review")
    return payload, output


def replay_review(execution: dict, call_index: int) -> dict:
    call = execution["model_calls"][call_index]
    context = call["request_context"]
    report = call["generated"]["data"]
    require(json.loads(call["raw_response"]) == report, "Raw response and generated declaration differ")
    require(not list(Draft202012Validator(call["schema"]).iter_errors(report)),
            "The declaration differs from the originally enforced schema")
    saved = [item for item in execution["semantic_reviews"] if
             item["report"]["input_sha256"] == context["input_sha256"] and
             item["report"]["output_sha256"] == context["output_sha256"]]
    require(len(saved) <= 1, "Ambiguous saved semantic review")
    if saved:
        require(saved[0]["report"] == report, "Saved review differs from its original model declaration")
        payload, output = saved[0]["reviewed_input"], saved[0]["reviewed_output"]
        binding = "original_reviewed_snapshots"
    else:
        payload, output = legacy_snapshots(execution, call_index)
        binding = "hash_verified_successful_stage_reconstruction"
    require(type(context["revision_count"]) is int and 0 <= context["revision_count"] <= 2,
            "Invalid recorded correction count")
    require(input_digest(payload) == context["input_sha256"] == call["input_sha256"] == report["input_sha256"],
            "Original input binding changed")
    require(input_digest(output) == context["output_sha256"] == report["output_sha256"],
            "Original candidate output binding changed")
    require(all(payload[key] == context[key] for key in ("request", "product", "sources", "features", "revision_count")),
            "Review context differs from its original input")
    require(output["concepts"] == context["concepts"] and call["revision_count"] == context["revision_count"],
            "Review context differs from its original candidates or count")
    original_events = [event for event in execution["trace"] if
                       event["operation"] in ("semantic_review", "semantic_review_error") and
                       event["inputs"] == context]
    require(len(original_events) == 1, "A unique original review event is required")
    if saved:
        require(original_events[0]["outputs"] == {"report": report, "decision": saved[0]["decision"]},
                "Saved review differs from its original validation event")
    try:
        validation = {"status": "validated", "decision": review_semantics(payload, output, report)}
    except DomainError as error:
        validation = {"status": "rejected", "error": error.response()["error"]}
    return {"call_index": call_index, "revision_count": context["revision_count"],
            "input_sha256": input_digest(payload), "output_sha256": input_digest(output),
            "report_sha256": input_digest(report), "snapshot_binding": binding,
            "binding_verified": True, "recorded_validation": original_events[0]["outputs"],
            "recorded_decision": saved[0]["decision"] if saved else None,
            "current_validation": validation}


def replay_execution(execution: dict) -> dict:
    require(execution["execution_kind"] in ("live_model", "fixture"), "Unknown original execution kind")
    calls = execution["model_calls"]
    reviews = [replay_review(execution, i) for i, call in enumerate(calls) if call["stage"] == "review"]
    measurements = {}
    for name in ("prompt_eval_count", "eval_count"):
        values = [call.get("metadata", {}).get(name) for call in calls]
        measured = all(type(value) is int and value >= 0 for value in values)
        measurements[name] = sum(values) if measured else None
    return {"original_execution_kind": execution["execution_kind"], "original_status": execution["status"],
            "recorded_model_calls": len(calls), "original_errors": execution["errors"],
            "models": [{"id": model_id, "digest": digest} for model_id, digest in
                       dict.fromkeys((call["model_id"], call["model_digest"]) for call in calls)],
            "recorded_token_totals_including_failed_calls": measurements,
            "review_calls": len(reviews), "reviews": reviews,
            "meaning_quality_scored": False}


def replay_files(paths: list[Path]) -> dict:
    require(bool(paths), "At least one original record is required")
    require(len({path.resolve() for path in paths}) == len(paths), "Duplicate original files would double count calls")
    sources, executions = [], []
    for path in paths:
        data = read_json(path)
        source_index = len(sources)
        label = path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else path.name
        sources.append({"path": label, "sha256": sha256(path)})
        records = [("execution", None, data)] if "model_calls" in data else [
            (name, data[name]["run"]["id"], data[name]["output"]["planning_execution"]) for name in ("first", "second")]
        for name, run_id, execution in records:
            executions.append({"source_index": source_index, "record": name, "run_id": run_id,
                               **replay_execution(execution)})
    return {"schema_version": 1, "execution_kind": "recorded_response_replay", "new_model_calls": 0,
            "sources": sources, "executions": executions,
            "validator_sources": [{"path": str(path.relative_to(ROOT).as_posix()), "sha256": sha256(path)} for path in
                                  (Path(__file__).resolve(), ROOT / "packages/core/src/lgax_core/semantic_review.py",
                                   ROOT / "packages/core/src/lgax_core/judgement_contract.py")],
            "meaning_quality_scored": False, "baseline_comparison_complete": False,
            "limitation": "Replays original declarations against current literal and scope guards. No new model output, correction result, independent quality score, or live improvement is established."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a fresh output file; original records must be preserved")
    result = replay_files(args.record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"executions": len(result["executions"]),
                      "reviews": sum(record["review_calls"] for record in result["executions"]),
                      "new_model_calls": 0, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
