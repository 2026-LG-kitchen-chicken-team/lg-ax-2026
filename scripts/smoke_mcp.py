"""Real MCP initialize -> tools/list -> tools/call over stdio or Streamable HTTP."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {"list_products", "search_evidence", "get_evidence"}


def _content(result):
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    return json.loads(next(item["text"] for item in result["content"] if item["type"] == "text"))


def assert_results(products, search, empty, invalid):
    assert products["ok"] and len(products["data"]["products"]) == 5
    assert search["ok"] and search["data"]["items"]
    assert all(e["model_id"] == "FRIDGE-A" and e["source_kind"] == "synthetic" for e in search["data"]["items"])
    assert empty["ok"] and empty["data"]["items"] == []
    assert invalid["ok"] is False and invalid["error"]["code"] == "INVALID_MODEL_ID"


async def smoke_stdio():
    params = StdioServerParameters(command=sys.executable, args=["-m", "lgax_mcp.server", "--transport", "stdio"], cwd=str(ROOT))
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
            calls = []
            for name, args in [("list_products", {}), ("search_evidence", {"q": "청소", "model_id": "FRIDGE-A"}),
                               ("search_evidence", {"q": "절대없는검색어"}),
                               ("search_evidence", {"q": "청소", "model_id": "WRONG"})]:
                result = await session.call_tool(name, args)
                calls.append(_content(result.model_dump(mode="json", by_alias=True)))
            assert_results(*calls)
            fetched = await session.call_tool("get_evidence", {"evidence_id": "MANUAL-001"})
            assert _content(fetched.model_dump(mode="json", by_alias=True))["data"]["evidence"]["locator"]["page"] == 1
            return {"transport": "stdio", "protocol_version": initialized.protocolVersion,
                    "tools": sorted(EXPECTED_TOOLS), "calls": 5, "status": "pass", "analysis_implemented": False}


def smoke_http(url):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with httpx.Client(timeout=15, headers=headers) as client:
        initialized = client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "lgax-smoke", "version": "0.1.0"}}})
        initialized.raise_for_status()
        version = initialized.json()["result"]["protocolVersion"]
        client.headers["MCP-Protocol-Version"] = version
        if initialized.headers.get("Mcp-Session-Id"):
            client.headers["Mcp-Session-Id"] = initialized.headers["Mcp-Session-Id"]
        notification = client.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        notification.raise_for_status()
        listed = client.post(url, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed.raise_for_status()
        names = {tool["name"] for tool in listed.json()["result"]["tools"]}
        assert names == EXPECTED_TOOLS
        results = []
        for request_id, (name, arguments) in enumerate([
            ("list_products", {}), ("search_evidence", {"q": "청소", "model_id": "FRIDGE-A"}),
            ("search_evidence", {"q": "절대없는검색어"}), ("search_evidence", {"q": "청소", "model_id": "WRONG"}),
            ("get_evidence", {"evidence_id": "MANUAL-001"}),
        ], 3):
            response = client.post(url, json={"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                                             "params": {"name": name, "arguments": arguments}})
            response.raise_for_status()
            results.append(_content(response.json()["result"]))
        assert_results(*results[:4])
        assert results[4]["data"]["evidence"]["locator"]["page"] == 1
    return {"transport": "streamable-http", "protocol_version": version, "tools": sorted(names),
            "calls": 5, "status": "pass", "analysis_implemented": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--url", help="Running MCP endpoint, e.g. http://127.0.0.1:18866/mcp")
    args = parser.parse_args()
    if args.url:
        result = smoke_http(args.url)
    elif args.transport == "stdio":
        result = asyncio.run(smoke_stdio())
    else:
        parser.error("--url is required for streamable-http")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
