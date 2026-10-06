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
from lgax_core.semantic_review import review_semantics, schema_for_review, semantic_feedback
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[1]


def declaration(payload, output):
    return fixtures.semantic_for({"input_sha256": input_digest(payload), "output_sha256": input_digest(output),
                                  "request": payload["request"], "concepts": output["concepts"],
                                  "sources": payload["sources"]})


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixtures.read("normal.input.json")
        self.output = fixtures.read("normal.fixture-output.json")
        self.report = declaration(self.payload, self.output)

    def review(self):
        return review_semantics(self.payload, self.output, self.report)

    def difference_row(self):
        return next(row for row in self.report["quality_assessments"]
                    if row["criterion"] == "difference_from_current_features")

    def test_difference_requires_both_review_and_manual_for_supported_residual_pain(self):
        row = self.difference_row()
        citations = deepcopy(row["source_quotes"])
        for kept in ([], citations[:1], citations[1:]):
            with self.subTest(citations=kept):
                row["source_quotes"] = kept
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertEqual(caught.exception.details["reason"], "difference_requires_review_and_manual")
                self.assertEqual(caught.exception.details["gap_id"], self.output["gaps"][0]["id"])
        row["source_quotes"] = citations
        self.assertEqual(self.output["gaps"][0]["support_status"], "supported")
        self.assertEqual(self.output["gap_assessments"][0]["resolution"], "remaining")
        self.assertEqual(self.review()["action"], "accept")

    def test_other_model_version_or_source_kind_cannot_ground_difference(self):
        manual = self.payload["sources"][1]
        for field in ("model_id", "document_version", "source_kind"):
            with self.subTest(field=field):
                original = manual[field]
                manual[field] = "public" if field == "source_kind" else "other"
                self.report["input_sha256"] = input_digest(self.payload)
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertEqual(caught.exception.details["reason"], "difference_requires_review_and_manual")
                manual[field] = original

    def test_unrelated_manual_cannot_substitute_for_own_gap_evidence(self):
        extra = deepcopy(self.payload["sources"][1])
        extra["id"] = "UNRELATED-MANUAL"
        self.payload["sources"].append(extra)
        self.report["input_sha256"] = input_digest(self.payload)
        self.difference_row()["source_quotes"][1]["evidence_id"] = extra["id"]
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "difference_requires_review_and_manual")

    def test_review_from_another_need_cannot_ground_own_gap(self):
        review = deepcopy(self.payload["sources"][0])
        review["id"] = "OTHER-NEED-REVIEW"
        self.payload["sources"].append(review)
        self.output["gaps"][0]["evidence_ids"][0] = review["id"]
        self.report = declaration(self.payload, self.output)
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "difference_requires_review_and_manual")

    def test_each_linked_feature_requires_its_own_manual(self):
        manual = deepcopy(self.payload["sources"][1])
        manual["id"] = "SECOND-MANUAL"
        feature = deepcopy(self.payload["features"][0])
        feature.update(id="SECOND-FEATURE", evidence_ids=[manual["id"]])
        self.payload["sources"].append(manual)
        self.payload["features"].append(feature)
        self.output["gaps"][0]["feature_ids"].append(feature["id"])
        self.output["gaps"][0]["evidence_ids"].append(manual["id"])
        self.report["input_sha256"] = input_digest(self.payload)
        self.report["output_sha256"] = input_digest(self.output)
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "difference_requires_linked_feature_manual")
        self.assertEqual(caught.exception.details["feature_id"], feature["id"])
        self.difference_row()["source_quotes"].append({"evidence_id": manual["id"], "quote": manual["text"]})
        self.assertEqual(self.review()["action"], "accept")

    def test_each_gap_requires_its_own_pair_and_genuine_uncertainty_stays_held(self):
        second = deepcopy(self.output["gaps"][0])
        second.update(id="SECOND-GAP", evidence_ids=[])
        self.output["gaps"].append(second)
        self.output["concepts"][0]["gap_ids"].append(second["id"])
        self.report["output_sha256"] = input_digest(self.output)
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "difference_requires_review_and_manual")
        self.difference_row().update(verdict="uncertain", source_quotes=[], reason="새 기능의 원 근거가 부족하다")
        self.report["questions"] = ["해당 기능의 같은 모델·버전 설명서가 있나요?"]
        self.assertEqual(self.review()["action"], "hold")

    def test_complete_literal_report_and_adapter_schema_budget(self):
        schema = schema_for_review(self.payload, self.output)
        Draft202012Validator.check_schema(schema)
        self.assertLess(len(json.dumps(schema).encode()), 16384)
        self.assertEqual(self.review()["action"], "accept")

    def test_generation_quotes_are_original_choices_without_changing_replay_validation(self):
        schema = schema_for_review(self.payload, self.output, literal_choices=True)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.report)
        self.report["quality_assessments"][0]["candidate_quote"] += "."
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(self.report)))
        self.report = declaration(self.payload, self.output)
        self.report["quality_assessments"][0]["candidate_quote"] = self.output["concepts"][0]["title"][:2]
        self.assertFalse(list(Draft202012Validator(schema_for_review(self.payload, self.output)).iter_errors(self.report)))
        self.assertEqual(self.review()["action"], "accept")

    def test_generation_schema_cannot_replace_user_exclusions_with_feature_conditions(self):
        schema = schema_for_review(self.payload, self.output)
        self.report["exclusion_assessments"][0]["condition"] = "설명서의 사용 조건을 충족해야 함"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(self.report)))

    def test_live_assessment_reason_can_be_quoted_to_request_correction(self):
        folder = ROOT / "evals/pm-intake/20261006/core/originals"
        case = next(c for c in json.loads((folder / "blinded-review-fresh/review.json").read_text("utf-8"))["cases"]
                    if c["case_id"] == "HOLD-01")
        self.payload = case["request"]
        self.output = deepcopy(case["outputs"]["B"]["raw_output"])
        original = deepcopy(self.output)
        self.report = declaration(self.payload, self.output)
        row = next(r for r in self.report["quality_assessments"] if r["criterion"] == "unsupported_factual_claims")
        row.update(verdict="violation", candidate_quote=self.output["concept_assessments"][0]["reason"],
                   reason="청소 접근의 어려움만 있으며 물리적인 세정 불가능은 원문에서 입증되지 않았다",
                   source_quotes=[{"evidence_id": s["id"], "quote": s["text"]} for s in self.payload["sources"]])
        Draft202012Validator(schema_for_review(self.payload, self.output, literal_choices=True)).validate(self.report)
        for count, action in ((0, "revise"), (1, "revise"), (2, "unresolved")):
            self.payload["revision_count"] = count
            self.report["input_sha256"] = input_digest(self.payload)
            self.assertEqual(self.review()["action"], action)
            self.assertEqual(semantic_feedback(self.report)[0]["details"]["candidate_quote"],
                             self.output["concept_assessments"][0]["reason"])
        self.assertEqual(self.output, original)

    def test_assessment_quote_must_belong_to_its_own_candidate(self):
        second = deepcopy(self.output["concepts"][0])
        second["id"] = "SECOND"
        self.output["concepts"].append(second)
        first = self.output["concept_assessments"][0]
        self.output["concept_assessments"].append({**deepcopy(first), "concept_id": "SECOND",
                                                "reason": "두 번째 후보만의 별도 사실 단정"})
        self.report = declaration(self.payload, self.output)
        row = next(r for r in self.report["quality_assessments"]
                   if r["concept_id"] == self.output["concepts"][0]["id"])
        row["candidate_quote"] = self.output["concept_assessments"][-1]["reason"]
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "candidate_quote_not_literal")

    def test_assessment_quote_cannot_use_other_candidate_or_changed_output_hash(self):
        reason = self.output["concept_assessments"][0]["reason"]
        self.report["quality_assessments"][0]["candidate_quote"] = reason
        self.assertEqual(self.review()["action"], "accept")
        self.output["concept_assessments"][0]["reason"] += " 바뀐 판단 사유"
        with self.assertRaises(DomainError):
            self.review()

    def test_coverage_is_cartesian_for_multiple_candidates_conditions_not_just_first(self):
        second = deepcopy(self.output["concepts"][0])
        second["id"] = "SECOND"
        self.output["concepts"].append(second)
        self.payload["request"]["exclusions"].append("추가 수조를 설치하지 않는다")
        self.report = declaration(self.payload, self.output)
        self.report["exclusion_assessments"][-1]["verdict"] = "violation"
        self.assertEqual(self.review()["action"], "revise")
        self.assertEqual(semantic_feedback(self.report)[0]["details"]["concept_id"], "SECOND")

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

    def test_public_decision_uses_core001_shape_while_feedback_preserves_literal_rows(self):
        canonical = review_judgement(self.payload, self.output)
        self.report["exclusion_assessments"][0]["verdict"] = "violation"
        decision = self.review()
        self.assertEqual(set(decision), set(canonical))
        self.assertEqual(decision["violations"], [{"code": "EXCLUSION_VIOLATION", "stage": "concepts"}])
        self.assertEqual(semantic_feedback(self.report)[0]["details"], self.report["exclusion_assessments"][0])

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

    def test_missing_difference_evidence_never_exports_candidate_after_two_corrections(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                for row in value["quality_assessments"]:
                    if row["criterion"] == "difference_from_current_features":
                        row["source_quotes"] = []
            return value
        case, agent, _transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["errors"][-1]["details"]["reason"], "difference_requires_review_and_manual")
        self.assertTrue(result["correction_budget"]["closed"])

    def test_review_is_separate_model_call_with_raw_metadata_and_literal_matrix(self):
        case, agent, transport = self.fixture()
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(transport.posts[-1]["skill"], "semantic_review")
        record = result["model_calls"][-1]
        self.assertEqual(record["metadata"]["revision"], fixtures.DIGEST)
        self.assertEqual(record["request_context"]["request"], case.payload["request"])
        self.assertEqual(record["request_context"]["concept_assessments"], result["output"]["concept_assessments"])
        self.assertTrue(record["raw_response"])
        self.assertEqual(result["semantic_reviews"][0]["decision"]["action"], "accept")

    def test_violation_uses_revision_skill_and_then_rechecks(self):
        def alter(skill, context, value, _count):
            if skill == "semantic_review" and context["revision_count"] == 0:
                value["exclusion_assessments"][0]["verdict"] = "violation"
            if skill == "review_revision" and context["revision_count"] == 1:
                value["result"]["concepts"][0]["title"] = "조건을 재검토한 변경 후보"
            return value
        case, agent, transport = self.fixture(alter)
        original = deepcopy(case.payload)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare", "concept_draft", "semantic_review", "review_revision", "semantic_review"])
        feedback = json.loads(transport.posts[4]["context"]["previous"]["violations"][0])
        self.assertEqual(feedback["code"], "EXCLUSION_VIOLATION")
        self.assertEqual(feedback["details"],
                         result["semantic_reviews"][0]["report"]["exclusion_assessments"][0])
        self.assertEqual(result["output"]["concepts"][0]["title"], "조건을 재검토한 변경 후보")
        self.assertEqual(case.payload, original)

    def test_stage_retry_and_revision_skill_share_budget_and_last_semantic_review(self):
        def alter(skill, context, value, _count):
            if skill == "need_extract" and context["revision_count"] == 0:
                return "not JSON"
            if skill == "semantic_review" and context["revision_count"] == 1:
                value["exclusion_assessments"][0]["verdict"] = "violation"
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["original_input"], case.payload)
        self.assertEqual(result["correction_budget"]["attempts"], [
            {"operation": "stage_retry", "revision_count": 1},
            {"operation": "review_revision", "revision_count": 2}])
        self.assertEqual(result["revision_session"]["revision_count"], 2)
        self.assertEqual([p["skill"] for p in transport.posts], [
            "need_extract", "need_extract", "product_compare", "concept_draft",
            "semantic_review", "review_revision", "semantic_review"])
        self.assertEqual(transport.posts[-1]["context"]["revision_count"], 2)
        for review in result["semantic_reviews"]:
            self.assertEqual(review_semantics(review["reviewed_input"], review["reviewed_output"], review["report"]),
                             review["decision"])

    def test_failed_revision_completion_spends_attempt_and_reuses_same_session(self):
        def alter(skill, context, value, _count):
            if skill == "semantic_review" and context["revision_count"] == 0:
                value["exclusion_assessments"][0]["verdict"] = "violation"
            if skill == "review_revision" and context["revision_count"] == 1:
                return "{broken revision"
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["input"]["revision_count"], 2)
        audit = result["revision_session"]["audit"]
        self.assertEqual([row["revision_count"] for row in audit], [1, 2])
        self.assertEqual(audit[0]["raw_response"], "{broken revision")
        self.assertEqual(result["correction_budget"]["attempts"], [
            {"operation": "review_revision", "revision_count": 1},
            {"operation": "review_revision", "revision_count": 2}])
        self.assertEqual([p["skill"] for p in transport.posts][-3:],
                         ["review_revision", "review_revision", "semantic_review"])
        self.assertEqual(result["semantic_reviews"][-1]["decision"]["action"], "accept")

    def test_two_invalid_revision_completions_stop_without_old_candidate_success(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                value["exclusion_assessments"][0]["verdict"] = "violation"
            return "{broken revision" if skill == "review_revision" else value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertTrue(result["rejected_output"]["concepts"])
        self.assertIsNone(result["decision"])
        self.assertEqual(len(transport.posts), 6)
        self.assertEqual(len(result["revision_session"]["audit"]), 2)
        self.assertEqual(result["errors"][-1]["code"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["output"]["revision_count"], 2)
        self.assertEqual(result["output"]["input_sha256"], input_digest(result["input"]))

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

    def test_held_review_preserves_exact_input_output_hash_and_can_be_replayed(self):
        def alter(skill, _context, value, _count):
            if skill == "semantic_review":
                value["exclusion_assessments"][0]["verdict"] = "uncertain"
                value["questions"] = ["장치와 모드의 범위를 확인할 수 있나요?"]
            return value
        case, agent, _transport = self.fixture(alter)
        result = agent.run(case.payload)
        review = result["semantic_reviews"][0]
        self.assertEqual(review["report"]["input_sha256"], input_digest(review["reviewed_input"]))
        self.assertEqual(review["report"]["output_sha256"], input_digest(review["reviewed_output"]))
        self.assertEqual(result["rejected_output"], review["reviewed_output"])
        self.assertEqual(review_semantics(review["reviewed_input"], review["reviewed_output"], review["report"]),
                         review["decision"])
        self.assertNotEqual(result["output"]["questions"], review["reviewed_output"]["questions"])

    def test_retry_then_review_error_does_not_save_an_old_correction_decision(self):
        for code, status in (("BACKEND_CONNECTION", "failed"), ("INVALID_ARGUMENT", "held")):
            with self.subTest(code=code):
                def alter(skill, context, value, _count, code=code):
                    if skill == "semantic_review":
                        if context["revision_count"] == 0:
                            value["exclusion_assessments"][0]["verdict"] = "violation"
                        else:
                            raise DomainError(code, "review stopped", {})
                    return value
                case, agent, _transport = self.fixture(alter)
                result = agent.run(case.payload)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["input"]["revision_count"], 1)
                self.assertIsNone(result["decision"])
                self.assertEqual(result["output"]["concepts"], [])
                self.assertEqual(result["errors"][-1]["code"], code)

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
        self.assertEqual(result["decision"]["next_revision_count"], 2)
        self.assertIsNone(result["decision"]["rerun_from"])
        self.assertEqual(set(result["decision"]["violations"][0]), {"code", "stage"})

    def test_generation_schema_failure_has_canonical_terminal_decision_and_detailed_retry(self):
        def alter(skill, _context, value, _count):
            if skill == "need_extract":
                return "not JSON"
            return value
        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["decision"]["next_revision_count"], 2)
        self.assertIsNone(result["decision"]["rerun_from"])
        self.assertEqual(set(result["decision"]["violations"][0]), {"code", "stage"})
        self.assertTrue(transport.posts[1]["context"]["feedback"][0]["details"])

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
