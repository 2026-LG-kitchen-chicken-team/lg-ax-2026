"""Pinned public snapshot CLI and no-generation hold persistence, not live-model quality."""

import json
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from hashlib import sha256
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from lgax_api import workspace_server
from lgax_api.server import create_app
from lgax_contracts import validate
from lgax_core.model_client import ModelConfig
from lgax_core.planning_agent import PlanningAgent
from lgax_core.workspace import WorkspaceStore
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/research/PM-DATA-intake-20261006/generated/dataset.json"
TOKENS = {role: "isolated-public-runtime-" + role + "-" * 40
          for role in ("editor", "viewer", "other")}


class WorkspacePublicRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / "public-only.sqlite"
        self.credentials = self.directory / "synthetic-credentials.json"
        self.credentials.write_text(json.dumps({"credentials": [
            {"principal_id": "other" if role == "other" else "planner",
             "role": "editor" if role == "other" else role,
             "token_sha256": sha256(token.encode()).hexdigest()}
            for role, token in TOKENS.items()
        ]}), encoding="utf-8")
        self.dataset = json.loads(PUBLIC.read_bytes())

    def args(self):
        return ["workspace", "--db", str(self.db), "--credentials", str(self.credentials)]

    def public_args(self, path=PUBLIC):
        return self.args() + ["--document-dataset", str(path),
                              "--document-dataset-sha256", sha256(path.read_bytes()).hexdigest()]

    def launch(self, args=None):
        with patch("sys.argv", self.public_args() if args is None else args), \
                patch.object(workspace_server.uvicorn, "run") as run:
            workspace_server.main()
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
        return run.call_args.args[0]

    def reject(self, args):
        captured = StringIO()
        with patch("sys.argv", args), patch.object(workspace_server.uvicorn, "run") as run, \
                redirect_stderr(captured), self.assertRaises(SystemExit) as stopped:
            workspace_server.main()
        self.assertEqual(stopped.exception.code, 2)
        run.assert_not_called()
        self.assertFalse(self.db.exists())
        self.assertNotIn(str(self.credentials), captured.getvalue())
        self.assertNotIn(TOKENS["editor"], captured.getvalue())
        return captured.getvalue()

    def headers(self, role="editor"):
        return {"Authorization": "Bearer " + TOKENS[role]}

    def project_body(self, app):
        data = app.state.workspace.evidence_store.bootstrap()["data"]
        product = data["products"][0]
        request = deepcopy(json.loads((ROOT / "data/demo/planning_requests.json").read_bytes())[0])
        request.update(product_group=product["product_group"], model_ids=[product["model_id"]],
                       dataset_version=data["manifest"]["version"])
        return {"name": "Public reference-only acceptance", "request": request,
                "document_versions": {product["model_id"]: product["document_version"]}}

    def test_cli_public_path_and_hash_are_paired_and_conflicts_precede_file_or_db_access(self):
        for partial in (["--document-dataset", "unread-public-file"],
                        ["--document-dataset-sha256", "0" * 64]):
            with self.subTest(partial=partial):
                self.assertIn("required together", self.reject(self.args() + partial))
        for conflict in (["--dataset", "unread-synthetic-file"],
                         ["--trend-metadata", "unread-sidecar"],
                         ["--trend-metadata-sha256", "0" * 64],
                         ["--allow-candidate-trend-metadata"]):
            with self.subTest(conflict=conflict):
                args = self.args() + ["--document-dataset", "unread-public-file",
                                      "--document-dataset-sha256", "0" * 64] + conflict
                self.assertIn("cannot be combined", self.reject(args))

    def test_exact_file_hash_is_checked_before_decoding_or_constructing_any_document_store(self):
        path = self.directory / "rejected-private-marker.json"
        path.write_bytes(b"private-fixture-marker\xff not JSON")
        for expected in ("0" * 64, "A" * 64, "short"):
            with self.subTest(expected=expected), \
                    patch("lgax_core.document_workspace.WorkspaceDocumentStore") as store:
                text = self.reject(self.args() + ["--document-dataset", str(path),
                                                  "--document-dataset-sha256", expected])
                self.assertNotIn("private-fixture-marker", text)
                store.assert_not_called()

    def test_hash_matching_malformed_or_nonpublic_snapshots_fail_safely_without_db(self):
        private = deepcopy(self.dataset)
        for collection in ("products", "evidence"):
            for item in private[collection]:
                item["source_kind"] = "private"
        wrong_link = deepcopy(self.dataset)
        wrong_link["features"][0]["evidence_ids"] = ["not-an-authorized-evidence"]
        inputs = [b'[]', b'{"dataset_version":"one","dataset_version":"two"}',
                  b'{"private-marker":NaN}', b'{"private-marker":"invalid-source"}',
                  json.dumps(private).encode(), json.dumps(wrong_link).encode()]
        for index, raw in enumerate(inputs):
            with self.subTest(index=index):
                path = self.directory / ("invalid-" + str(index) + ".json")
                path.write_bytes(raw)
                self.assertNotIn("private-marker", self.reject(self.public_args(path)))

    def test_cli_preserves_synthetic_defaults_and_explicit_dated_configuration(self):
        app = self.launch(self.args())
        self.assertEqual(app.state.workspace.evidence_store.bootstrap()["data"]["manifest"]["source_kind"],
                         "synthetic")
        self.assertIsNone(app.state.workspace.planning_runner)
        dated = ROOT / "data/demo/review-trends-dated"
        metadata = dated / "annotation.candidate.json"
        args = self.args() + ["--dataset", str(dated / "dataset.json"),
                              "--trend-metadata", str(metadata), "--trend-metadata-sha256",
                              sha256(metadata.read_bytes()).hexdigest(), "--allow-candidate-trend-metadata"]
        app = self.launch(args)
        self.assertIsNotNone(app.state.review_trends.collector)
        with TestClient(app, base_url="http://127.0.0.1") as api:
            self.assertFalse(api.get("/health").json()["planning_enabled"])

    def test_authenticated_public_bootstrap_project_scope_and_disabled_run_are_same_source(self):
        with patch("lgax_core.workspace_planning.StructuredModelClient.from_env") as model:
            app = self.launch()
            body = self.project_body(app)
            with TestClient(app, base_url="http://127.0.0.1") as api:
                self.assertEqual(api.get("/api/workspace/bootstrap").status_code, 401)
                wire = api.get("/api/workspace/bootstrap", headers=self.headers("viewer"))
                self.assertEqual(wire.status_code, 200)
                self.assertEqual(wire.headers["cache-control"], "no-store")
                data = wire.json()["data"]
                validate("WorkspaceBootstrapResponse", wire.json())
                self.assertEqual(data["manifest"]["source_kind"], "public")
                self.assertEqual(data["manifest"]["review_count"], 0)
                self.assertEqual(data["reviews"], [])
                self.assertEqual(data["evidence"], self.dataset["evidence"])
                self.assertEqual(data["manifest"]["dataset_sha256"], app.state.workspace.dataset_sha256)
                self.assertFalse(data["manifest"]["analysis_implemented"])
                self.assertEqual(api.post("/api/workspace/projects", headers=self.headers("viewer"),
                                          json=body).status_code, 403)
                for mutation in ("dataset", "document", "model"):
                    invalid = deepcopy(body)
                    if mutation == "dataset":
                        invalid["request"]["dataset_version"] = "different-dataset"
                    elif mutation == "document":
                        invalid["document_versions"] = {body["request"]["model_ids"][0]: "unverified-PDP"}
                    else:
                        invalid["request"]["model_ids"] = ["PDP-only-unregistered-model"]
                    self.assertEqual(api.post("/api/workspace/projects", headers=self.headers(),
                                              json=invalid).status_code, 409 if mutation == "dataset" else 422)
                project = api.post("/api/workspace/projects", headers=self.headers(), json=body).json()["data"]
                pid = project["project"]["id"]
                self.assertEqual(project["dataset_sha256"], data["manifest"]["dataset_sha256"])
                self.assertEqual(api.get("/api/workspace/projects/" + pid,
                                         headers=self.headers("other")).status_code, 403)
                saved = api.post("/api/workspace/projects/" + pid + "/runs", headers=self.headers(),
                                 json={"request": body["request"], "previous_run_id": None, "unconfirmed": []})
                self.assertEqual(saved.status_code, 201)
                self.assertEqual(saved.json()["data"]["run"]["status"], "not_implemented")
                self.assertEqual(saved.json()["data"]["run"]["concepts"], [])
                self.assertIsNone(saved.json()["data"]["output"])
            model.assert_not_called()
        with self.assertRaises(ValueError):
            create_app(app.state.workspace.evidence_store)

    def test_explicit_planning_no_review_gate_holds_without_generation_and_persists_originals(self):
        client = MagicMock()
        client.adapter.config = ModelConfig("http://127.0.0.1:9", "no-generation-fixture", "a" * 64)
        client.generate.side_effect = AssertionError("No model generation is authorized by this regression")

        def no_generation(request, versions, store):
            return PlanningAgent(client, store, execution_kind="fixture").run(
                build_planning_input(request, versions, store))

        with patch.object(workspace_server, "EnvPlanningRunner", return_value=no_generation) as factory:
            app = self.launch(self.public_args() + ["--enable-planning"])
        factory.assert_called_once_with()
        body = self.project_body(app)
        with TestClient(app, base_url="http://127.0.0.1") as api:
            project = api.post("/api/workspace/projects", headers=self.headers(), json=body).json()["data"]
            pid = project["project"]["id"]
            response = api.post("/api/workspace/projects/" + pid + "/runs", headers=self.headers(),
                                json={"request": body["request"], "previous_run_id": None, "unconfirmed": []})
            self.assertEqual(response.status_code, 201, response.text)
            saved = response.json()
            validate("WorkspaceRunResponse", saved)
            snapshot = saved["data"]
            self.assertEqual(snapshot["run"]["status"], "held")
            self.assertEqual(snapshot["run"]["concepts"], [])
            self.assertEqual(snapshot["output"]["planning_execution"]["model_calls"], [])
            self.assertEqual(snapshot["output"]["planning_execution"]["execution_kind"], "fixture")
            self.assertEqual(snapshot["output"]["planning_execution"]["original_input"]["sources"],
                             [e for e in self.dataset["evidence"]
                              if e["model_id"] == body["request"]["model_ids"][0]])
            rid = snapshot["run"]["id"]
            fetched = api.get("/api/workspace/runs/" + rid, headers=self.headers("viewer"))
            self.assertEqual(fetched.json(), saved)
            self.assertEqual(fetched.headers["cache-control"], "no-store")
            self.assertEqual(json.loads(json.dumps(saved, ensure_ascii=False)), saved)
        client.generate.assert_not_called()
        reopened = WorkspaceStore(self.db, app.state.workspace.evidence_store)
        self.assertEqual(workspace_server.public_run(reopened.get_run(rid, "planner")), snapshot)
        changed = deepcopy(self.dataset)
        changed["dataset_version"] += "-changed"
        path = self.directory / "changed-public.json"
        path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        changed_app = self.launch(self.public_args(path))
        with TestClient(changed_app, base_url="http://127.0.0.1") as api:
            self.assertEqual(api.get("/api/workspace/runs/" + rid, headers=self.headers()).json(), saved)
            stale = api.post("/api/workspace/projects/" + pid + "/runs", headers=self.headers(),
                             json={"request": body["request"], "previous_run_id": rid, "unconfirmed": []})
            self.assertEqual(stale.status_code, 409)


if __name__ == "__main__":
    unittest.main()
