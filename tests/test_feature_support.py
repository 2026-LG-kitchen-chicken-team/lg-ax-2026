"""Declarations and citation states, not a substitute for live semantic grading."""
import unittest
from copy import deepcopy

import test_planning_agent as fixtures
from lgax_core.feature_support import build_feature_support


class FeatureSupportTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixtures.read("normal.input.json")
        self.output = fixtures.read("normal.fixture-output.json")

    def test_all_four_bases_preserve_conditions_and_never_rewrite_exclusions(self):
        original = deepcopy(self.payload)
        for basis, status in (("explicit_supported", "supported"), ("explicit_unsupported", "unsupported"),
                              ("unmentioned", "insufficient_evidence"), ("conflicting", "insufficient_evidence")):
            with self.subTest(basis=basis):
                self.output["gap_assessments"][0]["support_basis"] = basis
                self.output["gaps"][0]["support_status"] = status
                report = build_feature_support(self.payload, self.output)
                self.assertFalse(report["violations"])
                row = report["rows"][0]
                self.assertEqual((row["support_basis"], row["support_status"]), (basis, status))
                self.assertEqual(row["features"][0]["conditions"], self.payload["features"][0]["conditions"])
                self.assertFalse(report["semantic_accuracy_verified"])
        self.assertEqual(self.payload, original)

    def test_missing_manual_scope_or_link_never_becomes_evidence_for_non_support(self):
        for mutation, expected in (("missing", "MISSING_EVIDENCE"), ("version", "SOURCE_SCOPE_MISMATCH"),
                                   ("kind", "SOURCE_SCOPE_MISMATCH"), ("link", "FEATURE_MANUAL_MISSING")):
            with self.subTest(mutation=mutation):
                payload = deepcopy(self.payload)
                manual = next(row for row in payload["sources"] if row["source_type"] == "manual")
                if mutation == "missing":
                    payload["sources"].remove(manual)
                elif mutation == "version":
                    manual["document_version"] = "another-version"
                elif mutation == "kind":
                    manual["source_kind"] = "public"
                else:
                    manual["feature_ids"] = []
                report = build_feature_support(payload, self.output)
                self.assertIn(expected, [row["code"] for row in report["violations"]])
                self.assertEqual(report["rows"][0]["support_status"], "supported")
                self.assertFalse(report["rows"][0]["valid"])

    def test_returned_sources_conditions_and_questions_do_not_alias_input(self):
        before = deepcopy((self.payload, self.output))
        report = build_feature_support(self.payload, self.output)
        report["rows"][0]["features"][0]["conditions"].append("external change")
        report["rows"][0]["evidence_ids"].clear()
        self.assertEqual((self.payload, self.output), before)

    def test_silent_manual_cannot_validate_explicit_unsupported_without_manual(self):
        self.output["gaps"][0]["evidence_ids"] = self.output["needs"][0]["evidence_ids"][:]
        self.output["gap_assessments"][0]["support_basis"] = "explicit_unsupported"
        self.output["gaps"][0]["support_status"] = "unsupported"
        report = build_feature_support(self.payload, self.output)
        self.assertIn("UNSUPPORTED_WITHOUT_MANUAL", [row["code"] for row in report["violations"]])
