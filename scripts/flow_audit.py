"""Bounded UX graph checks. No device simulation, safety certification or user prediction."""
import argparse
import json
from pathlib import Path
import sys


def audit(flow, known_sources):
    nodes = {n["id"]:n for n in flow["nodes"]}
    errors = []
    if len(nodes) != len(flow["nodes"]):
        errors.append("duplicate_node")
    if flow["start"] not in nodes:
        return ["missing_start"]
    for node in nodes.values():
        if not set(node.get("sources", [])) <= set(known_sources):
            errors.append(f"{node['id']}:unknown_source")
        for event, target in node.get("on", {}).items():
            if target not in nodes:
                errors.append(f"{node['id']}:{event}:missing_target")
    # Explore the finite graph without assuming that missing responses imply success.
    seen, pending = set(), [flow["start"]]
    while pending:
        nid = pending.pop()
        if nid in seen or nid not in nodes:
            continue
        seen.add(nid)
        pending.extend(nodes[nid].get("on", {}).values())
    for nid in set(nodes) - seen:
        errors.append(f"{nid}:unreachable")
    for requirement in flow["requirements"]:
        node = nodes.get(requirement["node"])
        if node is None:
            errors.append("requirement_node_missing")
            continue
        target = nodes.get(node.get("on", {}).get(requirement["event"]))
        if target is None:
            errors.append(f"{node['id']}:{requirement['event']}:missing_branch")
        elif target.get("kind") not in requirement["allowed_kinds"]:
            errors.append(f"{node['id']}:{requirement['event']}:wrong_outcome")
    for node in nodes.values():
        if node.get("kind") == "command":
            if not node.get("sources") or not node.get("requires"):
                errors.append(f"{node['id']}:unverified_command_contract")
            # The prototype is a UX model; no commands are sent to appliances.
        if node.get("kind") == "retry" and not (type(node.get("max_attempts")) is int
                                                  and 0 < node["max_attempts"] <= 2):
            errors.append(f"{node['id']}:unbounded_retry")
    return sorted(set(errors))


def trace(flow, events):
    nodes = {n["id"]:n for n in flow["nodes"]}
    nid, path = flow["start"], [flow["start"]]
    for event in events:
        target = nodes[nid].get("on", {}).get(event)
        if target is None:
            return {"status":"unhandled_event", "event":event,"path":path}
        if target not in nodes:
            return {"status":"missing_target", "path":path}
        nid = target
        path.append(nid)
    return {"status":nodes[nid]["kind"],"path":path}


def run(root):
    payload = json.loads((root/"research/atoz/flow_trials.json").read_text(encoding="utf-8"))
    results = []
    for case in payload["cases"]:
        before = audit(case["before"], payload["known_sources"])
        after = audit(case["after"], payload["known_sources"])
        traces = [{"events":t["events"], "expected":t["expected"],
                   "actual":trace(case["after"],t["events"])} for t in case["traces"]]
        results.append({"id":case["id"],"before":before,"after":after,"traces":traces,
                        "pass":bool(before) and not after and all(t["actual"]["status"]==t["expected"] for t in traces)})
    return {"mode":"Codex_authored_and_revised_graphs_with_executed_python_audit",
            "not_measured":["standalone model API","held-out generation quality","physical device behavior","real user benefit"],
            "results":results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=run(root)
    output=root/"research/atoz/flow_results.json"
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8")!=encoded:
            print("FAIL: flow output stale or missing")
            return 1
    else:
        output.write_text(encoded,encoding="utf-8",newline="\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if all(r["pass"] for r in result["results"]) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
