"""Retained real-source wire failures, not new model runs or semantic approval.

The caller receives the original full schema. Default native generation remains
strict; explicit PublicPlanner item recovery has its own boundary regressions.
"""
import json
import unittest
from copy import deepcopy

import test_model_client
from lgax_contracts.research import load_research_schema
from lgax_core.errors import DomainError
from lgax_core.public_planning import PublicPlanner, _output_schema, source_facts
from test_public_planning import real_bundle

FAULTY = "고객은 냉동 핫도그를 데웠으나, 1분 후에도 완전 차가운 냉동 상태였다고 보고했습니다."


def wire_problem(bundle, item_id, description):
    return {"id": item_id, "title": "TEST ONLY: 응답 경계 검사", "description": description,
            "source_ids": [bundle["sources"][0]["source_id"]], "counter_source_ids": [],
            "scope_caveat": "TEST ONLY: 고객 문제/품질/기획 승인 아님"}


def invoke(bundle, rows):
    output = {"problems": deepcopy(rows), "summaries": {"positive": [], "negative": [], "mixed": []}}
    stages, schemas = [], []

    def wire_caller(prompt, schema):
        context = json.loads(prompt.split("분석할 데이터(JSON):\n", 1)[1])
        stage = "discover" if "batch" in context else "repair_fields" if "rejected_fields" in context else "plan"
        stages.append(stage)
        schemas.append(deepcopy(schema))
        return deepcopy(output) if stage == "discover" else None

    result = PublicPlanner(wire_caller).run(bundle, "TEST ONLY: 原 입력 응답 경계 검사", [])
    return result, stages, schemas, output


class PublicPlanningIsolationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = real_bundle()

    def test_three_observed_bad_wordings_share_two_corrections_including_failures(self):
        rows = [wire_problem(self.bundle, f"test-only-rejected-{index}", FAULTY) for index in range(3)]
        result, stages, _, original = invoke(self.bundle, rows)
        self.assertEqual(stages, ["discover", "repair_fields", "repair_fields"])
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 2)
        self.assertEqual(result["runtime"]["model_calls"][0]["response"], original)
        self.assertEqual(len(result["runtime"]["item_issues"]), 3)
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])

    def test_missing_title_neighbor_does_not_erase_valid_source_copy_or_loosen_caller_schema(self):
        healthy = wire_problem(self.bundle, "test-only-source-copy", self.bundle["sources"][0]["text"])
        malformed = {key: value for key, value in healthy.items() if key != "title"}
        malformed["id"] = "test-only-missing-title"
        before = deepcopy(self.bundle)
        result, stages, schemas, original = invoke(self.bundle, [healthy, malformed])
        self.assertEqual(stages, ["discover", "repair_fields", "plan"])
        self.assertEqual(result["problems"], [{**healthy, "id": "problem-1"}])
        self.assertIn("title", schemas[0]["$defs"]["Problem"]["required"])
        self.assertEqual(schemas[0]["properties"]["problems"]["items"], {"$ref": "#/$defs/Problem"})
        self.assertEqual(result["runtime"]["model_calls"][0]["response"], original)
        self.assertEqual(result["status"], "needs_sources")
        self.assertEqual(result["concepts"], [])
        self.assertEqual(self.bundle, before)

    def test_nonobject_and_unhashable_ids_are_isolated_but_envelope_cardinality_is_not(self):
        healthy = wire_problem(self.bundle, "test-only-source-copy", self.bundle["sources"][0]["text"])
        bad_ids = {**healthy, "id": "test-only-bad-source", "source_ids": [{}]}
        result, _, _, _ = invoke(self.bundle, [healthy, None, bad_ids])
        self.assertEqual(result["problems"], [{**healthy, "id": "problem-1"}])
        over_limit, stages, _, _ = invoke(self.bundle, [healthy] * 4)
        self.assertEqual(stages, ["discover"])
        self.assertEqual(over_limit["problems"], [])
        self.assertEqual(over_limit["runtime"]["model_calls"][0]["status"], "rejected")

    def test_default_structured_client_rejects_whole_response_without_opt_in(self):
        healthy = wire_problem(self.bundle, "test-only-source-copy", self.bundle["sources"][0]["text"])
        malformed = {key: value for key, value in healthy.items() if key != "title"}
        output = {"problems": [healthy, malformed], "summaries": {"positive": [], "negative": [], "mixed": []}}
        fixture = test_model_client.ModelClientTests()
        self.addCleanup(fixture.doCleanups)
        client, backend = fixture.client(test_model_client.Backend(response=json.dumps(output)))
        schema = _output_schema({
            "problems": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/Problem"}},
            "summaries": deepcopy(load_research_schema()["$defs"]["PlanningBrief"]["properties"]["summaries"]),
        }, ("Problem", "SummaryItem"))
        with self.assertRaises(DomainError) as raised:
            client.generate("TEST ONLY: 기본 native 경계 검사", schema, test_model_client.MODEL)
        self.assertEqual(raised.exception.details["reason"], "schema_mismatch")
        self.assertEqual(len([r for r in backend.requests if r.url.path == "/api/generate"]), 1)

    def test_shared_limit_also_holds_through_actual_structured_client(self):
        rows = [wire_problem(self.bundle, f"test-only-rejected-{index}", FAULTY) for index in range(3)]
        output = {"problems": rows, "summaries": {"positive": [], "negative": [], "mixed": []}}
        fixture = test_model_client.ModelClientTests()
        self.addCleanup(fixture.doCleanups)
        # Returning the discovery again to a patch request is a rejected patch,
        # preserving the adapter's schema check and spending the failed attempt.
        client, backend = fixture.client(test_model_client.Backend(response=json.dumps(output)))
        result = PublicPlanner.from_model_client(client).run(self.bundle, "TEST ONLY: native 수정 한도", [])
        stages = [r["stage"] for r in result["runtime"]["model_calls"]]
        self.assertEqual(stages, ["discover", "repair_fields", "repair_fields"])
        self.assertEqual(len([r for r in backend.requests if r.url.path == "/api/generate"]), 3)
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 2)
        self.assertEqual(result["problems"], [])
