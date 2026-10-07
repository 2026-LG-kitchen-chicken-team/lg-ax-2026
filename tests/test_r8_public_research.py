"""R8 ingestion checks use actual pinned public records, never generated reviews."""

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from copy import deepcopy
from pathlib import Path

from jsonschema import ValidationError
from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_public_review_db import build_db, load_profile
from build_research_bundle import PACK, R5, build_pack, load_inputs, merge_records


class PublicResearchR8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs()
        cls.base = cls.inputs[str(R5 / "fixed18/records.json")]
        cls.added = cls.inputs[str(R5 / "balanced-pilot-v2/new_unique_records.json")]
        cls.values, _ = load_profile("r8")

    def test_all_238_original_fields_bodies_and_splits_survive(self):
        rows = merge_records(self.base, self.added)
        self.assertEqual(len(rows), 238)
        originals = {r["original_review_id"]: r for r in self.base + self.added}
        for row in rows:
            original = originals[row["original_review_id"]]
            self.assertEqual({key: row[key] for key in original}, original)
            self.assertEqual(hashlib.sha256(row["text"].encode()).hexdigest(), row["text_sha256"])
            self.assertIsNone(row["published_at"])
            self.assertIsNone(row["actual_purchased_model_id"])
            self.assertFalse(row["eligible_for_model_input"])

    def test_bundles_exclude_evaluation_demo_and_quarantine(self):
        review_ids = set()
        for name, bundle in self.values.items():
            if not name.startswith("bundles/"):
                continue
            validate_research_bundle(bundle)
            self.assertEqual(bundle["analysis_scope"], "product_group")
            for source in bundle["sources"]:
                self.assertEqual(source["source_kind"], "public")
                if source["source_type"] == "review":
                    self.assertEqual(source["metadata"]["split"], "development")
                    self.assertEqual(source["facts"], [])
                    review_ids.add(source["metadata"]["original_review_id"])
                if source["source_type"] == "manual":
                    self.assertEqual(source["coverage"], "excerpt")
                    self.assertIn("page", source["locator"])
                    self.assertIn("document_sha256", source["metadata"])
        self.assertEqual(len(review_ids), 141)
        self.assertEqual(self.values["manifest.json"]["split_counts"], {"development": 141, "independent_evaluation": 36, "demonstration": 49, "quarantine": 12})

    def test_unknown_purchased_sku_cannot_be_used_as_exact_model(self):
        bundle = deepcopy(self.values["bundles/dishwasher.development.research-bundle.json"])
        bundle["analysis_scope"] = "exact_model"
        with self.assertRaisesRegex(ValidationError, "confirmed purchased model"):
            validate_research_bundle(bundle)

    def test_duplicate_id_and_changed_public_body_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate original review ID"):
            merge_records(self.base, [self.base[0]])
        altered = deepcopy(self.added[0])
        altered["text"] += " "
        with self.assertRaisesRegex(ValueError, "Public body hash mismatch"):
            merge_records(self.base, [altered])

    def test_official_sources_do_not_invent_qa_or_model_applicability(self):
        official = self.values["official-sources.json"]
        self.assertEqual(len(official), 18)
        self.assertEqual(sum(s["source_type"] == "manual" for s in official), 15)
        self.assertFalse(any(s["source_type"] == "qa" for s in official))
        faq = next(s for s in official if s["source_type"] == "faq")
        install = next(s for s in official if s["source_type"] == "installation")
        competitor = next(s for s in official if s["brand"] == "Samsung")
        self.assertIsNone(faq["page_model"])
        self.assertIsNone(install["page_model"])
        self.assertEqual(competitor["page_model"], "DW99F79E1UHCS")
        self.assertTrue(competitor["metadata"]["comparison_limits"])

    def test_sqlite_roundtrip_preserves_reviews_official_sources_and_bundles(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "research.sqlite3"
            result = build_db("r8", output)
            self.assertTrue(result["json_rows_equal"])
            self.assertEqual(result["reviews"], 238)
            self.assertEqual(result["official_sources"], 18)
            self.assertEqual(result["research_bundles"], 3)
            with closing(sqlite3.connect(output)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reviews WHERE published_at IS NULL AND actual_purchased_model_id IS NULL").fetchone()[0], 238)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reviews WHERE split='quarantine'").fetchone()[0], 12)
            before = output.read_bytes()
            with self.assertRaisesRegex(ValueError, "already exists"):
                build_db("r8", output)
            self.assertEqual(output.read_bytes(), before)

    def test_offline_rebuild_matches_committed_json(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            build_pack(output=output)
            hashes = json.loads((output / "files.json").read_bytes())
            for name in hashes:
                self.assertEqual((output / name).read_bytes(), (ROOT / PACK / name).read_bytes())

    def test_changed_pinned_source_fails_before_output_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_input = root / R5 / "fixed18/records.json"
            first_input.parent.mkdir(parents=True)
            first_input.write_bytes((ROOT / R5 / "fixed18/records.json").read_bytes() + b" ")
            output = root / "new-output"
            with self.assertRaisesRegex(ValueError, "Pinned source changed"):
                build_pack(root=root, output=output)
            self.assertFalse(output.exists())

    def test_original_source_pack_cannot_be_an_output(self):
        with self.assertRaisesRegex(ValueError, "Original R5"):
            build_pack(output=ROOT / R5 / "fixed18")

    def test_existing_fixed18_db_profile_preserves_all_json_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            result = build_db("fixed18", Path(temp) / "fixed18.sqlite3")
            self.assertTrue(result["json_rows_equal"])
            self.assertEqual(result["expected_artifact_sha256"], "253d184c62f568d9f9ff336cc59ca64b22ec79c83728e5fb102959de154af289")
            self.assertEqual(result["reviews"], 179)


if __name__ == "__main__":
    unittest.main()
