"""Store PM's three original 122B executions through the real workspace HTTP API and keep serving them (R5, record 051).

Test-only, no model. Each case gets its own private DB and port because its evidence store is built from that run's own
original_input (tests/test_workspace_planning.dataset_for), so the server assembles exactly the original input and PM's
RecordedRunner (evals/pm-intake/20261006/replay_workspace.py, unchanged) returns the unchanged recording — or fails
closed. The tool POSTs project + run over HTTP, re-GETs the run and history, and writes the public snapshots (no
tokens) for comparison with the independent expectations. Run with PYTHONPATH on the main checkout (C:/ paths).
"""
import argparse
import hashlib
import importlib.util
import json
import secrets
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.store import DemoStore
from test_workspace_planning import dataset_for

USER_PORTS = {5173, 18867, 18869}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", type=Path, required=True, help="main checkout (for PM's replay_workspace.py)")
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True, help="git-ignored dir for DBs and the test token")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-port", type=int, default=18891)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("pm_replay", args.code / "evals/pm-intake/20261006/replay_workspace.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    expected = json.loads(args.expected.read_text("utf-8"))["cases"]
    args.private.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(40)
    (args.private / "viewer-credential.json").write_text(json.dumps({"token": token}))
    registry = TokenRegistry([{"principal_id": "r5-viewer", "role": "editor", "token_sha256": hashlib.sha256(token.encode()).hexdigest()}])
    servers, summary = [], {"kind": "r5_original_http_replay", "new_model_calls": 0, "cases": {}}
    for index, (name, case) in enumerate(expected.items()):
        port = args.base_port + index
        if port in USER_PORTS:
            raise SystemExit("user port")
        path = next(p for p in (args.originals / f"{name}.output.json", args.originals / f"{name}.json") if p.exists())
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != case["sha256"]:
            raise SystemExit(f"{name}: original bytes changed")
        execution = json.loads(raw)
        payload = execution["original_input"]
        runner = replay.RecordedRunner({name: execution}, {name: {"status": execution["status"], "actual_calls": len(execution["model_calls"]),
                                                                 "revision_count": execution["input"]["revision_count"]}})
        db = args.private / f"{name}.sqlite"
        db.unlink(missing_ok=True)
        app = create_workspace_app(db, registry, evidence_store=DemoStore(dataset_for(payload)), planning_runner=runner)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        while not server.started:
            time.sleep(0.05)
        servers.append((server, thread))
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + token, "Origin": "http://127.0.0.1:5173"}, trust_env=False, timeout=60) as client:
            request = payload["request"]
            project = client.post("/api/workspace/projects", json={"name": f"R5 원본 재조회 · {name}", "request": request,
                                                                 "document_versions": {payload["product"]["model_id"]: payload["product"]["document_version"]}})
            project.raise_for_status()
            pid = project.json()["data"]["project"]["id"]
            saved = client.post(f"/api/workspace/projects/{pid}/runs", json={"request": request, "previous_run_id": None, "unconfirmed": []})
            saved.raise_for_status()
            snapshot = saved.json()["data"]
            rid = snapshot["run"]["id"]
            again = client.get(f"/api/workspace/runs/{rid}").json()["data"]
            history = client.get(f"/api/workspace/projects/{pid}/runs").json()["data"]["runs"]
        if again != snapshot or history != [snapshot] or len(runner.calls) != 1:
            raise SystemExit(f"{name}: HTTP POST/GET/history differ or runner not called exactly once")
        text = json.dumps(snapshot, ensure_ascii=False)
        if token in text:
            raise SystemExit("token leaked into a snapshot")
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"{name}.public.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        summary["cases"][name] = {"port": port, "project_id": pid, "run_id": rid, "run_status": snapshot["run"]["status"],
                                  "public_sha256": hashlib.sha256((args.out / f"{name}.public.json").read_bytes()).hexdigest()}
        print(name, port, snapshot["run"]["status"], pid, rid, flush=True)
    (args.out / "http-replay.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ready", flush=True)
    for _, thread in servers:
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
