"""Follow original evidence edges and surface numerical claims for semantic review."""
import unittest
from copy import deepcopy

import test_planning_agent as fixtures
from lgax_core.concept_lineage import trace_concept_lineage


class ConceptLineageTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixtures.read("normal.input.json")
        self.output = fixtures.read("normal.fixture-output.json")

    def test_original_candidate_trace_binds_review_manual_and_requirements(self):
        original = deepcopy((self.payload, self.output))
        report = trace_concept_lineage(self.payload, self.output)
        self.assertFalse(report["violations"])
        candidate = report["candidates"][0]
        link = candidate["links"][0]
        self.assertEqual(link["need_id"], self.output["needs"][0]["id"])
        self.assertEqual(link["review_evidence_ids"], self.output["needs"][0]["evidence_ids"])
        self.assertTrue(link["manual_evidence_ids"])
        self.assertEqual(candidate["requirements"], self.output["concepts"][0]["requirements"])
        candidate["requirements"].clear()
        self.assertEqual((self.payload, self.output), original)

    def test_missing_resolved_or_uncertain_gap_cannot_support_candidate(self):
        for mutation, expected in (("missing", "CONCEPT_GAP_MISSING"),
                                   ("resolved", "CONCEPT_WITHOUT_CONFIRMED_GAP"),
                                   ("uncertain", "CONCEPT_WITHOUT_CONFIRMED_GAP"),
                                   ("citation", "CONCEPT_GROUNDING_MISSING")):
            with self.subTest(mutation=mutation):
                output = deepcopy(self.output)
                if mutation == "missing":
                    output["concepts"][0]["gap_ids"] = ["UNKNOWN-GAP"]
                elif mutation == "resolved":
                    output["gap_assessments"][0]["resolution"] = "resolved"
                    output["gaps"][0]["remaining_pain"] = ""
                elif mutation == "uncertain":
                    output["gap_assessments"][0]["support_basis"] = "unmentioned"
                    output["gaps"][0]["support_status"] = "insufficient_evidence"
                else:
                    output["concepts"][0]["evidence_ids"] = output["needs"][0]["evidence_ids"][:]
                self.assertIn(expected, [row["code"] for row in trace_concept_lineage(self.payload, output)["violations"]])

    def test_unknown_citation_duplicate_and_omitted_comparison_are_detected(self):
        self.output["concepts"][0]["evidence_ids"].append("UNKNOWN")
        self.output["concept_assessments"][0].update(duplication="duplicate", compared_feature_ids=[])
        codes = {row["code"] for row in trace_concept_lineage(self.payload, self.output)["violations"]}
        self.assertTrue({"MISSING_EVIDENCE", "DUPLICATE_CONCEPT", "DUPLICATION_COMPARISON_INCOMPLETE"} <= codes)

    def test_extra_evidence_from_other_model_cannot_enlarge_candidate_scope(self):
        extra = deepcopy(self.payload["sources"][0])
        extra.update(id="OTHER-MODEL-EVIDENCE", model_id="OTHER-MODEL")
        self.payload["sources"].append(extra)
        self.output["concepts"][0]["evidence_ids"].append(extra["id"])
        report = trace_concept_lineage(self.payload, self.output)
        self.assertIn("SOURCE_SCOPE_MISMATCH", [row["code"] for row in report["violations"]])
        self.assertFalse(report["candidates"][0]["valid"])

    def test_numeric_effect_and_design_target_both_go_to_semantic_review(self):
        self.output["concepts"][0]["differentiation"] = "청소 시간이 50% 줄어든다는 측정 완료 주장"
        self.output["concepts"][0]["requirements"] = ["후속 실험에서 20% 개선을 목표로 검증"]
        self.output["concept_assessments"][0]["reason"] = "실제 5분 절약이 입증됐다는 주장"
        mentions = trace_concept_lineage(self.payload, self.output)["candidates"][0]["numeric_mentions"]
        self.assertEqual({row["quote"] for row in mentions}, {"50%", "20%", "5분"})
        self.assertTrue(all(row["requires_semantic_review"] and not row["matching_evidence_ids"] for row in mentions))

    def test_zero_and_three_candidates_preserve_hold_and_maximum(self):
        output = deepcopy(self.output)
        output.update(concepts=[], concept_assessments=[], status="held",
                      hold_reasons=["근거 확인"], no_candidate_reasons=["근거 확인 전 보류"])
        report = trace_concept_lineage(self.payload, output)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["hold_reasons"], output["hold_reasons"])
        for index in range(2, 4):
            candidate = deepcopy(self.output["concepts"][0])
            candidate["id"] += str(index)
            self.output["concepts"].append(candidate)
            assessment = deepcopy(self.output["concept_assessments"][0])
            assessment["concept_id"] = candidate["id"]
            self.output["concept_assessments"].append(assessment)
        self.assertEqual(len(trace_concept_lineage(self.payload, self.output)["candidates"]), 3)
        self.payload["max_concepts"] = 1
        self.assertIn("CONCEPT_LIMIT", [row["code"] for row in trace_concept_lineage(self.payload, self.output)["violations"]])
