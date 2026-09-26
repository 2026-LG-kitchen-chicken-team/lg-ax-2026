"""Synthetic feasibility spike; no LLM, device connection or real cooking model."""
import json
import math


def inspect(flow, capabilities):
    if not isinstance(flow, list) or not flow:
        return ["empty_or_invalid_flow"]
    for step in flow:
        if not isinstance(step, dict) or not all(isinstance(step.get(k), str) and step[k]
                                               for k in ("id", "device", "action")):
            return ["invalid_step_schema"]
        if any(type(step.get(k)) not in (int, float) or not math.isfinite(step[k])
               for k in ("start", "duration")):
            return ["invalid_time_schema"]
        if not isinstance(step.get("after", []), list) or not all(isinstance(v, str) for v in step.get("after", [])):
            return ["invalid_dependency_schema"]
    issues = []
    ids = [step["id"] for step in flow]
    if len(ids) != len(set(ids)):
        return ["duplicate_step_id"]
    by_id = {step["id"]: step for step in flow}
    for step in flow:
        sid = step["id"]
        if step["duration"] <= 0 or step["start"] < 0:
            issues.append(f"{sid}:invalid_time")
        if step["action"] not in capabilities.get(step["device"], []):
            issues.append(f"{sid}:unsupported_action")
        for dependency in step.get("after", []):
            parent = by_id.get(dependency)
            if parent is None:
                issues.append(f"{sid}:missing_dependency")
            elif step["start"] < parent["start"] + parent["duration"]:
                issues.append(f"{sid}:dependency_not_finished")
    # Single-capacity resource model, synthetic timings, not a physical twin.
    for i, left in enumerate(flow):
        for right in flow[i + 1:]:
            if left["device"] == right["device"] and max(left["start"], right["start"]) < min(
                left["start"] + left["duration"], right["start"] + right["duration"]
            ):
                issues.append(f"{left['id']}+{right['id']}:resource_overlap")
    visiting, visited = set(), set()

    def visit(sid):
        if sid in visiting:
            return True
        if sid in visited:
            return False
        visiting.add(sid)
        for parent in by_id[sid].get("after", []):
            if parent in by_id and visit(parent):
                return True
        visiting.remove(sid)
        visited.add(sid)
        return False

    if any(visit(sid) for sid in ids):
        issues.append("dependency_cycle")
    return sorted(set(issues))


def examples():
    caps = {"oven": ["heat"], "dishwasher": ["wash"], "person": ["load"]}
    valid = [
        {"id": "load", "device": "person", "action": "load", "start": 0, "duration": 5},
        {"id": "heat", "device": "oven", "action": "heat", "start": 5, "duration": 20, "after": ["load"]},
    ]
    invalid = [dict(s) for s in valid]
    invalid[1] = dict(invalid[1], start=1)
    invalid.append({"id": "second", "device": "oven", "action": "heat", "start": 10, "duration": 10})
    unsupported = [dict(valid[1], action="robot_load", after=[])]
    return caps, {"valid": valid, "dependency_and_overlap": invalid, "unsupported": unsupported}


if __name__ == "__main__":
    caps, cases = examples()
    print(json.dumps({"mode": "synthetic_rule_check_no_llm_no_device", "results": {
        name: inspect(flow, caps) for name, flow in cases.items()
    }}, ensure_ascii=False, indent=2))
