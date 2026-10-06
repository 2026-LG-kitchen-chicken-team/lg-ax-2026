"""Declared complaints must not disappear before downstream generation.

Fixture transport only: no source-text classification or live quality claim.
"""
import unittest
from copy import deepcopy

import test_planning_agent as fixtures
from lgax_core.stage_alignment import stage_alignment_feedback


class ComplaintCoverageTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def omitted(self):
        declaration = fixtures.stages_for(self.output)["need_extract"]
        declaration["result"].update(needs=[], desired_outcomes=[])
        return declaration

    def test_feedback_names_declared_complaints_without_rewriting_them(self):
        declaration = self.omitted()
        original = deepcopy(declaration)
        feedback = stage_alignment_feedback(self.payload, "need_extract", declaration)
        self.assertIsNotNone(feedback)
        self.assertIn({"code": "COMPLAINT_NOT_EXTRACTED", "stage": "needs"}, feedback["violations"])
        self.assertEqual(feedback["unextracted_complaint_ids"],
                         [declaration["review_assessments"][0]["evidence_id"]])
        self.assertEqual(declaration, original)

    def test_persistent_omission_stops_before_compare_with_shared_two_corrections(self):
        def omit(skill, context, value, count):
            if skill == "need_extract":
                value["result"].update(needs=[], desired_outcomes=[])
            return value

        agent, transport = self.agent(omit)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual([post["skill"] for post in transport.posts], ["need_extract"] * 3)
        details = transport.posts[1]["context"]["feedback"][0]["details"]
        self.assertEqual(details["unextracted_complaint_ids"], [self.payload["sources"][0]["id"]])
        self.assertTrue(result["correction_budget"]["closed"])
        for call in result["model_calls"]:
            original = call["generated"]["data"]
            self.assertEqual(original["result"]["needs"], [])
            self.assertEqual(original["review_assessments"][0]["polarity"], "complaint")

    def test_one_correction_reextracts_before_compare_and_preserves_original(self):
        def once(skill, context, value, count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["result"].update(needs=[], desired_outcomes=[])
            return value

        agent, transport = self.agent(once)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual([post["skill"] for post in transport.posts],
                         ["need_extract", "need_extract", "product_compare", "concept_draft", "semantic_review"])
        self.assertEqual(result["model_calls"][0]["generated"]["data"]["result"]["needs"], [])
        self.assertEqual(result["model_calls"][1]["generated"]["data"]["result"]["needs"], self.output["needs"])

    def test_genuine_information_hold_does_not_require_inventing_a_need(self):
        def hold(skill, context, value, count):
            if skill == "need_extract":
                value["result"].update(needs=[], desired_outcomes=[], unresolved=["사용 조건 불명"])
                value.update(questions=["불편이 발생하는 사용 조건은 무엇인가요?"],
                             hold_reasons=["사용 조건 확인 필요"], no_candidate_reasons=["확정된 니즈 없음"])
            return value

        agent, transport = self.agent(hold)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual([post["skill"] for post in transport.posts], ["need_extract", "no_candidate_review"])
        self.assertEqual(result["output"]["needs"], [])

    def test_one_need_may_cover_multiple_declared_complaints(self):
        payload = deepcopy(self.payload)
        extra = deepcopy(payload["sources"][0])
        extra["id"] = "SECOND-REVIEW"
        payload["sources"].append(extra)
        declaration = fixtures.stages_for(self.output)["need_extract"]
        assessment = deepcopy(declaration["review_assessments"][0])
        assessment["evidence_id"] = extra["id"]
        declaration["review_assessments"].append(assessment)
        declaration["result"]["needs"][0]["evidence_ids"].append(extra["id"])
        self.assertIsNone(stage_alignment_feedback(payload, "need_extract", declaration))

    def test_noncomplaint_and_uncertain_declarations_do_not_force_needs(self):
        for polarity in ("positive", "irrelevant", "uncertain", "conflicting"):
            with self.subTest(polarity=polarity):
                declaration = self.omitted()
                declaration["review_assessments"][0]["polarity"] = polarity
                self.assertIsNone(stage_alignment_feedback(self.payload, "need_extract", declaration))


if __name__ == "__main__":
    unittest.main()
