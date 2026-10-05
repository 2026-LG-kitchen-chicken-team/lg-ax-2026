"""Real loopback HTTP regressions; synthetic sources and fixture runners only.

Executed by the trusted zero-auth validator, never by the model worker.
"""

import json
import socket
import threading
import time
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import uvicorn
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.store import DemoStore
from lgax_core.workspace_planning import build_planning_input, failed_execution

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/core-contract/development"
SECRET = "".join(('/server/private/fixture-only.sqlite Bea', 'rer fixture-only-not-a-real-token'))
TOKENS = {role: letter * 48 for role, letter in
          (("editor", "e"), ("viewer", "v"), ("other", "o"), ("admin", "a"))}


class FixtureRunner:
    def __init__(self):
        self.mode = "completed"
        self.calls = []

    def __call__(self, request, versions, store):
        payload = build_planning_input(request, versions, store)
        self.calls.append(deepcopy(payload))
        if self.mode == "raise":
            raise RuntimeError(SECRET)
        if self.mode == "rejected":
            return {"execution_kind": "fixture", "private_diagnostic": SECRET}
        if self.mode == "failed":
            result = failed_execution(payload, execution_kind="fixture")
            error = {"code": "MODEL_UNAVAILABLE", "message": SECRET,
                     "details": {"path": SECRET}}
            result["errors"] = [error]
            result["trace"][0]["outputs"]["error"] = deepcopy(error)
            return result
        output = json.loads((CASES / "normal.fixture-output.json").read_text("utf-8"))
        output.update(input_sha256=input_digest(payload), revision_count=0, status=self.mode)
        if self.mode == "held":
            output.update(concepts=[], concept_assessments=[],
                          hold_reasons=["추가 근거 확인 필요"], no_candidate_reasons=["근거 확인 전 보류"])
        return {"execution_kind": "fixture", "original_input": payload, "input": deepcopy(payload),
                "output": output, "status": self.mode, "decision": review_judgement(payload, output),
                "trace": [{"stage": "review", "operation": "fixture_review", "inputs": {}, "outputs": {}}],
                "model_calls": [], "errors": []}


class ApiRunFailureContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.payload = json.loads((CASES / "normal.input.json").read_text("utf-8"))
        self.request = deepcopy(self.payload["request"])
        fields = ("model_id", "text", "source_kind", "document_version", "source_id", "locator")
        reviews = [{"id": "ROW-" + item["id"], "evidence_id": item["id"],
                    **{key: item[key] for key in fields}} for item in self.payload["sources"]
                   if item["source_type"] == "review"]
        dataset = {"manifest": {"dataset_id": "api-run-fixture", "version": self.request["dataset_version"],
                                 "description": "Synthetic API regression only", "source_kind": "synthetic",
                                 "model_count": 1, "review_count": len(reviews), "analysis_implemented": False},
                   "products": [deepcopy(self.payload["product"])], "reviews": reviews,
                   "evidence": deepcopy(self.payload["sources"]), "features": deepcopy(self.payload["features"])}
        self.evidence = DemoStore(dataset)
        self.versions = {self.payload["product"]["model_id"]: self.payload["product"]["document_version"]}
        entries = [{"principal_id": "other" if role == "other" else "pm" if role == "admin" else "planner",
                    "role": "editor" if role == "other" else role,
                    "token_sha256": sha256(token.encode()).hexdigest()} for role, token in TOKENS.items()]
        self.runner = FixtureRunner()
        self.app = create_workspace_app(Path(self.temp.name) / "workspace.sqlite", TokenRegistry(entries),
                                        evidence_store=self.evidence, planning_runner=self.runner)
        sock = socket.socket()
        self.addCleanup(sock.close)
        sock.bind(("127.0.0.1", 0))
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level="critical", access_log=False,
                                                   lifespan="off"))
        thread = threading.Thread(target=self.server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()

        def stop():
            self.server.should_exit = True
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "loopback HTTP server did not stop")

        self.addCleanup(stop)
        deadline = time.monotonic() + 10
        while not self.server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.server.started, "loopback HTTP server did not start")
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}",
                                   timeout=10, trust_env=False)
        self.addCleanup(self.client.close)
        self.pid = self.project()

    def headers(self, role="editor"):
        return {"Authorization": "Bearer " + TOKENS[role], "X-LGAX-Client": "web"}

    def project(self):
        response = self.client.post("/api/workspace/projects", headers=self.headers(),
                                    json={"name": "API fixture", "request": self.request,
                                          "document_versions": self.versions})
        self.assertEqual(response.status_code, 201, response.text)
        validate("WorkspaceProjectResponse", response.json())
        return response.json()["data"]["project"]["id"]

    def create(self, request=None, parent=None, role="editor", pid=None):
        return self.client.post(f"/api/workspace/projects/{pid or self.pid}/runs", headers=self.headers(role),
                                json={"request": self.request if request is None else request,
                                      "previous_run_id": parent, "unconfirmed": ["수요 측정 전"]})

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        validate("ErrorResponse", response.json())
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        self.assertNotIn(SECRET, response.text)
        for token in TOKENS.values():
            self.assertNotIn(token, response.text)

    def assert_snapshot(self, response, status):
        self.assertEqual(response.status_code, 201, response.text)
        validate("WorkspaceRunResponse", response.json())
        saved = response.json()["data"]
        self.assertEqual(saved["run"]["status"], status)
        self.assertEqual(saved["document_versions"], self.versions)
        self.assertEqual(saved["run"]["dataset_version"], self.request["dataset_version"])
        self.assertEqual(saved["dataset_sha256"], self.app.state.workspace.dataset_sha256)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        stored = self.app.state.workspace.get_run(saved["run"]["id"], "planner")
        if status in {"completed", "held", "not_implemented"}:
            self.assertEqual(saved, stored)
        for role in ("editor", "viewer", "admin"):
            fetched = self.client.get(f"/api/workspace/runs/{saved['run']['id']}", headers=self.headers(role))
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json(), response.json())
            history = self.client.get(f"/api/workspace/projects/{self.pid}/runs", headers=self.headers(role))
            self.assertEqual(history.status_code, 200)
            validate("WorkspaceRunsResponse", history.json())
            self.assertIn(saved, history.json()["data"]["runs"])
            self.assertNotIn(SECRET, history.text)
        return saved

    def test_completed_held_failed_and_changed_input_keep_same_id_contract(self):
        first = self.assert_snapshot(self.create(), "completed")
        execution = first["output"]["planning_execution"]
        self.assertEqual(execution["execution_kind"], "fixture")
        self.assertEqual(execution["original_input"], self.payload)
        self.assertEqual(execution["original_input"]["sources"], self.payload["sources"])
        self.assertEqual(execution["original_input"]["product"]["source_kind"], "synthetic")
        changed = deepcopy(self.request)
        changed["exclusions"].append("추가 확인 전 전체 선반 교체 제외")
        self.runner.mode = "held"
        held = self.assert_snapshot(self.create(changed, first["run"]["id"]), "held")
        self.assertEqual(held["request"], changed)
        self.assertEqual(held["request_revision"], 1)
        self.assertEqual(held["previous_run_id"], first["run"]["id"])
        self.assertEqual(held["run"]["revision_count"], 0)
        self.assertEqual(held["run"]["concepts"], [])
        self.assertTrue(held["output"]["planning_execution"]["output"]["hold_reasons"])
        for mode, code in (("failed", "MODEL_UNAVAILABLE"), ("raise", "MODEL_UNAVAILABLE"),
                           ("rejected", "CONTRACT_MISMATCH")):
            with self.subTest(mode=mode):
                self.runner.mode = mode
                failed = self.assert_snapshot(self.create(changed, held["run"]["id"]), "failed")
                self.assertEqual(failed["request_revision"], 1)
                self.assertEqual(failed["run"]["concepts"], [])
                record = failed["output"]["planning_execution"]
                self.assertEqual(record["errors"][0]["code"], code)
                self.assertNotIn("rejected_execution", record)
                self.assertNotIn(SECRET, json.dumps(failed))
        original = self.client.get(f"/api/workspace/runs/{first['run']['id']}", headers=self.headers()).json()
        self.assertEqual(original["data"], first)

    def test_invalid_missing_forbidden_and_unauthenticated_are_distinct(self):
        saved = self.assert_snapshot(self.create(), "completed")
        rid = saved["run"]["id"]
        for path in (f"/api/workspace/runs/{rid}", f"/api/workspace/projects/{self.pid}/runs"):
            self.assert_error(self.client.get(path), 401, "UNAUTHORIZED")
            self.assert_error(self.client.get(path, headers=self.headers("other")), 403, "FORBIDDEN")
        self.assert_error(self.client.get("/api/workspace/runs/bad%20id", headers=self.headers()),
                          422, "INVALID_ARGUMENT")
        self.assert_error(self.client.get("/api/workspace/runs/run-missing", headers=self.headers()),
                          404, "NOT_FOUND")
        count = len(self.runner.calls)
        for role in ("viewer", "other"):
            self.assert_error(self.create(role=role), 403, "FORBIDDEN")
        self.assert_error(self.create(parent="run-missing"), 404, "NOT_FOUND")
        second_pid = self.project()
        self.assert_error(self.create(parent=rid, pid=second_pid), 422, "INVALID_ARGUMENT")
        for key, value, code in (("dataset_version", "wrong-version", "DATASET_MISMATCH"),
                                 ("model_ids", ["wrong-model"], "INVALID_ARGUMENT"),
                                 ("endpoint", SECRET, "INVALID_ARGUMENT")):
            changed = {**self.request, key: value}
            self.assert_error(self.create(changed), 409 if code == "DATASET_MISMATCH" else 422, code)
        self.assertEqual(len(self.runner.calls), count)

    def test_dataset_drift_blocks_new_runs_but_preserves_old_source_snapshot(self):
        saved = self.assert_snapshot(self.create(), "completed")
        changed = self.evidence.bootstrap()
        changed["data"]["manifest"]["description"] += " changed fixture"
        count = len(self.runner.calls)
        with patch.object(self.evidence, "bootstrap", side_effect=lambda: deepcopy(changed)):
            self.assert_error(self.create(parent=saved["run"]["id"]), 409, "DATASET_MISMATCH")
            fetched = self.client.get(f"/api/workspace/runs/{saved['run']['id']}", headers=self.headers())
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()["data"], saved)
            history = self.client.get(f"/api/workspace/projects/{self.pid}/runs", headers=self.headers())
            self.assertEqual(history.json()["data"]["runs"], [saved])
        self.assertEqual(len(self.runner.calls), count)

    def test_invalid_body_is_not_echoed_and_does_not_invoke_runner(self):
        path = f"/api/workspace/projects/{self.pid}/runs"
        for body in (SECRET, json.dumps({"request": SECRET})):
            response = self.client.post(path, headers={**self.headers(), "Content-Type": "application/json"},
                                        content=body)
            self.assert_error(response, 422, "INVALID_ARGUMENT")
        response = self.client.post(path, content=SECRET)
        self.assert_error(response, 401, "UNAUTHORIZED")
        self.assertEqual(self.runner.calls, [])

    def test_private_diagnostics_are_redacted_without_mutating_stored_record(self):
        self.runner.mode = "failed"
        saved = self.assert_snapshot(self.create(), "failed")
        private = self.app.state.workspace.get_run(saved["run"]["id"], "planner")
        self.assertIn(SECRET, json.dumps(private))
        self.assertNotIn(SECRET, json.dumps(saved))
        error = saved["output"]["planning_execution"]["errors"][0]
        self.assertEqual(error["details"], {})
        self.assertEqual(saved["output"]["planning_execution"]["original_input"], self.payload)
        # Historical adapter errors need not have the full Error shape.
        private["output"]["planning_execution"]["errors"] = [
            {"code": "MODEL_UNAVAILABLE", "message": SECRET},
            {"code": SECRET, "message": SECRET}, SECRET,
        ]
        with patch.object(self.app.state.workspace, "get_run", return_value=private):
            fetched = self.client.get(f"/api/workspace/runs/{saved['run']['id']}", headers=self.headers())
            self.assertEqual(fetched.status_code, 200)
            self.assertNotIn(SECRET, fetched.text)
            errors = fetched.json()["data"]["output"]["planning_execution"]["errors"]
            self.assertEqual([error["code"] for error in errors],
                             ["MODEL_UNAVAILABLE", "CONTRACT_MISMATCH", "CONTRACT_MISMATCH"])

    def test_unexpected_storage_and_domain_errors_use_safe_common_envelopes(self):
        for error, status, code in ((OSError(SECRET), 500, "CONNECTION_FAILED"),
                                    (DomainError("NOT_FOUND", SECRET, {"path": SECRET}), 404, "NOT_FOUND")):
            with self.subTest(code=code), patch.object(self.app.state.workspace, "get_run", side_effect=error):
                response = self.client.get("/api/workspace/runs/run-fixture", headers=self.headers())
                self.assert_error(response, status, code)
        with patch.object(self.app.state.workspace, "get_run", return_value={"invalid": SECRET}):
            response = self.client.get("/api/workspace/runs/run-fixture", headers=self.headers())
            self.assert_error(response, 422, "CONTRACT_MISMATCH")
        self.app.state.workspace.planning_runner = None
        saved = self.assert_snapshot(self.create(), "not_implemented")
        self.assertIsNone(saved["output"])
        self.assertEqual(saved["run"]["concepts"], [])


if __name__ == "__main__":
    unittest.main()
