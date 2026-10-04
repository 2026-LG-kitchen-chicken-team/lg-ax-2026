"""Literal review coverage and safe pipeline termination, without live LLM grading."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_planning_agent as fixtures
from jsonschema import Draft202012Validator
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.judgement_contract import schema_for as judgement_schema
from lgax_core.semantic_review import review_semantics, schema_for_review
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[1]


def declaration(payload, output):
    return fixtures.semantic_for({"input_sha256": input_digest(payload), "output_sha256": input_digest(output),
                                  "request": payload["request"], "concepts": output["concepts"]})


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixtures.read("normal.input.json")
        self.output = fixtures.read("normal.fixture-output.json")
        self.report = declaration(self.payload, self.output)

    def review(self):
        return review_semantics(self.payload, self.output, self.report)

    def test_complete_literal_report_and_adapter_schema_budget(self):
        schema = schema_for_review(self.payload, self.output)
        Draft202012Validator.check_schema(schema)
        self.assertLess(len(json.dumps(schema).encode()), 16384)
        self.assertEqual(self.review()["action"], "accept")

    def test_coverage_is_cartesian_for_multiple_candidates_conditions_not_just_first(self):
        second = deepcopy(self.output["concepts"][0])
        second["id"] = "SECOND"
        self.output["concepts"].append(second)
        self.payload["request"]["exclusions"].append("추가 수조를 설치하지 않는다")
        self.report = declaration(self.payload, self.output)
        self.report["exclusion_assessments"][-1]["verdict"] = "violation"
        self.assertEqual(self.review()["action"], "revise")
        self.assertEqual(self.review()["violations"][0]["details"]["concept_id"], "SECOND")

    def test_replayed_wrong_hash_missing_duplicate_and_changed_literal_rows_are_rejected(self):
        original = deepcopy(self.report)
        mutations = (
            lambda r: r.update(input_sha256="b" * 64),
            lambda r: r.update(output_sha256="b" * 64),
            lambda r: r["exclusion_assessments"].pop(),
            lambda r: r["quality_assessments"].pop(),
            lambda r: r["quality_assessments"].__setitem__(1, deepcopy(r["quality_assessments"][0])),
            lambda r: r["exclusion_assessments"][0].update(condition="위반하기 쉽게 바꾼 조건"),
            lambda r: r["exclusion_assessments"][0].update(candidate_quote="원 후보에 없는 설명"),
            lambda r: r["exclusion_assessments"][0].update(candidate_quote=""),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.report = deepcopy(original)
                mutation(self.report)
                with self.assertRaises(DomainError):
                    self.review()

    def test_duplicate_exclusion_pair_cannot_hide_a_missing_pair(self):
        self.payload["request"]["exclusions"].append("새 제외 조건")
        self.report = declaration(self.payload, self.output)
        self.report["exclusion_assessments"][1] = deepcopy(self.report["exclusion_assessments"][0])
        with self.assertRaises(DomainError):
            self.review()

    def test_source_quote_must_exist_in_current_scoped_original(self):
        self.report["quality_assessments"][0]["source_quotes"] = [
            {"evidence_id": self.payload["sources"][1]["id"], "quote": "지원되지 않는 기능을 꾸민 문장"}]
        with self.assertRaises(DomainError):
            self.review()

    def test_uncertainty_requires_question_then_holds_even_when_budget_exhausted(self):
        self.payload["revision_count"] = 2
        self.report = declaration(self.payload, self.output)
        self.report["exclusion_assessments"][0]["verdict"] = "uncertain"
        with self.assertRaises(DomainError):
            self.review()
        self.report["questions"] = ["기존 모드인지 새 장치인지 확인할 수 있나요?"]
        self.assertEqual(self.review()["action"], "hold")
        self.assertEqual(self.review()["next_revision_count"], 2)

    def test_quality_missing_description_is_a_violation_and_cannot_complete_at_two(self):
        for count, action in ((0, "revise"), (1, "revise"), (2, "unresolved")):
            self.payload["revision_count"] = count
            self.report = declaration(self.payload, self.output)
            self.report["quality_assessments"][0].update(verdict="violation", candidate_quote="",
                                                        reason="작동 방식 설명이 없다")
            self.assertEqual(self.review()["action"], action)

    def test_question_with_all_satisfied_rows_still_has_a_hold_reason(self):
        self.report["questions"] = ["제외 조건의 예외 범위를 확인할 수 있나요?"]
        result = self.review()
        self.assertEqual(result["action"], "hold")
        self.assertEqual(result["violations"][0]["code"], "SEMANTIC_QUESTION")

    def test_no_exclusions_still_checks_candidate_quality_without_placeholder_rows(self):
        self.payload["request"]["exclusions"] = []
        self.report = declaration(self.payload, self.output)
        self.assertEqual(self.report["exclusion_assessments"], [])
        self.assertEqual(self.review()["action"], "accept")

    def test_pm_original_contract_acceptance_replayed_and_independent_uncertain_declaration_blocks_it(self):
        raw = json.loads((ROOT / "evals/pm-integration/20261005/workspace-live.json").read_text("utf-8"))
        actual = raw["second"]["output"]["planning_execution"]
        self.assertEqual(actual["execution_kind"], "live_model")
        self.assertEqual(review_judgement(actual["input"], actual["output"])["action"], "accept")
        payload, output = deepcopy(actual["input"]), deepcopy(actual["output"])
        report = declaration(payload, output)
        row = next(r for r in report["exclusion_assessments"]
                   if r["concept_id"] == "CON-002" and r["condition"] == "자동 세척 장치 제안")
        row.update(verdict="uncertain", candidate_quote="자동 세척 모드 추가",
                   reason="기존 소프트웨어 모드인지 새 장치인지 현재 문서로 확인되지 않는다")
        report["questions"] = ["기존 기능으로 실행되는 모드라는 현재 모델 설명서 근거가 있나요?"]
        self.assertEqual(review_semantics(payload, output, report)["action"], "hold")
        # Recorded live generation is original; the new reviewer is an authored fixture.
        self.assertEqual(raw["second"]["output"]["planning_execution"], actual)

    def test_independent_condition_inputs_have_matching_store_and_no_development_sources(self):
        folder = ROOT / "evals/core-exclusions/independent"
        manifest = json.loads((folder / "cases.json").read_text("utf-8"))
        self.assertEqual({c["type"] for c in manifest["cases"]}, {
            "normal", "changed_exclusion", "negation", "synonym", "ambiguous_mode", "conflicting_conditions"})
        old_sources = [s for f in (ROOT / "evals/core-contract").glob("*/*.input.json")
                       for s in json.loads(f.read_text("utf-8"))["sources"]]
        independent_sources = []
        for case in manifest["cases"]:
            payload = json.loads((folder / case["input"]).read_text("utf-8"))
            dataset = json.loads((folder / case["dataset"]).read_text("utf-8"))
            with self.subTest(case=case["case_id"]):
                Draft202012Validator(judgement_schema("input")).validate(payload)
                store = DemoStore(dataset)
                self.assertEqual(store.bootstrap()["data"]["manifest"]["version"], payload["request"]["dataset_version"])
                self.assertEqual(store.bootstrap()["data"]["products"], [payload["product"]])
                self.assertEqual(store.bootstrap()["data"]["features"], payload["features"])
                for source in payload["sources"]:
                    self.assertEqual(store.get_evidence(source["id"])["data"]["evidence"], source)
                    self.assertNotIn(source["id"], {s["id"] for s in old_sources + independent_sources})
                    self.assertNotIn(source["text"], {s["text"] for s in old_sources + independent_sources})
                    independent_sources.append(source)
        before = json.loads((folder / "changed_exclusion.before.input.json").read_text("utf-8"))
        after = json.loads((folder / "changed_exclusion.input.json").read_text("utf-8"))
        self.assertNotEqual(before["request"]["exclusions"], after["request"]["exclusions"])
        before["request"]["exclusions"] = after["request"]["exclusions"]
        self.assertEqual(before, after)


class SemanticPipelineTests(unittest.TestCase):
    def fixture(self, alter=None):
        case = fixtures.PlanningAgentTests("test_three_stages_original_data_and_sources_are_preserved")
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent, transport = case.agent(alter)
        return case, agent, transport

    def test_review_is_separate_model_call_with_raw_metadata_and_literal_matrix(self):
        case, agent, transport = self.fixture()
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(transport.posts[-1]["skill"], "semantic_review")
        record = result["model_calls"][-1]
        self.assertEqual(record["metadata"]["revision"], fixtures.DIGEST)
        self.assertEqual(record["request_context"]["request"], case.payload["request"])
        self.assertTrue(record["raw_response"])
        self.assertEqual(result["semantic_reviews"][0]["decision"]["action"], "accept")

    def test_violation_feedback_revises_only_concepts_and_then_rechecks(self):
        def alter(skill, context, value, _count):
            if skill == "semantic_review" and context["revision_count"] == 0:
                value["exclusion_assessments"][0]["verdict"] = "violation"
            if skill == "concept_draft" and context["revision_count"] == 1:
                value["result"]["concepts"][0]["title"] = "조건을 재검토한 변경 후보"
            return value
        case, agent, transport = self.fixture(alter)
        original = deepcopy(case.payload)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare", "concept_draft", "semantic_review", "concept_draft", "semantic_review"])
        self.assertEqual(transport.posts[4]["context"]["feedback"][0]["code"], "EXCLUSION_VIOLATION")
        self.assertEqual(case.payload, original)

    def test_persistent_violation_clears_candidates_after_two_shared_revisions(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                value["exclusion_assessments"][0]["verdict"] = "violation"
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertTrue(result["rejected_output"]["concepts"])
        self.assertEqual(len(transport.posts), 8)
        self.assertEqual(len(result["semantic_reviews"]), 3)

    def test_ambiguous_device_or_mode_holds_with_question_and_no_new_attempt(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                value["exclusion_assessments"][0]["verdict"] = "uncertain"
                value["questions"] = ["새 장치인지 기존 기능인지 확인할 근거가 있나요?"]
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["input"]["revision_count"], 0)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["output"]["questions"], ["새 장치인지 기존 기능인지 확인할 근거가 있나요?"])
        self.assertTrue(result["output"]["hold_reasons"])
        self.assertEqual(len(transport.posts), 4)

    def test_bad_review_matrix_or_json_cannot_fall_back_to_contract_accept(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                value["exclusion_assessments"] = []
            return value
        case, agent, _transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertIn("INVALID_SEMANTIC_REVIEW", result["output"]["unresolved"])

    def test_review_backend_failure_cannot_export_unreviewed_candidates(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                raise DomainError("BACKEND_CONNECTION", "review backend unavailable", {})
            return value
        case, agent, _transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["output"]["status"], "failed")
        self.assertEqual(result["output"]["concepts"], [])
        self.assertTrue(result["rejected_output"]["concepts"])
        self.assertEqual(result["input"]["revision_count"], 0)

    def test_review_input_limit_holds_with_reason_question_and_no_candidates(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                raise DomainError("INVALID_ARGUMENT", "review prompt limit", {})
            return value
        case, agent, _transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["output"]["hold_reasons"], ["review prompt limit"])
        self.assertTrue(result["output"]["questions"])

    def test_contract_and_semantic_errors_share_the_same_two_round_budget(self):
        def alter(skill, context, value, _count):
            if skill == "concept_draft" and context["revision_count"] == 0:
                value["concept_assessments"][0]["duplication"] = "duplicate"
            if skill == "semantic_review":
                value["exclusion_assessments"][0]["verdict"] = "violation"
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(len(transport.posts), 7)
        self.assertEqual(result["output"]["concepts"], [])


if __name__ == "__main__":
    unittest.main()
