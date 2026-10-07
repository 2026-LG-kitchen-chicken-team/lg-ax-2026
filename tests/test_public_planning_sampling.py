"""Actual-corpus sampling and bounded empty-result fallback, without model calls."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.public_planning import PublicPlanner, _balanced_sources, is_customer_source, source_facts

PACK = (Path(__file__).resolve().parents[1] / "data/research/r8-public-official-expansion-20261007"
        / "bundles/dishwasher.development.research-bundle.json")


class PublicPlanningSamplingTests(unittest.TestCase):
    def test_small_actual_sample_includes_low_rating_mixed_text_and_other_model_without_mutation(self):
        bundle = json.loads(PACK.read_text("utf-8"))
        sources = [source for source in bundle["sources"] if is_customer_source(source)]
        before = deepcopy(sources)
        ordered = _balanced_sources(sources)
        first = ordered[:5]
        self.assertTrue(any(source["rating"] <= 3 for source in first))
        # This real five-star review includes both convenience and surprise at
        # consumables. It is sampled without assigning an automatic sentiment.
        self.assertIn("LGE-R8-REVIEW-853593", {source["source_id"] for source in first})
        self.assertGreater(len({source["page_model"] for source in first}), 1)
        self.assertEqual(sources, before)
        self.assertEqual(len(ordered), len(sources))
        self.assertEqual({source["source_id"] for source in ordered},
                         {source["source_id"] for source in sources})
        for source in ordered:
            self.assertIs(source, next(original for original in sources
                                      if original["source_id"] == source["source_id"]))

    def test_empty_discovery_reads_at_most_one_more_actual_batch_and_keeps_planning_repair_budget(self):
        original = json.loads(PACK.read_text("utf-8"))
        for budget, one_source, rejected, expected_calls in ((4, False, False, 2), (12, False, False, 2),
                                                            (4, True, False, 1), (4, False, True, 1)):
            with self.subTest(budget=budget, one_source=one_source, rejected=rejected):
                bundle = deepcopy(original)
                if one_source:
                    bundle["sources"] = [next(source for source in bundle["sources"]
                                              if is_customer_source(source))]
                before = deepcopy(bundle)
                calls = []

                def contract_only_empty(prompt, schema, observed=calls, reject=rejected):
                    # A transport stub with no generated customer text or
                    # accepted concept; this tests budget control, not quality.
                    context = json.loads(prompt.split("분석할 데이터(JSON):\n", 1)[1])
                    observed.append(context)
                    return None if reject else {
                        "problems": [], "summaries": {"positive": [], "negative": [], "mixed": []}}

                brief = PublicPlanner(contract_only_empty, max_model_calls=budget, max_problems=1,
                                      max_prompt_characters=6000).run(bundle, "실제 고객의 남은 사용 부담 발견", [])
                self.assertEqual(len(calls), expected_calls)
                self.assertLessEqual(len(calls) + 2, budget)
                self.assertEqual(brief["problems"], [])
                self.assertEqual(brief["concepts"], [])
                self.assertEqual(brief["source_facts"], source_facts(bundle))
                self.assertEqual(bundle, before)
                self.assertEqual(brief["runtime"]["selection_method"],
                                 "interleaved_rating_expression_page_model_v1")
                selected = [source["source_id"] for call in calls for source in call["sources"]]
                self.assertEqual(len(selected), len(set(selected)))
                for call in calls:
                    self.assertNotIn("sentiment", call)
                    for source in call["sources"]:
                        original_source = next(row for row in bundle["sources"]
                                               if row["source_id"] == source["source_id"])
                        self.assertEqual(source["text"], original_source["text"][:1600])
                        self.assertEqual(source["facts"], original_source["facts"])
                        self.assertNotIn("sampling_stratum", source)


if __name__ == "__main__":
    unittest.main()
