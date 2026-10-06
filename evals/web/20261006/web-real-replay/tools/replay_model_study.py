"""Replay PM's recorded real-model planning runs (finite model study) through a test workspace server.

Record 최길웅-20261006-034. No model is called. PM's `RecordedRunner` (evals/pm-intake/20261006/replay_workspace.py,
imported unchanged) returns a recording only when the server-assembled planning input is exactly the recording's
original_input. Three fridge recordings share one input, so `SelectedRunner` serves exactly one selected recording
per POST and fails closed otherwise (stored as failed, never a model call).

The runs stay in a private test DB so a read-only server (no planning runner) can show them to the web afterwards.
Only an envelope of each HTTP snapshot is written to the repository: `output.planning_execution` is replaced by a
reference to PM's recording plus its byte SHA-256, after checking that envelope + recording == the HTTP snapshot.
Never point the user's 18869 workspace or DB at this tool.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import secrets
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import httpx
import uvicorn
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app, public_run
from lgax_contracts import validate
from lgax_core.judgement_contract import input_digest
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[5]
STUDY_REL = "evals/pm-prototype/20261006/finite-model-study"
STUDY = ROOT / STUDY_REL
INPUTS = ROOT / "evals/pm-intake/20261006/core/cases"
DATASET = ROOT / "data/demo/dataset.json"
PM_REPLAY = ROOT / "evals/pm-intake/20261006/replay_workspace.py"
CASES = (  # variant, case_id, test project name
    ("27b-enum-guide", "fridge-normal", "모델 비교 기록 재생 · 27B 뜻풀이 · 냉장고"),
    ("27b-bounded12", "fridge-normal", "모델 비교 기록 재생 · 27B 12회 · 냉장고"),
    ("8b-bounded12", "fridge-normal", "모델 비교 기록 재생 · 8B 12회 · 냉장고"),
    ("8b-bounded12", "microwave-normal", "모델 비교 기록 재생 · 8B 12회 · 전자레인지"),
)
# PM's TOOLS constant predates the trend tools added to the private MCP on 10/6 (#156); everything else is unchanged.
TREND_TOOLS = {"review_trends", "get_review_trends", "trend_evidence"}
USER_PORTS = {5173, 18867, 18869}


def load_pm_replay():
    spec = importlib.util.spec_from_file_location("pm_replay_workspace", PM_REPLAY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(text.encode("utf-8")).hexdigest()


def write_new(path: Path, value) -> None:
    if path.exists():
        raise SystemExit(f"Refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


class SelectedRunner:
    """Serve exactly one selected recording per POST; with nothing selected it raises (no fallback, no model)."""

    def __init__(self):
        self.current = None
        self.served: list[str] = []

    def select(self, key: str, runner) -> None:
        self.current = (key, runner)

    def __call__(self, request, versions, store):
        if self.current is None:
            raise AssertionError("No recording selected; no fallback or model execution is allowed")
        key, runner = self.current
        self.current = None
        execution = runner(request, versions, store)
        self.served.append(key)
        return execution


@contextmanager
def fixed_port_server(app, port: int, require):
    bound = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        bound.bind(("127.0.0.1", port))
    except OSError as error:
        bound.close()
        raise SystemExit(f"127.0.0.1:{port} is already in use; other processes are left alone ({error})")
    bound.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error",
                                          access_log=False, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [bound]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    try:
        while not server.started:
            require(thread.is_alive() and time.monotonic() < deadline, "Test HTTP API did not start")
            time.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        bound.close()
        require(not thread.is_alive(), "Test HTTP API did not shut down")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=ROOT / "private/workspace-model-study-replay")
    parser.add_argument("--out", type=Path, default=ROOT / "evals/web/20261006/web-real-replay")
    parser.add_argument("--port", type=int, default=18879)
    args = parser.parse_args()
    if args.port in USER_PORTS:
        raise SystemExit(f"{args.port} belongs to the user's servers; use a separate test port")
    rw = load_pm_replay()
    require = rw.require

    manifest = json.loads((STUDY / "source-manifest.json").read_text(encoding="utf-8"))
    manifest_sha = {item["path"]: item["sha256"] for item in manifest["copied_inert_results"]}
    dataset, dataset_file_sha = rw.read_record(DATASET, maximum=16_777_216)
    records, pins, file_hashes, input_hashes = {}, {}, {}, {}
    for variant, case_id, _name in CASES:
        key = f"{variant}/{case_id}"
        summary = json.loads((STUDY / f"{variant}.summary.json").read_text(encoding="utf-8"))
        pin = next(item for item in summary["cases"] if item["case_id"] == case_id)
        require(pin["file"] == f"{key}.json", f"Producer summary does not point at {key}")
        record, file_sha = rw.read_record(STUDY / f"{key}.json", maximum=2_097_152)
        require(file_sha == manifest_sha[f"{key}.json"], f"Recording bytes differ from PM source manifest: {key}")
        original, input_sha = rw.read_record(INPUTS / f"{case_id}.input.json")
        require(input_sha == pin["input_sha256"], f"Producer input file changed: {key}")
        require(original == record["original_input"], f"Recording original_input differs from its producer input: {key}")
        require(dataset_file_sha == pin["dataset_sha256"], f"Dataset bytes differ from the recorded run: {key}")
        records[key], pins[key], file_hashes[key], input_hashes[key] = record, pin, file_sha, input_sha

    args.state_dir.mkdir(parents=True, exist_ok=False)  # fresh test DB only
    owner_token, viewer_token, outsider_token = (secrets.token_urlsafe(48) for _ in range(3))
    principal = "model-study-replay-owner"
    owner_entry = {"principal_id": principal, "role": "editor", "token_sha256": sha256(owner_token.encode()).hexdigest()}
    viewer_entry = {"principal_id": principal, "role": "viewer", "token_sha256": sha256(viewer_token.encode()).hexdigest()}
    outsider_entry = {"principal_id": "model-study-replay-other", "role": "viewer",
                      "token_sha256": sha256(outsider_token.encode()).hexdigest()}
    registry = TokenRegistry([owner_entry, viewer_entry, outsider_entry])
    # Private (git-ignored) state for the later read-only server and browser check. Hashes only in credentials.json.
    (args.state_dir / "credentials.json").write_text(json.dumps({"credentials": [owner_entry, viewer_entry]}), encoding="utf-8")
    (args.state_dir / "owner-credential.json").write_text(json.dumps({"token": owner_token}), encoding="utf-8")
    (args.state_dir / "viewer-credential.json").write_text(json.dumps({"token": viewer_token}), encoding="utf-8")
    mcp_home = args.state_dir / "mcp-home"
    mcp_home.mkdir()

    runner = SelectedRunner()
    app = create_workspace_app(args.state_dir / "workspace.sqlite", registry, planning_runner=runner,
                               evidence_store=DemoStore(dataset))
    workspace = app.state.workspace
    keys = [f"{variant}/{case_id}" for variant, case_id, _name in CASES]
    snapshots, projects, rows = {}, [], []
    with fixed_port_server(app, args.port, require) as url:
        with httpx.Client(base_url=url, trust_env=False, timeout=60,
                          headers={"Authorization": "Bearer " + owner_token, "X-LGAX-Client": "web"}) as client:
            for (variant, case_id, name), key in zip(CASES, keys):
                execution = records[key]
                original = execution["original_input"]
                request = original["request"]
                versions = {original["product"]["model_id"]: original["product"]["document_version"]}
                project = rw.response(client, "POST", "/api/workspace/projects", 201,
                                      json={"name": name, "request": request, "document_versions": versions})["data"]
                validate("WorkspaceProjectResponse", {"ok": True, "data": project})
                projects.append(project)
                runner.select(key, rw.RecordedRunner({key: execution}, {key: pins[key]}))
                saved = rw.response(client, "POST", f"/api/workspace/projects/{project['project']['id']}/runs", 201,
                                    json={"request": request, "previous_run_id": None, "unconfirmed": []})["data"]
                require(runner.served[-1:] == [key] and runner.current is None, f"Selected recording was not served: {key}")
                raw = workspace.get_run(saved["run"]["id"], principal)
                require(raw["output"]["planning_execution"] == execution, f"Stored execution changed or fell back: {key}")
                require(saved == public_run(raw), f"HTTP differs from the canonical diagnostic projection: {key}")
                require(saved["output"]["planning_execution"] == execution, f"HTTP planning_execution differs: {key}")
                require(saved["run"]["status"] == execution["status"] == pins[key]["status"],
                        f"Recorded held/failed status was rewritten: {key}")
                require(saved["run"]["status"] in {"held", "failed"} and saved["run"]["concepts"] == [],
                        f"Recorded quality failure appeared as a candidate: {key}")
                require(saved["request_revision"] == 0 and saved["previous_run_id"] is None, f"Unexpected user revision: {key}")
                require(saved["run"]["revision_count"] == execution["input"]["revision_count"], f"Agent revision conflated: {key}")
                validate("WorkspaceRunResponse", {"ok": True, "data": saved})
                fetched = rw.response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                require(fetched == saved, f"HTTP GET differs from POST: {key}")
                snapshots[key] = fetched
            first_project = projects[0]["project"]["id"]
            with httpx.Client(base_url=url, trust_env=False, timeout=15) as anonymous:
                require(rw.response(anonymous, "GET", f"/api/workspace/projects/{first_project}", 401)["error"]["code"]
                        == "UNAUTHORIZED", "Missing credential was not unauthorized")
            with httpx.Client(base_url=url, trust_env=False, timeout=15,
                              headers={"Authorization": "Bearer " + viewer_token}) as viewer:
                require(rw.response(viewer, "GET", f"/api/workspace/projects/{first_project}", 200)["data"] == projects[0],
                        "Same-owner viewer cannot read the project")
                require(rw.response(viewer, "POST", f"/api/workspace/projects/{first_project}/runs", 403,
                                    json={"request": records[keys[0]]["original_input"]["request"], "previous_run_id": None,
                                          "unconfirmed": []})["error"]["code"] == "FORBIDDEN", "Viewer write was not forbidden")
            with httpx.Client(base_url=url, trust_env=False, timeout=15,
                              headers={"Authorization": "Bearer " + outsider_token}) as outsider:
                require(rw.response(outsider, "GET", f"/api/workspace/projects/{first_project}", 403)["error"]["code"]
                        == "FORBIDDEN", "Other-owner read was not forbidden")
            require(runner.served == keys, "Permission checks executed the runner")
            pm_tools = sorted(rw.TOOLS)
            rw.TOOLS = set(rw.TOOLS) | TREND_TOOLS
            mcp = asyncio.run(rw.mcp_readback(url, args.state_dir / "owner-credential.json", mcp_home, projects, snapshots))
            require(runner.served == keys, "MCP reads created new runs")
            for key, saved in snapshots.items():
                again = rw.response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                require(again == saved, f"MCP reads changed a stored run: {key}")

    for (variant, case_id, name), key, project in zip(CASES, keys, projects):
        snapshot = snapshots[key]
        record_path = f"{STUDY_REL}/{key}.json"
        envelope = deepcopy(snapshot)
        envelope["output"]["planning_execution"] = {"$replay_record": record_path, "sha256": file_hashes[key]}
        rebuilt = deepcopy(envelope)
        rebuilt["output"]["planning_execution"] = records[key]
        require(rebuilt == snapshot, f"Envelope + recording is not the HTTP snapshot: {key}")
        envelope_rel = f"snapshots/{variant}--{case_id}.envelope.json"
        write_new(args.out / envelope_rel, envelope)
        execution = records[key]
        rows.append({
            "case": key, "project_name": name, "project_id": project["project"]["id"],
            "run_id": snapshot["run"]["id"], "envelope": envelope_rel, "recording": record_path,
            "recording_sha256": file_hashes[key], "recording_bytes": (STUDY / f"{key}.json").stat().st_size,
            "producer_input_file_sha256": input_hashes[key],
            "original_input_canonical_sha256": input_digest(execution["original_input"]),
            "http_snapshot_canonical_sha256": canonical(snapshot),
            "mcp_snapshot_canonical_sha256": canonical(mcp["runs"][key]),
            "recorded_status": snapshot["run"]["status"], "decision_action": (execution.get("decision") or {}).get("action"),
            "visible_candidates": len(snapshot["run"]["concepts"]), "request_revision": snapshot["request_revision"],
            "agent_internal_revision_count": snapshot["run"]["revision_count"],
            "historical_model_id": pins[key]["model_id"], "historical_model_digest": pins[key]["model_digest"],
            "historical_model_calls": pins[key]["actual_calls"], "historical_tokens": pins[key]["tokens"],
            "recorded_source_commit": pins[key]["source_commit"],
        })
    summary = {
        "kind": "recorded_live_execution_web_replay", "record": "최길웅-20261006-034",
        "observed_by": "choigilung (Claude Code, manual session)",
        "repository_commit": git("rev-parse", "HEAD"),
        "product_source_matches_commit": git("status", "--porcelain", "--", "apps/api", "apps/mcp", "packages", "data") == "",
        "pm_replay_tool": {"path": "evals/pm-intake/20261006/replay_workspace.py",
                           "sha256": sha256(PM_REPLAY.read_bytes()).hexdigest(), "imported_unchanged": True,
                           "tool_set_constant": pm_tools, "tool_set_used": sorted(rw.TOOLS),
                           "note": "PM's 7-tool constant predates the 3 trend tools on current main; only that constant was extended."},
        "server": {"url": f"http://127.0.0.1:{args.port}", "state_dir": "private/ (git-ignored test DB; tokens never written here)",
                   "planning_runner": "SelectedRunner over PM RecordedRunner (one recording per POST)"},
        "dataset_file_sha256": dataset_file_sha, "workspace_canonical_dataset_sha256": workspace.dataset_sha256,
        "new_model_calls": 0, "cases": rows,
        "checks": {"recording_bytes_match_pm_manifest": True, "original_input_exact": True, "stored_execution_unchanged": True,
                   "http_post_get_equal": True, "http_equals_public_run": True, "same_http_mcp_ids_and_snapshots": True,
                   "held_failed_visible_candidates_zero": True, "missing_credential_401": True, "viewer_write_403": True,
                   "other_owner_read_403": True, "reads_did_not_run_runner": True, "envelope_plus_recording_equals_http": True},
        "mcp": {key: value for key, value in mcp.items() if key != "runs"},
        "limitations": [
            "Historical real-model outputs (qwen3.5:27b held x2, qwen3:8b failed x2) on synthetic data are read back; no new model run.",
            "Shows storage/readback and honest held/failed display inputs only; not planning quality, accept, WEB003 Done or demand.",
            "PM states the 27B held is not an appropriate data-shortage hold; it is not the prototype's 'appropriate hold' case.",
        ],
    }
    write_new(args.out / "replay-summary.json", summary)
    print(json.dumps({"status": "pass", "cases": [(row["case"], row["recorded_status"], row["run_id"]) for row in rows],
                      "new_model_calls": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
