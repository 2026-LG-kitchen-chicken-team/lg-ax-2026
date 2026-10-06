"""Consume pinned historical executions through real isolated HTTP/SQLite/MCP.

This is recording replay, never fresh generation or a semantic quality gate.
Run only in the fixed zero-host-auth Docker validator. The producer bytes and
original input must stay exact; mismatches fail instead of repairing a result.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app, public_run
from lgax_core.store import DemoStore
import httpx

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "evals/pm-intake/20261006/replay_workspace.py"
spec = importlib.util.spec_from_file_location("recorded_workspace_base", BASE)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
# These three read-only tools were added after the original six-run probe.
# Preserve the complete current catalog check instead of weakening it to a subset.
base.TOOLS |= {"review_trends", "get_review_trends", "trend_evidence"}


class PinnedReplay:
    def __init__(self, records: dict, pins: dict):
        self.runners = {key: base.RecordedRunner({key: value}, {key: pins[key]})
                        for key, value in records.items()}
        self.current: str | None = None

    def __call__(self, request, versions, store):
        base.require(self.current in self.runners, "No explicitly selected recorded case")
        return self.runners[self.current](request, versions, store)


def run(manifest_path: Path, artifacts: Path) -> dict:
    manifest, manifest_hash = base.read_record(manifest_path)
    base.require(manifest.get("kind") == "pinned_historical_run_consumption", "Unexpected manifest kind")
    cases = manifest["cases"]
    base.require(1 <= len(cases) <= 12 and len({row["case_id"] for row in cases}) == len(cases),
                 "Finite unique recorded cases required")
    records, pins, paths = {}, {}, {}
    for row in cases:
        path = (ROOT / row["path"]).resolve()
        base.require(path.is_relative_to(ROOT / "evals") and not path.is_symlink(), "Unapproved source path")
        execution, digest = base.read_record(path, maximum=16_777_216)
        base.require(digest == row["sha256"], "Original producer recording bytes changed")
        base.require(execution["status"] == row["status"], "Producer terminal status differs")
        records[row["case_id"]], pins[row["case_id"]], paths[row["case_id"]] = execution, row, path
    dataset, dataset_file_hash = base.read_record(ROOT / "data/demo/dataset.json", maximum=16_777_216)
    base.require(dataset_file_hash == manifest["dataset_sha256"], "Pinned dataset bytes changed")
    store, runner = DemoStore(dataset), PinnedReplay(records, pins)
    token = secrets.token_urlsafe(48)
    principal = "pm-recorded-consumption"
    registry = TokenRegistry([{"principal_id": principal, "role": "editor",
                              "token_sha256": sha256(token.encode()).hexdigest()}])
    snapshots, projects, checks = {}, [], {}
    artifacts.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory(prefix="lgax-pm-recorded-consumption-") as temporary:
        temp = Path(temporary)
        credential = temp / "guest-mcp.json"
        credential.write_text(json.dumps({"token": token}), encoding="utf-8")
        credential.chmod(0o600)
        app = create_workspace_app(temp / "workspace.sqlite", registry,
                                   planning_runner=runner, evidence_store=store)
        with base.http_server(app) as url, httpx.Client(base_url=url, trust_env=False, timeout=60,
                headers={"Authorization": "Bearer " + token, "X-LGAX-Client": "web"}) as client:
            for row in cases:
                case_id = row["case_id"]
                execution = records[case_id]
                original = execution["original_input"]
                request = original["request"]
                versions = {original["product"]["model_id"]: original["product"]["document_version"]}
                project = base.response(client, "POST", "/api/workspace/projects", 201, json={
                    "name": "Pinned historical recording · " + case_id,
                    "request": request, "document_versions": versions})["data"]
                projects.append(project)
                runner.current = case_id
                saved = base.response(client, "POST", f"/api/workspace/projects/{project['project']['id']}/runs", 201,
                                      json={"request": request, "previous_run_id": None, "unconfirmed": []})["data"]
                raw = app.state.workspace.get_run(saved["run"]["id"], principal)
                base.require(raw["output"]["planning_execution"] == execution, "Original execution changed or fell back")
                base.require(saved == public_run(raw), "HTTP differed from the canonical public projection")
                base.require(saved["run"]["status"] == execution["status"], "Held/failed result rewritten")
                base.require(saved["output"]["planning_execution"]["original_input"] == original,
                             "Original request/evidence snapshot changed")
                if execution["status"] in {"held", "failed"}:
                    base.require(saved["run"]["concepts"] == [], "Held/failed recording shown as successful candidates")
                fetched = base.response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                base.require(fetched == saved, "GET/POST same run differed")
                snapshots[case_id] = fetched
            mcp = asyncio.run(base.mcp_readback(url, credential, temp, projects, snapshots))
            for case_id, saved in snapshots.items():
                fetched = base.response(client, "GET", f"/api/workspace/runs/{saved['run']['id']}", 200)["data"]
                base.require(fetched == saved, "MCP read modified the stored execution")
                base.require(base.read_record(paths[case_id], maximum=16_777_216)[1] == pins[case_id]["sha256"],
                             "Producer output bytes changed during consumption")
            base.require(sum(len(item.calls) for item in runner.runners.values()) == len(cases),
                         "Readback made an unexpected replay request")
            checks = {"actual_isolated_http": True, "temporary_sqlite": True,
                      "original_input_and_execution_preserved": True,
                      "same_http_mcp_ids_and_snapshots": True,
                      "reads_preserve_saved_records": True, "guest_minted_credential_only": True}
    rows = [{"case_id": key, "run_id": value["run"]["id"], "project_id": value["run"]["project_id"],
             "status": value["run"]["status"], "visible_candidates": len(value["run"]["concepts"]),
             "original_output_sha256": pins[key]["sha256"], "original_source_commit": pins[key]["source_commit"],
             "historical_model_calls": pins[key]["actual_calls"], "new_model_calls": 0} for key, value in snapshots.items()]
    result = {"kind": "pinned_historical_run_consumption", "status": "pass", "replay_only": True,
              "new_model_calls": 0, "quality_asserted": False, "normal_changed_hold_matrix_complete": False,
              "manifest_sha256": manifest_hash, "dataset_sha256": dataset_file_hash, "cases": rows,
              "checks": checks, "mcp_tools": mcp["tools"],
              "limitations": ["Historical recordings were replayed; no new model ran.",
                              "No browser or production endpoint was exercised by this probe.",
                              "No normal/changed/appropriate-hold semantic quality gate is satisfied."]}
    for name, value in (("http-readback.json", snapshots), ("mcp-readback.json", mcp["runs"]), ("summary.json", result)):
        (artifacts / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.artifacts)
    print(json.dumps({"status": result["status"], "recorded_cases": len(result["cases"]),
                      "new_model_calls": 0, "replay_only": True, "quality_asserted": False}))
