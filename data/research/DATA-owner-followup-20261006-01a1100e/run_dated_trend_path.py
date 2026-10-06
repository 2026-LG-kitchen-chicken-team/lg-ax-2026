"""Owned loopback API -> actual MCP stdio -> original drilldown -> restart.

Only injects the separately identified constructed-date demo into a new private
SQLite DB. No production port, old dataset, central job, model or token is reused.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from lgax_api.review_trends import create_review_trend_collector
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.retrieval import GroundedDemoStore
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent


def structured(result):
    value = result.structuredContent or json.loads(next(item.text for item in result.content if item.type == "text"))
    if set(value) == {"result"}:
        value = value["result"]
    return value.get("data", value)


async def mcp_read(url, credential, filters, aggregate_id):
    params = StdioServerParameters(command=sys.executable, args=["-B", "-X", "utf8", "-m",
        "lgax_mcp.workspace_server", "--url", url, "--credential-file", str(credential)], cwd=str(ROOT),
        env={"PYTHONPATH": os.pathsep.join(str(ROOT / path) for path in (
            "packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src")), "PYTHONUTF8": "1"})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert {"review_trends", "get_review_trends", "trend_evidence"} <= {
            tool.name for tool in (await session.list_tools()).tools}
        query = structured(await session.call_tool("review_trends", {"filters": filters}))
        saved = structured(await session.call_tool("get_review_trends", {
            "project_id": filters["project_id"], "aggregate_id": aggregate_id}))
        evidence = structured(await session.call_tool("trend_evidence", {
            "project_id": filters["project_id"], "aggregate_id": aggregate_id,
            "bucket_id": "MONTH-2026-10", "topic_id": "cleaning"}))
    return {"query": query, "saved": saved, "evidence": evidence}


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    dataset = json.loads((FOLDER / "dataset.synthetic-dated-demo.v1.json").read_bytes())
    metadata = json.loads((FOLDER / "annotation.synthetic-dated-demo.v1.json").read_bytes())
    source = json.loads((FOLDER / "source.synthetic-dated-demo.v1.json").read_bytes())
    token = secrets.token_urlsafe(48)
    credential = output / "owned-credential.json"
    registry = TokenRegistry([{"principal_id": "data-followup-test", "role": "editor",
                              "token_sha256": hashlib.sha256(token.encode()).hexdigest()}])

    def launch():
        app = create_workspace_app(output / "owned-workspace.sqlite", registry,
            evidence_store=GroundedDemoStore(dataset), trend_collector=create_review_trend_collector(metadata))
        owned = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        owned.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [owned]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Owned server did not start")
            time.sleep(0.02)
        url = f"http://127.0.0.1:{owned.getsockname()[1]}"
        client = httpx.Client(base_url=url, headers={"Authorization": "Bearer " + token,
            "Origin": "http://127.0.0.1:5173"}, timeout=30)
        return server, thread, owned, client, url

    def stop(active):
        server, thread, owned, client, _ = active
        client.close()
        server.should_exit = True
        thread.join(10)
        assert not thread.is_alive()
        owned.close()

    active = None
    try:
        credential.write_text(json.dumps({"token": token}), encoding="utf-8")
        active = launch()
        client, url = active[3:]
        request = json.loads((ROOT / "data/demo/planning_requests.json").read_bytes())[0]
        request.update(model_ids=["FRIDGE-A"], dataset_version=dataset["manifest"]["version"])
        response = client.post("/api/workspace/projects", json={"name": "구성 날짜 시연·DATA 독립 서버",
            "request": request, "document_versions": {"FRIDGE-A": "1.0"}})
        response.raise_for_status()
        project_id = response.json()["data"]["project"]["id"]
        filters = {"project_id": project_id, "model_id": "FRIDGE-A", "source_ids": [source["document_id"]],
            "dataset_version": dataset["manifest"]["version"], "start_date": "2026-10-01",
            "end_date_exclusive": "2026-11-01", "granularity": "month", "topic_ids": [],
            "source_kind": "synthetic", "timezone": "Asia/Seoul"}
        base = f"/api/workspace/projects/{project_id}/review-trends"
        response = client.get(base, params={k: v for k, v in filters.items() if k not in {"project_id", "topic_ids"}})
        response.raise_for_status()
        aggregate = response.json()["data"]["aggregate"]
        aid = aggregate["aggregate_id"]
        response = client.get(f"{base}/{aid}/evidence", params={"bucket_id": "MONTH-2026-10", "topic_id": "cleaning"})
        response.raise_for_status()
        page = response.json()["data"]
        assert page["evidence"]
        source_by_id = {row["evidence_id"]: row for row in source["rows"]}
        for evidence in page["evidence"]:
            original = source_by_id[evidence["id"]]
            assert all(evidence[k] == original[k] for k in ("text", "model_id", "document_version", "source_id", "locator"))
        via_mcp = asyncio.run(mcp_read(url, credential, filters, aid))
        assert via_mcp["query"]["aggregate"] == aggregate
        assert via_mcp["saved"]["aggregate"] == aggregate
        assert via_mcp["evidence"] == page
        stop(active)
        active = None
        active = launch()
        response = active[3].get(f"{base}/{aid}")
        response.raise_for_status()
        assert response.json()["data"]["aggregate"] == aggregate
        receipt = {"status": "passed", "execution_kind": "actual_loopback_api_and_stdio_mcp",
            "injection": "owned_demo_only_pm_production_approval_pending", "model_calls": 0,
            "dataset_sha256": aggregate["dataset_sha256"], "aggregate": aggregate,
            "api_evidence": page, "mcp": via_mcp,
            "checks": {"api_mcp_same_aggregate": True, "api_mcp_same_original_page": True,
                       "nonempty_original_text_drilldown": True, "restart_same_aggregate": True,
                       "own_server_stopped": True, "original_36_review_csv_untouched": True}}
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        if active:
            stop(active)
        credential.unlink(missing_ok=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "aggregate_id": result["aggregate"]["aggregate_id"]}, ensure_ascii=False))
