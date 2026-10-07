"""Check actual captured context, role separation and frozen-baseline boundaries."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from extend_research_bundle import BASE, PACK, build_expansion, load_sources


class OfficialExpansionTests(unittest.TestCase):
    def test_actual_qa_roles_do_not_become_usage_experience(self):
        _, sources = load_sources()
        qa = [source for source in sources if source["source_type"] == "qa"]
        self.assertEqual(len(qa), 2)
        self.assertEqual({s["source_role"] for s in qa}, {"customer_question", "official_answer"})
        self.assertEqual(len({s["url"] for s in qa}), 1)
        for source in qa:
            self.assertEqual(source["locator"]["question_no"], "473510")
            self.assertEqual(source["published_at"], "2026-10-07")
            self.assertEqual(source["date_kind"], "posting")
            self.assertEqual(source["page_model"], "MW25S")
            self.assertIsNone(source["purchased_model"])
            self.assertFalse(source["metadata"]["usage_problem_sample_eligible"])
        question = next(s for s in qa if s["source_role"] == "customer_question")
        answer = next(s for s in qa if s["source_role"] == "official_answer")
        self.assertEqual(question["facts"][0]["kind"], "expectation")
        self.assertEqual(answer["facts"][0]["kind"], "document_fact")
        self.assertNotIn("작성자", question["text"])
        self.assertNotIn("박", question["text"])
        self.assertFalse(answer["metadata"]["customer_question_sample_eligible"])

    def test_general_dates_and_model_patterns_are_not_confirmed_posting_or_sku(self):
        _, sources = load_sources()
        general = [s for s in sources if s["source_type"] == "faq"]
        self.assertEqual(len(general), 5)
        for source in general:
            self.assertIsNone(source["published_at"])
            self.assertEqual(source["date_kind"], "unknown")
            self.assertIsNone(source["page_model"])
            self.assertIsNone(source["purchased_model"])
        rinse = next(s for s in general if "rinse-entry" in s["source_id"])
        self.assertEqual(rinse["locator"]["model_pattern"], "DUE6***")
        self.assertIn("전원이 꺼진", rinse["text"])
        editorial = next(s for s in general if s["product_group"] == "microwave")
        self.assertTrue(editorial["metadata"]["editorial_FAQ_not_customer_submission"])
        self.assertFalse(editorial["metadata"]["customer_question_sample_eligible"])

    def test_sources_have_public_locators_and_excerpt_only_hashes(self):
        _, sources = load_sources()
        self.assertEqual(len({s["url"] for s in sources}), 6)
        for source in sources:
            self.assertEqual(source["source_kind"], "public")
            self.assertEqual(source["coverage"], "excerpt")
            self.assertTrue(source["locator"])
            self.assertEqual(source["metadata"]["excerpt_sha256"],
                             hashlib.sha256(source["text"].encode("utf-8")).hexdigest())
            self.assertIn("not_full_HTML", source["metadata"]["hash_scope"])
            self.assertFalse(source["metadata"]["full_document_captured"])
            self.assertTrue(source["collected_at"].endswith("Z"))

    def test_all_baseline_source_fields_registry_and_splits_stay_frozen(self):
        old_hashes = json.loads((ROOT / BASE / "files.json").read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "expanded"
            manifest = build_expansion(output=output)
            self.assertEqual(manifest["original_split_counts"],
                             {"development": 141, "independent_evaluation": 36,
                              "demonstration": 49, "quarantine": 12})
            self.assertEqual(manifest["registered_product_page_models"], 18)
            self.assertEqual(manifest["confirmed_customer_qa_usage_problem_count"], 0)
            for name, digest in old_hashes.items():
                self.assertEqual(hashlib.sha256((ROOT / BASE / name).read_bytes()).hexdigest(), digest)
                if not name.startswith("bundles/"):
                    continue
                old = json.loads((ROOT / BASE / name).read_bytes())
                new = json.loads((output / name).read_bytes())
                validate_research_bundle(new)
                self.assertEqual(new["sources"][:len(old["sources"])], old["sources"])
                self.assertEqual(new["analysis_scope"], "product_group")
                self.assertEqual(new["collection_manifest"]["page_models"],
                                 old["collection_manifest"]["page_models"])
                self.assertEqual([s for s in new["sources"] if s["source_type"] == "review"],
                                 [s for s in old["sources"] if s["source_type"] == "review"])

    def test_offline_build_matches_committed_expansion(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            build_expansion(output=output)
            for name, digest in json.loads((output / "files.json").read_bytes()).items():
                self.assertEqual((output / name).read_bytes(), (ROOT / PACK / name).read_bytes())
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_changed_capture_is_rejected_before_any_output_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root / PACK / "captured-sources.json"
            capture.parent.mkdir(parents=True)
            capture.write_bytes((ROOT / PACK / "captured-sources.json").read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "Pinned source changed"):
                load_sources(root)
            self.assertFalse((root / "expanded").exists())

    def test_original_baseline_output_path_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Frozen R8 baseline"):
            build_expansion(output=ROOT / BASE)
        with self.assertRaisesRegex(ValueError, "Frozen R8 baseline"):
            build_expansion(output=ROOT / BASE / "bundles")


if __name__ == "__main__":
    unittest.main()
