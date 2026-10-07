"""Real HTTP/stdio MCP projection; never a model or provider call."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest

import httpx

from lgax_api.public_validation import public_validation_details
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.store import DemoStore
from test_workspace_planning import FixtureRunner, dataset_for, read

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_validation_replay_helpers", ROOT / "evals/pm-intake/20261006/replay_workspace.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
# The historical helper predates the three registered review-trend read tools.
helpers.TOOLS = helpers.TOOLS | {"review_trends", "get_review_trends", "trend_evidence"}
PRIVATE = "private-fixture-diagnostic-value"


class DiagnosticRunner(FixtureRunner):
    def __call__(self, request, versions, store):
        result = super().__call__(request, versions, store)
        evidence_id = next(source["id"] for source in result["input"]["sources"] if source["source_type"] == "review")
        error = {"code": "VALIDATION_FAILED", "message": PRIVATE, "details": {
            "violations": [{"code": "UNCERTAINTY_CONTEXT_MISSING", "evidence_id": evidence_id,
                            "path": "uncertainty_assessments/0/questions", "instruction": PRIVATE},
                           {"code": PRIVATE, "evidence_id": PRIVATE},
                           {"code": "UNCERTAINTY_SCOPE_MISMATCH", "evidence_id": PRIVATE, "path": PRIVATE},
                           {"code": [PRIVATE]}, None],
            "code": "EMPTY_NEEDS_WITHOUT_JUDGEMENT", "reason": "schema_mismatch",
            "conflicting_paths": ["review_assessments", "result/review_assessments"],
            "evidence_id": evidence_id, "declared_polarity": "uncertain", "private_provider": PRIVATE}}
        result["errors"] = [error, {"code": "MODEL_UNAVAILABLE", "message": PRIVATE, "details": error["details"]}]
        result["model_calls"][0].update(stage="needs", skill_id="need_extract", execution_kind="fixture",
                                        revision_count=0, model_id="fixture", model_digest="b" * 64)
        result["trace"].append({"stage": "needs", "operation": "need_extract", "outputs": {"ok": False, "error": error}})
        result["model_calls"][0]["error"] = {"code": "MODEL_UNAVAILABLE", "message": PRIVATE, "details": error["details"]}
        result["rejected_execution"] = {"provider": PRIVATE}
        return result


class PublicValidationProjectionTests(unittest.TestCase):
    def test_grounding_projection_authorizes_every_id_and_discards_private_nested_fields(self):
        facts = {"code": "CONCEPT_GROUNDING_MISSING", "concept_id": "CONCEPT-001",
                 "missing_links": [{"gap_id": "GAP-001", "need_id": "NEED-001",
                                    "required_evidence_ids": ["REVIEW-001", "MANUAL-001"],
                                    "missing_evidence_ids": ["MANUAL-001"], "private_provider": PRIVATE}],
                 "private": PRIVATE}
        error = {"code": "VALIDATION_FAILED", "message": PRIVATE,
                 "details": {"reason": "schema_mismatch", "grounding_violations": [facts], "private": PRIVATE}}
        entities = {"concepts": {"CONCEPT-001"}, "gaps": {"GAP-001"}, "needs": {"NEED-001"}}
        result = public_validation_details(error, {"REVIEW-001", "MANUAL-001"}, entities)
        self.assertEqual(result["grounding_violations"][0]["missing_links"][0]["missing_evidence_ids"], ["MANUAL-001"])
        self.assertNotIn(PRIVATE, json.dumps(result))
        unscoped = public_validation_details(error, {"REVIEW-001"}, {})
        self.assertEqual(unscoped["grounding_violations"], [{"code": "CONCEPT_GROUNDING_MISSING"}])
        facts["missing_links"][0]["missing_evidence_ids"] = ["REVIEW-001", PRIVATE]
        result = public_validation_details(error, {"REVIEW-001", "MANUAL-001"}, entities)
        self.assertNotIn("missing_links", result["grounding_violations"][0])

    def test_need_presence_claims_are_scoped_and_non_validation_errors_stay_closed(self):
        error = {"code": "VALIDATION_FAILED", "details": {"reason": "reviewer_reports_existing_need",
                 "contradictions": [{"review_evidence_id": "REVIEW-001", "existing_need_ids": ["NEED-001"], "private": PRIVATE},
                                    {"review_evidence_id": PRIVATE, "existing_need_ids": ["NEED-001"]}]}}
        result = public_validation_details(error, {"REVIEW-001"}, {"needs": {"NEED-001"}})
        self.assertEqual(result['contradictions'], [{"review_evidence_id": "REVIEW-001", "existing_need_ids": ["NEED-001"]}])
        error['code'] = 'MODEL_UNAVAILABLE'
        self.assertEqual(public_validation_details(error, {"REVIEW-001"}, {"needs": {"NEED-001"}}), {})

    def test_malformed_new_diagnostic_ids_are_dropped_without_type_errors(self):
        error = {"code": "VALIDATION_FAILED", "details": {
            "grounding_violations": [{"code": "CONCEPT_GROUNDING_MISSING", "concept_id": [PRIVATE],
                                      "missing_links": [{"gap_id": [PRIVATE], "need_id": {"private": PRIVATE}}]}],
            "contradictions": [{"review_evidence_id": [PRIVATE], "existing_need_ids": [PRIVATE]}]}}
        result = public_validation_details(error, {"REVIEW-001"}, {"needs": {"NEED-001"}})
        self.assertEqual(result, {"grounding_violations": [{"code": "CONCEPT_GROUNDING_MISSING"}]})

    def test_public_run_authorizes_model_free_concept_from_its_gap_and_source_graph(self):
        import test_planning_agent as fixtures
        from lgax_api.workspace_server import public_run
        payload = fixtures.read('normal.input.json')
        output = fixtures.read('normal.fixture-output.json')
        concept = output['concepts'][0]
        gap = next(row for row in output['gaps'] if row['id'] in concept['gap_ids'])
        self.assertNotIn('model_id', concept)
        facts = {'code': 'CONCEPT_GROUNDING_MISSING', 'concept_id': concept['id'],
                 'missing_links': [{'gap_id': gap['id'], 'need_id': gap['need_id'],
                                    'required_evidence_ids': gap['evidence_ids'],
                                    'missing_evidence_ids': [gap['evidence_ids'][0]]}]}
        snapshot = {'output': {'planning_execution': {'input': payload, 'output': output,
                    'model_calls': [], 'trace': [], 'errors': [{'code': 'VALIDATION_FAILED',
                    'message': PRIVATE, 'details': {'grounding_violations': [facts]}}]}}}
        public = public_run(snapshot)
        actual = public['output']['planning_execution']['errors'][0]['details']['grounding_violations'][0]
        self.assertEqual(actual['concept_id'], concept['id'])
        self.assertEqual(actual['missing_links'][0]['gap_id'], gap['id'])
        self.assertEqual(snapshot['output']['planning_execution']['errors'][0]['message'], PRIVATE)
        snapshot['output']['planning_execution']['output']['concepts'][0]['gap_ids'] = ['UNAUTHORIZED-GAP']
        actual = public_run(snapshot)['output']['planning_execution']['errors'][0]['details']['grounding_violations'][0]
        self.assertNotIn('concept_id', actual)

    def test_malformed_sensitive_fields_are_not_public_validation_facts(self):
        for details in (None, [PRIVATE], {"code": [PRIVATE], "violations": "not-list"},
                        {"reason": PRIVATE, "evidence_id": PRIVATE, "declared_polarity": "uncertain",
                         "conflicting_paths": ["review_assessments", PRIVATE]},
                        {"conflicting_paths": [[PRIVATE], "result/review_assessments"]}):
            self.assertEqual(public_validation_details({"code": "VALIDATION_FAILED", "details": details}, {"PUBLIC-REVIEW"}), {})
        self.assertEqual(public_validation_details({"code": "MODEL_UNAVAILABLE", "details": {"code": "UNCERTAINTY_CONTEXT_MISSING"}}, set()), {})
        self.assertEqual(public_validation_details({"code": "VALIDATION_FAILED", "details": {"violations": [{"code": "UNCERTAINTY_FIELD_MISSING", "path": "uncertainty_assessments/0/questions/" + PRIVATE}] }}, set()), {"violations": [{"code": "UNCERTAINTY_FIELD_MISSING"}]})

    def test_http_post_get_history_and_stdio_mcp_preserve_only_safe_facts(self):
        payload = read("normal.input.json")
        request = payload["request"]
        versions = {payload["product"]["model_id"]: "1.0"}
        evidence = DemoStore(dataset_for(payload))
        token = secrets.token_urlsafe(40)
        registry = TokenRegistry([{"principal_id": "planner", "role": "editor", "token_sha256": sha256(token.encode()).hexdigest()}])
        runner = DiagnosticRunner(status="held")
        with TemporaryDirectory() as temporary:
            temp = Path(temporary)
            credential = temp / "guest-client.json"
            credential.write_text(json.dumps({"token": token}))
            app = create_workspace_app(temp / "workspace.sqlite", registry, evidence_store=evidence, planning_runner=runner)
            with helpers.http_server(app) as url, httpx.Client(base_url=url, trust_env=False, headers={"Authorization": "Bearer " + token}, timeout=30) as client:
                project = helpers.response(client, "POST", "/api/workspace/projects", 201, json={"name": "public projection fixture", "request": request, "document_versions": versions})["data"]
                pid = project["project"]["id"]
                saved = helpers.response(client, "POST", f"/api/workspace/projects/{pid}/runs", 201, json={"request": request, "previous_run_id": None, "unconfirmed": []})["data"]
                self.assertEqual(saved["run"]["status"], "held")
                execution = saved["output"]["planning_execution"]
                self.assertEqual(execution["input"]["sources"], payload["sources"])
                self.assertTrue(execution["output"]["hold_reasons"])
                details = execution["errors"][0]["details"]
                self.assertEqual(details["violations"][0]["code"], "UNCERTAINTY_CONTEXT_MISSING")
                self.assertEqual(details["violations"][0]["path"], "uncertainty_assessments/0/questions")
                self.assertEqual(set(details["violations"][1]), {"code"})
                self.assertEqual(execution["trace"][-1]["outputs"]["error"]["details"], details)
                self.assertEqual(execution["errors"][1]["details"], {})
                self.assertEqual(execution["model_calls"][0]["error"]["details"], {})
                self.assertNotIn("rejected_execution", execution)
                self.assertNotIn(PRIVATE, json.dumps(saved))
                self.assertNotIn(token, json.dumps(saved))
                rid = saved["run"]["id"]
                self.assertEqual(helpers.response(client, "GET", f"/api/workspace/runs/{rid}", 200)["data"], saved)
                self.assertEqual(helpers.response(client, "GET", f"/api/workspace/projects/{pid}/runs", 200)["data"]["runs"], [saved])
                raw = app.state.workspace.get_run(rid, "planner")
                self.assertIn(PRIVATE, json.dumps(raw))
                normal_runner = FixtureRunner(status="held")
                app.state.workspace.planning_runner = normal_runner
                normal_project = helpers.response(client, "POST", "/api/workspace/projects", 201, json={"name": "ordinary held fixture", "request": request, "document_versions": versions})["data"]
                normal_pid = normal_project["project"]["id"]
                normal = helpers.response(client, "POST", f"/api/workspace/projects/{normal_pid}/runs", 201, json={"request": request, "previous_run_id": None, "unconfirmed": []})["data"]
                normal_execution = normal["output"]["planning_execution"]
                self.assertEqual(normal["run"]["status"], "held")
                self.assertEqual(normal_execution["errors"], [])
                self.assertEqual(normal_execution["output"]["hold_reasons"], ["추가 근거 확인 필요"])
                self.assertEqual(normal_execution["output"]["no_candidate_reasons"], ["보류 상태에서 후보 생성하지 않음"])
                self.assertEqual(normal_execution["input"]["sources"], payload["sources"])
                self.assertEqual(helpers.response(client, "GET", f"/api/workspace/runs/{normal['run']['id']}", 200)["data"], normal)
                self.assertEqual(helpers.response(client, "GET", f"/api/workspace/projects/{normal_pid}/runs", 200)["data"]["runs"], [normal])
                actual_mcp = asyncio.run(helpers.mcp_readback(url, credential, temp, [project, normal_project], {"safe-validation": saved, "normal-hold": normal}))
                self.assertEqual(actual_mcp["runs"]["safe-validation"], saved)
                self.assertEqual(actual_mcp["runs"]["normal-hold"], normal)
                self.assertEqual(len(runner.calls), 1)
                self.assertEqual(len(normal_runner.calls), 1)
                proof_file = os.environ.get("LGAX_PUBLIC_VALIDATION_PROOF_FILE")
                if proof_file:
                    Path(proof_file).write_text(json.dumps({"snapshot": saved, "http_post_get_history_same": True, "normal_hold_readback_same": True, "stdio_mcp_same": True, "model_calls": 0}, ensure_ascii=False), encoding="utf-8")

    def test_normal_hold_keeps_its_existing_output(self):
        payload = read("normal.input.json")
        from lgax_api.workspace_server import public_run
        normal = {"output": {"planning_execution": {"input": deepcopy(payload), "output": {"questions": ["확인 질문"], "hold_reasons": ["추가 근거"], "unresolved": ["미확인"]}, "errors": [], "trace": [], "model_calls": []}}}
        self.assertEqual(public_run(normal), normal)


if __name__ == "__main__":
    unittest.main()
