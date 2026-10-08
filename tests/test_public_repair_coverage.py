"""Summary accounting reuse on retained real sources; no model quality grading.

The existing normal-r2 snapshot retains its reported mistakes. Added summary
rows and patches are marked protocol-only, never new customer observations.
"""
import json
import unittest
from copy import deepcopy
from hashlib import sha256

from lgax_api.research_planning import public_research_brief
from lgax_core.public_planning import PublicPlanner, is_customer_source, summary_reference_coverage
from test_public_repair import MANUAL, PACK, REVIEW, observed_draft, request


class SummaryCoverageReuseTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        self.previous = observed_draft(self.bundle)
        groups = {}
        for source in self.bundle["sources"]:
            if is_customer_source(source):
                groups.setdefault(source.get("duplicate_group") or source["source_id"], source["source_id"])
        self.customer_ids = set(groups.values())
        self.previous["summaries"]["positive"] = [{"text": "TEST ONLY: reference accounting", "source_ids": [REVIEW]}]
        self.previous["summaries"]["mixed"] = deepcopy(self.previous["summaries"]["positive"])

    def add_coverage(self, denominator=None):
        processed = {REVIEW} if denominator is None else denominator
        self.previous["runtime"]["processed_source_ids"] = sorted(processed)
        self.previous["runtime"]["summary_reference_coverage"] = summary_reference_coverage(
            self.previous["summaries"], self.customer_ids, processed)

    def test_successful_field_repair_preserves_original_discovery_counts_and_snapshot(self):
        self.add_coverage()
        before = deepcopy(self.previous)
        calls = []

        def patch(prompt, schema):
            calls.append(prompt)
            return {"patch": {"existing_response": "TEST ONLY: transport patch"}}

        result = PublicPlanner(patch).repair(self.bundle, self.previous, [request()])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["runtime"]["summary_reference_coverage"], before["runtime"]["summary_reference_coverage"])
        self.assertEqual(result["runtime"]["summary_reference_coverage_inheritance"], "preserved")
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "accepted")
        self.assertEqual(result["summaries"], before["summaries"])
        self.assertEqual(result["source_facts"], before["source_facts"])
        self.assertEqual(result["previous_brief_id"], before["brief_id"])
        self.assertEqual(self.previous, before)
        result["runtime"]["summary_reference_coverage"]["covered_source_ids"].clear()
        self.assertEqual(self.previous, before)  # No alias back into retained evidence.

    def test_failed_field_repair_does_not_reset_summary_denominator(self):
        self.add_coverage()
        before = deepcopy(self.previous)
        result = PublicPlanner(lambda prompt, schema: None).repair(self.bundle, self.previous, [request()])
        self.assertEqual(result["runtime"]["summary_reference_coverage"], before["runtime"]["summary_reference_coverage"])
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "failed")
        self.assertEqual(result["comparisons"], before["comparisons"])
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 1)
        self.assertEqual(self.previous, before)

    def test_same_summary_reuse_never_resets_shared_two_repair_budget(self):
        self.add_coverage()
        original_coverage = deepcopy(self.previous["runtime"]["summary_reference_coverage"])
        calls = []

        def patch(prompt, schema):
            calls.append(prompt)
            return {"patch": {"existing_response": "TEST ONLY: transport patch"}}

        planner = PublicPlanner(patch)
        result = self.previous
        for _ in range(3):
            result = planner.repair(self.bundle, result, [request()])
            self.assertEqual(result["runtime"]["summary_reference_coverage"], original_coverage)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 2)
        self.assertTrue(result["runtime"]["correction_budget"]["closed"])

    def test_missing_legacy_coverage_is_not_inferred_or_injected_by_caller(self):
        forged = {"summary_reference_coverage": {"coverage_ratio": 1, "classification_approved": True},
                  "summary_reference_coverage_inheritance": "preserved", "processed_source_ids": [REVIEW]}
        result = PublicPlanner(lambda prompt, schema: None, runtime_metadata=forged).repair(
            self.bundle, self.previous, [request()])
        self.assertNotIn("summary_reference_coverage", result["runtime"])
        self.assertNotIn("summary_reference_coverage_inheritance", result["runtime"])
        self.assertNotIn("processed_source_ids", result["runtime"])
        self.assertEqual(result["summaries"], self.previous["summaries"])

    def test_wrong_count_source_or_approval_is_not_inherited_or_reclassified(self):
        self.add_coverage()
        original = deepcopy(self.previous)
        for field, value in (("covered_customer_source_count", 999), ("denominator_source_ids", ["unknown"]),
                             ("classification_approved", True), ("coverage_ratio", "1.0")):
            previous = deepcopy(original)
            previous["runtime"]["summary_reference_coverage"][field] = value
            before = deepcopy(previous)
            with self.subTest(field=field):
                result = PublicPlanner(lambda prompt, schema: None).repair(self.bundle, previous, [request()])
                self.assertNotIn("summary_reference_coverage", result["runtime"])
                self.assertEqual(result["runtime"]["summary_reference_coverage_inheritance"], "invalid_previous_metadata")
                self.assertEqual(result["summaries"], previous["summaries"])
                self.assertEqual(previous, before)

    def test_valid_zero_denominator_stays_null_and_is_distinct_from_missing_metadata(self):
        self.add_coverage(set())
        result = PublicPlanner(lambda prompt, schema: None).repair(self.bundle, self.previous, [request()])
        coverage = result["runtime"]["summary_reference_coverage"]
        self.assertEqual(coverage["denominator_customer_source_count"], 0)
        self.assertIsNone(coverage["coverage_ratio"])
        self.assertEqual(result["runtime"]["summary_reference_coverage_inheritance"], "preserved")
        self.assertFalse(coverage["classification_approved"])
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])
        public = public_research_brief(result, sha256(PACK.read_bytes()).hexdigest(), self.bundle)
        self.assertEqual(public["runtime"]["summary_reference_coverage_state"], "provided")
        self.assertEqual(public["runtime"]["summary_reference_coverage"], coverage)

    def test_public_repair_projection_preserves_discovery_counts_and_separate_repair_sources(self):
        other_ids = sorted(self.customer_ids - {REVIEW})[:2]
        self.assertEqual(len(other_ids), 2)
        self.previous["summaries"]["negative"] = [
            {"text": "TEST ONLY: reference accounting", "source_ids": [other_ids[0]]},
        ]
        self.add_coverage({REVIEW, *other_ids})
        # Official input does not enter the customer denominator. Preserve
        # this prior processing order, rather than deriving it from repair.
        self.previous["runtime"]["processed_source_ids"] = [other_ids[1], REVIEW, MANUAL, other_ids[0]]
        original, bundle_before = deepcopy(self.previous), deepcopy(self.bundle)
        for succeeded in (True, False):
            with self.subTest(succeeded=succeeded):
                patch = {"patch": {"existing_response": "TEST ONLY: transport patch"}} if succeeded else None
                result = PublicPlanner(lambda _prompt, _schema, patch=patch: deepcopy(patch)).repair(
                    self.bundle, self.previous, [request()])
                self.assertEqual(result["runtime"]["processed_source_ids"], original["runtime"]["processed_source_ids"])
                self.assertEqual(set(result["runtime"]["selected_source_ids"]), {REVIEW, MANUAL})
                public = public_research_brief(result, sha256(PACK.read_bytes()).hexdigest(), self.bundle)
                coverage = public["runtime"]["summary_reference_coverage"]
                self.assertEqual(public["runtime"]["summary_reference_coverage_state"], "provided")
                self.assertEqual(coverage, original["runtime"]["summary_reference_coverage"])
                self.assertEqual(coverage, result["runtime"]["summary_reference_coverage"])
                self.assertEqual(coverage["summary_item_counts"], {"positive": 1, "negative": 1, "mixed": 1})
                self.assertEqual(coverage["denominator_customer_source_count"], 3)
                self.assertEqual(coverage["covered_customer_source_count"], 2)
                self.assertEqual(coverage["overlapping_polarity_source_count"], 1)
                self.assertFalse(coverage["classification_approved"])
                self.assertFalse(public["runtime"]["market_frequency_estimated"])
                self.assertFalse(public["runtime"]["independent_semantic_quality_verified"])
                self.assertEqual(result["source_facts"], original["source_facts"])
                self.assertEqual(result["summaries"], original["summaries"])
                result["runtime"]["processed_source_ids"].clear()
                coverage["covered_source_ids"].clear()
                self.assertEqual(self.previous, original)
                self.assertEqual(self.bundle, bundle_before)

    def test_malformed_or_mismatched_processing_cannot_approve_inherited_coverage(self):
        self.add_coverage()
        original, bundle_before = deepcopy(self.previous), deepcopy(self.bundle)
        another_customer = next(eid for eid in sorted(self.customer_ids) if eid != REVIEW)
        for processed in (None, REVIEW, [REVIEW, REVIEW], ["unregistered-source"], [True],
                          [[REVIEW]], [], [REVIEW, another_customer]):
            with self.subTest(processed=processed):
                previous = deepcopy(original)
                previous["runtime"]["processed_source_ids"] = deepcopy(processed)
                before = deepcopy(previous)
                result = PublicPlanner(lambda _prompt, _schema: None,
                    runtime_metadata={"processed_source_ids": [REVIEW]}).repair(
                    self.bundle, previous, [request()])
                self.assertNotIn("summary_reference_coverage", result["runtime"])
                self.assertEqual(result["runtime"]["summary_reference_coverage_inheritance"], "invalid_previous_metadata")
                if processed not in ([], [REVIEW, another_customer]):
                    self.assertNotIn("processed_source_ids", result["runtime"])
                public = public_research_brief(result, sha256(PACK.read_bytes()).hexdigest(), self.bundle)
                self.assertNotIn("summary_reference_coverage", public["runtime"])
                self.assertFalse(public["runtime"]["independent_semantic_quality_verified"])
                self.assertEqual(result["source_facts"], before["source_facts"])
                self.assertEqual(result["summaries"], before["summaries"])
                self.assertEqual(previous, before)
                self.assertEqual(self.bundle, bundle_before)
