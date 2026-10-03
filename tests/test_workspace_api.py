"""Owner/role isolation and common source-scoped API/MCP records."""

import json
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_contracts import validate

TOKENS = {"editor": "e" * 48, "viewer": "v" * 48, "other": "o" * 48, "admin": "a" * 48}


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        entries = [
            {
                "principal_id": "other" if role == "other" else "pm" if role == "admin" else "planner",
                "role": "editor" if role == "other" else role,
                "token_sha256": sha256(token.encode()).hexdigest(),
            }
            for role, token in TOKENS.items()
        ]
        self.app = create_workspace_app(Path(self.temp.name) / "workspace.sqlite", TokenRegistry(entries))
        self.client = TestClient(self.app, base_url="http://127.0.0.1")
        root = Path(__file__).resolve().parents[1]
        self.request = json.loads((root / "data/demo/planning_requests.json").read_text("utf-8"))[0]
        self.project_input = {
            "name": "냉장고 청소 기획",
            "request": self.request,
            "document_versions": {model: "1.0" for model in self.request["model_ids"]},
        }

    def headers(self, role="editor", **extras):
        return {"Authorization": "Bearer " + TOKENS[role], **extras}

    def create(self):
        response = self.client.post(
            "/api/workspace/projects", headers=self.headers(), json=self.project_input
        )
        self.assertEqual(response.status_code, 201, response.text)
        validate("WorkspaceProjectResponse", response.json())
        return response.json()["data"]["project"]["id"]

    def test_auth_happens_before_private_body_processing(self):
        response = self.client.post("/api/workspace/projects", content="not json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")
        self.assertNotIn("not json", response.text)
        wrong = self.client.get("/api/workspace/projects", headers={"Authorization": "Bearer " + "x" * 48})
        self.assertEqual(wrong.status_code, 401)
        self.assertNotIn("x" * 48, wrong.text)

    def test_readonly_and_owner_and_admin_are_distinct(self):
        pid = self.create()
        self.assertEqual(
            self.client.get(f"/api/workspace/projects/{pid}", headers=self.headers("viewer")).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                "/api/workspace/projects", headers=self.headers("viewer"), json=self.project_input
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"/api/workspace/projects/{pid}", headers=self.headers("other")).status_code, 403
        )
        other = self.client.get("/api/workspace/projects", headers=self.headers("other")).json()
        self.assertEqual(other["data"]["projects"], [])
        self.assertEqual(
            self.client.get(f"/api/workspace/projects/{pid}", headers=self.headers("admin")).status_code, 200
        )

    def test_saved_runs_preserve_inputs_parent_and_unimplemented_status(self):
        pid = self.create()
        payload = {"request": self.request, "previous_run_id": None, "unconfirmed": ["용량 감소 확인 필요"]}
        first = self.client.post(
            f"/api/workspace/projects/{pid}/runs",
            headers=self.headers(**{"X-LGAX-Client": "web"}),
            json=payload,
        )
        self.assertEqual(first.status_code, 201, first.text)
        snapshot = first.json()["data"]
        validate("WorkspaceRunResponse", first.json())
        self.assertEqual(snapshot["run"]["status"], "not_implemented")
        self.assertEqual(snapshot["run"]["concepts"], [])
        self.assertIsNone(snapshot["output"])
        changed = deepcopy(self.request)
        changed["exclusions"] = ["전체 선반 교체 제외"]
        second = self.client.post(
            f"/api/workspace/projects/{pid}/runs",
            headers=self.headers(**{"X-LGAX-Client": "mcp"}),
            json={"request": changed, "previous_run_id": snapshot["run"]["id"], "unconfirmed": []},
        )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["data"]["previous_run_id"], snapshot["run"]["id"])
        self.assertEqual(second.json()["data"]["request_revision"], 1)
        original = self.client.get(
            f"/api/workspace/runs/{snapshot['run']['id']}", headers=self.headers()
        ).json()
        self.assertEqual(original, first.json())
        self.assertEqual(
            len(
                self.client.get(f"/api/workspace/projects/{pid}/runs", headers=self.headers()).json()["data"][
                    "runs"
                ]
            ),
            2,
        )

    def test_project_scoped_search_cannot_mix_model_or_document_version(self):
        pid = self.create()
        response = self.client.get(
            f"/api/workspace/projects/{pid}/evidence",
            headers=self.headers(),
            params={"q": "청소", "model_id": "FRIDGE-A"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        validate("WorkspaceEvidenceResponse", response.json())
        data = response.json()["data"]
        self.assertEqual(data["project_id"], pid)
        self.assertTrue(data["search"]["data"]["items"])
        self.assertEqual({e["document_version"] for e in data["search"]["data"]["items"]}, {"1.0"})
        wrong = self.client.get(
            f"/api/workspace/projects/{pid}/evidence",
            headers=self.headers(),
            params={"q": "청소", "model_id": "MICROWAVE-A"},
        )
        self.assertEqual(wrong.status_code, 422)

    def test_origin_host_and_client_kind_checked(self):
        self.assertEqual(
            self.client.get(
                "/api/workspace/projects", headers=self.headers(Origin="https://foreign.example")
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/health", headers={"Host": "foreign.example"}).status_code, 400)
        preflight = self.client.options(
            "/api/workspace/projects",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,X-LGAX-Client,Content-Type",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        pid = self.create()
        invalid = self.client.post(
            f"/api/workspace/projects/{pid}/runs",
            headers=self.headers(**{"X-LGAX-Client": "fake"}),
            json={"request": self.request, "previous_run_id": None, "unconfirmed": []},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_bad_body_does_not_echo_sensitive_input(self):
        value = {"name": "SECRET-BODY", "unknown": "SECRET-BODY"}
        response = self.client.post("/api/workspace/projects", headers=self.headers(), json=value)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("SECRET-BODY", response.text)


if __name__ == "__main__":
    unittest.main()
