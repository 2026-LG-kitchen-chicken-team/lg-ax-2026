"""Support and discomfort are independent for each canonical product input."""
import unittest

import test_planning_agent as fixtures
from lgax_core.residual_matrix import build_residual_matrix


class ResidualMatrixTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixtures.read("normal.input.json")
        self.output = fixtures.read("normal.fixture-output.json")

    def test_three_products_keep_supported_function_and_remaining_burden(self):
        for product, pain in (("fridge", "먼저 식품을 이동하는 부담"), ("dishwasher", "식기 조합 배치 부담"),
                              ("microwave", "용기별 조건 확인 부담")):
            with self.subTest(product=product):
                self.payload["product"]["product_group"] = product
                self.payload["request"]["product_group"] = product
                self.output["gaps"][0]["remaining_pain"] = pain
                row = build_residual_matrix(self.payload, self.output)["rows"][0]
                self.assertEqual(row["support_status"], "supported")
                self.assertEqual((row["resolution"], row["remaining_pain"]), ("remaining", pain))
                self.assertTrue(row["candidate_eligible"])

    def test_resolved_declaration_needs_empty_remaining_pain(self):
        self.output["gap_assessments"][0]["resolution"] = "resolved"
        report = build_residual_matrix(self.payload, self.output)
        self.assertEqual(report["violations"][0]["code"], "RESOLUTION_PAIN_MISMATCH")
        self.assertFalse(report["rows"][0]["candidate_eligible"])
        self.output["gaps"][0]["remaining_pain"] = ""
        report = build_residual_matrix(self.payload, self.output)
        self.assertFalse(report["violations"])
        self.assertFalse(report["rows"][0]["candidate_eligible"])

    def test_unmentioned_conflicting_and_unknown_need_questions_and_hold(self):
        for basis in ("unmentioned", "conflicting"):
            self.output["gap_assessments"][0].update(support_basis=basis, resolution="unknown")
            self.output["gaps"][0]["support_status"] = "insufficient_evidence"
            report = build_residual_matrix(self.payload, self.output)
            self.assertIn("SUPPORT_UNKNOWN", [row["code"] for row in report["violations"]])
            self.output.update(status="held", hold_reasons=["지원 범위를 확인해야 함"])
            self.output["gaps"][0]["questions"] = ["지원 조건의 원문이 있나요?"]
            report = build_residual_matrix(self.payload, self.output)
            self.assertFalse(report["violations"])
            self.assertTrue(report["rows"][0]["requires_confirmation"])
            self.assertFalse(report["rows"][0]["candidate_eligible"])
            self.output.update(status="completed", hold_reasons=[])
            self.output["gaps"][0]["questions"] = []
