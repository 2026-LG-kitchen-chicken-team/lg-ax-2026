"""Local API regression for project-scoped parent runs; no model or server."""

import json
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app


class WorkspaceProjectParentTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        token = "local-parent-regression-fixture-" + "x" * 32
        registry = TokenRegistry([{
            "principal_id": "parent-fixture-user",
            "role": "editor",
            "token_sha256": sha256(token.encode()).hexdigest(),
        }])
        app = create_workspace_app(
            Path(temp.name) / "workspace.sqlite", registry, planning_runner=None
        )
        self.client = self.enterContext(TestClient(app, base_url="http://127.0.0.1"))
        self.client.headers.update({"Authorization": "Bearer " + token})
        root = Path(__file__).resolve().parents[1]
        self.request = json.loads(
            (root / "data/demo/planning_requests.json").read_text("utf-8")
        )[0]

    def create_project(self, name):
        response = self.client.post("/api/workspace/projects", json={
            "name": name,
            "request": self.request,
            "document_versions": {model: "1.0" for model in self.request["model_ids"]},
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["data"]["owner_id"], "parent-fixture-user")
        return response.json()["data"]["project"]["id"]

    def history(self, project_id):
        response = self.client.get(f"/api/workspace/projects/{project_id}/runs")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]["runs"]

    def test_cross_project_parent_rejected_without_mutation_and_same_project_succeeds(self):
        project_a = self.create_project("Project A")
        project_b = self.create_project("Project B")
        self.assertNotEqual(project_a, project_b)
        first = self.client.post(f"/api/workspace/projects/{project_a}/runs", json={
            "request": self.request, "previous_run_id": None, "unconfirmed": [],
        })
        self.assertEqual(first.status_code, 201, first.text)
        original = first.json()
        parent = original["data"]
        parent_id = parent["run"]["id"]
        self.assertEqual(parent["request_revision"], 0)
        history_a = self.history(project_a)
        self.assertEqual(len(history_a), 1)
        self.assertEqual(self.history(project_b), [])

        changed = deepcopy(self.request)
        changed["exclusions"] = ["전체 선반 교체 제외"]
        payload = {"request": changed, "previous_run_id": parent_id, "unconfirmed": []}
        rejected = self.client.post(f"/api/workspace/projects/{project_b}/runs", json=payload)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(rejected.json()["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.history(project_b), [])
        self.assertEqual(self.history(project_a), history_a)
        unchanged = self.client.get(f"/api/workspace/runs/{parent_id}")
        self.assertEqual(unchanged.status_code, 200, unchanged.text)
        self.assertEqual(unchanged.json(), original)

        accepted = self.client.post(f"/api/workspace/projects/{project_a}/runs", json=payload)
        self.assertEqual(accepted.status_code, 201, accepted.text)
        child = accepted.json()["data"]
        self.assertNotEqual(child["run"]["id"], parent_id)
        self.assertEqual(child["previous_run_id"], parent_id)
        self.assertEqual(child["request_revision"], parent["request_revision"] + 1)
        self.assertEqual(len(self.history(project_a)), 2)
        self.assertEqual(self.history(project_b), [])
        unchanged = self.client.get(f"/api/workspace/runs/{parent_id}")
        self.assertEqual(unchanged.status_code, 200, unchanged.text)
        self.assertEqual(unchanged.json(), original)


if __name__ == "__main__":
    unittest.main()
