"""Real DATA Skill schema with CORE's frozen metadata policy; fixture only."""
import unittest
from copy import deepcopy

from tests import test_planning_agent as fixtures


class Data190Core198IntegrationTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def uncertain(self, value, polarity="uncertain", keep_need=False):
        if not keep_need:
            value["result"].update(needs=[], desired_outcomes=[], unresolved=[])
        value["review_assessments"][0].update(polarity=polarity, reason="Original missing use context")
        value.update(questions=[], hold_reasons=[], no_candidate_reasons=[])
        value["result"].update(
            review_assessments=deepcopy(value["review_assessments"]), questions=[],
            uncertainty_assessments=[{"evidence_id": self.payload["sources"][0]["id"],
                "reason": "ORIGINAL_HOLD_REASON", "missing_information": ["ORIGINAL_MISSING_CONDITION"],
                "questions": ["ORIGINAL_QUESTION"]}])
        return value

    def test_actual_schema_uncertain_metadata_keeps_final_hold_and_raw_reply(self):
        originals = []

        def alter(skill, context, value, count):
            if skill == "need_extract":
                self.uncertain(value)
                originals.append(deepcopy(value))
            return value

        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["output"]["questions"], ["ORIGINAL_QUESTION"])
        self.assertEqual(result["output"]["hold_reasons"], ["ORIGINAL_HOLD_REASON"])
        self.assertEqual(result["output"]["unresolved"], ["ORIGINAL_MISSING_CONDITION"])
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["model_calls"][0]["generated"]["data"], originals[0])
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])

    def test_actual_schema_conflicting_need_keeps_core_question_hold_policy(self):
        def alter(skill, context, value, count):
            if skill == "need_extract":
                self.uncertain(value, "conflicting", keep_need=True)
            return value

        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertTrue(result["output"]["needs"])
        self.assertEqual(result["output"]["review_assessments"][0]["polarity"], "conflicting")
        self.assertEqual(result["output"]["questions"], ["ORIGINAL_QUESTION"])
        self.assertEqual(result["output"]["hold_reasons"], ["ORIGINAL_HOLD_REASON"])
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])

    def test_actual_schema_inconsistent_polarity_cannot_reach_accept(self):
        def alter(skill, context, value, count):
            if skill == "need_extract":
                self.uncertain(value)
                value["review_assessments"][0].update(polarity="positive", reason="No verified pain")
            return value

        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract"] * 3)
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertTrue(result["correction_budget"]["closed"])
        details = transport.posts[1]["context"]["feedback"][0]["details"]
        self.assertEqual(details["conflicting_paths"], ["review_assessments", "result/review_assessments"])
        self.assertEqual(result["model_calls"][0]["generated"]["data"]["result"]
                         ["review_assessments"][0]["polarity"], "uncertain")

    def test_positive_and_irrelevant_review_still_cannot_be_confirmed_need(self):
        for polarity in ("positive", "irrelevant"):
            with self.subTest(polarity=polarity):
                def alter(skill, context, value, count, polarity=polarity):
                    if skill == "need_extract":
                        value["review_assessments"][0].update(polarity=polarity, reason="No verified complaint")
                        value["result"].update(review_assessments=deepcopy(value["review_assessments"]),
                                               uncertainty_assessments=[], questions=[])
                    return value

                agent, _transport = self.agent(alter)
                result = agent.run(self.payload)
                self.assertEqual(result["status"], "failed")
                self.assertNotEqual(result["decision"]["action"], "accept")


if __name__ == "__main__":
    unittest.main()
