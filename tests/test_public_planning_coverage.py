"""C4 reference accounting only: real retained IDs, no opinion/LLM quality grades.

Protocol-only summary rows deliberately overlap. They are not new reviews or
semantic declarations; this verifies source reference math and failure scope.
"""
import unittest
from copy import deepcopy

from lgax_core.public_planning import PublicPlanner, source_facts, summary_reference_coverage
from test_public_planning import real_bundle


class SummaryReferenceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.bundle = real_bundle()
        self.review = self.bundle["sources"][0]["source_id"]
        self.manual = self.bundle["sources"][1]["source_id"]

    def summaries(self, **references):
        return {polarity: [{"text": "TEST ONLY: source reference accounting", "source_ids": ids}
                           for ids in references.get(polarity, [])]
                for polarity in ("positive", "negative", "mixed")}

    def test_repeated_and_cross_polarity_references_do_not_inflate_source_denominator(self):
        rows = self.summaries(positive=[[self.review], [self.review]], mixed=[[self.review]])
        original = deepcopy(rows)
        receipt = summary_reference_coverage(rows, {self.review}, {self.review})
        self.assertEqual(receipt["summary_item_counts"], {"positive": 2, "negative": 0, "mixed": 1})
        self.assertEqual(receipt["polarity_source_counts"], {"positive": 1, "negative": 0, "mixed": 1})
        self.assertEqual(receipt["covered_customer_source_count"], 1)
        self.assertEqual(receipt["denominator_customer_source_count"], 1)
        self.assertEqual(receipt["overlapping_polarity_source_count"], 1)
        self.assertEqual(receipt["coverage_ratio"], 1.0)
        self.assertEqual(rows, original)
        self.assertFalse(receipt["classification_approved"])
        self.assertFalse(receipt["market_frequency_estimated"])

    def test_empty_successful_discovery_denominator_is_null_not_zero_sentiment(self):
        receipt = summary_reference_coverage(self.summaries(), {self.review}, set())
        self.assertEqual(receipt["denominator_customer_source_count"], 0)
        self.assertIsNone(receipt["coverage_ratio"])
        self.assertEqual(receipt["unprocessed_input_source_count"], 1)
        self.assertEqual(receipt["polarity_source_counts"], {"positive": 0, "negative": 0, "mixed": 0})

    def test_official_document_reference_never_becomes_customer_denominator(self):
        rows = self.summaries(negative=[[self.review, self.manual]], positive=[[self.manual]])
        receipt = summary_reference_coverage(rows, {self.review}, {self.review, self.manual})
        self.assertEqual(receipt["denominator_source_ids"], [self.review])
        self.assertEqual(receipt["polarity_source_ids"]["positive"], [])
        self.assertEqual(receipt["polarity_source_ids"]["negative"], [self.review])
        self.assertEqual(receipt["covered_source_ids"], [self.review])

    def test_unreferenced_processed_source_is_not_automatically_negative_or_positive(self):
        receipt = summary_reference_coverage(self.summaries(), {self.review}, {self.review})
        self.assertEqual(receipt["unreferenced_processed_source_count"], 1)
        self.assertEqual(receipt["unprocessed_input_source_count"], 0)
        self.assertEqual(receipt["coverage_ratio"], 0.0)
        self.assertEqual(sum(receipt["polarity_source_counts"].values()), 0)

    def test_failed_real_source_discovery_keeps_zero_denominator_and_original_facts(self):
        before = deepcopy(self.bundle)
        result = PublicPlanner(lambda prompt, schema: None).run(self.bundle, "TEST ONLY: failure accounting", [])
        coverage = result["runtime"]["summary_reference_coverage"]
        self.assertEqual(coverage["denominator_customer_source_count"], 0)
        self.assertIsNone(coverage["coverage_ratio"])
        self.assertEqual(coverage["unprocessed_input_source_count"], 1)
        self.assertEqual(result["concepts"], [])
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertEqual(self.bundle, before)

    def test_empty_successful_summary_is_distinct_from_failed_discovery(self):
        output = {"problems": [], "summaries": self.summaries()}
        result = PublicPlanner(lambda prompt, schema: deepcopy(output)).run(
            self.bundle, "TEST ONLY: empty successful accounting", [])
        coverage = result["runtime"]["summary_reference_coverage"]
        self.assertEqual(coverage["denominator_customer_source_count"], 1)
        self.assertEqual(coverage["unreferenced_processed_source_count"], 1)
        self.assertEqual(coverage["coverage_ratio"], 0.0)
        self.assertEqual(result["summaries"], output["summaries"])
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])
