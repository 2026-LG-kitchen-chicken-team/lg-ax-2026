"""New MCP feedback wire checks only: fixed actual sources, no model or quality claim."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

import httpx
from lgax_mcp.workspace_client import WorkspaceClient
from lgax_mcp.workspace_server import create_workspace_mcp

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data/research/r8-public-research-20261007/bundles/dishwasher.development.research-bundle.json"
EXPECTED_TOOLS = {
    "list_workspace_projects", "create_workspace_project", "get_workspace_project",
    "create_workspace_run", "get_workspace_run", "list_workspace_runs", "search_workspace_evidence",
    "review_trends", "get_review_trends", "trend_evidence",
    "list_research_bundles", "get_research_bundle", "create_research_run", "get_research_run",
}


def tool_payload(result):
    if isinstance(result, tuple):
        return result[1]
    if isinstance(result, dict):
        return result
    return json.loads(result[0].text)


class ResearchMcpFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        # Only the wire response is a stub. Source originals and facts come from the fixed public pack.
        self.brief = {
            "schema_version": "1.0", "brief_id": "test-wire-brief-2", "run_id": "test-wire-run-2",
            "bundle_id": self.bundle["bundle_id"], "revision": 1,
            "previous_brief_id": "test-wire-brief-1", "status": "needs_sources",
            "product_group": self.bundle["product_group"], "analysis_scope": self.bundle["analysis_scope"],
            "goal": "TEST ONLY: MCP 전송 검사", "constraints": ["TEST ONLY: 기존 조건 유지"],
            "problems": [], "comparisons": [], "concepts": [],
            "source_facts": [{"source_id": source["source_id"], "facts": deepcopy(source["facts"])}
                             for source in self.bundle["sources"]],
            "uncertainties": ["TEST ONLY: 모델 호출·대상 의미 검증·품질 평가를 수행하지 않습니다."],
            "summaries": {"positive": [], "negative": [], "mixed": []}, "relations": [],
            "runtime": {"execution_kind": "test_only_wire_stub", "model_calls": []},
        }
        self.feedback = [{
            "item_kind": "Comparison", "item_id": "test-wire-comparison",
            "fields": ["existing_response"], "message": "TEST ONLY: 지정 필드 수정 의견 전송",
        }]
        self.requests = []

        def handle(request):
            body = json.loads(request.content) if request.content else None
            self.requests.append((request.method, request.url.path, body))
            return httpx.Response(201 if request.method == "POST" else 200, json=deepcopy(self.brief))

        self.client = WorkspaceClient("http://127.0.0.1", "x" * 48, transport=httpx.MockTransport(handle))

    def test_optional_feedback_keeps_existing_payload_without_null_field(self):
        self.client.create_research_run(self.bundle["bundle_id"], self.brief["goal"])
        self.assertEqual(self.requests, [("POST", "/api/research/planning-runs", {
            "bundle_id": self.bundle["bundle_id"], "goal": self.brief["goal"],
            "constraints": [], "previous_run_id": None,
        })])

    def test_empty_feedback_is_preserved_for_backend_validation(self):
        self.client.create_research_run(self.bundle["bundle_id"], self.brief["goal"],
                                        self.brief["constraints"], "test-wire-run-1", [])
        self.assertEqual(self.requests[0][2]["review_feedback"], [])

    def test_mcp_feedback_and_readback_preserve_exact_saved_version(self):
        server = create_workspace_mcp(self.client)
        feedback_before = deepcopy(self.feedback)
        saved = tool_payload(asyncio.run(server.call_tool("create_research_run", {
            "bundle_id": self.bundle["bundle_id"], "goal": self.brief["goal"],
            "constraints": self.brief["constraints"], "previous_run_id": "test-wire-run-1",
            "review_feedback": self.feedback,
        })))
        readback = tool_payload(asyncio.run(server.call_tool("get_research_run", {"run_id": saved["run_id"]})))
        self.assertEqual(saved, self.brief)
        self.assertEqual(readback, saved)
        self.assertEqual(self.feedback, feedback_before)
        self.assertEqual(self.requests, [
            ("POST", "/api/research/planning-runs", {
                "bundle_id": self.bundle["bundle_id"], "goal": self.brief["goal"],
                "constraints": self.brief["constraints"], "previous_run_id": "test-wire-run-1",
                "review_feedback": feedback_before,
            }),
            ("GET", "/api/research/planning-runs/test-wire-run-2", None),
        ])

    def test_mcp_lists_exact_tools_and_optional_feedback_schema(self):
        tools = asyncio.run(create_workspace_mcp(self.client).list_tools())
        self.assertEqual({tool.name for tool in tools}, EXPECTED_TOOLS)
        repair = next(tool for tool in tools if tool.name == "create_research_run")
        self.assertIn("review_feedback", repair.inputSchema["properties"])
        self.assertNotIn("review_feedback", repair.inputSchema.get("required", []))
        self.assertEqual(repair.inputSchema["properties"]["review_feedback"]["default"], None)
        self.assertFalse(repair.annotations.idempotentHint)
        self.assertEqual(self.requests, [])

    def test_backend_rejection_is_returned_without_automatic_retry(self):
        attempts = []

        def reject(request):
            attempts.append(json.loads(request.content))
            return httpx.Response(422, json={"ok": False, "error": {
                "code": "INVALID_ARGUMENT", "message": "TEST ONLY: 수정 대상을 확인해 주세요.",
            }})

        client = WorkspaceClient("http://127.0.0.1", "x" * 48, transport=httpx.MockTransport(reject))
        result = tool_payload(asyncio.run(create_workspace_mcp(client).call_tool("create_research_run", {
            "bundle_id": self.bundle["bundle_id"], "goal": self.brief["goal"],
            "constraints": self.brief["constraints"], "previous_run_id": "test-wire-run-1",
            "review_feedback": self.feedback,
        })))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["review_feedback"], self.feedback)


if __name__ == "__main__":
    unittest.main()
