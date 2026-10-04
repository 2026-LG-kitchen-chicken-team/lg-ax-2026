"""Normal no-candidate termination differs from insufficient-evidence holds."""
import unittest
from copy import deepcopy

import test_planning_agent as fixtures
from lgax_core.judgement_contract import review_judgement
from lgax_core.skill_runner import SkillRuntime


class NoCandidateTerminationTests(unittest.TestCase):
    def fixture(self, alter=None):
        case = fixtures.PlanningAgentTests("test_three_stages_original_data_and_sources_are_preserved")
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent, transport = case.agent(alter)
        return case, agent, transport

    def test_already_resolved_gaps_complete_without_concept_model_or_retry(self):
        def resolved(skill, _context, value, _count):
            if skill == "product_compare":
                value["result"]["gaps"][0]["remaining_pain"] = ""
                value["gap_assessments"][0]["resolution"] = "resolved"
            if skill == "concept_draft":
                self.fail("A resolved complaint must not trigger new concept generation")
            return value
        case, agent, transport = self.fixture(resolved)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual([row["skill"] for row in transport.posts], ["need_extract", "product_compare"])
        self.assertEqual(result["output"]["concepts"], [])
        self.assertTrue(result["output"]["no_candidate_reasons"])
        self.assertEqual(result["output"]["hold_reasons"], [])
        self.assertEqual(result["output"]["unresolved"], [])
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual(review_judgement(result["input"], result["output"])["action"], "accept")
        self.assertIn("skip_resolved", [row["operation"] for row in result["trace"]])

    def test_no_suitable_candidate_with_reason_completes_and_preserves_grounding(self):
        def exclude(skill, _context, value, _count):
            if skill == "concept_draft":
                value["result"]["concepts"] = []
                value["result"]["hold_reasons"] = []
                value["concept_assessments"] = []
                value["no_candidate_reasons"] = ["제외 조건을 만족하는 적절한 신규 후보가 없습니다."]
            return value
        case, agent, transport = self.fixture(exclude)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(len(transport.posts), 3)
        self.assertEqual(result["output"]["needs"], case.output["needs"])
        self.assertEqual(result["output"]["gaps"], case.output["gaps"])
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["output"]["hold_reasons"], [])
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual(review_judgement(result["input"], result["output"])["action"], "accept")

    def test_no_candidate_without_any_reason_still_fails_after_two_revisions(self):
        def silent(skill, _context, value, _count):
            if skill == "concept_draft":
                value["result"].update(concepts=[], hold_reasons=[])
                value.update(concept_assessments=[], no_candidate_reasons=[])
            return value
        case, agent, transport = self.fixture(silent)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(transport.posts), 5)
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["decision"]["action"], "unresolved")

    def test_missing_support_remains_held_and_does_not_generate_concepts(self):
        def missing(skill, _context, value, _count):
            if skill == "product_compare":
                value["result"]["gaps"][0].update(support_status="insufficient_evidence",
                                                    questions=["추가 명세가 있나요?"])
                value["gap_assessments"][0].update(support_basis="unmentioned", resolution="unknown")
                value.update(questions=["추가 명세가 있나요?"], hold_reasons=["지원 근거 부족"],
                             no_candidate_reasons=["추가 근거 확인 전 보류"])
            return value
        case, agent, transport = self.fixture(missing)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(len(transport.posts), 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertTrue(result["output"]["hold_reasons"])
        self.assertEqual(result["input"]["revision_count"], 0)

    def test_conflicting_duplicate_reason_representations_are_rejected(self):
        def conflict(skill, _context, value, _count):
            if skill == "concept_draft":
                value["result"].update(concepts=[], hold_reasons=[], no_candidate_reasons=["A"])
                value.update(concept_assessments=[], no_candidate_reasons=["B"])
            return value
        case, agent, transport = self.fixture(conflict)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(transport.posts), 5)
        self.assertEqual(result["input"]["revision_count"], 2)

    def test_direct_skill_accepts_normal_reason_but_rejects_silent_or_blank_reason(self):
        case, agent, _transport = self.fixture()
        payload = {"model_id": case.payload["product"]["model_id"],
                   "document_version": case.payload["product"]["document_version"],
                   "needs": deepcopy(case.output["needs"]), "gaps": deepcopy(case.output["gaps"]),
                   "constraints": [], "max_concepts": 3}
        for reasons, expected in [(["제외 조건 때문에 신규 후보 없음"], True), ([], False), (["   "], False)]:
            with self.subTest(reasons=reasons):
                runtime = SkillRuntime(agent.store)
                runtime.register_handler("concept_draft", lambda _p, _s, r=reasons: {
                    "concepts": [], "hold_reasons": [], "no_candidate_reasons": r},
                    backend_id="fixture:no-candidate", execution_kind="fixture")
                result = runtime.execute("concept_draft", payload)
                self.assertEqual(result["ok"], expected, result)
                if expected:
                    self.assertEqual(result["data"]["result"]["no_candidate_reasons"], reasons)
                    self.assertTrue(result["data"]["sources"])
                else:
                    self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
