"""Execute narrow candidate Skills on curated inputs; no LLM call or device control.

This does not generate new ideas, parse raw documents, or score product value.
Codex authors concept seeds/input records; this program applies explicit rules.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

try:
    from .scenario_spike import inspect
except ImportError:
    from scenario_spike import inspect

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/topic_trial"


def has_sources(ids, known):
    return bool(ids) and set(ids) <= known


def assess_concepts(request, known):
    """Compare curated function labels, preserving scope and missing-evidence status."""
    results = []
    for concept in request["concepts"]:
        supported = has_sources(concept["source_ids"], known)
        matches = [feature for feature in request["features"]
                   if concept["proposed_function"] in feature["functions"]
                   and has_sources(feature["source_ids"], known)]
        invalid_feature_sources = any(not has_sources(f["source_ids"], known)
                                      for f in request["features"])
        if not supported or invalid_feature_sources:
            decision = "hold_missing_evidence"
        elif matches:
            decision = "deprioritize_existing_function"
        else:
            decision = "investigate_hypothesis"
        results.append({
            "id": concept["id"], "human_task": concept["human_task"],
            "concept_seed": concept["concept_seed"], "decision": decision,
            "source_ids": concept["source_ids"],
            "counterevidence": [{"feature_id": f["id"], "source_ids": f["source_ids"],
                                  "scope": f["scope"], "kind": f["kind"]} for f in matches],
            "target_coverage": ("listed_in_matching_scope" if any(
                f["scope"] == request["target_scope"] for f in matches) else "unverified"),
            "novelty": "not_established",
            "demand": "unmeasured",
            "next_validation": ("기존 기능과 다른 추가 가치가 있는지 다시 정의" if matches else
                                "실제 사용자에게 수고·대처 행동을 확인하고 더 넓은 제품 기능 조사"),
        })
    return results


def repair_flow(request):
    """Greedy topological scheduling of a synthetic profile, not a cooking simulator."""
    original = copy.deepcopy(request["flow"])
    findings = inspect(original, request["capabilities"])
    fixable = (":dependency_not_finished", ":resource_overlap")
    if any(not issue.endswith(fixable) for issue in findings):
        return {"status": "needs_designer_input", "before": findings,
                "after": findings, "flow": original, "profile_kind": request["profile_kind"]}
    pending = copy.deepcopy(original)
    finished, busy_until, repaired = {}, {}, []
    while pending:
        ready = next((step for step in pending if all(
            parent in finished for parent in step.get("after", []))), None)
        if ready is None:
            return {"status": "needs_designer_input", "before": findings,
                    "after": ["unresolvable_dependencies"], "flow": original}
        start = max([ready["start"], busy_until.get(ready["device"], 0)] +
                    [finished[parent] for parent in ready.get("after", [])])
        ready["start"] = start
        finished[ready["id"]] = start + ready["duration"]
        busy_until[ready["device"]] = finished[ready["id"]]
        repaired.append(ready)
        pending.remove(ready)
    after = inspect(repaired, request["capabilities"])
    finish = max(finished.values())
    if finish > request["deadline"]:
        after.append("deadline_exceeded")
    return {"status": "needs_designer_input" if after else "consistent_synthetic_schedule",
            "before": findings, "after": after, "flow": repaired,
            "finish": finish, "deadline": request["deadline"],
            "profile_kind": request["profile_kind"],
            "limitation": "Neither task durations nor UX usefulness validated on real users or devices."}


def design_completion_ux(request):
    """Generate a bounded UX outline from an explicit state; never infer readiness."""
    if request["goal"] not in {"now", "later"} or request["readiness"] not in {"unknown", "wet", "ready"}:
        raise ValueError("invalid goal or readiness")
    if not request["cycle_complete"]:
        branch = "await_cycle"
    elif not request["user_available"]:
        branch = "await_user"
    elif request["readiness"] == "unknown":
        branch = "ask_readiness"
    elif request["readiness"] == "wet":
        branch = "user_decides_next_action"
    else:
        branch = "confirm_storage"
    emphasis = "needed_items_first" if request["goal"] == "now" else "later_review"
    return {
        "status": "draft_ux_requires_user_validation", "source_ids": request["source_ids"],
        "entry": branch, "emphasis": emphasis, "ready": request["readiness"] == "ready"
        and request["cycle_complete"] and request["user_available"],
        "nodes": [
            {"id":"await_cycle", "label":"기기 종료 확인 대기", "next":"ask_readiness"},
            {"id":"await_user", "label":"사용자 확인 대기", "next":"ask_readiness"},
            {"id":"ask_readiness", "label":"필요한 식기의 상태를 직접 확인해 주세요",
             "branches":{"unknown":"await_user", "wet":"user_decides_next_action", "ready":"confirm_storage"}},
            {"id":"user_decides_next_action", "label":"모델·식기 안내를 확인하고 다음 행동을 선택",
             "branches":{"defer":"await_user", "recheck":"ask_readiness"}},
            {"id":"confirm_storage", "label":"사용 준비·정리 완료를 사용자가 확인", "next":"done"},
            {"id":"done", "label":"사용자가 완료 확인"}
        ],
        "unknowns": ([] if request["model_known"] else ["model_specific_guidance"]),
        "device_commands": [], "event_kind": request["event_kind"],
        "limitation": "User statements are inputs; no sensor inference, sterilization claim, or measured UX benefit."
    }


def execute(inputs, sources):
    known = {s["id"] for s in sources["sources"]}
    runs = []
    def record(candidate, case, output, assertions):
        runs.append({"candidate": candidate, "case": case, "output": output,
                     "checks": assertions, "pass": all(assertions.values())})

    base = assess_concepts(inputs["a4"], known)
    by_id = {r["id"]: r for r in base}
    record("A4", "baseline_real_sources", base, {
        "existing_cycle_not_new": by_id["auto_cycle"]["decision"] == "deprioritize_existing_function",
        "existing_notification_not_new": by_id["cycle_notice"]["decision"] == "deprioritize_existing_function",
        "remaining_tasks_are_hypotheses": all(by_id[k]["decision"] == "investigate_hypothesis"
                                               for k in ("load_review", "readiness")),
        "foreign_feature_not_local_support": by_id["auto_cycle"]["target_coverage"] == "unverified"})
    changed = copy.deepcopy(inputs["a4"])
    changed["features"].append({"id":"synthetic_loading_feature", "source_ids":["TEST_ONLY"],
        "scope": changed["target_scope"], "functions":["confirm_loading_clearance"],
        "kind":"synthetic_adversarial_counterexample_not_market_fact"})
    out = assess_concepts(changed, known | {"TEST_ONLY"})
    record("A4", "synthetic_counterevidence_added", out, {
        "changes_judgment": out[0]["decision"] == "deprioritize_existing_function",
        "scope_preserved": out[0]["target_coverage"] == "listed_in_matching_scope"})
    missing = copy.deepcopy(inputs["a4"])
    missing["concepts"][0]["source_ids"] = []
    out = assess_concepts(missing, known)
    record("A4", "missing_source", out, {"abstains":out[0]["decision"] == "hold_missing_evidence"})

    out = repair_flow(inputs["b1"])
    record("B1", "baseline_synthetic_profile", out, {"consistent":out["after"] == []})
    changed = copy.deepcopy(inputs["b1"])
    changed["flow"][1]["start"] = 1
    changed["flow"].append({"id":"second_wash", "device":"dishwasher", "action":"wash", "start":10, "duration":5})
    out = repair_flow(changed)
    record("B1", "dependency_and_resource_conflict", out, {
        "detects_conflict":bool(out["before"]), "repair_consistent":out["after"] == []})
    changed = copy.deepcopy(inputs["b1"])
    changed["capabilities"]["dishwasher"] = []
    out = repair_flow(changed)
    record("B1", "capability_removed", out, {"asks_instead_of_inventing":out["status"] == "needs_designer_input"})

    out = design_completion_ux(inputs["b5"])
    record("B5", "cycle_end_readiness_unknown", out, {
        "cycle_end_not_ready":not out["ready"], "asks_user":out["entry"] == "ask_readiness"})
    changed = copy.deepcopy(inputs["b5"])
    changed["readiness"] = "wet"
    out = design_completion_ux(changed)
    record("B5", "user_reports_water", out, {
        "does_not_force_ready":not out["ready"], "retains_model_unknown":bool(out["unknowns"]),
        "no_invented_device_action":out["device_commands"] == []})
    changed = copy.deepcopy(inputs["b5"])
    changed.update(goal="later", user_available=False)
    out = design_completion_ux(changed)
    record("B5", "goal_changed_user_absent", out, {
        "changes_flow_emphasis":out["emphasis"] == "later_review",
        "unanswered_remains_pending":out["entry"] == "await_user" and not out["ready"]})
    return {"execution_mode":"curated_inputs_and_deterministic_skills_no_llm_api",
            "input_author":"Codex in current conversation; not an independent evaluator",
            "case_count":len(runs), "passed":sum(r["pass"] for r in runs), "runs":runs,
            "limitations":["Development probes, not a model benchmark or held-out evaluation",
                           "Passing rules does not establish demand, novelty or commercial value",
                           "No model cost, latency, generation accuracy or device measurements"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed replay output without changing files")
    args = parser.parse_args()
    inputs = json.loads((DATA / "pilot_inputs.json").read_text(encoding="utf-8"))
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    result = execute(inputs, sources)
    result["input_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA / "pilot_inputs.json", DATA / "sources.json", Path(__file__)]}
    output = DATA / "pilot_outputs.json"
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != serialized:
            print("FAIL: replay output missing or stale")
            return 1
    else:
        output.write_text(serialized, encoding="utf-8", newline="\n")
    print(f"Candidate Skill probes: {result['passed']}/{result['case_count']} passed; no LLM API/device run")
    return 0 if result["passed"] == result["case_count"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
