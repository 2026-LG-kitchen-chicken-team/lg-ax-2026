"""Replay the real empty-result false acceptance, then verify bounded correction."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_planning_agent as fixtures
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.no_candidate_review import CRITERIA, review_no_candidate


def report_for(payload, output):
    source = payload["sources"][0]
    return {"input_sha256": input_digest(payload), "output_sha256": input_digest(output),
            "assessments": [{"criterion": criterion, "verdict": "consistent", "reason": "모의 검사 선언",
                             "candidate_quote": output["no_candidate_reasons"][0],
                             "source_quotes": [{"evidence_id": source["id"], "quote": source["text"]}]}
                            for criterion in CRITERIA], "questions": []}


class NoCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        fixtures.PlanningAgentTests.setUp(self)
        artifact = Path(__file__).resolve().parents[1] / (
            "evals/pm-intake/20261006/core/originals/thinking-8b-02-recommended-sampling.json")
        self.false_output = json.loads(artifact.read_text("utf-8"))["output"]

    def agent(self, alter=None):
        stages = fixtures.stages_for(self.output)
        stages["no_candidate_review"] = {}
        return fixtures.PlanningAgentTests.agent(self, alter, stages=stages)

    def empty_response(self, skill, context, value, count):
        if skill == "product_compare":
            value["result"]["gaps"][0]["remaining_pain"] = ""
            value["gap_assessments"][0]["resolution"] = "resolved"
        if skill == "no_candidate_review":
            return report_for(self.payload | {"revision_count": context["judgement"]["revision_count"]},
                              context["judgement"])
        return value

    def test_recorded_false_resolved_output_cannot_pass_without_semantic_gate(self):
        # This is the real model output that formerly passed canonical structure.
        self.assertEqual(review_judgement(self.payload, self.false_output)["action"], "accept")
        declaration = report_for(self.payload, self.false_output)
        declaration["assessments"][1].update(verdict="violation", reason="사용 조건 자체가 리뷰의 잔여 불편이다")
        checked = review_no_candidate(self.payload, self.false_output, declaration)
        self.assertEqual(checked["action"], "revise")
        self.assertEqual(checked["rerun_from"], "compare")

    def test_false_empty_result_reruns_compare_and_discards_stale_resolved_reason(self):
        def alter(skill, context, value, count):
            if skill == "product_compare" and context["revision_count"] == 0:
                return self.empty_response(skill, context, value, count)
            if skill == "no_candidate_review":
                value = report_for(self.payload, context["judgement"])
                value["assessments"][1].update(verdict="violation", reason="작동 조건이 희망 결과를 해결하지 않는다")
            return value
        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["output"]["concepts"])
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual(result["output"]["no_candidate_reasons"], [])
        self.assertEqual([post["skill"] for post in transport.posts], [
            "need_extract", "product_compare", "no_candidate_review",
            "product_compare", "concept_draft", "semantic_review"])
        self.assertIn("원 자료", transport.posts[2]["request"]["prompt"])

    def test_repeated_false_empty_claim_never_gets_third_correction(self):
        def alter(skill, context, value, count):
            if skill == "no_candidate_review":
                value = report_for(self.payload | {"revision_count": context["judgement"]["revision_count"]},
                                   context["judgement"])
                value["assessments"][1].update(verdict="violation", reason="고객 불편 미해결")
                return value
            return self.empty_response(skill, context, value, count)
        result = self.agent(alter)[0].run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(len(result["no_candidate_reviews"]), 3)
        self.assertFalse(result["output"]["concepts"])
        self.assertTrue(result["correction_budget"]["closed"])

    def test_consistent_mock_declaration_is_recorded_before_empty_acceptance(self):
        result = self.agent(self.empty_response)[0].run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["no_candidate_reviews"]), 1)
        self.assertEqual(result["output"]["concepts"], [])

    def test_tampered_scope_quote_and_missing_criterion_are_rejected(self):
        for change in (lambda r: r.update(output_sha256="0" * 64),
                       lambda r: r["assessments"][0]["source_quotes"][0].update(quote="꾸민 원문"),
                       lambda r: r["assessments"][0].update(candidate_quote="꾸민 판단문"),
                       lambda r: r["assessments"][0].update(criterion="feature_resolution")):
            value = report_for(self.payload, self.false_output)
            change(value)
            with self.assertRaises(DomainError):
                review_no_candidate(self.payload, self.false_output, value)

    def test_uncertain_requires_question_and_stops_for_missing_material(self):
        value = report_for(self.payload, self.false_output)
        value["assessments"][1]["verdict"] = "uncertain"
        with self.assertRaises(DomainError):
            review_no_candidate(self.payload, self.false_output, value)
        value["questions"] = ["현재 사용 조건의 상세 설명서를 제공할 수 있나요?"]
        self.assertEqual(review_no_candidate(self.payload, self.false_output, value)["action"], "hold")

    def test_consistent_held_declaration_never_promotes_original_hold_to_accept(self):
        held = deepcopy(self.false_output)
        held.update(status="held", questions=["관련 상세 조건을 제공할 수 있나요?"],
                    hold_reasons=["추가 자료 필요"])
        self.assertEqual(review_judgement(self.payload, held)["action"], "hold")
        decision = review_no_candidate(self.payload, held, report_for(self.payload, held))
        self.assertEqual(decision["action"], "hold")
        self.assertEqual(decision["next_revision_count"], 0)

    def test_structurally_valid_false_hold_is_reviewed_and_corrected_with_same_budget(self):
        def alter(skill, context, value, _count):
            if skill == "product_compare" and context["revision_count"] == 0:
                value["result"]["unresolved"] = ["현재 기능 설명서가 없다고 판단했다"]
                value["hold_reasons"] = ["현재 기능 설명서가 없다고 판단했다"]
                value["questions"] = ["설명서를 제공할 수 있나요?"]
            if skill == "no_candidate_review":
                value["assessments"][1].update(verdict="violation", reason="연결된 설명서 원문과 위치가 이미 제공됐다")
            return value
        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual(result["no_candidate_reviews"][0]["reviewed_output"]["status"], "held")
        self.assertEqual(result["no_candidate_reviews"][0]["decision"]["rerun_from"], "compare")
        self.assertEqual([p["skill"] for p in transport.posts], [
            "need_extract", "product_compare", "no_candidate_review",
            "product_compare", "concept_draft", "semantic_review"])
        self.assertEqual(result["output"]["hold_reasons"], [])

    def test_genuine_hold_preserves_questions_and_never_generates_candidates(self):
        def alter(skill, _context, value, _count):
            if skill == "product_compare":
                value["result"]["unresolved"] = ["고객이 원하는 추가 조건은 아직 없다"]
                value["hold_reasons"] = ["고객이 원하는 추가 조건은 아직 없다"]
                value["questions"] = ["추가 조건을 제공할 수 있나요?"]
            return value
        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual(result["output"]["questions"], ["추가 조건을 제공할 수 있나요?"])
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual([p["skill"] for p in transport.posts], [
            "need_extract", "product_compare", "no_candidate_review"])
