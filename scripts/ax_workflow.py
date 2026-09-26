"""Codex-native A-to-Z workflow: prepare task packets, validate artifacts, resume.

The current Codex conversation executes packet actions using its tools.
This CLI does not silently run an LLM, create agents, or upload submissions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = "harness/atoz_state.json"
CONFIG = "harness/atoz.json"


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def fingerprint(root, path):
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("artifact must be an existing file inside this repository")
    return {"path":target.relative_to(root).as_posix(), "sha256":hashlib.sha256(target.read_bytes()).hexdigest()}


def valid_record(root, record):
    try:
        return fingerprint(root, record["path"]) == record
    except (KeyError, ValueError, OSError):
        return False


def completed(root, config, state):
    if state.get("config") and not valid_record(root, state["config"]):
        return set()
    if state.get("request_sha256") and state["request_sha256"] != hashlib.sha256(state["request"].encode()).hexdigest():
        return set()
    good = set()
    for stage in config["stages"]:
        record = state["completed"].get(stage["id"])
        if (record and set(stage["needs"]) <= good and valid_record(root, record["artifact"])
                and all(valid_record(root, e) for e in record.get("evidence", []))):
            good.add(stage["id"])
    return good


def packet(root, config, state, requested=None):
    done = completed(root, config, state)
    eligible = [s for s in config["stages"] if s["id"] not in done and set(s["needs"]) <= done]
    if requested:
        stage = next((s for s in config["stages"] if s["id"] == requested), None)
        if stage is None or not set(stage["needs"]) <= done:
            raise ValueError("unknown stage or prerequisites not complete")
    elif eligible:
        stage = eligible[0]
    else:
        return {"complete":len(done) == len(config["stages"]), "next":None}
    return {"stage":stage["id"], "title":stage["title"], "executor":config["executor"],
            "objective":config["objective"], "user_request":state["request"],
            "actions":stage["actions"], "required_content":stage["fields"],
            "inputs":[state["completed"][s]["artifact"] for s in stage["needs"]],
            "artifact_path":f"harness/runs/current/{stage['id']}.json",
            "envelope":{"stage":stage["id"], "content":{f:"REPLACE_WITH_ACTUAL_RESULT" for f in stage["fields"]},
                        "evidence_paths":[], "review":{"by":"Codex", "limitations":["actual limitations"]}},
            "finish_command":f"python scripts/ax_workflow.py finish {stage['id']} harness/runs/current/{stage['id']}.json",
            "ready_stages":[s["id"] for s in eligible]}


def artifact_errors(root, stage, artifact, config, state):
    errors = []
    if artifact.get("stage") != stage["id"]:
        errors.append("artifact stage mismatch")
    content = artifact.get("content", {})
    if not isinstance(content, dict):
        return ["content must be an object"]
    for key in stage["fields"]:
        if not content.get(key) or "REPLACE_WITH_ACTUAL_RESULT" in json.dumps(content[key]):
            errors.append(f"missing actual result: {key}")
    review = artifact.get("review", {})
    if not review.get("by") or not review.get("limitations"):
        errors.append("named review and explicit limitations required")
    paths = artifact.get("evidence_paths", [])
    if not isinstance(paths, list) or not paths:
        errors.append("local evidence paths required")
    else:
        for path in paths:
            try:
                fingerprint(root, path)
            except (ValueError, OSError, TypeError):
                errors.append("invalid evidence path")
    sid = stage["id"]
    if sid == "ideate":
        candidates = content.get("candidates", [])
        if (not isinstance(candidates, list) or len(candidates) < 6
                or not all(isinstance(c, dict) for c in candidates)):
            errors.append("at least six structured candidates required")
        else:
            ids = [c.get("id") for c in candidates]
            if len(set(ids)) != len(ids) or not all(ids):
                errors.append("unique candidate ids required")
            for theme in ("A", "B"):
                if sum(c.get("theme") == theme for c in candidates) < 3:
                    errors.append("at least three candidates per theme required")
            for candidate in candidates:
                if not all(candidate.get(k) for k in ("user","problem","loop","hardest","demo","sources")):
                    errors.append("candidate lacks work definition or evidence")
    if sid == "research":
        sources = content.get("sources", [])
        if not isinstance(sources, list) or len(sources) < 4 or not all(
            isinstance(s, dict) and all(s.get(k) for k in ("id","url","supports","limitations")) for s in sources):
            errors.append("at least four sources with provenance required")
    if sid in ("select", "design") and content.get("candidate_id"):
        prior = state["completed"].get("ideate")
        if prior:
            candidates = read(root, prior["artifact"]["path"])["content"]["candidates"]
            if content["candidate_id"] not in {c["id"] for c in candidates}:
                errors.append("selected candidate not in exploration")
        if sid == "design":
            chosen = read(root, state["completed"]["select"]["artifact"]["path"])["content"]["candidate_id"]
            if content["candidate_id"] != chosen:
                errors.append("design and selection disagree")
    return errors


def finish(root, config, state, sid, path):
    task = packet(root, config, state, sid)
    stage = next(s for s in config["stages"] if s["id"] == sid)
    stamp = fingerprint(root, path)
    artifact = read(root, stamp["path"])
    errors = artifact_errors(root, stage, artifact, config, state)
    if errors:
        raise ValueError("; ".join(errors))
    state["completed"][sid] = {"artifact":stamp,
        "evidence":[fingerprint(root, p) for p in artifact["evidence_paths"]],
        "finished_at":datetime.now(timezone.utc).isoformat(timespec="seconds")}
    state["config"] = fingerprint(root, CONFIG)
    state["request_sha256"] = hashlib.sha256(state["request"].encode()).hexdigest()
    # A changed upstream result invalidates every descendant, even if old files exist.
    invalid = {sid}
    for step in config["stages"]:
        if set(step["needs"]) & invalid:
            state["completed"].pop(step["id"], None)
            invalid.add(step["id"])
    return task


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["next","packet","finish","validate"])
    p.add_argument("stage", nargs="?")
    p.add_argument("artifact", nargs="?")
    args = p.parse_args()
    try:
        config, state = read(ROOT, CONFIG), read(ROOT, STATE)
        if args.command in ("next", "packet"):
            result = packet(ROOT, config, state, args.stage)
        elif args.command == "finish":
            if not args.stage or not args.artifact:
                raise ValueError("finish requires stage and artifact path")
            finish(ROOT, config, state, args.stage, args.artifact)
            (ROOT/STATE).write_text(json.dumps(state, ensure_ascii=False, indent=2)+"\n",encoding="utf-8",newline="\n")
            result = {"finished":args.stage,"next":packet(ROOT,config,state).get("stage")}
        else:
            done = completed(ROOT,config,state)
            stale = set(state["completed"]) - done
            if stale:
                raise ValueError("stale artifact/dependency: " + ", ".join(sorted(stale)))
            for stage in config["stages"]:
                if stage["id"] in done:
                    artifact = read(ROOT,state["completed"][stage["id"]]["artifact"]["path"])
                    errors = artifact_errors(ROOT,stage,artifact,config,state)
                    if errors:
                        raise ValueError("; ".join(errors))
            result = {"valid":True,"completed":sorted(done),"total":len(config["stages"]),
                      "note":"Contracts/provenance validated; content judgment belongs to Codex and team."}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(f"BLOCKED: {exc}")
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
