"""New research boundaries tested against actual, frozen public sources."""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from jsonschema import ValidationError
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_contracts.research import validate_research_bundle


ROOT = Path(__file__).resolve().parents[1]
PACK = Path(os.environ.get("LGAX_TEST_RESEARCH_BUNDLE", ROOT / "data/research/r8-public-research-20261007/bundles/dishwasher.development.research-bundle.json"))


class ActualResearchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)
        self.token = "manual-research-test-credential-20261007"
        registry = TokenRegistry([{"principal_id": "research-tester", "role": "editor", "token_sha256": sha256(self.token.encode()).hexdigest()},
                                  {"principal_id": "research-viewer", "role": "viewer", "token_sha256": sha256((self.token + "-viewer").encode()).hexdigest()}])
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


if __name__ == "__main__":
    unittest.main()
