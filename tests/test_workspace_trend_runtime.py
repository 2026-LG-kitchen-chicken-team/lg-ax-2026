"""Pinned DATA collector over real loopback HTTP and SDK stdio, with synthetic credentials.

Run in the zero-auth validator container. Dates/topics are demo fixtures, not
customer-date approval, external ChatGPT/Claude discovery or live-model quality.
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import httpx
import uvicorn
from fastapi.testclient import TestClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from lgax_api.server import create_app as create_public_app
from lgax_api.trend_configuration import CANDIDATE_WARNING, load_synthetic_store, load_trend_runtime
from lgax_api.trend_validation import annotation_digest
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.store import DemoStore
from lgax_core.documents import DocumentRepository
from lgax_core.documents_server import create_app as create_documents_app
from lgax_mcp.workspace_client import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data/demo/review-trends-dated"
ORIGINAL = ROOT / "data/demo/dataset.json"
CANDIDATE = ROOT / "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json"
TOKENS = {role: "synthetic-runtime-" + role + "-" * 40 for role in ("editor", "viewer", "other")}


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configured(*, original=False):
    path = CANDIDATE if original else DEMO / "annotation.candidate.json"
    return load_trend_runtime(dataset_path=None if original else DEMO / "dataset.json",
                              metadata_path=path, metadata_sha256=file_sha(path), allow_candidate=True)


def registry():
    return TokenRegistry([
        {"principal_id": "other" if role == "other" else "owner", "role": "editor" if role == "other" else role,
         "token_sha256": hashlib.sha256(token.encode()).hexdigest()}
        for role, token in TOKENS.items()
    ])


@contextmanager
def live_server(app):
    """Bind an isolated ephemeral loopback socket; use no deployed service/port."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Isolated loopback server did not start")
            time.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("Isolated loopback server did not stop")


class TrendRuntimeConfigurationTests(unittest.TestCase):
    def test_default_stays_disconnected_and_file_sha_is_distinct_from_annotation_sha(self):
        self.assertIsNone(load_trend_runtime().collector)
        for kwargs in ({"metadata_path": CANDIDATE}, {"metadata_sha256": file_sha(CANDIDATE)},
                       {"allow_candidate": True},
                       {"metadata_path": CANDIDATE, "metadata_sha256": "0" * 64, "allow_candidate": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                load_trend_runtime(**kwargs)
        annotation = json.loads(CANDIDATE.read_text("utf-8"))
        self.assertNotEqual(file_sha(CANDIDATE), annotation["annotation_sha256"])

    def test_candidate_requires_preview_and_dataset_review_binding_is_checked_at_startup(self):
        with self.assertRaisesRegex(ValueError, "Candidate"):
            load_trend_runtime(metadata_path=CANDIDATE, metadata_sha256=file_sha(CANDIDATE))
        with self.assertRaisesRegex(ValueError, "dataset version/hash"):
            load_trend_runtime(dataset_path=DEMO / "dataset.json", metadata_path=CANDIDATE,
                               metadata_sha256=file_sha(CANDIDATE), allow_candidate=True)
        metadata = json.loads(CANDIDATE.read_text("utf-8"))
        metadata["rows"][0]["text_sha256"] = "0" * 64
        metadata["annotation_sha256"] = annotation_digest(metadata)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tampered.json"
            path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                load_trend_runtime(metadata_path=path, metadata_sha256=file_sha(path), allow_candidate=True)

    def test_sidecar_duplicate_json_keys_and_missing_reviews_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sidecar.json"
            path.write_bytes(b'{"dataset_version":"a","dataset_version":"b"}')
            with self.assertRaisesRegex(ValueError, "Duplicate key"):
                load_trend_runtime(metadata_path=path, metadata_sha256=file_sha(path), allow_candidate=True)
            metadata = json.loads(CANDIDATE.read_text("utf-8"))
            metadata["rows"].pop()
            metadata["annotation_sha256"] = annotation_digest(metadata)
            path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "every canonical review"):
                load_trend_runtime(metadata_path=path, metadata_sha256=file_sha(path), allow_candidate=True)

    def test_original_and_dated_pack_remain_separate_and_public_store_is_synthetic_only(self):
        original = json.loads(ORIGINAL.read_text("utf-8"))
        dated = json.loads((DEMO / "dataset.json").read_text("utf-8"))
        metadata = json.loads((DEMO / "annotation.candidate.json").read_text("utf-8"))
        dates = json.loads((DEMO / "date-schedule.json").read_text("utf-8"))
        self.assertEqual(file_sha(ORIGINAL), "97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0")
        self.assertEqual(len(original["reviews"]), 36)
        self.assertEqual(len(dated["reviews"]), 36)
        self.assertTrue({r["id"] for r in original["reviews"]}.isdisjoint(r["id"] for r in dated["reviews"]))
        self.assertNotEqual(dated["manifest"]["version"], original["manifest"]["version"])
        self.assertTrue(all(row["published_at"] is None for row in json.loads(CANDIDATE.read_text("utf-8"))["rows"]))
        for row in metadata["rows"]:
            if row["date_provenance"] is not None:
                self.assertEqual(row["date_provenance"]["source_sha256"], file_sha(DEMO / "date-schedule.json"))
                scheduled = dates["rows"][row["date_provenance"]["locator"]["row"] - 1]
                self.assertEqual((scheduled["review_id"], scheduled["published_at"]),
                                 (row["review_id"], row["published_at"]))
        with TestClient(create_public_app(load_synthetic_store(DEMO / "dataset.json"))) as public:
            self.assertEqual(public.get("/api/bootstrap").json()["data"]["manifest"]["version"],
                             dated["manifest"]["version"])
            self.assertFalse(public.get("/health").json()["analysis_implemented"])
            self.assertEqual(public.post("/api/planning-requests").status_code, 501)
        with self.assertRaises(ValueError):
            create_public_app(object())
        changed = deepcopy(dated)
        changed["products"][0]["source_kind"] = "public"
        with self.assertRaisesRegex(ValueError, "synthetic"):
            DemoStore(changed)


class TrendRuntimeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "new-isolated-workspace.sqlite"

    def app(self, runtime):
        return create_workspace_app(self.db, registry(), evidence_store=runtime.evidence_store,
                                    trend_collector=runtime.collector, planning_runner=None)

    def project(self, proxy, runtime):
        request = json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))[0]
        request.update(model_ids=["FRIDGE-A"], dataset_version=runtime.evidence_store.bootstrap()["data"]["manifest"]["version"])
        return proxy.create_project("별도 합성 동향 시연", request, {"FRIDGE-A": "1.0"})["data"]["project"]["id"]

    def filters(self, project_id, runtime):
        data = runtime.evidence_store.bootstrap()["data"]
        return {"project_id": project_id, "model_id": "FRIDGE-A",
                "source_ids": sorted({r["source_id"] for r in data["reviews"] if r["model_id"] == "FRIDGE-A"}),
                "dataset_version": data["manifest"]["version"], "start_date": "2026-10-01",
                "end_date_exclusive": "2026-11-01", "granularity": "month", "topic_ids": ["cleaning"],
                "source_kind": "synthetic", "timezone": "Asia/Seoul"}

    def test_original_null_dates_are_200_empty_counts_not_501_or_invented_dates(self):
        runtime = configured(original=True)
        with live_server(self.app(runtime)) as url:
            proxy = WorkspaceClient(url, TOKENS["editor"])
            pid = self.project(proxy, runtime)
            aggregate = proxy.review_trends(self.filters(pid, runtime))["data"]["aggregate"]
            self.assertEqual(aggregate["counts"]["excluded_undated_count"], 10)
            self.assertEqual(aggregate["counts"]["eligible_unique_review_count"], 0)
            self.assertIsNone(aggregate["buckets"][0]["topics"][0]["ratio"])
            self.assertIn(CANDIDATE_WARNING, aggregate["warnings"])

    def test_dated_collector_sdk_stdio_and_web_http_share_id_sources_and_permissions(self):
        runtime = configured()
        with live_server(self.app(runtime)) as url:
            editor = WorkspaceClient(url, TOKENS["editor"])
            pid = self.project(editor, runtime)
            filters = self.filters(pid, runtime)
            web = WorkspaceClient(url, TOKENS["viewer"], client_kind="web")
            expected = web.review_trends(filters)
            aggregate = expected["data"]["aggregate"]
            self.assertEqual(aggregate["counts"]["eligible_unique_review_count"], 3)
            self.assertEqual(aggregate["buckets"][0]["topics"][0]["topic_review_count"], 1)
            detail = web.trend_evidence(pid, aggregate["aggregate_id"], "MONTH-2026-10", "cleaning")
            self.assertEqual(detail["data"]["total"], 1)
            originals = {e["id"]: e for e in runtime.evidence_store.bootstrap()["data"]["evidence"]}
            self.assertEqual(detail["data"]["evidence"], [originals[eid] for eid in aggregate["buckets"][0]["topics"][0]["evidence_ids"]])
            credentials = Path(self.temp.name) / "synthetic-sdk-credentials.json"
            credentials.write_text(json.dumps({"token": TOKENS["viewer"]}), encoding="utf-8")

            async def sdk():
                # Use the exported current sources rather than the image's editable wheel mapping.
                launch = ("import sys,runpy; sys.meta_path[:]=[f for f in sys.meta_path if not "
                          "getattr(f,'__module__','').startswith('editables')]; "
                          "runpy.run_module('lgax_mcp.workspace_server',run_name='__main__')")
                params = StdioServerParameters(command=sys.executable,
                    args=["-c", launch, "--url", url, "--credential-file", str(credentials)], cwd=str(ROOT),
                    env={"PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in (
                        "apps/api/src", "apps/mcp/src", "packages/core/src", "packages/contracts/src"))})
                async with stdio_client(params) as streams, ClientSession(*streams) as session:
                    await session.initialize()
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    for name in ("review_trends", "get_review_trends", "trend_evidence"):
                        self.assertTrue(tools[name].annotations.readOnlyHint)
                        self.assertTrue(tools[name].annotations.idempotentHint)
                    for name, args, value in [
                        ("review_trends", {"filters": filters}, expected),
                        ("get_review_trends", {"project_id": pid, "aggregate_id": aggregate["aggregate_id"]}, expected),
                        ("trend_evidence", {"project_id": pid, "aggregate_id": aggregate["aggregate_id"],
                                            "bucket_id": "MONTH-2026-10", "topic_id": "cleaning"}, detail),
                    ]:
                        reply = await session.call_tool(name, args)
                        self.assertFalse(reply.isError)
                        wire = reply.model_dump(mode="json", by_alias=True)
                        result = wire.get("structuredContent") or json.loads(next(
                            x["text"] for x in wire["content"] if x["type"] == "text"))
                        self.assertEqual(result, value)
            asyncio.run(sdk())
            path = f"/api/workspace/projects/{pid}/review-trends"
            query = {k: v for k, v in filters.items() if k != "project_id"}
            with httpx.Client(base_url=url, trust_env=False) as client:
                self.assertEqual(client.get(path, params=query).status_code, 401)
                self.assertEqual(client.get(path, params=query, headers={"Authorization": "Bearer " + TOKENS["other"]}).status_code, 403)
                response = client.get(path, params={**query, "trend_metadata": "untrusted-file", "allow_candidate": "true"},
                                      headers={"Authorization": "Bearer " + TOKENS["viewer"]})
                self.assertEqual(response.json(), expected)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_saved_sources_and_membership_survive_restart_with_different_live_dataset(self):
        runtime = configured()
        with live_server(self.app(runtime)) as url:
            proxy = WorkspaceClient(url, TOKENS["editor"])
            pid = self.project(proxy, runtime)
            filters = self.filters(pid, runtime)
            filters.update(start_date="2026-01-01", end_date_exclusive="2027-01-01", granularity="year")
            saved = proxy.review_trends(filters)
            aid = saved["data"]["aggregate"]["aggregate_id"]
            page = proxy.trend_evidence(pid, aid, "YEAR-2026", "cleaning", limit=1)
            self.assertEqual(page["data"]["next_offset"], 1)
        with live_server(self.app(load_trend_runtime())) as url:
            proxy = WorkspaceClient(url, TOKENS["viewer"])
            self.assertEqual(proxy.get_review_trends(pid, aid), saved)
            self.assertEqual(proxy.trend_evidence(pid, aid, "YEAR-2026", "cleaning", limit=1), page)
            with httpx.Client(base_url=url, trust_env=False, headers={"Authorization": "Bearer " + TOKENS["viewer"]}) as client:
                path = f"/api/workspace/projects/{pid}/review-trends"
                self.assertEqual(client.get(path, params={k: v for k, v in filters.items() if k != "project_id"}).status_code, 409)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"),
                         "Actual PDF extraction requires an explicitly supplied external pypdf environment")
    def test_original_three_pdf_registration_search_and_restart_in_new_isolated_repository(self):
        # Actual pinned PDF bytes/parser, not the mocked parser used by earlier unit fixtures.
        # This dedicated authenticated document API stays separate from synthetic bootstrap/trends.
        plan = json.loads((ROOT / "data/document_plans/lg-three-models-20261005.json").read_text("utf-8"))
        directory = Path(self.temp.name) / "new-document-repository"
        repo = DocumentRepository(directory, plan, sys.executable)
        headers = {"Authorization": "Bearer " + TOKENS["editor"]}
        with live_server(create_documents_app(repo, TOKENS["editor"])) as url:
            with httpx.Client(base_url=url, trust_env=False, timeout=120) as client:
                for spec in plan["documents"]:
                    source = next((ROOT / "data/sources/lg-manuals-20261005").glob(
                        spec["product"]["model_id"] + "-" + spec["sha256"][:12] + ".pdf"))
                    self.assertEqual(file_sha(source), spec["sha256"])
                    path = "/api/documents/" + spec["document_id"]
                    self.assertEqual(client.post(path, content=source.read_bytes()).status_code, 401)
                    result = client.post(path, content=source.read_bytes(), headers=headers)
                    self.assertEqual(result.status_code, 200, result.text)
                    record = result.json()["data"]
                    self.assertFalse(record["idempotent"])
                    self.assertEqual(record["sha256"], spec["sha256"])
                    self.assertEqual(client.get(path + "/original", headers=headers).content, source.read_bytes())
        reopened = DocumentRepository(directory, plan, sys.executable)
        with live_server(create_documents_app(reopened, TOKENS["editor"])) as url:
            with httpx.Client(base_url=url, trust_env=False, timeout=120, headers=headers) as client:
                for spec in plan["documents"]:
                    selection = spec["selections"][0]
                    query = {"q": selection["excerpt"][:20], "model_id": spec["product"]["model_id"],
                             "document_version": spec["document_version"]}
                    response = client.get("/api/evidence/search", params=query)
                    self.assertEqual(response.status_code, 200, response.text)
                    items = response.json()["data"]["items"]
                    self.assertTrue(items)
                    self.assertTrue(all(item["model_id"] == spec["product"]["model_id"]
                                        and item["document_version"] == spec["document_version"]
                                        and item["source_id"] == spec["document_id"] for item in items))
                    self.assertEqual(reopened.original(spec["document_id"]), next(
                        (ROOT / "data/sources/lg-manuals-20261005").glob(
                            spec["product"]["model_id"] + "-" + spec["sha256"][:12] + ".pdf")).read_bytes())
        with self.assertRaises(ValueError):
            create_public_app(reopened.store())


if __name__ == "__main__":
    unittest.main()
