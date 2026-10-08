"""New research boundaries tested against actual, frozen public sources."""

import json
import os
import tempfile
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import ValidationError
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_contracts.research import validate_planning_brief, validate_research_bundle
from lgax_core.errors import DomainError

ROOT = Path(__file__).resolve().parents[1]
PACK = Path(os.environ.get("LGAX_TEST_RESEARCH_BUNDLE", ROOT / "data/research/r8-public-research-20261007/bundles/dishwasher.development.research-bundle.json"))


class ContractOnlyPlanner:
    """Explicit test-only wire stub: actual sources, no fabricated reviews or quality claim."""

    def __init__(self):
        self.calls = []
        self.last_raw = None

    def run(self, bundle, goal, constraints, previous=None):
        self.calls.append(deepcopy(previous))
        sequence = len(self.calls)
        brief = {
            "schema_version": "1.0", "brief_id": f"test-brief-{sequence}", "run_id": f"test-run-{sequence}",
            "bundle_id": bundle["bundle_id"], "revision": previous["revision"] + 1 if previous else 0,
            "previous_brief_id": previous["brief_id"] if previous else None, "status": "needs_sources",
            "product_group": bundle["product_group"], "analysis_scope": bundle["analysis_scope"],
            "goal": goal, "constraints": deepcopy(constraints), "problems": [], "comparisons": [], "concepts": [],
            "source_facts": [{"source_id": source["source_id"], "facts": deepcopy(source["facts"])}
                             for source in bundle["sources"]],
            "uncertainties": ["TEST ONLY: 계약·저장 검사용이며 모델 기획 품질을 입증하지 않습니다."],
            "summaries": {"positive": [], "negative": [], "mixed": []}, "relations": [],
            "runtime": {
                "execution_kind": "test_only_contract_stub", "model_id": "test-contract-stub",
                "independent_semantic_quality_verified": True, "market_frequency_estimated": True,
                "selected_source_ids": [bundle["sources"][0]["source_id"], "http://private.example"],
                "model_calls": [
                    {"stage": "discover_1", "status": "returned", "response": {"private": "private-provider-message"},
                     "metadata": {"endpoint": "http://127.0.0.1:18875/private", "token_name": "LGAX_PRIVATE_TOKEN"}},
                    {"stage": "repair_fields", "status": "rejected", "error_code": "MODEL_UNAVAILABLE",
                     "error_reason": "output_truncated", "message": "private-provider-message"},
                ],
                "item_issues": [{"kind": "Comparison", "item_id": "test-item", "issues": [
                    {"field": "existing_response", "code": "quantity_not_in_cited_sources",
                     "message": "private-provider-message"}]}],
                "endpoint": "http://127.0.0.1:18875/private", "token": "private-token-value",
            },
        }
        self.last_raw = deepcopy(brief)
        return brief


class ActualResearchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)
        self.token = "manual-research-test-credential-20261007"
        registry = TokenRegistry([{"principal_id": "research-tester", "role": "editor", "token_sha256": sha256(self.token.encode()).hexdigest()},
                                  {"principal_id": "research-viewer", "role": "viewer", "token_sha256": sha256((self.token + "-viewer").encode()).hexdigest()},
                                  {"principal_id": "research-other", "role": "editor", "token_sha256": sha256((self.token + "-other").encode()).hexdigest()},
                                  {"principal_id": "research-admin", "role": "admin", "token_sha256": sha256((self.token + "-admin").encode()).hexdigest()}])
        self.research = ResearchWorkspace(path / "research.sqlite3", [PACK])
        self.client = TestClient(create_workspace_app(path / "workspace.sqlite3", registry, research_workspace=self.research), base_url="http://127.0.0.1")
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer " + self.token, "Origin": "http://127.0.0.1:5175"}

    def test_real_source_bundle_is_authenticated_and_unchanged(self):
        self.assertEqual(self.client.get("/api/research/bundles").status_code, 401)
        listed = self.client.get("/api/research/bundles", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["bundles"][0]["source_count"], len(self.bundle["sources"]))
        original = self.client.get("/api/research/bundles/" + self.bundle["bundle_id"], headers=self.headers)
        self.assertEqual(original.json(), self.bundle)
        self.assertEqual(original.headers["cache-control"], "no-store")

    def test_model_opt_in_does_not_return_a_fake_plan(self):
        response = self.client.post("/api/research/planning-runs", headers=self.headers,
                                    json={"bundle_id": self.bundle["bundle_id"], "goal": "공개 자료에서 개선 기회 찾기", "constraints": []})
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["error"]["code"], "NOT_IMPLEMENTED")
        with self.research.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0], 0)

    def test_viewer_and_foreign_origin_cannot_start_generation(self):
        payload = {"bundle_id": self.bundle["bundle_id"], "goal": "개선 기회", "constraints": []}
        viewer = {**self.headers, "Authorization": "Bearer " + self.token + "-viewer"}
        self.assertEqual(self.client.post("/api/research/planning-runs", headers=viewer, json=payload).status_code, 403)
        forbidden = {**self.headers, "Origin": "http://untrusted.example"}
        self.assertEqual(self.client.get("/api/research/bundles", headers=forbidden).status_code, 403)

    def test_actual_source_missing_sku_stays_group_scoped(self):
        validate_research_bundle(self.bundle)
        changed = deepcopy(self.bundle)
        changed["analysis_scope"] = "exact_model"
        with self.assertRaises(ValidationError):
            validate_research_bundle(changed)

    def test_purchase_date_cannot_become_posting_date(self):
        changed = deepcopy(self.bundle)
        review = next(source for source in changed["sources"] if source["source_type"] == "review")
        review["published_at"] = "2026-07-01"
        review["date_kind"] = "purchase"
        with self.assertRaises(ValidationError):
            validate_research_bundle(changed)

    def test_created_run_preserves_real_facts_and_private_diagnostics_on_post_and_get(self):
        planner = ContractOnlyPlanner()
        self.research.planner = planner
        payload = {"bundle_id": self.bundle["bundle_id"], "goal": "실제 자료 저장 경계 검사", "constraints": []}
        response = self.client.post("/api/research/planning-runs", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201)
        public = response.json()
        validate_planning_brief(public)
        self.assertEqual(public["status"], "needs_sources")
        self.assertEqual(public["source_facts"], planner.last_raw["source_facts"])
        self.assertEqual(public["runtime"]["call_count"], 2)
        self.assertEqual(public["runtime"]["repair_count"], 1)
        self.assertEqual(public["runtime"]["model_failures"], [{"call_index": 1, "error_code": "MODEL_UNAVAILABLE", "error_reason": "output_truncated"}])
        self.assertFalse(public["runtime"]["independent_semantic_quality_verified"])
        self.assertFalse(public["runtime"]["market_frequency_estimated"])
        self.assertEqual(public["runtime"]["omitted_source_count"], len(self.bundle["sources"]) - 1)
        self.assertEqual(public["runtime"]["validation_issues"][0]["code"], "quantity_not_in_cited_sources")
        retrieved = self.client.get("/api/research/planning-runs/" + public["run_id"], headers=self.headers)
        self.assertEqual(retrieved.json(), public)
        for private in ("127.0.0.1", "private.example", "LGAX_PRIVATE_TOKEN", "private-token-value", "private-provider-message"):
            self.assertNotIn(private, response.text)
            self.assertNotIn(private, retrieved.text)
        with self.research.connect() as connection:
            saved = json.loads(connection.execute("SELECT brief FROM research_runs").fetchone()[0])
            attempt = connection.execute("SELECT status, run_id, error_code FROM research_attempts").fetchone()
        expected_saved = deepcopy(planner.last_raw)
        expected_saved['runtime'].update(user_selected_source_ids=[source['source_id'] for source in self.bundle['sources']],
                                         input_scope='full_bundle')
        self.assertEqual(saved, expected_saved)
        self.assertEqual(attempt, ("completed", public["run_id"], None))
        public["source_facts"][0]["facts"].append({"fact_id": "local-edit", "kind": "unknown", "text": "local edit"})
        self.assertEqual(self.research.get_bundle(self.bundle["bundle_id"]), self.bundle)
        self.assertEqual(planner.last_raw["source_facts"], saved["source_facts"])

    def test_saved_run_owner_and_revision_require_same_source_digest(self):
        planner = ContractOnlyPlanner()
        self.research.planner = planner
        payload = {"bundle_id": self.bundle["bundle_id"], "goal": "실제 자료 저장 경계 검사", "constraints": []}
        first = self.client.post("/api/research/planning-runs", headers=self.headers, json=payload).json()
        changed = {**payload, "previous_run_id": first["run_id"], "constraints": ["하드웨어 변경 불가"]}
        other = {**self.headers, "Authorization": "Bearer " + self.token + "-other"}
        admin = {**self.headers, "Authorization": "Bearer " + self.token + "-admin"}
        self.assertEqual(self.client.get("/api/research/planning-runs/" + first["run_id"], headers=other).status_code, 404)
        self.assertEqual(self.client.post("/api/research/planning-runs", headers=other, json=changed).status_code, 404)
        self.assertEqual(self.client.get("/api/research/planning-runs/" + first["run_id"], headers=admin).status_code, 200)
        self.assertEqual(self.client.post("/api/research/planning-runs", headers=admin, json=changed).status_code, 409)
        second_response = self.client.post("/api/research/planning-runs", headers=self.headers, json=changed)
        self.assertEqual(second_response.status_code, 201)
        second = second_response.json()
        self.assertEqual(second["revision"], 1)
        self.assertEqual(second["previous_brief_id"], first["brief_id"])
        self.assertNotEqual(second["run_id"], first["run_id"])
        self.assertEqual(second["constraints"], changed["constraints"])
        self.assertEqual(second["source_facts"], first["source_facts"])
        self.assertEqual(planner.calls[1]["runtime"]["model_calls"][0]["metadata"]["token_name"], "LGAX_PRIVATE_TOKEN")
        self.assertEqual(self.client.get("/api/research/planning-runs/" + first["run_id"], headers=self.headers).json(), first)
        digest = self.research.digests[self.bundle["bundle_id"]]
        self.research.digests[self.bundle["bundle_id"]] = "0" * 64
        self.assertEqual(self.client.post("/api/research/planning-runs", headers=self.headers, json=changed).status_code, 409)
        self.research.digests[self.bundle["bundle_id"]] = digest
        self.assertEqual(len(planner.calls), 2)

    def test_failed_attempts_preserve_cause_without_creating_an_accepted_brief(self):
        class FailedPlanner:
            def __init__(self, failure):
                self.failure = failure

            def run(self, bundle, goal, constraints, previous=None):
                if self.failure == "initialization":
                    raise DomainError("INVALID_ARGUMENT", "private-provider-message", {
                        "reason": "missing_model_environment", "endpoint": "http://127.0.0.1:18875/private"})
                if self.failure == "execution":
                    raise RuntimeError("private-provider-message LGAX_PRIVATE_TOKEN")
                if self.failure == "contract":
                    return {"runtime": {"endpoint": "http://127.0.0.1:18875/private"}}
                # Even an adapter that mutates its copy cannot redefine the input facts.
                document = next(source for source in bundle["sources"] if source["facts"])
                document["facts"][0]["text"] += " altered"
                return ContractOnlyPlanner().run(bundle, goal, constraints, previous)

        expected = {
            "initialization": ("INVALID_ARGUMENT", "missing_model_environment"),
            "execution": ("MODEL_UNAVAILABLE", "unhandled_exception"),
            "contract": ("CONTRACT_MISMATCH", "contract_schema_mismatch"),
            "facts": ("CONTRACT_MISMATCH", "run_snapshot_mismatch"),
        }
        payload = {"bundle_id": self.bundle["bundle_id"], "goal": "실제 자료 실패 저장 경계 검사", "constraints": []}
        for failure, cause in expected.items():
            with self.subTest(failure=failure):
                self.research.planner = FailedPlanner(failure)
                response = self.client.post("/api/research/planning-runs", headers=self.headers, json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], cause[0])
                self.assertNotIn("private-provider-message", response.text)
                self.assertNotIn("127.0.0.1", response.text)
                with self.research.connect() as connection:
                    row = connection.execute("SELECT status, error_code, error_reason, run_id, bundle_sha256 FROM research_attempts ORDER BY rowid DESC LIMIT 1").fetchone()
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0], 0)
                self.assertEqual(row[:4], ("failed", cause[0], cause[1], None))
                self.assertEqual(row[4], self.research.digests[self.bundle["bundle_id"]])
                self.assertEqual(self.research.get_bundle(self.bundle["bundle_id"]), self.bundle)
        with self.research.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM research_attempts").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
