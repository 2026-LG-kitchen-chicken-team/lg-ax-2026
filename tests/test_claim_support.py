"""Public development counterexamples and field protocol; no live quality grade."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_planning_agent as fixtures
from jsonschema import Draft202012Validator
from lgax_core import claim_support
from lgax_core.concept_lineage import build_quality_context
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest
from lgax_core.model_client import ModelConfig, StructuredModelClient
from lgax_core.semantic_review import (
    ACTIVE_INSTRUCTIONS,
    review_semantics,
    schema_for_review,
    semantic_feedback,
    semantic_grounding_requirements,
    semantic_model_context,
)
from lgax_core.source_boundary import SourceBoundary
from test_r5_semantic_prompt import DIGEST, MODEL, PreparationCapture, PreparedWithoutGeneration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/pm-prototype/20261007/r6-core/normal-1f25-upstream-literal-counterexample.json"
PIN = "3ca94273f3829df13899a677608c92467305d6f47afbe80da3fde4fa8021a00b"


class ClaimSupportTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), PIN)
        self.case = json.loads(self.raw)
        self.payload = deepcopy(self.case["payload"])
        self.output = deepcopy(self.case["output"])
        self.context = {"request": self.payload["request"], "product": self.payload["product"],
                        "sources": self.payload["sources"], "features": self.payload["features"],
                        **{key: deepcopy(self.output[key]) for key in (
                            "needs", "desired_outcomes", "gaps", "review_assessments", "gap_assessments",
                            "concepts", "concept_assessments")},
                        "revision_count": self.payload["revision_count"],
                        "input_sha256": input_digest(self.payload), "output_sha256": input_digest(self.output),
                        "skill_input": {"constraints": self.payload["request"]["exclusions"]}, "feedback": [],
                        "quality_context": build_quality_context(self.payload, self.output),
                        "semantic_grounding_requirements": semantic_grounding_requirements(self.payload, self.output),
                        "upstream_review_required": True, "claim_review_required": True}
        self.report = fixtures.semantic_for(self.context)

    def tearDown(self):
        self.assertEqual(FIXTURE.read_bytes(), self.raw)

    def review(self):
        return review_semantics(self.payload, self.output, self.report,
                                require_upstream=True, require_claims=True)

    def row(self, kind, identifier):
        if kind == "concept":
            return next(row for row in self.report["quality_assessments"]
                        if row["concept_id"] == identifier and row["criterion"] == "unsupported_factual_claims")
        return next(row for row in self.report["upstream_assessments"]
                    if (row["entity_kind"], row["entity_id"]) == (kind, identifier))

    def check(self, kind, identifier, field):
        return next(check for check in self.row(kind, identifier)["claims"] if check["field"] == field)

    def test_original_all_consistent_report_cannot_skip_actual_claim_fields(self):
        self.assertEqual(len(self.case["original_report"]["upstream_assessments"]), 18)
        with self.assertRaises(DomainError) as caught:
            review_semantics(self.payload, self.output, self.case["original_report"],
                             require_upstream=True, require_claims=True)
        self.assertEqual(caught.exception.details["reason"], "semantic_review_schema")
        self.assertEqual(caught.exception.details["stage"], "concepts")
        # Earlier declaration replay has no new required claim fields.
        old_schema = schema_for_review(self.payload, self.output, include_upstream=True)
        Draft202012Validator(old_schema).validate(self.case["original_report"])

    def test_title_only_missing_duplicate_or_wrong_field_cannot_certify_candidate_reason(self):
        original = deepcopy(self.report)
        for mutation, expected in (
            (lambda row: row["claims"].pop(), "semantic_review_schema"),
            (lambda row: row["claims"][1].update(field="title"), "semantic_review_schema"),
            (lambda row: row["claims"][1].update(field="differentiation"), "claim_field_coverage"),
        ):
            with self.subTest(expected=expected):
                self.report = deepcopy(original)
                row = self.row("concept", "CONCEPT-003")
                self.assertEqual(row["candidate_quote"], self.output["concepts"][2]["title"])
                mutation(row)
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertEqual(caught.exception.details["reason"], expected)
                self.assertEqual(caught.exception.details["stage"], "concepts")

    def test_observation_cannot_be_certified_by_manual_or_product_fact_by_review(self):
        original = deepcopy(self.report)
        for kind, identifier, field, basis, source in (
            ("need", "NEED-007", "pain", "review_observation", "MANUAL-001"),
            ("concept", "CONCEPT-003", "reason", "manual_fact", "REVIEW-EVIDENCE-005"),
        ):
            with self.subTest(kind=kind):
                self.report = deepcopy(original)
                self.check(kind, identifier, field).update(basis=basis, source_ids=[source])
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertIn(caught.exception.details["reason"],
                              ("claim_evidence_role_mismatch", "claim_source_not_linked_and_quoted"))
                self.assertEqual(caught.exception.details["stage"], "needs" if kind == "need" else "concepts")

    def test_unquoted_or_unrelated_sources_and_nonempty_empty_claim_are_rejected(self):
        original = deepcopy(self.report)
        for mutation, reason in (
            (lambda row: row["source_quotes"].clear(), "claim_source_not_linked_and_quoted"),
            (lambda row: row["claims"][1].update(source_ids=["REVIEW-EVIDENCE-001"]),
             "claim_source_not_linked_and_quoted"),
            (lambda row: row["claims"][1].update(basis="empty", source_ids=[]), "claim_nonempty_field"),
        ):
            with self.subTest(reason=reason):
                self.report = deepcopy(original)
                mutation(self.row("concept", "CONCEPT-003"))
                with self.assertRaises(DomainError) as caught:
                    self.review()
                self.assertEqual(caught.exception.details["reason"], reason)

    def test_single_review_role_cannot_include_manual_support_as_an_extra_source(self):
        need = self.output["needs"][0]
        need["evidence_ids"].append("MANUAL-001")
        check = self.check("need", need["id"], "pain")
        check.update(basis="review_observation", source_ids=["REVIEW-EVIDENCE-001", "MANUAL-001"])
        with self.assertRaises(DomainError) as caught:
            claim_support.validate(self.payload, self.output, self.row("need", need["id"]), "need", need["id"])
        self.assertEqual(caught.exception.details["reason"], "claim_evidence_role_mismatch")
        self.assertEqual(caught.exception.details["actual_source_types"], ["manual", "review"])

    def test_four_public_errors_cannot_be_hidden_by_parent_consistent_or_satisfied(self):
        # Human-labelled development counterexamples; the validator does not
        # infer these labels from Korean words or claim real model improvement.
        for kind, identifier, field, scope, verdict, reason in (
            ("gap", "GAP-004", "reason", "mismatch", "supported", "문서 존재는 발견성 해결 근거가 아니다."),
            ("gap", "GAP-005", "reason", "mismatch", "supported", "선반 문서와 바구니 경험은 대상이 다르다."),
            ("need", "NEED-007", "pain", "aligned", "violation", "욕구만 있는 원문에 이동 제약 경험을 추가했다."),
            ("concept", "CONCEPT-002", "reason", "mismatch", "supported", "사용자 공간 부족은 제품 공간 부재를 입증하지 않는다."),
        ):
            self.check(kind, identifier, field).update(scope=scope, verdict=verdict, reason=reason)
        self.assertTrue(all(row["verdict"] == "consistent" for row in self.report["upstream_assessments"]))
        self.assertTrue(all(row["verdict"] == "satisfied" for row in self.report["quality_assessments"]))
        decision = self.review()
        self.assertEqual((decision["action"], decision["rerun_from"]), ("revise", "needs"))
        claims = [row for row in semantic_feedback(self.report) if row["code"].startswith("CLAIM_")]
        self.assertEqual(len(claims), 4)
        self.assertEqual({row["stage"] for row in claims}, {"needs", "compare", "concepts"})
        self.assertTrue(all(row["details"]["field"] in ("pain", "reason") for row in claims))
        self.payload["revision_count"] = 2
        self.report["input_sha256"] = input_digest(self.payload)
        self.assertEqual((self.review()["action"], self.review()["next_revision_count"]), ("unresolved", 2))

    def test_real_uncertainty_keeps_question_and_resolved_empty_field_is_explicit(self):
        empty = self.check("gap", "GAP-004", "remaining_pain")
        self.assertEqual((empty["basis"], empty["source_ids"]), ("empty", []))
        self.check("concept", "CONCEPT-002", "reason").update(
            verdict="uncertain", scope="unconfirmed", source_ids=[], reason="새 주장에 필요한 제품 원문을 확인할 수 없다.")
        with self.assertRaises(DomainError) as caught:
            self.review()
        self.assertEqual(caught.exception.details["reason"], "uncertain_requires_question")
        self.report["questions"] = ["해당 주장 자체를 입증할 같은 제품의 원문이 있나요?"]
        self.assertEqual(self.review()["action"], "hold")

    def test_direct_review_observation_and_manual_fact_keep_distinct_support_roles(self):
        # Test-owned positive declarations copy the actual source literals. This
        # tests role/coverage, not a semantic grade of the recorded model output.
        sources = {source["id"]: source for source in self.payload["sources"]}
        need = self.output["needs"][0]
        review_id = "REVIEW-EVIDENCE-001"
        need.update(pain=sources[review_id]["text"], situation=sources[review_id]["text"],
                    evidence_ids=[review_id])
        row = self.row("need", need["id"])
        for check in row["claims"]:
            check.update(basis="review_observation", source_ids=[review_id])
        claim_support.validate(self.payload, self.output, row, "need", need["id"])
        gap = self.output["gaps"][0]
        gap.update(remaining_pain="", evidence_ids=["MANUAL-001"])
        assessment = next(item for item in self.output["gap_assessments"] if item["gap_id"] == gap["id"])
        assessment["reason"] = sources["MANUAL-001"]["text"]
        row = self.row("gap", gap["id"])
        self.check("gap", gap["id"], "remaining_pain").update(basis="empty", source_ids=[])
        self.check("gap", gap["id"], "reason").update(basis="manual_fact", source_ids=["MANUAL-001"])
        claim_support.validate(self.payload, self.output, row, "gap", gap["id"])
        # A manual may establish a feature fact, never an observed user need.
        need["evidence_ids"].append("MANUAL-001")
        self.check("need", need["id"], "pain").update(source_ids=["MANUAL-001"])
        with self.assertRaises(DomainError) as caught:
            claim_support.validate(self.payload, self.output, self.row("need", need["id"]), "need", need["id"])
        self.assertEqual(caught.exception.details["reason"], "claim_evidence_role_mismatch")

    def test_active_pipeline_mock_protocol_preserves_field_coverage_and_budget(self):
        helper = fixtures.PlanningAgentTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        agent, _transport = helper.agent()
        result = agent.run(helper.payload)
        self.assertEqual(result["status"], "completed", result)
        report = result["semantic_reviews"][0]["report"]
        self.assertTrue(all(len(row["claims"]) == 2 for row in report["upstream_assessments"]))
        self.assertEqual(result["correction_budget"]["max_revisions"], 2)
        self.assertTrue(result["model_calls"][-1]["request_context"]["claim_review_required"])

    def test_wrong_role_feedback_reruns_original_need_stage_with_shared_two_revision_budget(self):
        helper = fixtures.PlanningAgentTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)

        def wrong_role(skill, _context, value, _count):
            if skill == "semantic_review":
                row = next(item for item in value["upstream_assessments"] if item["entity_kind"] == "need")
                row["claims"][0].update(basis="manual_fact")
            return value

        agent, transport = helper.agent(wrong_role)
        result = agent.run(helper.payload)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["input"]["revision_count"], 2)
        revision_calls = [post for post in transport.posts if post["skill"] == "review_revision"]
        self.assertEqual(len(revision_calls), 2)
        for post in revision_calls:
            feedback = json.loads(post["context"]["previous"]["violations"][0])
            self.assertEqual(feedback["stage"], "needs")
            self.assertEqual(feedback["details"]["reason"], "claim_evidence_role_mismatch")
            self.assertEqual(feedback["details"]["field"], "pain")
        self.assertEqual(result["correction_budget"]["max_revisions"], 2)

    def test_actual9_need9_gap3_concept_native_request_fits_unchanged_caps(self):
        projected = semantic_model_context(self.context)
        schema = schema_for_review(self.payload, self.output, literal_choices=True,
                                   include_upstream=True, include_claims=True)
        Draft202012Validator(schema).validate(self.report)
        wire = json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertLessEqual(len(wire), 16384)
        adapter = PreparationCapture(ModelConfig("http://127.0.0.1:11434", MODEL, DIGEST,
                                                 max_output_tokens=8192, context_tokens=16384))
        self.addCleanup(adapter.close)
        client = StructuredModelClient(adapter)
        policy = SourceBoundary(self.payload, allowed_tools=("get_evidence", "list_products")).messages()[0]["content"]
        prompt = policy + "\n" + ACTIVE_INSTRUCTIONS + json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
        with self.assertRaises(PreparedWithoutGeneration):
            client.generate(prompt, schema, MODEL)
        formatted, submitted = adapter.prepared
        self.assertEqual(submitted, schema)
        self.assertLessEqual(len(formatted), 24000)
        self.assertLessEqual(len(formatted.encode("utf-8")), 45000)
        print(json.dumps({"claim_active_native_schema_bytes": len(wire), "formatted_prompt_chars": len(formatted),
                          "formatted_prompt_utf8_bytes": len(formatted.encode("utf-8")), "model_calls": 0}))


if __name__ == "__main__":
    unittest.main()
