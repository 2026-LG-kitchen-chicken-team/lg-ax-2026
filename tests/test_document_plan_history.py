"""A new citation recipe must never reserve or rewrite historical run evidence."""

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("document_plan_recipe", ROOT / "scripts/prepare_lg_document_plan.py")
RECIPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECIPE)


class DocumentPlanHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.history = self.root / "data/research/history"
        self.history.mkdir(parents=True)
        self.sentinel = self.history / "mapping.json"
        self.sentinel.write_bytes(b"original history\n")
        self.plan = self.root / "data/document_plans/current.json"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_bytes(b"original plan\n")
        root_patch = patch.object(RECIPE, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def assert_preserved(self):
        self.assertEqual(self.sentinel.read_bytes(), b"original history\n")
        self.assertEqual(self.plan.read_bytes(), b"original plan\n")

    def test_existing_run_is_rejected_before_any_output_changes(self):
        with patch("sys.argv", ["prepare_lg_document_plan", "--run-directory", str(self.history)]), \
                self.assertRaises(FileExistsError):
            RECIPE.main()
        self.assert_preserved()

    def test_no_implicit_historical_output_directory(self):
        with patch("sys.argv", ["prepare_lg_document_plan"]), redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as error:
            RECIPE.main()
        self.assertEqual(error.exception.code, 2)
        self.assert_preserved()

    def test_fresh_run_reserved_once_and_duplicate_writer_rejected(self):
        run = self.root / "data/research/new-run"
        self.assertEqual(RECIPE.reserve_run_directory(run), run.resolve())
        (run / "mapping.json").write_bytes(b"first writer\n")
        with self.assertRaises(FileExistsError):
            RECIPE.reserve_run_directory(run)
        self.assertEqual((run / "mapping.json").read_bytes(), b"first writer\n")
        self.assert_preserved()

    def test_outside_research_is_rejected_without_creating_directory(self):
        run = self.root / "private/new-run"
        with self.assertRaises(ValueError):
            RECIPE.reserve_run_directory(run)
        self.assertFalse(run.exists())
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
