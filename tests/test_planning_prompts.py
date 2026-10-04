"""Stage-specific prompt boundaries and source identity constraints, with fixtures."""
import json
import unittest
from copy import deepcopy

import test_planning_agent as fixtures
from jsonschema import Draft202012Validator
from lgax_core.planning_agent import generation_schema


class PlanningPromptTests(unittest.TestCase):
    def fixture(self, alter=None):
        case = fixtures.PlanningAgentTests("test_three_stages_original_data_and_sources_are_preserved")
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent, transport = case.agent(alter)
        return case, agent, transport

    def test_need_schema_accepts_review_polarity_but_not_a_manual_identity(self):
        case, _agent, _transport = self.fixture()
        review = case.payload["sources"][0]["id"]
        manual = case.payload["sources"][1]["id"]
        schema = generation_schema("need_extract", review_evidence_ids=[review])
        declared = fixtures.stages_for(case.output)["need_extract"]
        validator = Draft202012Validator(schema)
        for polarity in ("complaint", "positive", "conflicting", "irrelevant", "uncertain"):
            changed = deepcopy(declared)
            changed["review_assessments"][0]["polarity"] = polarity
            self.assertFalse(list(validator.iter_errors(changed)), polarity)
        changed = deepcopy(declared)
        changed["review_assessments"][0]["evidence_id"] = manual
        self.assertTrue(list(validator.iter_errors(changed)))
        changed["review_assessments"] = []
        self.assertTrue(list(validator.iter_errors(changed)))

    def test_manual_as_review_is_rejected_at_generation_before_later_stages(self):
        def add_manual_once(skill, context, value, _count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["review_assessments"].append({
                    "evidence_id": context["manual_evidence_ids"][0],
                    "polarity": "positive", "reason": "설명서를 리뷰로 착각한 응답"})
            return value
        case, agent, transport = self.fixture(add_manual_once)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual([post["skill"] for post in transport.posts],
                         ["need_extract", "need_extract", "product_compare", "concept_draft"])
        self.assertEqual(result["input"]["revision_count"], 1)
        first = result["model_calls"][0]
        self.assertEqual(first["error"]["details"]["reason"], "schema_mismatch")
        self.assertEqual(len(json.loads(first["raw_response"])["review_assessments"]), 2)
        self.assertEqual(len(result["output"]["review_assessments"]), 1)

    def test_review_and_manual_ids_and_upstream_judgements_reach_correct_stage(self):
        case, agent, transport = self.fixture()
        original = deepcopy(case.payload)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        first, compare, concept = [post["context"] for post in transport.posts]
        for context in (first, compare, concept):
            self.assertEqual(context["review_evidence_ids"], [case.payload["sources"][0]["id"]])
            self.assertEqual(context["manual_evidence_ids"], [case.payload["sources"][1]["id"]])
            self.assertEqual(context["sources"], original["sources"])
        self.assertEqual(first["upstream_assessments"], {})
        need_declaration = result["model_calls"][0]["generated"]["data"]
        self.assertEqual(compare["upstream_assessments"], {
            "review_assessments": need_declaration["review_assessments"],
            "desired_outcomes": need_declaration["result"]["desired_outcomes"]})
        self.assertEqual(concept["upstream_assessments"]["gap_assessments"],
                         result["model_calls"][1]["generated"]["data"]["gap_assessments"])
        self.assertNotIn("metadata", concept["upstream_assessments"])
        self.assertEqual(case.payload, original)

    def test_prompt_distinguishes_present_pain_from_unverified_future_design(self):
        case, agent, _transport = self.fixture()
        result = agent.run(case.payload)
        need = result["model_calls"][0]["prompt"].split("DATA_JSON:\n", 1)[0]
        self.assertIn("설명서는 리뷰가 아니므로 polarity", need)
        self.assertIn("명확한 사용 불편의 추출을 보류하지", need)
        self.assertIn("향후 제품의 제조 가능성", need)
        self.assertNotIn("resolution=remaining", need)
        self.assertNotIn(case.payload["sources"][0]["text"], need)
        compare = result["model_calls"][1]["prompt"].split("DATA_JSON:\n", 1)[0]
        self.assertIn("desired_outcomes", compare)
        self.assertIn("resolution=remaining", compare)
        self.assertIn("unmentioned/insufficient_evidence", compare)
        concept = result["model_calls"][2]["prompt"].split("DATA_JSON:\n", 1)[0]
        self.assertIn("assumptions/requirements", concept)
        self.assertIn("정상적으로 적절한 신규 후보가 없으면", concept)

    def test_concept_prompt_allows_new_hypotheses_without_fabricating_existing_facts(self):
        case, agent, _transport = self.fixture()
        result = agent.run(case.payload)
        concept = result["model_calls"][2]["prompt"].split("DATA_JSON:\n", 1)[0]
        self.assertIn("현재 설명서에 없는 형태·기능·서비스를 기획 가설로 제안할 수", concept)
        self.assertIn("기존 기능의 사실 근거", concept)
        self.assertIn("제조·성능·인증·효과를 이미 검증한 제품처럼 주장하지", concept)
        self.assertIn("적절한 신규 후보가 없으면 concepts는 비우고", concept)
        self.assertNotIn(case.output["concepts"][0]["title"], concept)
        self.assertNotIn("자료에 없는 근거를 만들지", concept)

    def test_generated_hypothesis_stays_needs_review_with_unchanged_source_facts(self):
        def proposed(skill, _context, value, _count):
            if skill == "concept_draft":
                candidate = value["result"]["concepts"][0]
                candidate.update(title="후속 검증이 필요한 사용 흐름 개선안", kind="service",
                                 status="needs_review", assumptions=["제조와 실제 사용 효과는 미검증"],
                                 requirements=["현재 사용 부담을 줄이는지 후속 검증"])
            return value
        case, agent, transport = self.fixture(proposed)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(len(transport.posts), 3)
        candidate = result["output"]["concepts"][0]
        self.assertEqual(candidate["status"], "needs_review")
        self.assertEqual(candidate["assumptions"], ["제조와 실제 사용 효과는 미검증"])
        self.assertEqual(result["original_input"]["sources"], case.payload["sources"])
        self.assertEqual(candidate["evidence_ids"], case.output["concepts"][0]["evidence_ids"])
        self.assertEqual(result["input"]["revision_count"], 0)

    def test_upstream_context_is_reset_on_each_run(self):
        case, agent, transport = self.fixture()
        self.assertEqual(agent.run(case.payload)["status"], "completed")
        again = agent.run(case.payload)
        self.assertEqual(again["status"], "completed")
        self.assertEqual(transport.posts[3]["context"]["upstream_assessments"], {})
        self.assertEqual(len(again["model_calls"]), 3)


if __name__ == "__main__":
    unittest.main()
