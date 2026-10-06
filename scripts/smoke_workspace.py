"""Actual private API + MCP stdio handoff of a project created by the web adapter."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from lgax_contracts import validate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def content(result):
    result = result.model_dump(mode="json", by_alias=True)
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    return json.loads(next(item["text"] for item in result["content"] if item["type"] == "text"))


async def smoke(url: str, credential_file: Path, web_proof: Path):
    before = json.loads(web_proof.read_text("utf-8"))
    pid = before["project"]["project"]["id"]
    rid = before["run"]["run"]["id"]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "lgax_mcp.workspace_server",
            "--url",
            url,
            "--credential-file",
            str(credential_file.resolve()),
        ],
        cwd=str(ROOT),
    )
    async with stdio_client(parameters) as streams, ClientSession(*streams) as session:
        initialized = await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert len(names) == 10
        assert {"review_trends", "get_review_trends", "trend_evidence"} <= names
        results = []

        async def call(name, arguments, definition=None):
            value = content(await session.call_tool(name, arguments))
            if definition:
                validate(definition, value)
            results.append({"tool": name, "result": value})
            return value

        project = await call("get_workspace_project", {"project_id": pid}, "WorkspaceProjectResponse")
        saved = await call("get_workspace_run", {"run_id": rid}, "WorkspaceRunResponse")
        assert project["data"] == before["project"]
        assert saved["data"] == before["run"]
        changed = {**before["input"], "exclusions": ["전체 선반 교체 제외"]}
        second = await call(
            "create_workspace_run",
            {
                "project_id": pid,
                "request": changed,
                "previous_run_id": rid,
                "unconfirmed": ["탈착 후 수납 용량을 확인해야 함"],
            },
            "WorkspaceRunResponse",
        )
        assert second["data"]["client"] == "mcp"
        assert second["data"]["previous_run_id"] == rid
        assert second["data"]["request_revision"] == 1
        assert second["data"]["run"]["status"] == "not_implemented"
        assert second["data"]["run"]["concepts"] == []
        original = await call("get_workspace_run", {"run_id": rid}, "WorkspaceRunResponse")
        assert original["data"] == before["run"]
        history = await call("list_workspace_runs", {"project_id": pid}, "WorkspaceRunsResponse")
        assert len(history["data"]["runs"]) == 2
        search = await call(
            "search_workspace_evidence",
            {"project_id": pid, "q": "청소", "model_id": "FRIDGE-A"},
            "WorkspaceEvidenceResponse",
        )
        assert search["data"]["search"]["data"]["items"]
        assert all(item["document_version"] == "1.0" for item in search["data"]["search"]["data"]["items"])
        invalid = await call("get_workspace_run", {"run_id": "../outside"})
        assert invalid["ok"] is False and invalid["error"]["code"] == "INVALID_ARGUMENT"
    credential_directory = credential_file.parent
    editor = json.loads(credential_file.read_text("utf-8"))["token"]
    viewer = json.loads((credential_directory / "viewer-client.json").read_text("utf-8"))["token"]
    with httpx.Client(base_url=url, timeout=15) as api:
        statuses = {}
        statuses["missing_auth"] = api.get("/api/workspace/projects").status_code
        statuses["invalid_auth"] = api.get(
            "/api/workspace/projects", headers={"Authorization": "Bearer " + "wrong" * 10}
        ).status_code
        statuses["viewer_read"] = api.get(
            f"/api/workspace/runs/{rid}", headers={"Authorization": "Bearer " + viewer}
        ).status_code
        statuses["viewer_write"] = api.post(
            "/api/workspace/projects",
            headers={"Authorization": "Bearer " + viewer},
            json={"name": "읽기 전용 검증"},
        ).status_code
        assert statuses == {"missing_auth": 401, "invalid_auth": 401, "viewer_read": 200, "viewer_write": 403}
        with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + editor}, timeout=15) as another:
            from_api = another.get(f"/api/workspace/runs/{second['data']['run']['id']}").json()
            assert from_api == second
    return {
        "status": "pass",
        "execution_kind": "live_service",
        "protocol": initialized.protocolVersion,
        "project_id": pid,
        "web_run_id": rid,
        "mcp_run_id": second["data"]["run"]["id"],
        "tools": sorted(names),
        "authorization_http_statuses": statuses,
        "same_server_and_ids": True,
        "original_input_unchanged": True,
        "analysis_implemented": False,
        "limitations": [
            "SDK stdio MCP and actual TypeScript HTTP adapter; not a ChatGPT/Claude workspace OAuth test",
            "Planning/core/semantic Skills remain unimplemented",
        ],
        "calls": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18869")
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--web-proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(smoke(args.url, args.credential_file, args.web_proof))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "execution_kind",
                    "project_id",
                    "web_run_id",
                    "mcp_run_id",
                    "same_server_and_ids",
                    "analysis_implemented",
                )
            }
        )
    )
