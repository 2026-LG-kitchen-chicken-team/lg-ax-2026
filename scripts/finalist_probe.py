"""Small deterministic feasibility probes, not contestant Agent or model evaluation."""
import argparse
import copy
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/theme_selection"


def screen_space(product, context):
    if context["market"] != product["market"]:
        return {"status": "hold_market_mismatch", "violations": []}
    if context["unit"] != product["unit"]:
        return {"status": "hold_unit_mismatch", "violations": []}
    needed = {"width_limit": product["width"] + 2 * product["side_gap"],
              "height_limit": product["height"] + product["top_gap"],
              "open_width_limit": product["open_width"]}
    missing = sorted(set(needed) - set(context))
    violations = [{"field": k, "required": v, "available": context[k]}
                  for k, v in needed.items() if k in context and context[k] < v]
    status = "reject_constraints" if violations else ("hold_missing_information" if missing else "limited_screen_pass")
    return {"status": status, "violations": violations, "missing": missing,
            "required": needed, "installation_approval": False}


def solve(tasks, available, deadline=None):
    """Enumerate priority orders; list-schedule each at its earliest feasible slot."""
    if not tasks or len(tasks) > 8:
        return {"status": "unsupported_task_count"}
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        return {"status": "invalid_ids"}
    for t in tasks:
        if type(t.get("duration")) is not int or t["duration"] <= 0:
            return {"status": "needs_duration", "task": t["id"]}
        if not t["resources"] or not set(t["resources"]) <= set(available):
            return {"status": "unavailable_resource", "task": t["id"]}
        if not set(t["after"]) <= set(ids):
            return {"status": "missing_dependency", "task": t["id"]}
    best = None
    for order in itertools.permutations(tasks):
        placed = {}
        for t in order:
            if not set(t["after"]) <= placed.keys():
                break
            start = max((placed[p]["end"] for p in t["after"]), default=0)
            while True:
                collisions = [p for p in placed.values()
                              if set(p["resources"]) & set(t["resources"])
                              and max(start, p["start"]) < min(start+t["duration"], p["end"])]
                if not collisions:
                    break
                start = max(p["end"] for p in collisions)
            placed[t["id"]] = {"id": t["id"], "resources": t["resources"],
                               "start": start, "end": start+t["duration"]}
        else:
            makespan = max(p["end"] for p in placed.values())
            if best is None or makespan < best["makespan"]:
                best = {"makespan": makespan, "schedule": sorted(placed.values(), key=lambda p: (p["start"],p["id"]))}
    if best is None:
        return {"status": "dependency_cycle"}
    best["status"] = "feasible" if deadline is None or best["makespan"] <= deadline else "deadline_unmet"
    return best


def verify_schedule(tasks, result):
    """Check constraints independently of the scheduling search."""
    if "schedule" not in result:
        return None
    rows = result["schedule"]
    by_id = {p["id"]: p for p in rows}
    errors = []
    if len(by_id) != len(rows) or set(by_id) != {t["id"] for t in tasks}:
        errors.append("task_set")
        return errors
    for t in tasks:
        p = by_id[t["id"]]
        if set(p["resources"]) != set(t["resources"]):
            errors.append("resources")
        if p["start"] < 0 or p["end"]-p["start"] != t["duration"]:
            errors.append("duration")
        if any(by_id[parent]["end"] > p["start"] for parent in t["after"]):
            errors.append("precedence")
    for a,b in itertools.combinations(rows,2):
        if (set(a["resources"]) & set(b["resources"])
                and max(a["start"],b["start"]) < min(a["end"],b["end"])):
            errors.append("resource_overlap")
    if result["makespan"] != max(p["end"] for p in rows):
        errors.append("makespan")
    return errors


def run():
    inputs = json.loads((DATA/"probe_inputs.json").read_text(encoding="utf-8"))
    space = [{"case": c["id"], "model": p["id"], "result": screen_space(p,c)}
             for c in inputs["space_cases"] for p in inputs["products"]]
    changed = copy.deepcopy(inputs["tasks"])
    next(t for t in changed if t["id"] == "heat_a")["duration"] = 20
    unknown = copy.deepcopy(inputs["tasks"])
    unknown[0]["duration"] = None
    cyclic = copy.deepcopy(inputs["tasks"])
    cyclic[0]["after"] = ["finish_a"]
    variants = [("normal",inputs["tasks"],inputs["resources"],30),
                ("longer_task",changed,inputs["resources"],30),
                ("oven_unavailable",inputs["tasks"],["person"],30),
                ("missing_duration",unknown,inputs["resources"],30),
                ("impossible_deadline",inputs["tasks"],inputs["resources"],20),
                ("dependency_cycle",cyclic,inputs["resources"],30)]
    schedules = []
    for name,tasks,resources,deadline in variants:
        result = solve(tasks,resources,deadline)
        schedules.append({"case":name,"result":result,"constraint_errors":verify_schedule(tasks,result)})
    return {"mode":inputs["mode"],"space":space,"schedule":schedules,
            "serial_duration":sum(t["duration"] for t in inputs["tasks"]),
            "limitations":inputs["space_limitations"]+inputs["schedule_limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    args = parser.parse_args()
    results = run()
    encoded = json.dumps(results,ensure_ascii=False,indent=2)+"\n"
    path = DATA/"probe_results.json"
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != encoded:
            raise SystemExit("stale finalist probe results")
    else:
        path.write_text(encoded,encoding="utf-8",newline="\n")
    assert all(not r["constraint_errors"] for r in results["schedule"])
    print(json.dumps({"space_cases":len(results["space"]),"schedule_cases":len(results["schedule"]),
                      "schedule_states":{x["case"]:x["result"]["status"] for x in results["schedule"]},
                      "normal_makespan":results["schedule"][0]["result"]["makespan"],
                      "changed_makespan":results["schedule"][1]["result"]["makespan"]},indent=2))


if __name__ == "__main__":
    main()
