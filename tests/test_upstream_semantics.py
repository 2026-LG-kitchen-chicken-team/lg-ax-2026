"""Observed counterexamples and active protocol guards; no live semantic grade."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_planning_agent as fixtures
from jsonschema import Draft202012Validator
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest
from lgax_core.model_client import ModelConfig, StructuredModelClient
from lgax_core.semantic_review import (
    INSTRUCTIONS,
    review_semantics,
    schema_for_review,
    semantic_feedback,
    semantic_model_context,
)
from lgax_core.source_boundary import SourceBoundary
from test_r5_semantic_prompt import DIGEST, MODEL, PreparationCapture, PreparedWithoutGeneration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/pm-prototype/20261007/r5-core/normal-8ec-upstream-counterexample.json"
PIN = "e2c5539485a8e4d62d7284cfeca12bd00b607be4ea150c6344a4a9c881d9dd6b"


class UpstreamSemanticTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), PIN)
        self.case = json.loads(self.raw)
        self.payload, self.output = self.case["payload"], self.case["output"]
        context = {**deepcopy(self.case["request_context"]), "upstream_review_required": True}
        self.report = fixtures.semantic_for(context)
        self.report["quality_assessments"] = deepcopy(self.case["original_report"]["quality_assessments"])
        self.schema = schema_for_review(self.payload, self.output, include_upstream=True)

    def tearDown(self):
        self.assertEqual(FIXTURE.read_bytes(), self.raw)

    def review(self):
        return review_semantics(self.payload, self.output, self.report, require_upstream=True)

    def assessment(self, kind, identifier):
        return next(row for row in self.report["upstream_assessments"]
                    if row["entity_kind"] == kind and row["entity_id"] == identifier)

    def test_observed_completed_report_without_need_gap_review_cannot_accept_active_run(self):
        self.assertEqual(self.case["original_output_sha256"],
                         "276e774a69eeae1fb24c414a003335b837be2d7fde64b16bd60168a3f0af418a")
        old = self.case["original_report"]
        self.assertTrue(all(row["verdict"] == "satisfied" for row in old["quality_assessments"]))
        self.assertEqual(review_semantics(self.payload, self.output, old)["action"], "accept")
        with self.assertRaises(DomainError) as caught:
            review_semantics(self.payload, self.output, old, require_upstream=True)
        self.assertEqual(caught.exception.details["reason"], "semantic_review_schema")
        self.assertFalse(any("GAP-004" in row["gap_ids"] for row in self.output["concepts"]))
        self.assertIn(("gap", "GAP-004"),
                      {(row["entity_kind"], row["entity_id"]) for row in self.report["upstream_assessments"]})

    def test_three_human_labelled_errors_route_to_original_stage_with_shared_budget(self):
        reasons = {("need", "NEED-007"): "욕구 원문에는 전체 식품 이동 경험을 명시하지 않았다.",
                   ("gap", "GAP-004"): "설명문 존재는 해당 방법의 발견성 해결 근거가 아니다.",
                   ("gap", "GAP-005"): "선반 설명서는 바구니의 명시 지원을 입증하지 않는다."}
        for (kind, identifier), reason in reasons.items():
            self.assessment(kind, identifier).update(verdict="violation", reason=reason)
        Draft202012Validator(self.schema).validate(self.report)
        result = self.review()
        self.assertEqual((result["action"], result["rerun_from"], result["next_revision_count"]),
                         ("revise", "needs", 2))
        self.assertEqual({row["stage"] for row in semantic_feedback(self.report)}, {"needs", "compare"})
        self.assertIn("욕구 원문", semantic_feedback(self.report)[0]["details"]["reason"])
        self.payload["revision_count"] = 2
        self.report["input_sha256"] = input_digest(self.payload)
        self.assertEqual(self.review()["action"], "unresolved")
        self.assertEqual(self.review()["next_revision_count"], 2)

    def test_gap_only_error_routes_to_compare_not_candidate_only(self):
        self.assessment("gap", "GAP-004")["verdict"] = "violation"
        self.assertEqual(self.review()["rerun_from"], "compare")

    def test_each_upstream_entity_is_scoped_once_and_quote_belongs_to_that_entity(self):
        original = deepcopy(self.report)
        for mutation, reason in (
            (lambda rows: rows.__setitem__(0, deepcopy(rows[1])), "upstream_entity_coverage"),
            (lambda rows: rows[0].update(entity_kind="gap"), "upstream_entity_coverage"),
            (lambda rows: rows[0].update(judgement_quote=self.output["needs"][1]["pain"]),
             "upstream_judgement_quote_not_literal"),
            (lambda rows: rows[0]["source_quotes"][0].update(quote="原文にない fabricated constraint"),
             "upstream_source_quote_not_scoped_literal"),
        ):
            with self.subTest(reason=reason):
                self.report = deepcopy(original)
                mutation(self.report["upstream_assessments"])
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertEqual(caught.exception.details["reason"], reason)

    def test_unrelated_review_or_missing_manual_cannot_certify_consistency(self):
        row = self.assessment("need", "NEED-007")
        row["source_quotes"] = [{"evidence_id": "REVIEW-EVIDENCE-001",
                                 "quote": self.payload["sources"][1]["text"]}]
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "upstream_requires_linked_review")
        row["verdict"] = "violation"
        row = self.assessment("gap", "GAP-005")
        source = next(source for source in self.payload["sources"] if source["id"] == "REVIEW-EVIDENCE-005")
        row["source_quotes"] = [{"evidence_id": source["id"], "quote": source["text"]}]
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "upstream_requires_feature_manual")

    def test_real_uncertainty_requires_question_without_force_accept(self):
        self.assessment("gap", "GAP-004")["verdict"] = "uncertain"
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "uncertain_requires_question")
        self.report["questions"] = ["사용자가 해당 방법을 발견하는 경로를 확인할 수 있나요?"]
        self.assertEqual(self.review()["action"], "hold")

    def test_active_pipeline_uses_same_revision_session_and_retains_upstream_feedback(self):
        helper = fixtures.PlanningAgentTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)

        def alter(skill, context, value, _count):
            if skill == "semantic_review" and context["revision_count"] == 0:
                value["upstream_assessments"][0].update(
                    verdict="violation", reason="Mock source-fidelity correction; not live model quality")
            return value

        agent, transport = helper.agent(alter)
        result = agent.run(helper.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual([row["skill"] for row in transport.posts],
                         ["need_extract", "product_compare", "concept_draft", "semantic_review",
                          "review_revision", "semantic_review"])
        self.assertEqual(result["semantic_reviews"][0]["decision"]["rerun_from"], "needs")
        self.assertEqual(result["correction_budget"]["revision_count"], 1)
        self.assertEqual(result["correction_budget"]["max_revisions"], 2)
        corrected = next(row for row in transport.posts if row["skill"] == "review_revision")
        feedback = json.loads(corrected["context"]["previous"]["violations"][0])
        self.assertEqual((feedback["code"], feedback["stage"]), ("UPSTREAM_NEED_VIOLATION", "needs"))
        self.assertEqual(feedback["details"]["judgement_quote"], helper.output["needs"][0]["pain"])

    def test_actual_formatted_prompt_and_complete_declarations_fit_unchanged_limits(self):
        context = {**deepcopy(self.case["request_context"]), "upstream_review_required": True}
        projected = semantic_model_context(context)
        for field in ("needs", "desired_outcomes", "gaps", "review_assessments", "gap_assessments"):
            table = projected[field]
            self.assertEqual([dict(zip(table["columns"], row, strict=True)) for row in table["values"]],
                             context[field])
        for field in ("sources", "features", "concepts", "semantic_grounding_requirements"):
            self.assertEqual(projected[field], context[field])
        self.assertIn("restores every field exactly", projected["quality_context"]["reference"])
        adapter = PreparationCapture(ModelConfig("http://127.0.0.1:11434", MODEL, DIGEST,
                                                 max_output_tokens=8192, context_tokens=16384))
        self.addCleanup(adapter.close)
        client = StructuredModelClient(adapter)
        policy = SourceBoundary(self.payload, allowed_tools=("get_evidence", "list_products")).messages()[0]["content"]
        prompt = policy + "\n" + INSTRUCTIONS + json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
        schema = schema_for_review(self.payload, self.output, literal_choices=True, include_upstream=True)
        with self.assertRaises(PreparedWithoutGeneration):
            client.generate(prompt, schema, MODEL)
        formatted, actual_schema = adapter.prepared
        self.assertEqual(actual_schema, schema)
        self.assertLessEqual(len(formatted), 24000)
        self.assertLessEqual(len(formatted.encode("utf-8")), 45000)
        self.assertEqual(len(self.report["upstream_assessments"]), 18)
        print(json.dumps({"upstream_active_formatted_prompt_chars": len(formatted),
                          "utf8_bytes": len(formatted.encode("utf-8")), "unchanged_limits": [24000, 45000],
                          "needs_gaps_concepts": [9, 9, 3], "model_calls": 0}))


if __name__ == "__main__":
    unittest.main()
