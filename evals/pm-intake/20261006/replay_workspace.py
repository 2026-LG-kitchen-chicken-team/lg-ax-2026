"""Replay recorded live executions through real ephemeral HTTP + MCP storage.

No model is called. This verifies readback and permissions, not planning quality.
Run only inside the approved zero-host-credential validator container.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import time

import httpx
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app, public_run
from lgax_contracts import validate
from lgax_core.judgement_contract import input_digest
from lgax_core.store import DemoStore
from lgax_core.workspace_planning import build_planning_input
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import uvicorn

ROOT = Path(__file__).resolve().parents[3]
CASE_IDS = tuple(f"{group}-{kind}" for group in ("fridge", "dishwasher", "microwave")
                 for kind in ("normal", "changed"))
TOOLS = {"list_workspace_projects", "create_workspace_project", "get_workspace_project",
         "create_workspace_run", "get_workspace_run", "list_workspace_runs", "search_workspace_evidence"}


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def read_record(path: Path, maximum: int = 1_048_576) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink(), f"Missing or linked input: {path.name}")
    raw = path.read_bytes()
    require(len(raw) <= maximum, f"Oversized input: {path.name}")
    record = json.loads(raw)
    require(isinstance(record, dict), f"Non-object input: {path.name}")
    return record, sha256(raw).hexdigest()


class RecordedRunner:
    """Return an unchanged recording only for its exactly identical real input."""

    def __init__(self, records: dict[str, dict], pins: dict[str, dict]):
        self.records, self.pins = records, pins
        self.by_input: dict[str, str] = {}
        self.calls: list[str] = []
        for case_id, execution in records.items():
            original = execution["original_input"]
            digest = input_digest(original)
            require(digest not in self.by_input, "Duplicate recorded input")
            require(execution["execution_kind"] == "live_model", f"Not an original live execution: {case_id}")
            require(execution["status"] == pins[case_id]["status"], f"Recorded status mismatch: {case_id}")
            require(len(execution["model_calls"]) == pins[case_id]["actual_calls"],
                    f"Historical call count differs from its producer summary: {case_id}")
            require(execution["input"]["revision_count"] == pins[case_id]["revision_count"],
                    f"Historical internal revision differs from its producer summary: {case_id}")
            self.by_input[digest] = case_id

    def __call__(self, request, versions, store):
        payload = build_planning_input(request, versions, store)
        case_id = self.by_input.get(input_digest(payload))
        require(case_id is not None, "No exact recorded input exists; no fallback or model execution is allowed")
        execution = self.records[case_id]
        require(payload == execution["original_input"], f"Original input differs from actual source lookup: {case_id}")
        expected_terminal = {**payload, "revision_count": execution["input"]["revision_count"]}
        require(execution["input"] == expected_terminal, f"Recorded terminal source/request was mutated: {case_id}")
        self.calls.append(case_id)
        return deepcopy(execution)


@contextmanager
def http_server(app):
    bound = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bound.bind(("127.0.0.1", 0))
    bound.listen(128)
    port = bound.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                          log_level="error", access_log=False, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [bound]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    try:
        while not server.started:
            require(thread.is_alive() and time.monotonic() < deadline, "Ephemeral HTTP API did not start")
            time.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        bound.close()
        require(not thread.is_alive(), "Ephemeral HTTP API did not shut down")


def response(client, method: str, path: str, status: int, **kwargs) -> dict:
    result = client.request(method, path, **kwargs)
    require(result.status_code == status, f"HTTP {method} {path}: expected {status}, got {result.status_code}")
    return result.json()


def tool_payload(result) -> dict:
    dumped = result.model_dump(mode="json", by_alias=True)
    require(not dumped.get("isError"), "MCP tool returned a protocol error")
    if dumped.get("structuredContent") is not None:
        return dumped["structuredContent"]
    return json.loads(next(item["text"] for item in dumped["content"] if item["type"] == "text"))


async def mcp_readback(url: str, credential: Path, temp: Path, projects: list[dict], snapshots: dict[str, dict]):
    # stdio SDK defaults intentionally do not inherit arbitrary PYTHONPATH or host credentials.
    # Source paths are explicit; this child gets only a guest-minted credential file.
    source_paths = [ROOT / item for item in ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src")]
    child_env = {"PYTHONPATH": os.pathsep.join(map(str, source_paths)), "PYTHONNOUSERSITE": "1",
                 "PYTHONUTF8": "1", "HOME": str(temp), "PATH": os.defpath}
    params = StdioServerParameters(command=sys.executable,
                                  args=["-m", "lgax_mcp.workspace_server", "--url", url,
                                        "--credential-file", str(credential)],
                                  cwd=str(ROOT), env=child_env)
    results: dict[str, dict] = {}
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            require({item.name for item in tools.tools} == TOOLS, "Unexpected private MCP tool set")
            listed = tool_payload(await session.call_tool("list_workspace_projects", {}))
            require({item["project"]["id"] for item in listed["data"]["projects"]}
                    == {item["project"]["id"] for item in projects}, "MCP project IDs differ from HTTP")
            for project in projects:
                project_id = project["project"]["id"]
                found = tool_payload(await session.call_tool("get_workspace_project", {"project_id": project_id}))
                require(found["data"] == project, "MCP project input/scope differs from HTTP")
                history = tool_payload(await session.call_tool("list_workspace_runs", {"project_id": project_id}))
                expected_ids = {item["run"]["id"] for item in snapshots.values() if item["run"]["project_id"] == project_id}
                require({item["run"]["id"] for item in history["data"]["runs"]} == expected_ids,
                        "MCP history uses different run IDs")
            for case_id, expected in snapshots.items():
                fetched = tool_payload(await session.call_tool("get_workspace_run", {"run_id": expected["run"]["id"]}))
                validate("WorkspaceRunResponse", fetched)
                require(fetched["data"] == expected, f"MCP and actual HTTP readback differ: {case_id}")
                results[case_id] = fetched["data"]
            return {"protocol_version": initialized.protocolVersion, "tools": sorted(TOOLS),
                    "manual_pythonpath": True, "host_credentials": False, "runs": results}


def replay(args) -> dict:
    args.artifacts.mkdir(parents=True, exist_ok=False)
    summary, summary_hash = read_record(args.records / "summary.json", maximum=262_144)
    pins = {item["case_id"]: item for item in summary["cases"]}
    require(set(pins) == set(CASE_IDS) and len(summary["cases"]) == len(CASE_IDS), "Expected exactly the original six cases")
    records, file_hashes, input_file_hashes = {}, {}, {}
    for case_id in CASE_IDS:
        record, digest = read_record(args.records / f"{case_id}.output.json")
        require(digest == pins[case_id]["output_sha256"], f"Recorded output bytes changed: {case_id}")
        original_input, input_file_hash = read_record(args.inputs / f"{case_id}.input.json")
        require(input_file_hash == pins[case_id]["input_sha256"], f"Recorded input file bytes changed: {case_id}")
        require(original_input == record["original_input"], f"Recorded output original input differs from its source input: {case_id}")
        records[case_id], file_hashes[case_id] = record, digest
        input_file_hashes[case_id] = input_file_hash
    dataset, dataset_file_hash = read_record(args.dataset, maximum=16_777_216)
    require(all(dataset_file_hash == item["dataset_sha256"] for item in pins.values()),
            "Dataset file bytes differ from the actually recorded six-case source")
    store, runner = DemoStore(dataset), RecordedRunner(records, pins)
    owner_token, viewer_token, outsider_token = (secrets.token_urlsafe(48) for _ in range(3))
    principal = "recorded-replay-owner"
    registry = TokenRegistry([
        {"principal_id": principal, "role": "editor", "token_sha256": sha256(owner_token.encode()).hexdigest()},
        {"principal_id": principal, "role": "viewer", "token_sha256": sha256(viewer_token.encode()).hexdigest()},
        {"principal_id": "recorded-replay-other", "role": "viewer", "token_sha256": sha256(outsider_token.encode()).hexdigest()},
    ])
    snapshots, projects, rows = {}, [], []
    with TemporaryDirectory(prefix="lgax-recorded-replay-") as temporary:
        temp = Path(temporary)
        credential = temp / "guest-mcp.json"
        credential.write_text(json.dumps({"token": owner_token}), encoding="utf-8")
        credential.chmod(0o600)
        app = create_workspace_app(temp / "workspace.sqlite", registry, planning_runner=runner, evidence_store=store)
        workspace = app.state.workspace
        # Producer runs pin the source file bytes; WorkspaceStore independently
        # pins canonical JSON content. Keep both conventions, never equate them.
        workspace_dataset_sha256 = workspace.dataset_sha256
        with http_server(app) as url:
            with httpx.Client(base_url=url, trust_env=False, timeout=60,
                              headers={"Authorization": "Bearer " + owner_token, "X-LGAX-Client": "web"}) as client:
                for group in ("fridge", "dishwasher", "microwave"):
                    original = records[f"{group}-normal"]["original_input"]
                    versions = {original["product"]["model_id"]: original["product"]["document_version"]}
                    project = response(client, "POST", "/api/workspace/projects", 201, json={
                        "name": f"Recorded live execution readback · {group}", "request": original["request"],
                        "document_versions": versions,
                    })["data"]
                    validate("WorkspaceProjectResponse", {"ok": True, "data": project})
                    projects.append(project)
                    previous = None
                    preserved_parent = None
                    for kind in ("normal", "changed"):
                        case_id = f"{group}-{kind}"
                        execution = records[case_id]
                        request = execution["original_input"]["request"]
                        saved = response(client, "POST", f"/api/workspace/projects/{project['project']['id']}/runs", 201,
                                         json={"request": request, "previous_run_id": previous, "unconfirmed": []})["data"]
                        raw = workspace.get_run(saved["run"]["id"], principal)
                        require(raw["output"]["planning_execution"] == execution, f"Stored original execution changed/fell back: {case_id}")
                        require(saved == public_run(raw), f"Actual HTTP differs from canonical diagnostic projection: {case_id}")
                        require(saved["request"] == request and saved["output"]["planning_execution"]["original_input"] == execution["original_input"],
                                f"HTTP original request/source input changed: {case_id}")
                        require(saved["run"]["status"] == execution["status"], f"Historical failed/held status was rewritten: {case_id}")
                        require(saved["request_revision"] == (0 if kind == "normal" else 1), f"Wrong user revision: {case_id}")
                        require(saved["run"]["revision_count"] == execution["input"]["revision_count"]
                                and saved["run"]["max_revisions"] == 2, f"Agent internal revision was conflated: {case_id}")
                        require(saved["previous_run_id"] == previous, f"Broken parent link: {case_id}")
                        require(saved["run"]["status"] in {"held", "failed"} and saved["run"]["concepts"] == [],
                                f"Original quality failure appeared as a successful candidate: {case_id}")
                        validate("WorkspaceRunResponse", {"ok": True, "data": saved})
                        fetched = response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                        require(fetched == saved, f"HTTP GET differs from POST: {case_id}")
                        if preserved_parent is not None:
                            old = response(client, "GET", f"/api/workspace/runs/{previous}", 200)["data"]
                            require(old == preserved_parent, f"Creating a child mutated the original run: {case_id}")
                        snapshots[case_id] = fetched
                        rows.append({"case_id": case_id, "project_id": project["project"]["id"], "run_id": saved["run"]["id"],
                                     "previous_run_id": previous, "request_revision": saved["request_revision"],
                                     "agent_internal_revision_count": saved["run"]["revision_count"], "agent_max_revisions": 2,
                                     "recorded_status": saved["run"]["status"], "visible_candidates": 0,
                                     "historical_model_calls": pins[case_id]["actual_calls"],
                                     "historical_model_id": pins[case_id]["model_id"],
                                     "historical_model_digest": pins[case_id]["model_digest"],
                                     "recorded_source_commit": pins[case_id]["source_commit"],
                                     "recorded_output_sha256": file_hashes[case_id], "original_input_canonical_sha256": input_digest(execution["original_input"]),
                                     "recorded_input_file_sha256": input_file_hashes[case_id],
                                     "dataset_sha256": workspace.dataset_sha256, "stored_execution_unchanged": True,
                                     "recorded_dataset_file_sha256": dataset_file_hash,
                                     "actual_http_readback_equal": True})
                        previous, preserved_parent = saved["run"]["id"], deepcopy(saved)
                first_project = projects[0]["project"]["id"]
                with httpx.Client(base_url=url, trust_env=False, timeout=15) as unauthenticated:
                    denied = response(unauthenticated, "GET", f"/api/workspace/projects/{first_project}", 401)
                    require(denied["error"]["code"] == "UNAUTHORIZED", "Missing credential was not unauthorized")
                with httpx.Client(base_url=url, trust_env=False, timeout=15,
                                  headers={"Authorization": "Bearer " + viewer_token}) as viewer:
                    require(response(viewer, "GET", f"/api/workspace/projects/{first_project}", 200)["data"] == projects[0],
                            "Same-owner viewer cannot read an existing project")
                    denied = response(viewer, "POST", f"/api/workspace/projects/{first_project}/runs", 403,
                                      json={"request": records["fridge-normal"]["original_input"]["request"],
                                            "previous_run_id": None, "unconfirmed": []})
                    require(denied["error"]["code"] == "FORBIDDEN", "Viewer write was not forbidden")
                with httpx.Client(base_url=url, trust_env=False, timeout=15,
                                  headers={"Authorization": "Bearer " + outsider_token}) as outsider:
                    denied = response(outsider, "GET", f"/api/workspace/projects/{first_project}", 403)
                    require(denied["error"]["code"] == "FORBIDDEN", "Other-owner read was not forbidden")
                require(runner.calls == list(CASE_IDS), "Permission checks unexpectedly executed the replay runner")
                mcp = asyncio.run(mcp_readback(url, credential, temp, projects, snapshots))
                require(runner.calls == list(CASE_IDS), "MCP readback unexpectedly created new runs")
                for case_id, saved in snapshots.items():
                    fetched = response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                    require(fetched == saved, f"MCP reads changed a stored run: {case_id}")
            for case_id in CASE_IDS:
                require(read_record(args.records / f"{case_id}.output.json")[1] == file_hashes[case_id], "Recorded input artifact was mutated")
                require(read_record(args.inputs / f"{case_id}.input.json")[1] == input_file_hashes[case_id], "Original model input file changed")
            require(read_record(args.records / "summary.json", maximum=262_144)[1] == summary_hash, "Original quality summary changed")
            require(read_record(args.dataset, maximum=16_777_216)[1] == dataset_file_hash, "Original dataset changed")
    result = {"status": "pass", "verification_kind": "recorded_live_execution_http_mcp_readback",
              "new_model_calls": 0, "historical_quality_failures_preserved": True, "quality_complete": False,
              "historical_model_calls": sum(item["actual_calls"] for item in pins.values()),
              "application_requirements_complete": False, "dataset_file_sha256": dataset_file_hash,
              "workspace_canonical_dataset_sha256": workspace_dataset_sha256,
              "recorded_summary_sha256": summary_hash, "cases": rows,
              "checks": {"actual_loopback_http": True, "ephemeral_sqlite": True, "guest_minted_tokens_only": True,
                         "original_input_exact": True, "parent_run_immutable": True, "same_http_mcp_ids_and_snapshots": True,
                         "user_revision_separate_from_agent_internal_revision": True, "held_failed_candidate_count_zero": True,
                         "missing_credential_401": True, "viewer_write_403": True, "other_owner_read_403": True},
              "mcp": {key: value for key, value in mcp.items() if key != "runs"},
              "limitations": ["Recorded historical live-model outputs are read back; this is not a new model run.",
                              "Original synthetic-input quality failures remain unresolved.",
                              "This ephemeral replay does not prove production cutover, browser use or external host connection."]}
    for name, value in (("http-readback.json", snapshots), ("mcp-readback.json", mcp["runs"]), ("summary.json", result)):
        (args.artifacts / name).write_bytes(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=ROOT / "evals/pm-intake/20261006/live-quality/original-six")
    parser.add_argument("--inputs", type=Path, default=ROOT / "evals/pm-intake/20261006/core/cases")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/demo/dataset.json")
    parser.add_argument("--artifacts", type=Path, default=Path("/artifacts/recorded-workspace-replay"))
    args = parser.parse_args()
    result = replay(args)
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]),
                      "new_model_calls": 0, "quality_complete": False,
                      "verification_kind": result["verification_kind"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
