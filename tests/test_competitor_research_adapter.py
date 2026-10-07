"""New adapter checks for frozen actual official excerpts; no collection/model/quality experiment."""

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import ValidationError
from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("competitor_adapter", ROOT / "scripts/import_competitor_research.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class CompetitorResearchAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.sidecar, cls.comparison, cls.pins = adapter.load_inputs()

    def build(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "new-adapter"
        manifest = adapter.build_adapter(output=output)
        bundle = json.loads((output / adapter.BUNDLE_FILE).read_bytes())
        return output, manifest, bundle

    def test_existing_54_source_objects_facts_dates_and_review_holds_are_unchanged(self):
        _, manifest, bundle = self.build()
        validate_research_bundle(bundle)
        self.assertEqual(bundle["sources"][:54], self.base["sources"])
        self.assertNotEqual(bundle["bundle_id"], self.base["bundle_id"])
        self.assertEqual(len(bundle["sources"]), 66)
        self.assertEqual(manifest["source_type_counts"], {"review": 48, "manual": 6, "spec": 7, "installation": 5})
        for source in bundle["sources"][:54]:
            if source["source_type"] == "review":
                self.assertIsNone(source["purchased_model"])
                self.assertIsNone(source["published_at"])
                self.assertEqual(source["metadata"]["split"], "development")
                self.assertFalse(source["metadata"]["strict_exact_model_eligible_for_model_input"])
                self.assertEqual(source["facts"], [])

    def test_new_12_text_hash_model_version_locators_time_and_roles_follow_exact_parent(self):
        sources, lineage = adapter.convert_sources(self.sidecar)
        by_excerpt = {row["metadata"]["origin_excerpt_id"]: row for row in sources}
        for page in self.sidecar["sources"]:
            for excerpt in page["excerpts"]:
                source = by_excerpt[excerpt["id"]]
                self.assertEqual(source["text"], excerpt["text"])
                self.assertEqual(source["metadata"]["text_sha256"], excerpt["text_sha256"])
                self.assertEqual(source["metadata"]["origin_page"]["source_sha256"], page["source_sha256"])
                self.assertEqual(source["document_version"], page["capture_version"])
                self.assertEqual(source["page_model"], page["model_id"])
                self.assertEqual(source["collected_at"], page["captured_at"])
                self.assertEqual(source["url"], page["final_url"])
                for key in ("normalized_text_range", "location_basis", "locators"):
                    self.assertEqual(source["locator"][key], excerpt[key])
                self.assertEqual(source["facts"][0]["text"], excerpt["text"])
                self.assertEqual(source["facts"][0]["kind"], "document_fact")
                self.assertEqual(source["facts"][0]["locator"], source["locator"])
                self.assertEqual(source["coverage"], "excerpt")
                self.assertIsNone(source["purchased_model"])
                self.assertIsNone(source["published_at"])
                self.assertEqual(source["date_kind"], "unknown")
                expected_role = "official_specification" if source["source_type"] == "spec" else "official_document"
                self.assertEqual(source["source_role"], expected_role)
        self.assertEqual(len(sources), len(lineage))
        self.assertEqual(len(sources), 12)

    def test_problem_context_links_original_source_and_preserves_balanced_constraints(self):
        _, manifest, bundle = self.build()
        focus = manifest["problem_focus"]
        review = next(row for row in bundle["sources"] if row["source_id"] == focus["source_id"])
        self.assertEqual(focus["source_id"], "LGE-R8-REVIEW-848850")
        self.assertEqual(len(focus["literal_contexts"]), 4)
        for context in focus["literal_contexts"]:
            start, end = context["text_range"]
            self.assertEqual(review["text"][start:end], context["quote"])
            self.assertEqual(context["source_id"], focus["source_id"])
        self.assertFalse(focus["external_depth_is_internal_arm_reach"])
        self.assertFalse(focus["customer_burden_resolved"])
        self.assertFalse(focus["independent_semantic_quality_verified"])
        self.assertIsNone(focus["first_problem_id"])
        self.assertFalse(manifest["registered_for_api"])
        self.assertFalse(manifest["planning_run_executed"])
        self.assertFalse(manifest["parent_done"])
        self.assertEqual(bundle["collection_manifest"]["original_comparison_conditions"],
                         self.comparison["comparability"])
        self.assertEqual(bundle["collection_manifest"]["comparison_model_conditions"], self.comparison["models"])

    def test_corrupt_hash_duplicate_excerpt_and_mismatched_capture_version_are_rejected(self):
        for change in ("text", "duplicate", "version"):
            value = deepcopy(self.sidecar)
            with self.subTest(change=change):
                if change == "text":
                    value["sources"][0]["excerpts"][0]["text"] += " edited"
                elif change == "duplicate":
                    value["sources"][0]["excerpts"].append(deepcopy(value["sources"][0]["excerpts"][0]))
                else:
                    value["sources"][0]["capture_version"] = "unknown"
                with self.assertRaises(ValueError):
                    adapter.convert_sources(value)

    def test_official_sources_cannot_be_reclassified_as_customer_experience(self):
        _, _, bundle = self.build()
        bundle["sources"][-1]["source_role"] = "customer_experience"
        with self.assertRaises(ValidationError):
            validate_research_bundle(bundle)

    def test_derived_files_pin_exact_bytes_and_frozen_area_cannot_be_output(self):
        output, _, bundle = self.build()
        file_pins = json.loads((output / "files.json").read_bytes())
        for name, expected in file_pins.items():
            self.assertEqual(adapter.digest((output / name).read_bytes()), expected)
        lineage = json.loads((output / "lineage.json").read_bytes())
        for source in bundle["sources"][:54]:
            self.assertEqual(adapter.digest(adapter.json_bytes(source)),
                             lineage["baseline_source_sha256"][source["source_id"]])
        before = (ROOT / adapter.BASE).read_bytes()
        with self.assertRaises(ValueError):
            adapter.build_adapter(output=ROOT / adapter.BASE.parent)
        self.assertEqual((ROOT / adapter.BASE).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
