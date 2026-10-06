"""Full Agent regressions for optional DATA metadata, with no model/network calls."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_planning_agent as fixtures
from lgax_core.judgement_contract import schema_for as judgement_schema
from lgax_core.skill_runner import schema_for as original_skill_schema


def optional_metadata_schema(skill_id, direction):
    schema = original_skill_schema(skill_id, direction)
    if skill_id == "need_extract" and direction == "output":
        props = schema["oneOf"][0]["properties"]["data"]["properties"]["result"]["properties"]
        contract = judgement_schema("output")["properties"]
        props["review_assessments"] = deepcopy(contract["review_assessments"])
        props["questions"] = deepcopy(contract["questions"])
        props["uncertainty_assessments"] = {
            "type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["evidence_id", "reason", "missing_information", "questions"],
            "properties": {"evidence_id": {"type": "string", "minLength": 1},
                           "reason": {"type": "string", "minLength": 1},
                           "missing_information": {"type": "array", "minItems": 1,
                                                   "items": {"type": "string", "minLength": 1}},
                           "questions": deepcopy(contract["questions"])}}}
    return schema


class StageMetadataTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def run_optional(self, alter):
        with patch("lgax_core.planning_agent.skill_schema", optional_metadata_schema), \
             patch("lgax_core.skill_runner.schema_for", optional_metadata_schema):
            agent, transport = self.agent(alter)
            return agent.run(self.payload), transport

    def test_conflicting_duplicate_polarity_never_reaches_accept(self):
        def alter(skill, context, value, count):
            if skill == "need_extract":
                value["result"]["review_assessments"] = deepcopy(value["review_assessments"])
                value["result"]["review_assessments"][0]["polarity"] = "positive"
            return value
        result, transport = self.run_optional(alter)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract"] * 3)
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertTrue(result["correction_budget"]["closed"])
        details = transport.posts[1]["context"]["feedback"][0]["details"]
        self.assertEqual(details["conflicting_paths"], ["review_assessments", "result/review_assessments"])
        self.assertEqual(result["model_calls"][0]["generated"]["data"]["result"]
                         ["review_assessments"][0]["polarity"], "positive")

    def test_uncertainty_metadata_reaches_shared_hold_without_invented_fields(self):
        originals = []
        def alter(skill, context, value, count):
            if skill == "need_extract":
                value["result"].update(needs=[], desired_outcomes=[], unresolved=[])
                value["review_assessments"][0].update(polarity="uncertain", reason="Missing context")
                value.update(questions=[], hold_reasons=[], no_candidate_reasons=[])
                value["result"].update(review_assessments=deepcopy(value["review_assessments"]), questions=[],
                    uncertainty_assessments=[{"evidence_id": self.payload["sources"][0]["id"],
                        "reason": "NESTED_HOLD_REASON", "missing_information": ["NESTED_MISSING_FIELD"],
                        "questions": ["NESTED_QUESTION"]}])
                originals.append(deepcopy(value))
            return value
        result, transport = self.run_optional(alter)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])
        self.assertEqual(result["output"]["questions"], ["NESTED_QUESTION"])
        self.assertEqual(result["output"]["hold_reasons"], ["NESTED_HOLD_REASON"])
        self.assertEqual(result["output"]["unresolved"], ["NESTED_MISSING_FIELD"])
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["model_calls"][0]["generated"]["data"], originals[0])

    def test_pm_original_positive_uncertain_counterexample_is_rejected(self):
        import json
        path = fixtures.ROOT / "evals/core-manual-quality/20261006/metadata-consistency/pm-original-blocker.json"
        original = path.read_bytes()
        case = json.loads(original)["finding"]["fixture"]
        def alter(skill, context, value, count):
            if skill == "need_extract":
                value["result"] = deepcopy(case["new_nested_need_result"])
                value["review_assessments"] = deepcopy(case["legacy_top_level_review_assessments"])
                value.update(questions=[], hold_reasons=[], no_candidate_reasons=["No verified pain"])
            return value
        result, transport = self.run_optional(alter)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract"] * 3)
        self.assertEqual(transport.posts[1]["context"]["feedback"][0]["details"]["conflicting_paths"],
                         ["review_assessments", "result/review_assessments"])
        self.assertEqual(result["model_calls"][0]["generated"]["data"]["result"], case["new_nested_need_result"])
        self.assertEqual(path.read_bytes(), original)

    def test_matching_duplicate_metadata_keeps_existing_candidate_pipeline(self):
        def alter(skill, context, value, count):
            if skill == "need_extract":
                value["result"].update(review_assessments=deepcopy(value["review_assessments"]),
                                       questions=deepcopy(value["questions"]))
            return value
        result, _transport = self.run_optional(alter)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["decision"]["action"], "accept")
        self.assertEqual(result["input"]["revision_count"], 0)

    def test_conflicting_duplicate_question_uses_shared_retry(self):
        def alter(skill, context, value, count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["result"]["questions"] = ["Nested-only question"]
            return value
        result, transport = self.run_optional(alter)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual(transport.posts[1]["context"]["feedback"][0]["details"]["conflicting_paths"],
                         ["questions", "result/questions"])

    def test_conflicting_need_keeps_existing_question_hold_policy(self):
        def alter(skill, context, value, count):
            if skill == "need_extract":
                value["review_assessments"][0].update(polarity="conflicting", reason="Conflicting use context")
                value.update(questions=[], hold_reasons=[], no_candidate_reasons=[])
                value["result"].update(review_assessments=deepcopy(value["review_assessments"]), questions=[],
                    uncertainty_assessments=[{"evidence_id": self.payload["sources"][0]["id"],
                        "reason": "CONFLICT_CONTEXT", "missing_information": ["CONFLICT_MISSING_CONDITION"],
                        "questions": ["CONFLICT_QUESTION"]}])
            return value
        result, transport = self.run_optional(alter)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["output"]["review_assessments"][0]["polarity"], "conflicting")
        self.assertEqual(result["output"]["questions"], ["CONFLICT_QUESTION"])
        self.assertEqual(result["output"]["hold_reasons"], ["CONFLICT_CONTEXT"])
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])


if __name__ == "__main__":
    unittest.main()
