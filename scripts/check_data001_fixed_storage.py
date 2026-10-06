"""Probe a supplied frozen output through HTTP routes and SQLite reopen. No model generation."""

import json
import secrets
from copy import deepcopy
from hashlib import sha256
from pathlib import Path


def probe(packet, db_path):
    from fastapi.testclient import TestClient
    from lgax_api.workspace_auth import TokenRegistry
    from lgax_api.workspace_server import create_workspace_app
    from lgax_core.document_store import DocumentStore
    from lgax_core.store import DemoStore
    from lgax_core.workspace import WorkspaceStore
    from lgax_core.workspace_planning import build_planning_input

    execution = packet["execution"]
    if execution.get("output") is None:
        return {
            "status": "fixed_output_pending",
            "r06_final_output_verified": False,
            "reason": "Output-null failure envelopes cannot prove final output persistence",
            "model_generations": 0,
        }
    if (
        execution.get("status") not in ("completed", "held")
        or execution["output"].get("status") not in ("completed", "held")
    ):
        return {
            "status": "final_judgement_unverified",
            "r06_final_output_verified": False,
            "reason": "Failed or unfinished executions cannot prove a completed or held final judgement",
            "model_generations": 0,
        }
    dataset = packet["dataset"]
    store = (
        DocumentStore(dataset) if dataset.get("artifact_kind") == "document_dataset" else DemoStore(dataset)
    )
    original = execution["original_input"]
    request = original["request"]
    versions = {original["product"]["model_id"]: original["product"]["document_version"]}
    if build_planning_input(request, versions, store) != original:
        raise ValueError("Fixed execution input does not match the original dataset snapshot")
    calls = []

    def captured_runner(actual_request, actual_versions, actual_store):
        if build_planning_input(actual_request, actual_versions, actual_store) != original:
            raise ValueError("Changed request/dataset must not reuse a frozen output")
        calls.append("supplied_output_only")
        return deepcopy(execution)

    token = secrets.token_urlsafe(36)
    owner = "fixed-output-review"
    registry = TokenRegistry(
        [{"principal_id": owner, "role": "editor", "token_sha256": sha256(token.encode()).hexdigest()}]
    )
    app = create_workspace_app(Path(db_path), registry, planning_runner=captured_runner, evidence_store=store)
    headers = {"Authorization": "Bearer " + token}
    with TestClient(app, base_url="http://127.0.0.1") as api:
        response = api.post(
            "/api/workspace/projects",
            headers=headers,
            json={
                "name": "fixed output persistence check",
                "request": request,
                "document_versions": versions,
            },
        )
        if response.status_code != 201:
            raise ValueError("Project HTTP route rejected frozen scope")
        pid = response.json()["data"]["project"]["id"]
        saved = api.post(
            f"/api/workspace/projects/{pid}/runs",
            headers=headers,
            json={"request": request, "previous_run_id": None, "unconfirmed": []},
        )
        if saved.status_code != 201:
            raise ValueError("Run HTTP route rejected frozen output")
        wire = saved.json()["data"]
        rid = wire["run"]["id"]
        fetched = api.get(f"/api/workspace/runs/{rid}", headers=headers)
        if fetched.status_code != 200 or fetched.json()["data"] != wire:
            raise ValueError("HTTP saved/queried output differs")
        public_execution = wire["output"]["planning_execution"]
        if public_execution["output"] != execution["output"]:
            raise ValueError("HTTP projection changed final judgement fields")
    resumed = WorkspaceStore(Path(db_path), evidence_store=store).get_run(rid, owner)
    if resumed["output"]["planning_execution"]["output"] != execution["output"]:
        raise ValueError("SQLite reopen changed final judgement fields")
    return {
        "status": "fixed_output_persisted",
        "r06_final_output_verified": True,
        "run_id": rid,
        "http_saved_and_queried_equal": True,
        "sqlite_reopen_preserved_output": True,
        "model_generations": 0,
        "captured_output_replayed_count": len(calls),
        "semantic_judgement_verified": False,
        "execution_kind": execution["execution_kind"],
    }


def main():
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    if args.db.exists() or args.report.exists():
        p.error("Use fresh database and report paths; preserve prior checks")
    result = probe(json.loads(args.packet.read_bytes()), args.db)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return 0 if result["r06_final_output_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
