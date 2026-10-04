"""Opt-in persistence integration; all model responses here are explicit fixtures."""

import json
import sqlite3
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore
from lgax_core.workspace import WorkspaceStore
from lgax_core.workspace_planning import EnvPlanningRunner, build_planning_input

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/core-contract/development"


def read(name):
    return json.loads((CASES / name).read_text("utf-8"))


def dataset_for(payload):
    fields = ("model_id", "text", "source_kind", "document_version", "source_id", "locator")
    reviews = [{"id": "ROW-" + item["id"], "evidence_id": item["id"],
                **{key: item[key] for key in fields}} for item in payload["sources"]
               if item["source_type"] == "review"]
    return {"manifest": {"dataset_id": "workspace-planning-fixture",
                         "version": payload["request"]["dataset_version"],
                         "description": "Synthetic persistence regression, never live model evidence",
                         "source_kind": "synthetic", "model_count": 1, "review_count": len(reviews),
                         "analysis_implemented": False},
            "products": [deepcopy(payload["product"])], "reviews": reviews,
            "evidence": deepcopy(payload["sources"]), "features": deepcopy(payload["features"])}


class FixtureRunner:
    def __init__(self, status="completed", revisions=0):
        self.calls = []
        self.status, self.revisions = status, revisions

    def __call__(self, request, versions, store):
        payload = build_planning_input(request, versions, store)
        self.calls.append(deepcopy(payload))
        final = {**payload, "revision_count": self.revisions}
        output = read("normal.fixture-output.json")
        output.update(input_sha256=input_digest(final), revision_count=self.revisions, status=self.status)
        if self.status != "completed":
            output["concepts"], output["concept_assessments"] = [], []
            output["hold_reasons"] = ["추가 근거 확인 필요"]
            output["no_candidate_reasons"] = ["보류 상태에서 후보 생성하지 않음"]
        return {"execution_kind": "fixture", "original_input": payload, "input": final,
                "output": output, "status": self.status, "decision": review_judgement(final, output),
                "trace": [{"stage": "review", "operation": "fixture_review", "inputs": {},
                           "outputs": {"status": self.status}}],
                "model_calls": [{"raw_response": "fixture response", "execution_kind": "fixture"}],
                "errors": []}


class WorkspacePlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.payload = read("normal.input.json")
        self.request = self.payload["request"]
        self.versions = {self.payload["product"]["model_id"]: "1.0"}
        self.evidence = DemoStore(dataset_for(self.payload))
        self.path = Path(self.temp.name) / "workspace.sqlite"

    def store(self, runner=None):
        store = WorkspaceStore(self.path, self.evidence, planning_runner=runner)
        project = store.create_project("fixture planning", self.request, "planner", self.versions)
        return store, project["project"]["id"]

    def test_default_remains_request_storage_without_any_model_configuration(self):
        with patch("lgax_core.workspace_planning.StructuredModelClient.from_env") as factory:
            store, pid = self.store()
            result = store.create_run(pid, self.request, "planner", "api")
        factory.assert_not_called()
        self.assertEqual(result["run"]["status"], "not_implemented")
        self.assertIsNone(result["output"])

    def test_checked_result_canonical_output_and_source_trace_survive_restart(self):
        runner = FixtureRunner()
        store, pid = self.store(runner)
        result = store.create_run(pid, self.request, "planner", "web", unconfirmed=["수요 측정 전"])
        validate("WorkspaceRunSnapshot", result)
        self.assertEqual(result["run"]["status"], "completed")
        self.assertEqual(result["output"]["planning_execution"]["execution_kind"], "fixture")
        self.assertEqual(result["run"]["concepts"], read("normal.fixture-output.json")["concepts"])
        self.assertEqual(runner.calls[0]["sources"], self.payload["sources"])
        self.assertEqual(runner.calls[0]["features"], self.payload["features"])
        reopened = WorkspaceStore(self.path, self.evidence)
        self.assertEqual(reopened.get_run(result["run"]["id"], "planner"), result)

    def test_changed_input_is_new_run_and_user_revision_is_separate_from_agent_retry(self):
        runner = FixtureRunner(revisions=2)
        store, pid = self.store(runner)
        first = store.create_run(pid, self.request, "planner", "web")
        original = deepcopy(first)
        changed = {**self.request, "improvement_task": "작은 오염을 청소할 때 식품 이동을 줄인다",
                   "exclusions": [*self.request["exclusions"], "자동 세척 제외"]}
        second = store.create_run(pid, changed, "planner", "mcp", first["run"]["id"])
        self.assertEqual(second["request_revision"], 1)
        self.assertEqual(second["run"]["revision_count"], 2)
        self.assertEqual(runner.calls[-1]["request"], changed)
        self.assertEqual(runner.calls[-1]["revision_count"], 0)
        self.assertEqual(store.get_run(first["run"]["id"], "planner"), original)
        self.assertNotEqual(first["run"]["id"], second["run"]["id"])

    def test_no_sqlite_write_transaction_is_held_during_runner(self):
        fixture = FixtureRunner()

        def runner(request, versions, evidence):
            other = sqlite3.connect(self.path, timeout=0)
            try:
                other.execute("BEGIN IMMEDIATE")
                other.rollback()
            finally:
                other.close()
            return fixture(request, versions, evidence)

        store, pid = self.store(runner)
        self.assertEqual(store.create_run(pid, self.request, "planner", "api")["run"]["status"], "completed")

    def test_forbidden_owner_and_invalid_parent_never_invoke_runner(self):
        runner = FixtureRunner()
        store, pid = self.store(runner)
        for actor, parent, code in (("other", None, "FORBIDDEN"), ("planner", "run-missing", "NOT_FOUND")):
            with self.assertRaises(DomainError) as raised:
                store.create_run(pid, self.request, actor, "web", parent)
            self.assertEqual(raised.exception.code, code)
        self.assertEqual(runner.calls, [])
        self.assertEqual(store.list_runs(pid, "planner"), [])

    def test_hold_and_model_exception_are_saved_with_trace_and_no_false_candidate(self):
        store, pid = self.store(FixtureRunner(status="held"))
        held = store.create_run(pid, self.request, "planner", "api")
        self.assertEqual(held["run"]["status"], "held")
        self.assertEqual(held["run"]["concepts"], [])
        self.assertEqual(held["output"]["planning_execution"]["model_calls"][0]["raw_response"], "fixture response")

        def crash(*_args):
            raise RuntimeError("fixture secret provider-address must not be stored")

        store.planning_runner = crash
        failed = store.create_run(pid, self.request, "planner", "api", held["run"]["id"])
        self.assertEqual(failed["run"]["status"], "failed")
        self.assertEqual(failed["run"]["concepts"], [])
        self.assertEqual(failed["output"]["needs"], [])
        self.assertNotIn("fixture secret provider-address", json.dumps(failed))
        self.assertEqual(store.get_run(held["run"]["id"], "planner"), held)

    def test_unchecked_completed_and_tampered_request_are_saved_as_failed(self):
        fixture = FixtureRunner()

        def invalid(request, versions, evidence):
            result = fixture(request, versions, evidence)
            result["output"]["concepts"][0]["evidence_ids"] = ["missing-evidence"]
            return result

        store, pid = self.store(invalid)
        saved = store.create_run(pid, self.request, "planner", "api")
        self.assertEqual(saved["run"]["status"], "failed")
        self.assertEqual(saved["run"]["concepts"], [])
        self.assertIn("rejected_execution", saved["output"]["planning_execution"])

        def changed(request, versions, evidence):
            result = fixture(request, versions, evidence)
            result["original_input"]["request"]["improvement_task"] = "different input"
            return result

        store.planning_runner = changed
        self.assertEqual(store.create_run(pid, self.request, "planner", "api")["run"]["status"], "failed")

    def test_agent_revision_beyond_two_cannot_be_completed(self):
        store, pid = self.store(FixtureRunner(revisions=3))
        saved = store.create_run(pid, self.request, "planner", "api")
        self.assertEqual(saved["run"]["status"], "failed")
        self.assertEqual(saved["run"]["revision_count"], 0)

    def test_held_output_cannot_publish_another_model_or_source(self):
        fixture = FixtureRunner(status="held")

        def invalid(request, versions, evidence):
            result = fixture(request, versions, evidence)
            result["output"]["needs"][0]["evidence_ids"] = ["OTHER-MODEL-SOURCE"]
            return result

        store, pid = self.store(invalid)
        saved = store.create_run(pid, self.request, "planner", "api")
        self.assertEqual(saved["run"]["status"], "failed")
        self.assertEqual(saved["output"]["needs"], [])
        self.assertIn("rejected_execution", saved["output"]["planning_execution"])

    def test_builder_rejects_multi_model_or_new_document_version_before_call(self):
        with self.assertRaises(DomainError) as multi:
            build_planning_input({**self.request, "model_ids": ["A", "B"]}, {}, self.evidence)
        self.assertEqual(multi.exception.code, "NOT_IMPLEMENTED")
        with self.assertRaises(DomainError) as version:
            build_planning_input(self.request, {self.request["model_ids"][0]: "2.0"}, self.evidence)
        self.assertEqual(version.exception.code, "NOT_IMPLEMENTED")

    def test_server_environment_failure_does_not_echo_configuration_exception(self):
        with patch("lgax_core.workspace_planning.StructuredModelClient.from_env",
                   side_effect=DomainError("MODEL_UNAVAILABLE", "fixture credential-like string", {})):
            result = EnvPlanningRunner()(self.request, self.versions, self.evidence)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("credential-like", json.dumps(result))
        self.assertEqual(result["model_calls"], [])

    def test_actual_planning_pipeline_with_mock_transport_is_explicit_fixture(self):
        expected = read("normal.fixture-output.json")
        fields = {"need_extract": ("needs", "desired_outcomes", "unresolved"),
                  "product_compare": ("gaps", "unresolved"), "concept_draft": ("concepts", "hold_reasons")}
        assessment = {"need_extract": "review_assessments", "product_compare": "gap_assessments",
                      "concept_draft": "concept_assessments"}
        calls = []

        def transport(request):
            if request.method == "GET":
                response = {"models": [{"name": "fixture-qwen", "digest": "b" * 64}]}
            else:
                body = json.loads(request.content)
                skill = body["prompt"].split("업무=", 1)[1].split(".", 1)[0]
                calls.append(skill)
                stage = {"result": {key: expected[key] for key in fields[skill]},
                         assessment[skill]: expected[assessment[skill]],
                         **{key: expected[key] for key in ("questions", "hold_reasons", "no_candidate_reasons")}}
                response = {"model": "fixture-qwen", "done": True, "done_reason": "stop",
                            "response": json.dumps(stage), "prompt_eval_count": 100, "eval_count": 50,
                            "total_duration": 1000}
            return httpx.Response(200, stream=httpx.ByteStream(json.dumps(response).encode()))

        adapter = OllamaAdapter(ModelConfig("http://127.0.0.1:18864", "fixture-qwen", "b" * 64,
                                            max_output_tokens=2048, context_tokens=8192),
                                transport=httpx.MockTransport(transport))
        client = StructuredModelClient(adapter)
        self.addCleanup(client.close)

        def runner(request, versions, evidence):
            return PlanningAgent(client, evidence, execution_kind="fixture").run(
                build_planning_input(request, versions, evidence))

        store, pid = self.store(runner)
        saved = store.create_run(pid, self.request, "planner", "api")
        self.assertEqual(saved["run"]["status"], "completed", saved)
        self.assertEqual(calls, ["need_extract", "product_compare", "concept_draft"])
        execution = saved["output"]["planning_execution"]
        self.assertEqual(execution["execution_kind"], "fixture")
        self.assertEqual(len(execution["model_calls"]), 3)


class WorkspacePlanningApiTests(unittest.TestCase):
    setUp = WorkspacePlanningTests.setUp
    def api(self, runner):
        tokens = {"editor": "e" * 48, "viewer": "v" * 48, "other": "o" * 48}
        entries = [{"principal_id": "other" if role == "other" else "planner",
                    "role": "editor" if role == "other" else role,
                    "token_sha256": sha256(token.encode()).hexdigest()} for role, token in tokens.items()]
        app = create_workspace_app(self.path, TokenRegistry(entries), planning_runner=runner,
                                   evidence_store=self.evidence)
        client = TestClient(app, base_url="http://127.0.0.1")
        headers = {role: {"Authorization": "Bearer " + token} for role, token in tokens.items()}
        result = client.post("/api/workspace/projects", headers=headers["editor"],
                             json={"name": "fixture", "request": self.request,
                                   "document_versions": self.versions})
        self.assertEqual(result.status_code, 201)
        return client, result.json()["data"]["project"]["id"], headers

    def test_api_opt_in_and_permission_checks_precede_runner(self):
        runner = FixtureRunner()
        client, pid, headers = self.api(runner)
        url = f"/api/workspace/projects/{pid}/runs"
        body = {"request": self.request, "previous_run_id": None, "unconfirmed": []}
        for role in ("viewer", "other"):
            self.assertEqual(client.post(url, headers=headers[role], json=body).status_code, 403)
        self.assertEqual(runner.calls, [])
        response = client.post(url, headers=headers["editor"], json=body)
        self.assertEqual(response.status_code, 201, response.text)
        validate("WorkspaceRunResponse", response.json())
        self.assertEqual(response.json()["data"]["run"]["status"], "completed")
        self.assertTrue(client.get("/health").json()["planning_enabled"])
        self.assertEqual(len(runner.calls), 1)

    def test_request_cannot_select_provider_model_endpoint_or_file(self):
        runner = FixtureRunner()
        client, pid, headers = self.api(runner)
        for key in ("endpoint", "model", "dataset_path", "enable_planning"):
            payload = {"request": {**self.request, key: "fixture-untrusted-selector"},
                       "previous_run_id": None, "unconfirmed": []}
            response = client.post(f"/api/workspace/projects/{pid}/runs", headers=headers["editor"], json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("fixture-untrusted-selector", response.text)
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
