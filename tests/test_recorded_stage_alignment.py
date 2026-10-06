"""Replay preserved PM completions; no model calls or semantic auto-labels."""
import json
import unittest
from copy import deepcopy

import test_planning_agent as fixtures


class RecordedStageAlignmentTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def test_recorded_positive_need_stops_before_later_stages_with_ids(self):
        for name in ("fridge-normal", "microwave-normal"):
            with self.subTest(name=name):
                path = fixtures.ROOT / f"evals/pm-prototype/20261006/finite-model-study/8b-bounded12/{name}.json"
                original = path.read_bytes()
                recorded = json.loads(original)
                self.payload = deepcopy(recorded["original_input"])
                declarations = [c["generated"]["data"] for c in recorded["model_calls"]
                                if c["skill_id"] == "need_extract"]

                def replay(skill, context, value, count, original_calls=recorded["model_calls"]):
                    responses = [c["generated"]["data"] for c in original_calls if c["skill_id"] == skill]
                    return deepcopy(responses[context["revision_count"]])

                agent, transport = self.agent(replay)
                result = agent.run(self.payload)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["input"]["revision_count"], 2)
                self.assertEqual([p["skill"] for p in transport.posts], ["need_extract"] * 3)
                self.assertEqual([c["generated"]["data"] for c in result["model_calls"]], declarations)
                self.assertTrue(result["correction_budget"]["closed"])
                details = transport.posts[1]["context"]["feedback"][0]["details"]
                self.assertIn({"code": "NON_COMPLAINT_AS_NEED", "stage": "needs"}, details["violations"])
                first = declarations[0]["result"]["needs"][0]
                self.assertIn({"need_id": first["id"], "evidence_id": first["evidence_ids"][0],
                               "declared_polarity": "positive"}, details["non_complaint_links"])
                self.assertEqual(path.read_bytes(), original)

    def test_empty_concepts_with_recorded_assessments_retries_only_concepts(self):
        path = fixtures.ROOT / "evals/pm-prototype/20261006/finite-model-study/8b-bounded12/fridge-normal.json"
        original = path.read_bytes()
        recorded = json.loads(original)
        declarations = [c["generated"]["data"] for c in recorded["model_calls"]
                        if c["skill_id"] == "concept_draft"]

        def replay(skill, context, value, count):
            if skill == "concept_draft":
                return deepcopy(declarations[context["revision_count"]])
            return value

        agent, transport = self.agent(replay)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare"] + ["concept_draft"] * 3)
        self.assertEqual([c["generated"]["data"] for c in result["model_calls"][2:]], declarations)
        details = transport.posts[3]["context"]["feedback"][0]["details"]
        self.assertEqual(details["assessment_coverage"]["expected_ids"], [])
        self.assertEqual(details["assessment_coverage"]["unexpected_ids"], ["CONCEPT-001", "CONCEPT-002", "CONCEPT-003"])
        self.assertFalse(result["no_candidate_reviews"])
        self.assertEqual(path.read_bytes(), original)

    def test_one_need_polarity_correction_uses_shared_budget_and_keeps_original(self):
        def once(skill, context, value, count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["review_assessments"][0]["polarity"] = "positive"
            return value
        agent, transport = self.agent(once)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "need_extract", "product_compare", "concept_draft", "semantic_review"])
        self.assertEqual(result["model_calls"][0]["generated"]["data"]["review_assessments"][0]["polarity"], "positive")

    def test_early_and_late_errors_share_two_corrections(self):
        def two_errors(skill, context, value, count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["review_assessments"][0]["polarity"] = "positive"
            if skill == "concept_draft" and context["revision_count"] < 2:
                value["concept_assessments"][0]["duplication"] = "duplicate"
            return value
        agent, transport = self.agent(two_errors)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "need_extract", "product_compare", "concept_draft",
                          "concept_draft", "semantic_review"])

    def test_duplicate_gap_assessment_is_caught_before_concepts(self):
        def duplicate(skill, context, value, count):
            if skill == "product_compare":
                value["gap_assessments"].append(deepcopy(value["gap_assessments"][0]))
            return value
        agent, transport = self.agent(duplicate)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract"] + ["product_compare"] * 3)
        details = transport.posts[2]["context"]["feedback"][0]["details"]
        self.assertEqual(details["assessment_coverage"]["duplicate_ids"], [self.output["gaps"][0]["id"]])

    def test_uncertain_review_keeps_grounding_hold_and_semantic_review(self):
        def uncertain(skill, context, value, count):
            if skill == "need_extract":
                value["result"].update(needs=[], desired_outcomes=[], unresolved=["사용 조건 불명"])
                value["review_assessments"][0]["polarity"] = "uncertain"
                value.update(questions=["사용 조건을 확인할 원문이 있나요?"], hold_reasons=["사용 조건 불명"],
                             no_candidate_reasons=["확정된 불편 없음"])
            return value
        agent, transport = self.agent(uncertain)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])
        self.assertEqual(result["output"]["concepts"], [])
