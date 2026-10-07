"""Check only R9 input lineage, permitted metadata corrections and reproducibility."""

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("research_runtime_inputs", ROOT / "scripts/prepare_research_runtime.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class ResearchRuntimeInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "r9"
        self.inputs = {
            group: ROOT / adapter.INPUT_BASE / group / "research-bundle.json" for group in adapter.GROUPS
        }

    def test_three_outputs_preserve_all_source_fields_except_five_page_relations(self):
        original_bytes = {group: path.read_bytes() for group, path in self.inputs.items()}
        manifest = adapter.prepare_runtime_inputs(self.inputs, self.output)
        changed_ids = []
        reviews = 0
        for group in adapter.GROUPS:
            original = json.loads(original_bytes[group])
            output = json.loads((self.output / f"{group}.research-bundle.json").read_bytes())
            validate_research_bundle(output)
            self.assertNotEqual(original["bundle_id"], output["bundle_id"])
            self.assertEqual(original_bytes[group], self.inputs[group].read_bytes())
            restored = deepcopy(output)
            restored["bundle_id"] = original["bundle_id"]
            for before, after in zip(original["sources"], restored["sources"], strict=True):
                if before != after:
                    source_id = after["source_id"]
                    changed_ids.append(source_id)
                    self.assertEqual(group, "dishwasher")
                    old_pages, new_pages, _ = adapter.CORRECTIONS[source_id]
                    self.assertEqual(after["metadata"]["continuation_pages"], new_pages)
                    after["metadata"]["continuation_pages"] = old_pages
                    self.assertEqual(before, after)
                if before["source_type"] == "review":
                    reviews += 1
                    self.assertEqual(before["metadata"]["split"], "development")
                    self.assertIsNone(before["published_at"])
                    self.assertIsNone(before["purchased_model"])
            self.assertEqual(original, restored)
            raw = (self.output / manifest["groups"][group]["output_path"]).read_bytes()
            self.assertEqual(sha256(raw).hexdigest(), manifest["groups"][group]["output_sha256"])
        self.assertCountEqual(changed_ids, adapter.CORRECTIONS)
        self.assertEqual(reviews, 141)
        self.assertEqual(len(manifest["metadata_corrections"]), 5)

    def test_producer_is_reproducible_and_preserves_a_different_existing_edition(self):
        adapter.prepare_runtime_inputs(self.inputs, self.output)
        first = {path.name: path.read_bytes() for path in self.output.iterdir()}
        adapter.prepare_runtime_inputs(self.inputs, self.output)
        self.assertEqual(first, {path.name: path.read_bytes() for path in self.output.iterdir()})
        target = self.output / "dishwasher.research-bundle.json"
        target.write_text("prior edition", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Preserve prior output"):
            adapter.prepare_runtime_inputs(self.inputs, self.output)
        self.assertEqual(target.read_text(encoding="utf-8"), "prior edition")

    def test_changed_frozen_input_and_incomplete_group_set_are_rejected(self):
        changed = self.output.parent / "changed-fridge.json"
        changed.write_bytes(self.inputs["fridge"].read_bytes() + b" ")
        altered = dict(self.inputs, fridge=changed)
        with self.assertRaisesRegex(ValueError, "Frozen fridge input hash changed"):
            adapter.prepare_runtime_inputs(altered, self.output)
        self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, "Exactly fridge"):
            adapter.prepare_runtime_inputs({"fridge": self.inputs["fridge"]}, self.output)
        self.assertFalse(self.output.exists())

    def test_audit_references_match_frozen_committed_artifacts(self):
        for reference in adapter.AUDIT_REFERENCES:
            self.assertEqual(sha256((ROOT / reference["path"]).read_bytes()).hexdigest(), reference["sha256"])


class ManualReferenceInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "manual-reference"
        self.pack_path = ROOT / adapter.OUTPUT / "manual-excerpts.json"

    def test_document_only_bundle_keeps_the_five_complete_source_objects_and_live_inputs(self):
        live_paths = [ROOT / adapter.OUTPUT / f"{group}.research-bundle.json" for group in adapter.GROUPS]
        before = {path: path.read_bytes() for path in live_paths}
        manifest = adapter.prepare_manual_reference_bundle(self.pack_path, self.output)
        bundle = json.loads((self.output / adapter.MANUAL_REFERENCE_FILE).read_bytes())
        validate_research_bundle(bundle)
        self.assertEqual(bundle["sources"], json.loads(self.pack_path.read_bytes())["sources"])
        self.assertEqual(bundle["bundle_id"], adapter.MANUAL_REFERENCE_ID)
        self.assertEqual(bundle["collection_manifest"]["review_count"], 0)
        self.assertEqual(bundle["collection_manifest"]["customer_experience_count"], 0)
        self.assertEqual(bundle["collection_manifest"]["purpose"], "manual_draft_reference")
        self.assertFalse(bundle["collection_manifest"]["semantic_quality_verified"])
        self.assertEqual(manifest["review_count"], 0)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_manual_cli_registry_preserves_seven_existing_inputs_and_lists_one_reference(self):
        from lgax_api.research_planning import ResearchWorkspace

        cli_spec = importlib.util.spec_from_file_location("manual_research_cli", ROOT / "scripts/serve_research_prototype.py")
        cli = importlib.util.module_from_spec(cli_spec)
        cli_spec.loader.exec_module(cli)
        paths = cli.research_bundle_paths()
        self.assertEqual(len(paths), 8)
        self.assertEqual(paths[-1], ROOT / adapter.OUTPUT / adapter.MANUAL_REFERENCE_FILE)
        self.assertEqual(len(set(paths)), 8)
        workspace = ResearchWorkspace(self.output.parent / "list-only.sqlite3", paths, planner=None)
        rows = workspace.list_bundles()["bundles"]
        self.assertEqual(len(rows), 8)
        references = [row for row in rows if row["bundle_id"] == adapter.MANUAL_REFERENCE_ID]
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["source_count"], 5)
        self.assertEqual(references[0]["review_count"], 0)
        self.assertEqual(references[0]["collection_manifest"]["purpose"], "manual_draft_reference")
        self.assertEqual(workspace.planner, None)

    def test_unpinned_manual_pack_is_rejected_before_writing(self):
        altered = self.output.parent / "changed-manual-excerpts.json"
        altered.write_bytes(self.pack_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Frozen manual excerpt pack hash changed"):
            adapter.prepare_manual_reference_bundle(altered, self.output)
        self.assertFalse(self.output.exists())


class BoundedPrototypeConfigurationTests(unittest.TestCase):
    """CLI routing only: no model client, network, service or quality evaluation is run."""

    def setUp(self):
        cli_spec = importlib.util.spec_from_file_location(
            "bounded_research_cli", ROOT / "scripts/serve_research_prototype.py"
        )
        self.cli = importlib.util.module_from_spec(cli_spec)
        cli_spec.loader.exec_module(self.cli)
        original = json.loads((ROOT / adapter.OUTPUT / "dishwasher.research-bundle.json").read_bytes())
        # Keep six real sources, in frozen bundle order, including the longest original excerpts.
        selected = {row["source_id"] for row in sorted(original["sources"], key=lambda row: len(row["text"]), reverse=True)[:6]}
        self.bundle = deepcopy(original)
        self.bundle["sources"] = [row for row in self.bundle["sources"] if row["source_id"] in selected]
        self.assertEqual(len(self.bundle["sources"]), 6)
        # Provenance/facts make the input object larger than the prompt cap. It must remain intact;
        # the planner owns prompt construction, so serialized bundle length is not a prompt/token measurement.
        self.assertGreater(len(json.dumps(self.bundle, ensure_ascii=False)), 9000)
        self.goal = "공식 원문과 고객 자료의 남은 사용 부담을 검토하기"
        self.constraints = ["기존 기능을 새로운 발명으로 제안하지 않기", "하드웨어 변경 없이 개선"]

    def assert_bounded_forwarding(self, previous):
        before = deepcopy((self.bundle, self.constraints, previous))
        context = MagicMock()
        context.__enter__.return_value = sentinel.model_client
        planner = MagicMock()
        planner.run.return_value = sentinel.planning_result
        with (
            patch.object(self.cli.StructuredModelClient, "from_env", return_value=context) as from_env,
            patch.object(self.cli.PublicPlanner, "from_model_client", return_value=planner) as factory,
        ):
            result = self.cli.BoundedPrototypePlanner().run(self.bundle, self.goal, self.constraints, previous)
        from_env.assert_called_once_with()
        factory.assert_called_once_with(sentinel.model_client, max_model_calls=4, max_problems=1,
                                       max_prompt_characters=9000, max_source_characters=1000)
        planner.run.assert_called_once_with(self.bundle, self.goal, self.constraints, previous)
        self.assertIs(planner.run.call_args.args[0], self.bundle)
        self.assertIs(planner.run.call_args.args[2], self.constraints)
        self.assertIs(planner.run.call_args.args[3], previous)
        self.assertEqual((self.bundle, self.constraints, previous), before)
        self.assertIs(result, sentinel.planning_result)
        context.__enter__.assert_called_once_with()
        context.__exit__.assert_called_once_with(None, None, None)

    def test_cli_new_9000_budget_keeps_six_original_sources_without_pretruncating(self):
        self.assert_bounded_forwarding(None)

    def test_cli_new_9000_revision_keeps_previous_and_constraints_without_input_loss(self):
        previous = {"run_id": "TEST-saved-run", "revision": 2,
                    "source_facts": [{"source_id": row["source_id"], "facts": deepcopy(row["facts"])}
                                     for row in self.bundle["sources"]],
                    "constraints": ["기존 기능을 새로운 발명으로 제안하지 않기"]}
        self.assert_bounded_forwarding(previous)


if __name__ == "__main__":
    unittest.main()
