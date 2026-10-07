"""Independent expectations from PM's three original 122B executions (R5, record 최길웅-20261007-051).

Reads the exact original bytes (SHA-256 checked against the PM manifest) and derives, without any web code, what an
honest screen/export must show for each run: status and decision, internal revisions and end reason, error codes and
their public validation detail codes, the model's questions/hold reasons/unresolved, model calls and reported tokens,
review counts, turned-down candidates, the request and every source ID with its kind and text hash. No model is called.
"""
import argparse
import hashlib
import json
from pathlib import Path

PUBLIC_CODES = {"REVIEW_SCOPE_MISMATCH", "REVIEW_REASON_MISSING", "REVIEW_ASSESSMENT_COVERAGE", "UNCERTAINTY_CONTEXT_MISSING",
                "UNCERTAINTY_SCOPE_MISMATCH", "UNCERTAINTY_FIELD_MISSING", "EMPTY_NEEDS_WITHOUT_JUDGEMENT", "NON_COMPLAINT_AS_NEED"}


def total(values):
    return sum(values) if values and all(isinstance(v, (int, float)) for v in values) else None


def expected(execution: dict) -> dict:
    output = execution.get("output") or {}
    decision = execution.get("decision") or {}
    calls = execution["model_calls"]
    meta = [call.get("metadata") or {} for call in calls]
    budget = execution.get("correction_budget") or {}
    rejected = execution.get("rejected_output") or {}
    reviews = [step for step in execution["trace"] if step.get("operation") == "review_decision"]
    errors = []
    for error in execution["errors"]:
        details = error.get("details") if isinstance(error.get("details"), dict) else {}
        codes = [v.get("code") for v in details.get("violations", []) if isinstance(v, dict) and v.get("code") in PUBLIC_CODES]
        if details.get("code") in PUBLIC_CODES:
            codes.append(details["code"])
        errors.append({"code": error["code"], "public_detail_codes": codes,
                       "conflicting_paths": details.get("conflicting_paths") if error["code"] == "VALIDATION_FAILED" else None,
                       "schema_mismatch": details.get("reason") == "schema_mismatch"})
    request = execution["original_input"]["request"]
    return {
        "status": execution["status"], "execution_kind": execution["execution_kind"],
        "decision_action": decision.get("action"),
        "revision_count": budget.get("revision_count", execution["input"]["revision_count"]), "max_revisions": budget.get("max_revisions", 2),
        "terminal_reason": budget.get("terminal_reason"),
        "check_rounds": [{"action": (s.get("outputs") or {}).get("action"), "codes": [v.get("code") for v in (s.get("outputs") or {}).get("violations", [])]} for s in reviews],
        "errors": errors,
        "questions": output.get("questions", []), "hold_reasons": output.get("hold_reasons", []), "unresolved": output.get("unresolved", []),
        "no_candidate_reasons": output.get("no_candidate_reasons", []),
        "accepted_concepts": [c["id"] for c in output.get("concepts", [])] if decision.get("action") == "accept" else [],
        "rejected_concepts": [c["id"] for c in rejected.get("concepts", [])],
        "model_calls": len(calls), "model_ids": sorted({c["model_id"] for c in calls}),
        "prompt_tokens": total([m.get("prompt_eval_count") for m in meta]), "output_tokens": total([m.get("eval_count") for m in meta]),
        "model_elapsed_ms": total([m.get("elapsed_ms") for m in meta]),
        "semantic_reviews": len(execution.get("semantic_reviews") or []), "no_candidate_reviews": len(execution.get("no_candidate_reviews") or []),
        "trusted_collector_verified": (execution.get("skill_trace") or {}).get("trusted_collector_verified"),
        "request": {key: request[key] for key in ("product_group", "model_ids", "dataset_version", "improvement_task", "exclusions")},
        "product": execution["original_input"]["product"],
        "sources": [{"id": s["id"], "source_type": s["source_type"], "source_kind": s["source_kind"], "model_id": s["model_id"],
                     "document_version": s["document_version"], "text_sha256": hashlib.sha256(s["text"].encode("utf-8")).hexdigest()}
                    for s in execution["original_input"]["sources"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True, help="directory with the three *.output.json (or *.json) files")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text("utf-8"))
    result = {"kind": "r5_independent_expectations", "model": manifest["model"], "dataset_kind": manifest["dataset_kind"],
              "handoff_base_commit": manifest["handoff_base_commit"], "cases": {}}
    for item in manifest["files"]:
        name = item["path"].replace(".output.json", "")
        path = next(p for p in (args.originals / item["path"], args.originals / f"{name}.json") if p.exists())
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != item["sha256"]:
            raise SystemExit(f"{name}: SHA-256 differs from the PM manifest")
        execution = json.loads(raw)
        case = expected(execution)
        if case["status"] != item["status"] or case["model_calls"] != item["model_calls"]:
            raise SystemExit(f"{name}: status/model_calls differ from the PM manifest")
        result["cases"][name] = {"sha256": digest, **case}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, case in result["cases"].items():
        print(name, case["status"], case["decision_action"], f"rev {case['revision_count']}/{case['max_revisions']}", case["terminal_reason"],
              "errors", [e["code"] + str(e["public_detail_codes"] or "") for e in case["errors"]], "calls", case["model_calls"],
              "tokens", case["prompt_tokens"], case["output_tokens"], "q/h/u", len(case["questions"]), len(case["hold_reasons"]), len(case["unresolved"]),
              "rejected", case["rejected_concepts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
