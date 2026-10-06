"""Synthetic reuse regressions through MockTransport; no live model claims."""
import unittest
from copy import deepcopy

import httpx
import test_planning_agent as fixtures
from lgax_core.judgement_contract import input_digest
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore


class PlanningReuseTests(unittest.TestCase):
    def test_failed_changed_then_held_requests_are_isolated(self):
        for hold_at in ("need_extract", "semantic_review"):
            with self.subTest(hold_at=hold_at):
                self.check_flow(hold_at)

    def check_flow(self, hold_at):
        payload = fixtures.read("normal.input.json")
        original = deepcopy(payload)
        changed_task = "식품을 덜 옮기는 부분 청소 방식을 검토한다."
        held_task = "청소 방식 판단에 필요한 추가 근거를 확인한다."
        question = "기존 기능인지 새 장치인지 확인할 설명서 근거가 있나요?"

        def alter(skill, context, value, _count):
            task = context["request"]["improvement_task"]
            if task == original["request"]["improvement_task"]:
                if skill == "concept_draft" and context["revision_count"] == 0:
                    return '{"result":'  # Actually parsed and rejected by the client/Skill.
                if skill == "semantic_review":
                    value["exclusion_assessments"][0]["verdict"] = "violation"
            elif task == held_task and skill == hold_at:
                if skill == "need_extract":
                    value["result"].update(needs=[], desired_outcomes=[], unresolved=["불편 근거 부족"])
                    value["review_assessments"][0]["polarity"] = "uncertain"
                    value.update(questions=[question], hold_reasons=["불편 근거 부족"],
                                 no_candidate_reasons=["불편 근거 부족"])
                else:
                    value["exclusion_assessments"][0].update(
                        verdict="uncertain", reason="현재 설명서로 제외 조건 충족 여부를 확인할 수 없다")
                    value["questions"] = [question]
            return value

        transport = fixtures.Transport(fixtures.stages_for(
            fixtures.read("normal.fixture-output.json")), alter)
        adapter = OllamaAdapter(ModelConfig("http://127.0.0.1:18864", fixtures.MODEL,
                                            fixtures.DIGEST, max_output_tokens=2048,
                                            context_tokens=8192),
                                transport=httpx.MockTransport(transport))
        with StructuredModelClient(adapter) as client:
            agent = PlanningAgent(client, DemoStore(fixtures.dataset_for(payload)), execution_kind="fixture")
            first = agent.run(payload)
            self.assertEqual(payload, original)
            self.assertEqual(first["status"], "failed")
            self.assertEqual(first["decision"]["action"], "unresolved")
            self.assertEqual(first["decision"]["next_revision_count"], 2)
            self.assertIsNone(first["decision"]["rerun_from"])
            self.assertEqual(first["input"]["revision_count"], 2)
            self.assertEqual(first["output"]["concepts"], [])
            self.assertTrue(first["rejected_output"]["concepts"])
            self.assertEqual([c["skill_id"] for c in first["model_calls"]], [
                "need_extract", "product_compare", "concept_draft", "concept_draft",
                "semantic_review", "review_revision", "semantic_review"])
            self.assertEqual([c["revision_count"] for c in first["model_calls"]], [0, 0, 0, 1, 1, 2, 2])
            self.assertEqual(first["model_calls"][2]["raw_response"], '{"result":')
            self.assertEqual(first["model_calls"][2]["error"]["code"], "VALIDATION_FAILED")
            self.assertEqual(len(first["semantic_reviews"]), 2)
            self.assertEqual(sum(e["operation"] == "revise" for e in first["trace"]), 1)
            self.assertEqual(sum(e["operation"] == "review_revision" for e in first["trace"]), 1)
            self.assertEqual(first["correction_budget"]["attempts"], [
                {"operation": "stage_retry", "revision_count": 1},
                {"operation": "review_revision", "revision_count": 2}])
            self.assertTrue(first["correction_budget"]["closed"])
            self.assertEqual(len(first["revision_session"]["audit"]), 1)
            frozen_first = deepcopy(first)

            # Reuse the caller's mutable input and the exact same agent/client.
            payload["request"].update(improvement_task=changed_task, exclusions=["자동 세척 장치 제안"])
            second_original = deepcopy(payload)
            second = agent.run(payload)
            frozen_second = deepcopy(second)
            self.assertEqual(second["status"], "completed")
            self.assertEqual(second["decision"]["action"], "accept")
            self.assertTrue(second["output"]["concepts"])
            self.assertEqual(second["errors"], [])
            self.assertEqual(len(second["semantic_reviews"]), 1)
            self.assertEqual(first, frozen_first)
            self.assertNotEqual(input_digest(original), input_digest(second_original))

            payload["request"]["improvement_task"] = held_task
            third_original = deepcopy(payload)
            third = agent.run(payload)
            self.assertEqual(third["status"], "held")
            self.assertEqual(third["decision"]["action"], "hold")
            self.assertEqual(third["output"]["concepts"], [])
            self.assertEqual(third["output"]["concept_assessments"], [])
            self.assertEqual(third["output"]["questions"], [question])
            self.assertTrue(third["output"]["hold_reasons"])
            self.assertTrue(third["output"]["no_candidate_reasons"])
            self.assertEqual(third["errors"], [])
            self.assertEqual(len(third["semantic_reviews"]), int(hold_at == "semantic_review"))
            self.assertEqual(len(third["no_candidate_reviews"]), int(hold_at == "need_extract"))
            if hold_at == "need_extract":
                self.assertEqual(third["no_candidate_reviews"][0]["decision"]["action"], "hold")
            self.assertEqual(first, frozen_first)
            self.assertEqual(second, frozen_second)

        for result, snapshot in ((first, original), (second, second_original), (third, third_original)):
            self.assertEqual(result["execution_kind"], "fixture")
            self.assertEqual(result["original_input"], snapshot)
            self.assertEqual(result["trace"][0]["inputs"], snapshot["request"])
            for call in result["model_calls"]:
                self.assertEqual(call["execution_kind"], "fixture")
                self.assertEqual(call["model_digest"], fixtures.DIGEST)
                request_context = call["request_context"]
                if call["skill_id"] == "review_revision":
                    request_context = request_context["context"]
                self.assertEqual(request_context["request"], snapshot["request"])
        for result, snapshot in ((second, second_original), (third, third_original)):
            expected_skills = (["need_extract", "no_candidate_review"]
                               if result is third and hold_at == "need_extract"
                               else ["need_extract", "product_compare", "concept_draft", "semantic_review"])
            self.assertEqual([c["skill_id"] for c in result["model_calls"]], expected_skills)
            self.assertEqual(result["input"]["revision_count"], 0)
            self.assertEqual(result["output"]["input_sha256"], input_digest(snapshot))
            for call in result["model_calls"]:
                self.assertEqual(call["revision_count"], 0)
                self.assertEqual(call["input_sha256"], input_digest(snapshot))
                self.assertEqual(call["request_context"]["feedback"], [])
            self.assertFalse(any(e["operation"] == "revise" for e in result["trace"]))
        self.assertEqual(len(transport.posts), sum(len(r["model_calls"]) for r in (first, second, third)))

        # Check nested identity, including nonempty review records, before mutation.
        def mutable_ids(value):
            if isinstance(value, dict):
                return {id(value)}.union(*(mutable_ids(v) for v in value.values()))
            if isinstance(value, list):
                return {id(value)}.union(*(mutable_ids(v) for v in value))
            return set()

        for left, right in ((first, second), (first, third), (second, third)):
            self.assertFalse(mutable_ids(left) & mutable_ids(right))
        for result in (first, second, third):
            self.assertFalse(mutable_ids(result) & mutable_ids(payload))

        payload["sources"][0]["text"] = "호출자가 실행 뒤 바꾼 원문"
        payload["request"]["exclusions"].append("실행 뒤 추가한 조건")
        for key in ("original_input", "input", "output"):
            third[key].clear()
        for key in ("trace", "model_calls", "semantic_reviews"):
            third[key].append({"later_mutation": True})
        self.assertEqual(first, frozen_first)
        self.assertEqual(second, frozen_second)
        second["semantic_reviews"][0]["report"]["questions"].append("후속 결과 수정")
        second["model_calls"][0]["request_context"]["request"]["exclusions"].clear()
        second["trace"][0]["inputs"].clear()
        self.assertEqual(first, frozen_first)


if __name__ == "__main__":
    unittest.main()
