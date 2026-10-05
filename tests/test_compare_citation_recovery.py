"""Bounded model correction of present-but-omitted manual citations, without live calls."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_planning_agent as fixtures
from test_planning_agent import stages_for


class CompareCitationRecoveryTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def omit_manual(self, value):
        value = deepcopy(value)
        manual_ids = {source["id"] for source in self.payload["sources"] if source["source_type"] == "manual"}
        for gap in value["result"]["gaps"]:
            gap["evidence_ids"] = [eid for eid in gap["evidence_ids"] if eid not in manual_ids]
            gap["support_status"] = "unsupported"
            gap["questions"] = ["해당 설명서가 있나요?"]
        for assessment in value["gap_assessments"]:
            assessment["support_basis"] = "explicit_unsupported"
        value["result"]["unresolved"] = ["설명서가 제공되지 않았습니다."]
        value.update(questions=["설명서가 있나요?"], hold_reasons=["설명서가 제공되지 않았습니다."])
        return value

    def test_present_exact_manual_omission_gets_model_retry_without_silent_repair(self):
        def alter(skill, context, value, count):
            if skill == "product_compare" and not context["feedback"]:
                return self.omit_manual(value)
            return value

        agent, transport = self.agent(alter)
        original = deepcopy(self.payload)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([post["skill"] for post in transport.posts],
                         ["need_extract", "product_compare", "product_compare", "concept_draft", "semantic_review"])
        comparisons = [call for call in result["model_calls"] if call["skill_id"] == "product_compare"]
        manual_id = self.payload["features"][0]["evidence_ids"][0]
        self.assertNotIn(manual_id, comparisons[0]["generated"]["data"]["result"]["gaps"][0]["evidence_ids"])
        self.assertIn(manual_id, comparisons[1]["generated"]["data"]["result"]["gaps"][0]["evidence_ids"])
        feedback = comparisons[1]["request_context"]["feedback"][0]
        self.assertEqual(feedback["linked_manual_evidence_ids"], [manual_id])
        self.assertEqual(feedback["required_review_evidence_ids"], self.output["needs"][0]["evidence_ids"])
        self.assertEqual(result["correction_budget"]["attempts"], [{"operation": "stage_retry", "revision_count": 1}])
        self.assertEqual(self.payload, original)

    def test_repeated_omission_exhausts_same_two_attempt_budget(self):
        agent, transport = self.agent(lambda skill, context, value, count:
                                     self.omit_manual(value) if skill == "product_compare" else value)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([post["skill"] for post in transport.posts], ["need_extract"] + ["product_compare"] * 3)
        self.assertEqual(result["correction_budget"]["attempts"],
                         [{"operation": "stage_retry", "revision_count": 1},
                          {"operation": "stage_retry", "revision_count": 2}])
        self.assertEqual(result["output"]["concepts"], [])

    def test_citation_retry_and_review_revision_share_the_same_budget(self):
        def alter(skill, context, value, count):
            if skill == "product_compare" and not context["feedback"]:
                return self.omit_manual(value)
            if skill == "semantic_review" and context["revision_count"] == 1:
                value["quality_assessments"][0].update(verdict="violation", reason="테스트 의미 수정 요청")
            return value

        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed", result["errors"])
        self.assertEqual(result["correction_budget"]["attempts"],
                         [{"operation": "stage_retry", "revision_count": 1},
                          {"operation": "review_revision", "revision_count": 2}])
        self.assertEqual([post["skill"] for post in transport.posts],
                         ["need_extract", "product_compare", "product_compare", "concept_draft",
                          "semantic_review", "review_revision", "semantic_review"])

    def test_actual_rejected_fridge_completions_retry_but_are_never_accepted_unchanged(self):
        path = Path(__file__).resolve().parents[1] / "evals/pm-intake/20261006/core/actual-fridge-normal-compare-rejected.json"
        recorded = json.loads(path.read_text("utf-8"))
        self.payload = recorded["original_input"]
        agent, transport = self.agent(stages=recorded["stage_outputs"])
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["decision"]["action"], "unresolved")
        self.assertEqual(len(result["correction_budget"]["attempts"]), 2)
        self.assertEqual([post["skill"] for post in transport.posts], ["need_extract"] + ["product_compare"] * 3)
        original_reviews = [item for item in result["trace"] if item["operation"] == "review_judgement"]
        self.assertEqual(original_reviews[0]["outputs"], recorded["observed_decision"])
        self.assertEqual(result["original_input"], recorded["original_input"])

    def test_genuinely_absent_manual_is_hold_without_model_retry(self):
        self.payload["features"] = []
        self.payload["sources"] = [source for source in self.payload["sources"] if source["source_type"] == "review"]
        stages = stages_for(self.output)
        comparison = self.omit_manual(stages["product_compare"])
        for gap in comparison["result"]["gaps"]:
            gap["feature_ids"] = []
            gap["evidence_ids"] = list(self.output["needs"][0]["evidence_ids"])
        stages["product_compare"] = comparison
        agent, transport = self.agent(stages=stages)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["correction_budget"]["attempts"], [])
        self.assertEqual([post["skill"] for post in transport.posts], ["need_extract", "product_compare"])

    def test_unknown_or_conflicting_comparison_stays_hold_even_with_omitted_manual(self):
        for basis in ("unmentioned", "conflicting"):
            with self.subTest(basis=basis):
                stages = stages_for(self.output)
                comparison = self.omit_manual(stages["product_compare"])
                unknown_gap = deepcopy(stages["product_compare"]["result"]["gaps"][0])
                unknown_gap.update(id="UNKNOWN-GAP", support_status="insufficient_evidence",
                                   questions=["상충 또는 미언급된 원문을 확인할 수 있나요?"])
                comparison["result"]["gaps"].append(unknown_gap)
                comparison["gap_assessments"].append({"gap_id": "UNKNOWN-GAP", "support_basis": basis,
                                                       "resolution": "unknown", "reason": "확인 불가능한 비교 근거"})
                stages["product_compare"] = comparison
                agent, transport = self.agent(stages=stages)
                result = agent.run(self.payload)
                self.assertEqual(result["status"], "held")
                self.assertEqual(result["correction_budget"]["attempts"], [])
                self.assertEqual([post["skill"] for post in transport.posts], ["need_extract", "product_compare"])


if __name__ == "__main__":
    unittest.main()
