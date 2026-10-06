"""Same aggregate through the real workspace API and a real MCP stdio server (record 최길웅-20261006-031).

Runs against a workspace server with a trusted collector (here the unit FixtureCollector server). Steps:
project → review_trends (API) → saved aggregate by ID (API) → original-text page (API) → MCP review_trends /
get_review_trends / trend_evidence over real HTTP. Every comparison is written to the output JSON; tokens are never
printed or stored. A 501 from a server without a collector is recorded as `not_connected`, not as success.
"""
import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[5]


def structured(result) -> dict:
    data = getattr(result, "structuredContent", None)
    if data is None:
        data = json.loads(next(item.text for item in result.content if item.type == "text"))
    return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data


async def mcp_calls(url: str, credential: Path, project_id: str, filters: dict, aggregate_id: str) -> dict:
    params = StdioServerParameters(command=sys.executable, args=[
        "-X", "utf8", "-m", "lgax_mcp.workspace_server", "--url", url, "--credential-file", str(credential)], cwd=str(ROOT))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = sorted(tool.name for tool in (await session.list_tools()).tools)
        query = structured(await session.call_tool("review_trends", {"filters": filters}))
        saved = structured(await session.call_tool("get_review_trends", {"project_id": project_id, "aggregate_id": aggregate_id}))
        page = structured(await session.call_tool("trend_evidence", {
            "project_id": project_id, "aggregate_id": aggregate_id, "bucket_id": "MONTH-2026-10", "topic_id": "cleaning"}))
        return {"tools": tools, "query": query, "saved": saved, "evidence": page}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18879")
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    token = json.loads(args.credential_file.read_text("utf-8"))["token"]
    api = httpx.Client(base_url=args.url, headers={"Authorization": f"Bearer {token}", "Origin": "http://127.0.0.1:5173"}, timeout=30)
    request = json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))[0]
    request["model_ids"] = ["FRIDGE-A"]
    created = api.post("/api/workspace/projects", json={"name": "R3 동향 소비 경로 단위 fixture", "request": request,
                                                       "document_versions": {"FRIDGE-A": "1.0"}})
    created.raise_for_status()
    project = created.json()["data"]["project"]
    document_versions = created.json()["data"]["document_versions"]
    project_id = project["id"]
    # Empty topic_ids on purpose: assignment R3 asks to compare an empty topic filter exactly.
    filters = {"project_id": project_id, "model_id": "FRIDGE-A", "source_ids": ["REVIEWS-CSV-v1.0"], "dataset_version": "0.1.0",
               "start_date": "2026-10-01", "end_date_exclusive": "2026-11-01", "granularity": "month", "topic_ids": [],
               "source_kind": "synthetic", "timezone": "Asia/Seoul"}
    base = f"/api/workspace/projects/{project_id}/review-trends"
    query = {key: value for key, value in filters.items() if key not in ("project_id", "topic_ids")}
    first = api.get(base, params=query)
    out: dict = {"kind": "review_trend_consumption_path", "observed_at": datetime.now(UTC).isoformat(), "server": args.url,
                 "collector": "tests/test_workspace_trends.py::FixtureCollector (unit fixture, not DATA #148)", "project_id": project_id,
                 "filters": filters, "checks": {}}
    if first.status_code == 501:
        out["result"] = "not_connected"
        out["api_query"] = first.json()
    else:
        first.raise_for_status()
        aggregate = first.json()["data"]["aggregate"]
        aid = aggregate["aggregate_id"]
        again = api.get(f"{base}/{aid}").json()["data"]["aggregate"]
        page = api.get(f"{base}/{aid}/evidence", params={"bucket_id": "MONTH-2026-10", "topic_id": "cleaning", "offset": 0, "limit": 50}).json()["data"]
        via_mcp = asyncio.run(mcp_calls(args.url, args.credential_file, project_id, filters, aid))
        m_query, m_saved, m_page = (via_mcp[key].get("data", via_mcp[key]) for key in ("query", "saved", "evidence"))
        m_query_agg, m_saved_agg = m_query.get("aggregate", m_query), m_saved.get("aggregate", m_saved)
        checks = out["checks"]
        checks["api_requery_same_aggregate"] = again == aggregate
        checks["api_empty_topic_filter_kept"] = aggregate["filters"]["topic_ids"] == []
        checks["api_evidence_same_key"] = (page["aggregate_id"], page["bucket_id"], page["topic_id"]) == (aid, "MONTH-2026-10", "cleaning")
        checks["api_evidence_in_bucket_ids"] = sorted(item["id"] for item in page["evidence"]) == sorted(aggregate["buckets"][0]["topics"][0]["evidence_ids"])
        checks["api_evidence_document_version"] = sorted({item["document_version"] for item in page["evidence"]}) == [document_versions["FRIDGE-A"]]
        checks["mcp_tools_present"] = {"review_trends", "get_review_trends", "trend_evidence"} <= set(via_mcp["tools"])
        checks["mcp_query_same_id"] = m_query_agg.get("aggregate_id") == aid
        checks["mcp_saved_identical"] = m_saved_agg == aggregate
        checks["mcp_same_dataset_sha256"] = m_saved_agg.get("dataset_sha256") == aggregate["dataset_sha256"]
        checks["mcp_evidence_identical"] = m_page == page
        out["aggregate_id"] = aid
        out["dataset_sha256"] = aggregate["dataset_sha256"]
        out["counts"] = aggregate["counts"]
        out["buckets"] = aggregate["buckets"]
        out["evidence_ids"] = [item["id"] for item in page["evidence"]]
        out["mcp_tools"] = via_mcp["tools"]
        out["result"] = "consumption_path_ok" if all(checks.values()) else "consumption_path_mismatch"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": out["result"], "checks": out["checks"], "aggregate_id": out.get("aggregate_id")}, ensure_ascii=False))
    return 0 if out["result"] in ("consumption_path_ok", "not_connected") else 1


if __name__ == "__main__":
    raise SystemExit(main())
