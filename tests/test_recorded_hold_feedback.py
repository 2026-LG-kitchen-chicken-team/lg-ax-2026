"""Replay fixed8B failures; preserve refusal, original response and correction2."""
import json
import unittest
from copy import deepcopy

import test_planning_agent as fixtures


class RecordedHoldFeedbackTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def test_recorded_invalid_holds_report_values_without_clearing_them(self):
        for name in ("fridge-normal", "fridge-changed", "fridge-missing-manual"):
            with self.subTest(case=name):
                path = fixtures.ROOT / f"evals/core-manual-quality/20261006/r4/results/{name}.json"
                original = path.read_bytes()
                recorded = json.loads(original)
                self.payload = deepcopy(recorded["original_input"])
                declarations = [c["generated"]["data"] for c in recorded["model_calls"]]

                def replay(skill, context, value, count, responses=declarations):
                    self.assertEqual(skill, "need_extract")
                    return deepcopy(responses[context["revision_count"]])

                agent, transport = self.agent(replay)
                result = agent.run(self.payload)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["decision"], recorded["decision"])
                self.assertEqual(result["input"]["revision_count"], 2)
                self.assertEqual([p["skill"] for p in transport.posts], ["need_extract"] * 3)
                self.assertEqual([c["generated"]["data"] for c in result["model_calls"]], declarations)
                for index in (1, 2):
                    feedback = transport.posts[index]["context"]["feedback"][0]
                    previous = declarations[index - 1]
                    self.assertEqual(feedback["code"], "HOLD_WITHOUT_QUESTIONS")
                    self.assertEqual(feedback["details"]["unresolved"], previous["result"]["unresolved"])
                    self.assertEqual(feedback["details"]["questions"], previous["questions"])
                    self.assertEqual(feedback["details"]["hold_reasons"],
                                     previous["hold_reasons"] or previous["result"]["unresolved"])
                    self.assertIn("실제 누락 사실", feedback["message"])
                self.assertEqual(path.read_bytes(), original)

    def test_real_missing_fact_question_keeps_hold_without_revision(self):
        def missing_fact(skill, context, value, count):
            if skill == "product_compare":
                value["result"]["gaps"][0].update(support_status="insufficient_evidence",
                                                questions=["사용 조건 근거가 있나요?"])
                value["gap_assessments"][0].update(support_basis="unmentioned", resolution="unknown")
                value.update(questions=["추가 설명서가 있나요?"], hold_reasons=["문서 미언급"],
                             no_candidate_reasons=["지원 여부 미확인"])
            return value

        agent, transport = self.agent(missing_fact)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual(result["output"]["questions"], ["추가 설명서가 있나요?"])
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare", "no_candidate_review"])
