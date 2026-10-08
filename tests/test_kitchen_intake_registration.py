"""Check only two new public intakes and their additive, model-free CLI registration."""

import importlib.util
import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "data/research/r9-kitchen-intake-20261008"
EXPECTED_NEW_DIGESTS = {
    "kimchi_refrigerator": "5f08c24239bfdcc71f30181bcbd79df362024d91da5fe1383c441ba944a38535",
    "lightwave_oven": "cdaf599d4db2c75aaf2875e4e88fb02afbc78bfb1b1621d23d37beb83195b315",
}


class KitchenIntakeRegistrationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("kitchen_intake_cli", ROOT / "scripts/serve_research_prototype.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.manifest = json.loads((INTAKE / "runtime-intake.manifest.json").read_bytes())
        self.bundles = {
            group: json.loads((INTAKE / f"{group}.research-bundle.json").read_bytes())
            for group in EXPECTED_NEW_DIGESTS
        }

    def test_ten_paths_preserve_the_eight_original_digests_and_add_two_unchanged_packs(self):
        paths = self.cli.research_bundle_paths()
        baseline = self.manifest["existing_registry_preserved"]
        self.assertEqual(len(baseline), 8)
        self.assertEqual(len(paths), 10)
        self.assertEqual(len(set(paths)), 10)
        self.assertEqual(paths[:8], [ROOT / item["path"] for item in baseline])
        for path, recorded in zip(paths[:8], baseline, strict=True):
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), recorded["sha256"])
            self.assertEqual(json.loads(path.read_bytes())["bundle_id"], recorded["bundle_id"])
        self.assertEqual(paths[8:], [INTAKE / f"{group}.research-bundle.json" for group in EXPECTED_NEW_DIGESTS])
        originals = json.loads((INTAKE / "official-and-preview-sources.json").read_bytes())["sources"]
        for group, digest in EXPECTED_NEW_DIGESTS.items():
            bundle = self.bundles[group]
            validate_research_bundle(bundle)
            self.assertEqual(sha256((INTAKE / f"{group}.research-bundle.json").read_bytes()).hexdigest(), digest)
            self.assertEqual(bundle["sources"], [source for source in originals if source["product_group"] == group])
            self.assertFalse(bundle["collection_manifest"]["runtime_registered"])
            self.assertTrue(all(source["metadata"]["runtime_registered"] is False for source in bundle["sources"]))
        for artifact in self.manifest["copied_artifacts"]:
            self.assertTrue(artifact["byte_identical_to_producer"])
            self.assertEqual(sha256((INTAKE / artifact["file"]).read_bytes()).hexdigest(), artifact["sha256"])

    def test_preview_unknowns_and_document_only_scope_are_not_promoted_to_verified_customer_data(self):
        from lgax_core.public_planning import is_customer_source

        kimchi, lightwave = self.bundles["kimchi_refrigerator"], self.bundles["lightwave_oven"]
        previews = [source for source in kimchi["sources"] if source["source_type"] == "review"]
        self.assertEqual(len(kimchi["sources"]), 6)
        self.assertEqual(len(previews), 3)
        for source in previews:
            self.assertEqual(source["source_role"], "customer_experience")
            self.assertEqual(source["coverage"], "excerpt")
            self.assertIsNone(source["metadata"]["original_review_id"])
            self.assertIsNone(source["rating"])
            self.assertFalse(source["metadata"]["independent_evaluation_approved"])
        self.assertEqual(len(lightwave["sources"]), 4)
        self.assertTrue(all(source["source_type"] == "spec" and source["source_role"] == "official_specification"
                            for source in lightwave["sources"]))
        self.assertEqual(sum(is_customer_source(source) for source in kimchi["sources"]), 3)
        self.assertFalse(any(is_customer_source(source) for source in lightwave["sources"]))
        for bundle in (kimchi, lightwave):
            self.assertEqual(bundle["analysis_scope"], "product_group")
            self.assertEqual(bundle["collection_manifest"]["new_customer_qa_count"], 0)
            self.assertEqual(bundle["collection_manifest"]["new_manual_pdf_count"], 0)
            for source in bundle["sources"]:
                self.assertIsNone(source["purchased_model"])
                self.assertIsNone(source["published_at"])
                self.assertEqual(source["date_kind"], "unknown")
                self.assertEqual(source["metadata"]["split"], "unassigned_intake")
        for candidate in self.manifest["new_registry_candidates"]:
            self.assertFalse(candidate["customer_problem_discovery_approved"])
            self.assertFalse(candidate["semantic_quality_verified"])
        self.assertFalse(self.manifest["quality_scope"]["market_frequency_estimated"])
        self.assertFalse(self.manifest["live_service_modified"])
        self.assertEqual(self.manifest["model_calls"], 0)

    def test_actual_workspace_lists_two_candidates_without_model_setup_or_source_mutation(self):
        from lgax_api.research_planning import ResearchWorkspace

        paths = self.cli.research_bundle_paths()
        before = {path: path.read_bytes() for path in paths}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(self.cli.StructuredModelClient, "from_env", side_effect=AssertionError("No model setup")),
            patch.object(self.cli.PublicPlanner, "from_model_client", side_effect=AssertionError("No planner setup")),
        ):
            workspace = ResearchWorkspace(Path(folder) / "list-only.sqlite3", paths, planner=None)
            rows = workspace.list_bundles()["bundles"]
            self.assertEqual(len(rows), 10)
            self.assertEqual(workspace.planner, None)
            by_id = {row["bundle_id"]: row for row in rows}
            for group, digest in EXPECTED_NEW_DIGESTS.items():
                bundle = self.bundles[group]
                row = by_id[bundle["bundle_id"]]
                self.assertEqual(row["bundle_sha256"], digest)
                self.assertEqual(row["source_count"], len(bundle["sources"]))
                self.assertEqual(row["review_count"], 3 if group == "kimchi_refrigerator" else 0)
                self.assertEqual(row["collection_manifest"], bundle["collection_manifest"])
                self.assertEqual(workspace.get_bundle(bundle["bundle_id"]), bundle)
        self.assertEqual({path: path.read_bytes() for path in paths}, before)


if __name__ == "__main__":
    unittest.main()
