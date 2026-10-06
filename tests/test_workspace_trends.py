"""Private trend gateway regression; synthetic collector fixture, no model/network.

The 36 canonical demo reviews remain unchanged. One review receives an explicit
unit-fixture date/topic annotation; this is not an approved production sidecar,
source-date verification, successful live collector or customer-demand evidence.
"""

import asyncio
import json
import os
import sqlite3
import sys
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from fastapi.testclient import TestClient
from lgax_api.trend_validation import (
    annotation_digest,
    trend_identity,
    trend_periods,
    trend_sample_warnings,
)
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_api.workspace_trends import TrendCollection
from lgax_contracts import validate
from lgax_core.store import DemoStore
from lgax_mcp.workspace_client import WorkspaceClient
from lgax_mcp.workspace_server import create_workspace_mcp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
TOKENS = {"editor": "e" * 48, "viewer": "v" * 48, "other": "o" * 48, "admin": "a" * 48}
TREND_TOOLS = {"review_trends", "get_review_trends", "trend_evidence"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def fixture_collection(project, dataset, filters):
    """Build a bound unit fixture from originals, never manufacture review text."""
    templates = json.loads((ROOT / "packages/contracts/fixtures/review-trends.v1.json")
                           .read_text("utf-8"))["templates"]
    digest = sha256(canonical(dataset).encode("utf-8")).hexdigest()
    metadata = deepcopy(templates["metadata"])
    metadata.update(dataset_version=dataset["manifest"]["version"], dataset_sha256=digest,
                    annotation_version="synthetic-workspace-unit.v1")
    metadata["rows"] = []
    selected = next(review for review in dataset["reviews"] if review["id"] == "REVIEW-001")
    for review in dataset["reviews"]:
        row = deepcopy(templates["row_day"])
        row.update(review_id=review["id"], evidence_id=review["evidence_id"],
                   source_id=review["source_id"], model_id=review["model_id"],
                   document_version=review["document_version"], source_kind=review["source_kind"],
                   text_sha256=sha256(review["text"].encode("utf-8")).hexdigest(),
                   published_at=None, date_precision="unknown", date_provenance=None,
                   topic_ids=[], classification_status="unclassified", dedup_key=None)
        if review["id"] == selected["id"]:
            row.update(published_at="2026-10-05", date_precision="day", topic_ids=["cleaning"],
                       classification_status="classified", date_provenance={
                           "source_id": review["source_id"], "locator": deepcopy(review["locator"]),
                           "source_sha256": digest,
                       })
        metadata["rows"].append(row)
    metadata["annotation_sha256"] = annotation_digest(metadata)
    aggregate = deepcopy(templates["aggregate"])
    aggregate.update(project_id=filters["project_id"], filters=deepcopy(filters),
                     dataset_version=metadata["dataset_version"], dataset_sha256=digest,
                     annotation_version=metadata["annotation_version"],
                     annotation_sha256=metadata["annotation_sha256"],
                     classification=deepcopy(metadata["classification"]),
                     topic_taxonomy_version=metadata["topic_taxonomy_version"],
                     dedup_policy_version=metadata["dedup_policy_version"],
                     warnings=["합성 날짜를 명시한 단위 collector fixture입니다. 수요 증거가 아닙니다."],
                     notes="36개 원문 보존, 테스트용 날짜 1개. 실제 원문 날짜 확인 주장이 아닙니다.")
    aggregate["counts"] = {
        "input_review_count": 36, "excluded_out_of_scope_count": 26,
        "in_scope_review_count": 10, "excluded_undated_count": 9,
        "excluded_outside_period_count": 0, "duplicate_count": 0,
        "eligible_unique_review_count": 1, "unclassified_review_count": 0,
    }
    aggregate["buckets"] = [{
        **trend_periods(filters)[0], "total_reviews": 1, "topics": [{
            "topic_id": "cleaning", "topic_review_count": 1, "ratio": 1,
            "evidence_count": 1, "evidence_ids": [selected["evidence_id"]],
            "evidence_ids_truncated": False,
        }],
    }]
    aggregate["warnings"].extend(trend_sample_warnings(aggregate["buckets"]))
    aggregate["aggregate_id"] = trend_identity(filters, metadata, aggregate["aggregation_version"])
    memberships = {"MONTH-2026-10": {"__all__": [selected["evidence_id"]],
                                        "cleaning": [selected["evidence_id"]]}}
    return TrendCollection(aggregate, metadata, memberships)


class FixtureCollector:
    """Only trusted test injection: no inference, downloads or external requests."""

    def __init__(self):
        self.calls = 0
        self.mutate = None
        self.last = None

    def __call__(self, project, dataset, filters):
        self.calls += 1
        collection = fixture_collection(project, dataset, filters)
        if self.mutate is not None:
            self.mutate(collection)
        self.last = collection
        return collection


class WorkspaceTrendTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "workspace.sqlite"
        self.registry = TokenRegistry([
            {"principal_id": "other" if role == "other" else "pm" if role == "admin" else "planner",
             "role": "editor" if role == "other" else role,
             "token_sha256": sha256(token.encode()).hexdigest()}
            for role, token in TOKENS.items()
        ])
        self.collector = FixtureCollector()
        self.app = create_workspace_app(self.db_path, self.registry,
                                        planning_runner=None, trend_collector=self.collector)
        self.client = self.enterContext(TestClient(self.app, base_url="http://127.0.0.1"))
        request = json.loads((ROOT / "data/demo/planning_requests.json").read_text("utf-8"))[0]
        request["model_ids"] = ["FRIDGE-A"]
        self.project_input = {"name": "합성 리뷰 동향 단위 fixture", "request": request,
                              "document_versions": {"FRIDGE-A": "1.0"}}
        response = self.client.post("/api/workspace/projects", headers=self.headers(),
                                    json=self.project_input)
        self.assertEqual(response.status_code, 201, response.text)
        self.project_id = response.json()["data"]["project"]["id"]
        self.filters = {
            "project_id": self.project_id, "model_id": "FRIDGE-A",
            "source_ids": ["REVIEWS-CSV-v1.0"], "dataset_version": "0.1.0",
            "start_date": "2026-10-01", "end_date_exclusive": "2026-11-01",
            "granularity": "month", "topic_ids": ["cleaning"],
            "source_kind": "synthetic", "timezone": "Asia/Seoul",
        }

    def headers(self, role="editor"):
        return {"Authorization": "Bearer " + TOKENS[role]}

    def url(self, project_id=None):
        return f"/api/workspace/projects/{project_id or self.project_id}/review-trends"

    def query(self, **changes):
        filters = {**deepcopy(self.filters), **changes}
        return {key: value for key, value in filters.items() if key != "project_id"}

    def collect(self, role="editor", **changes):
        return self.client.get(self.url(), headers=self.headers(role), params=self.query(**changes))

    def saved(self):
        response = self.collect()
        self.assertEqual(response.status_code, 200, response.text)
        validate("WorkspaceReviewTrendResponse", response.json())
        return response.json()["data"]["aggregate"]

    def evidence(self, aggregate_id, role="editor", **changes):
        params = {"bucket_id": "MONTH-2026-10", "topic_id": "cleaning",
                  "offset": 0, "limit": 50, **changes}
        return self.client.get(f"{self.url()}/{aggregate_id}/evidence",
                               headers=self.headers(role), params=params)

    def test_missing_or_invalid_auth_is_401_before_collector(self):
        for headers in ({}, {"Authorization": "Bearer " + "x" * 48}):
            with self.subTest(headers=bool(headers)):
                response = self.client.get(self.url(), headers=headers, params=self.query())
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")
        self.assertEqual(self.collector.calls, 0)

    def test_viewer_reads_and_other_owner_rejected_before_collector(self):
        denied = self.collect("other")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.headers["cache-control"], "no-store")
        self.assertEqual(self.collector.calls, 0)
        self.assertEqual(self.collect("viewer").status_code, 200)
        self.assertEqual(self.collect("admin").status_code, 200)
        self.assertEqual(self.client.post("/api/workspace/projects", headers=self.headers("viewer"),
                                          json=self.project_input).status_code, 403)

    def test_missing_collector_is_501_not_an_empty_success(self):
        self.app.state.review_trends.collector = None
        response = self.collect()
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["error"]["code"], "NOT_IMPLEMENTED")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_invalid_query_is_422_and_never_invokes_collector(self):
        cases = [{"model_id": "FRIDGE-B"}, {"source_ids": ["MISSING-SOURCE"]},
                 {"source_kind": "public"},
                 {"start_date": "2026-02-30"}, {"end_date_exclusive": "2026-09-01"},
                 {"granularity": "week"}, {"timezone": "UTC"}]
        for changes in cases:
            with self.subTest(changes=changes):
                response = self.collect(**changes)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.collector.calls, 0)

    def test_changed_dataset_version_is_409_before_collector(self):
        response = self.collect(dataset_version="different.v1")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["error"]["code"], "DATASET_MISMATCH")
        self.assertEqual(self.collector.calls, 0)

    def test_success_counts_nullable_dates_and_originals_are_bound(self):
        aggregate = self.saved()
        self.assertEqual(aggregate["counts"]["input_review_count"], 36)
        self.assertEqual(aggregate["counts"]["excluded_undated_count"], 9)
        self.assertEqual(aggregate["buckets"][0]["total_reviews"], 1)
        metadata = self.collector.last.metadata
        self.assertEqual(len(metadata["rows"]), 36)
        self.assertEqual(sum(row["published_at"] is None for row in metadata["rows"]), 35)
        self.assertEqual(metadata["annotation_sha256"], annotation_digest(metadata))
        self.assertEqual(aggregate["aggregate_id"],
                         trend_identity(aggregate["filters"], metadata, aggregate["aggregation_version"]))
        response = self.evidence(aggregate["aggregate_id"], role="viewer")
        self.assertEqual(response.status_code, 200, response.text)
        validate("WorkspaceTrendEvidenceResponse", response.json())
        expected = DemoStore().get_evidence("REVIEW-EVIDENCE-001")["data"]["evidence"]
        self.assertEqual(response.json()["data"]["evidence"], [expected])
        self.assertEqual(response.json()["data"]["total"], 1)
        self.assertIsNone(response.json()["data"]["next_offset"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_bound_snapshot_has_same_id_for_repeat_collection(self):
        first = self.saved()
        second = self.saved()
        self.assertEqual(first, second)
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM workspace_review_trends").fetchone()[0], 1)

    def test_reordered_metadata_rows_reuse_same_immutable_snapshot(self):
        first = self.saved()
        self.collector.mutate = lambda collection: collection.metadata["rows"].reverse()
        response = self.collect()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["aggregate"], first)
        fetched = self.client.get(f"{self.url()}/{first['aggregate_id']}", headers=self.headers())
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["data"]["aggregate"], first)
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM workspace_review_trends").fetchone()[0], 1)

    def test_provider_wrong_model_source_and_original_hash_are_rejected(self):
        for field, value in (("model_id", "FRIDGE-B"), ("source_id", "WRONG-SOURCE"),
                             ("document_version", "different.v1"), ("source_kind", "public"),
                             ("evidence_id", "MANUAL-001"), ("text_sha256", "0" * 64)):
            with self.subTest(field=field):
                def corrupt(collection, field=field, value=value):
                    collection.metadata["rows"][0][field] = value
                    collection.metadata["annotation_sha256"] = annotation_digest(collection.metadata)
                    collection.aggregate["annotation_sha256"] = collection.metadata["annotation_sha256"]
                    collection.aggregate["aggregate_id"] = trend_identity(
                        collection.aggregate["filters"], collection.metadata,
                        collection.aggregate["aggregation_version"])
                self.collector.mutate = corrupt
                response = self.collect()
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "CONTRACT_MISMATCH")
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM workspace_review_trends").fetchone()[0], 0)

    def test_provider_dataset_annotation_and_identity_hashes_are_checked(self):
        cases = [("dataset_sha256", "0" * 64, 409, "DATASET_MISMATCH"),
                 ("annotation_sha256", "0" * 64, 409, "DATASET_MISMATCH"),
                 ("aggregate_id", "TREND-" + "0" * 64, 422, "CONTRACT_MISMATCH")]
        for field, value, status, code in cases:
            with self.subTest(field=field):
                self.collector.mutate = lambda collection, field=field, value=value: collection.aggregate.update({field: value})
                response = self.collect()
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(response.json()["error"]["code"], code)

    def test_provider_arithmetic_and_membership_cannot_claim_unincluded_reviews(self):
        mutations = [
            lambda collection: collection.aggregate["buckets"][0].update(total_reviews=2),
            lambda collection: collection.aggregate["buckets"][0]["topics"][0].update(ratio=0.5),
            lambda collection: collection.memberships["MONTH-2026-10"]["cleaning"].append("REVIEW-EVIDENCE-002"),
            lambda collection: collection.memberships["MONTH-2026-10"].update(__all__=[]),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(case=index):
                self.collector.mutate = mutation
                response = self.collect()
                self.assertEqual(response.status_code, 422, response.text)

    def test_provider_missing_small_sample_warning_is_rejected(self):
        def omit_warning(collection):
            required = set(trend_sample_warnings(collection.aggregate["buckets"]))
            collection.aggregate["warnings"] = [warning for warning in collection.aggregate["warnings"]
                                                  if warning not in required]
        self.collector.mutate = omit_warning
        response = self.collect()
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "CONTRACT_MISMATCH")

    def test_same_identity_changed_payload_does_not_overwrite_original(self):
        first = self.saved()
        self.collector.mutate = lambda collection: collection.aggregate["warnings"].append("변경된 fixture 표시")
        response = self.collect()
        self.assertEqual(response.status_code, 422, response.text)
        fetched = self.client.get(f"{self.url()}/{first['aggregate_id']}", headers=self.headers())
        self.assertEqual(fetched.json()["data"]["aggregate"], first)

    def test_saved_snapshot_survives_restart_without_collector(self):
        first = self.saved()
        restarted = create_workspace_app(self.db_path, self.registry, planning_runner=None, trend_collector=None)
        with TestClient(restarted, base_url="http://127.0.0.1") as client:
            response = client.get(f"{self.url()}/{first['aggregate_id']}", headers=self.headers("viewer"))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"]["aggregate"], first)
            detail = client.get(f"{self.url()}/{first['aggregate_id']}/evidence", headers=self.headers(),
                                params={"bucket_id": "MONTH-2026-10", "topic_id": "cleaning"})
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json()["data"]["evidence"][0]["id"], "REVIEW-EVIDENCE-001")

    def test_saved_drilldown_preserves_original_after_live_dataset_changes(self):
        aid = self.saved()["aggregate_id"]
        original = self.evidence(aid).json()
        dataset = DemoStore().bootstrap()["data"]
        dataset.pop("contract_version", None)
        dataset["reviews"][0]["text"] = "다른 합성 자료로 변경된 본문"
        next(item for item in dataset["evidence"] if item["id"] == "REVIEW-EVIDENCE-001")["text"] = dataset["reviews"][0]["text"]
        restarted = create_workspace_app(self.db_path, self.registry, planning_runner=None,
                                          evidence_store=DemoStore(dataset), trend_collector=None)
        with TestClient(restarted, base_url="http://127.0.0.1") as client:
            detail = client.get(f"{self.url()}/{aid}/evidence", headers=self.headers(),
                                params={"bucket_id": "MONTH-2026-10", "topic_id": "cleaning"})
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json(), original)

    def test_saved_snapshot_checksum_corruption_is_rejected(self):
        aid = self.saved()["aggregate_id"]
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("UPDATE workspace_review_trends SET snapshot_sha256=? WHERE aggregate_id=?",
                               ("0" * 64, aid))
        response = self.client.get(f"{self.url()}/{aid}", headers=self.headers())
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "CONTRACT_MISMATCH")
        self.assertEqual(self.evidence(aid).status_code, 422)

    def test_saved_snapshot_and_drilldown_stay_in_project_owner_scope(self):
        aggregate = self.saved()
        aid = aggregate["aggregate_id"]
        for path in (f"{self.url()}/{aid}", f"{self.url()}/{aid}/evidence"):
            response = self.client.get(path, headers=self.headers("other"),
                                       params={"bucket_id": "MONTH-2026-10", "topic_id": "cleaning"})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.evidence(aid, role="admin").status_code, 200)
        second = self.client.post("/api/workspace/projects", headers=self.headers(),
                                  json={**self.project_input, "name": "다른 프로젝트"})
        pid = second.json()["data"]["project"]["id"]
        response = self.client.get(f"{self.url(pid)}/{aid}", headers=self.headers())
        self.assertEqual(response.status_code, 404)

    def test_drilldown_rejects_missing_memberships_and_invalid_page_bounds(self):
        aid = self.saved()["aggregate_id"]
        for changes in ({"bucket_id": "MISSING"}, {"topic_id": "missing"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.evidence(aid, **changes).status_code, 404)
        for changes in ({"offset": -1}, {"limit": 0}, {"limit": 51}):
            with self.subTest(changes=changes):
                self.assertEqual(self.evidence(aid, **changes).status_code, 422)
        empty = self.evidence(aid, offset=1, limit=1)
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()["data"]["evidence"], [])
        self.assertEqual(empty.json()["data"]["total"], 1)

    def test_drilldown_reserved_denominator_is_invalid_input(self):
        aid = self.saved()["aggregate_id"]
        response = self.evidence(aid, topic_id="__all__")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")

    def test_provider_diagnostics_are_hidden_and_failure_not_saved(self):
        def fail(project, dataset, filters):
            raise RuntimeError("PRIVATE-COLLECTOR-DIAGNOSTIC")
        self.app.state.review_trends.collector = fail
        response = self.collect()
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("PRIVATE-COLLECTOR-DIAGNOSTIC", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM workspace_review_trends").fetchone()[0], 0)

    def test_http_and_mcp_proxy_share_aggregate_and_original_evidence(self):
        http_result = self.collect().json()
        seen = []
        def handle(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.headers["x-lgax-client"], "mcp")
            seen.append(str(request.url))
            response = self.client.get(str(request.url), headers=dict(request.headers))
            return httpx.Response(response.status_code, json=response.json(), headers=response.headers)
        proxy = WorkspaceClient("http://127.0.0.1", TOKENS["viewer"], transport=httpx.MockTransport(handle))
        result = proxy.review_trends(self.filters)
        self.assertEqual(result, http_result)
        aid = result["data"]["aggregate"]["aggregate_id"]
        self.assertEqual(proxy.get_review_trends(self.project_id, aid), result)
        detail = proxy.trend_evidence(self.project_id, aid, "MONTH-2026-10", "cleaning")
        self.assertEqual(detail, self.evidence(aid).json())
        self.assertEqual(len(seen), 3)

    def test_sdk_stdio_lists_three_readonly_trend_tools_and_calls_mock_transport(self):
        aggregate_response = self.collect().json()
        aid = aggregate_response["data"]["aggregate"]["aggregate_id"]
        fixture = {"filters": self.filters, "aggregate_response": aggregate_response,
                   "evidence_response": self.evidence(aid).json()}
        fixture_path = Path(self.temp.name) / "stdio-fixture.json"
        fixture_path.write_text(canonical(fixture), "utf-8")

        async def check():
            params = StdioServerParameters(command=sys.executable,
                args=[str(Path(__file__).resolve()), "--fixture-stdio", str(fixture_path)], cwd=str(ROOT),
                env={"PYTHONPATH": os.pathsep.join(str(ROOT / relative) for relative in (
                    "apps/api/src", "apps/mcp/src", "packages/core/src", "packages/contracts/src",
                ))})
            async with stdio_client(params) as streams, ClientSession(*streams) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                self.assertTrue(TREND_TOOLS <= set(tools))
                for name in TREND_TOOLS:
                    annotations = tools[name].annotations
                    self.assertTrue(annotations.readOnlyHint)
                    self.assertTrue(annotations.idempotentHint)
                    self.assertFalse(annotations.destructiveHint)
                    self.assertFalse(annotations.openWorldHint)
                calls = [
                    ("review_trends", {"filters": self.filters}, aggregate_response),
                    ("get_review_trends", {"project_id": self.project_id, "aggregate_id": aid}, aggregate_response),
                    ("trend_evidence", {"project_id": self.project_id, "aggregate_id": aid,
                                        "bucket_id": "MONTH-2026-10", "topic_id": "cleaning"},
                     fixture["evidence_response"]),
                ]
                for name, arguments, expected in calls:
                    result = await session.call_tool(name, arguments)
                    self.assertFalse(result.isError)
                    wire = result.model_dump(mode="json", by_alias=True)
                    structured = wire.get("structuredContent")
                    if structured is None:
                        structured = json.loads(next(item["text"] for item in wire["content"]
                                                     if item["type"] == "text"))
                    self.assertEqual(structured, expected)
        asyncio.run(check())


def fixture_stdio(path):
    """SDK child process uses MockTransport exclusively; it opens no HTTP socket."""
    fixture = json.loads(Path(path).read_text("utf-8"))
    filters = fixture["filters"]
    aid = fixture["aggregate_response"]["data"]["aggregate"]["aggregate_id"]
    base = f"/api/workspace/projects/{filters['project_id']}/review-trends"

    def handle(request):
        if (request.method != "GET" or request.url.host != "127.0.0.1"
                or request.headers.get("authorization") != "Bearer " + TOKENS["viewer"]
                or request.headers.get("x-lgax-client") != "mcp"):
            raise AssertionError("Unexpected mock request boundary")
        if request.url.path == base:
            if request.url.params.get("model_id") != filters["model_id"]:
                raise AssertionError("Mock query model mismatch")
            payload = fixture["aggregate_response"]
        elif request.url.path == f"{base}/{aid}":
            payload = fixture["aggregate_response"]
        elif request.url.path == f"{base}/{aid}/evidence":
            if request.url.params.get("topic_id") != "cleaning":
                raise AssertionError("Mock drilldown mismatch")
            payload = fixture["evidence_response"]
        else:
            raise AssertionError("Unexpected mock request path")
        return httpx.Response(200, json=payload, headers={"Cache-Control": "no-store"})

    client = WorkspaceClient("http://127.0.0.1", TOKENS["viewer"], transport=httpx.MockTransport(handle))
    create_workspace_mcp(client).run(transport="stdio")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture-stdio":
        fixture_stdio(sys.argv[2])
    else:
        unittest.main()
