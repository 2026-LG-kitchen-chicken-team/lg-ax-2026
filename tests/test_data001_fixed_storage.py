"""Real HTTP serialization/SQLite persistence of explicit fixture output; no generated claims."""

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

spec = importlib.util.spec_from_file_location(
    "fixed_probe", Path(__file__).resolve().parents[1] / "scripts/check_data001_fixed_storage.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FixedStorageTests(unittest.TestCase):
    def test_missing_final_output_is_not_reported_as_r06_success(self):
        with TemporaryDirectory() as temp:
            result = module.probe({"execution": {"output": None}}, Path(temp) / "case.sqlite")
            self.assertFalse(result["r06_final_output_verified"])
            self.assertFalse((Path(temp) / "case.sqlite").exists())

    def test_failed_execution_with_output_is_not_a_valid_final_judgement(self):
        with TemporaryDirectory() as temp:
            result = module.probe(
                {"execution": {"status": "failed", "output": {"status": "held"}}}, Path(temp) / "case.sqlite"
            )
            self.assertFalse(result["r06_final_output_verified"])
            self.assertEqual(result["status"], "final_judgement_unverified")
            self.assertFalse((Path(temp) / "case.sqlite").exists())

    def test_fixture_final_hold_survives_http_query_and_sqlite_reopen(self):
        from test_workspace_planning import FixtureRunner, dataset_for, read

        payload = read("normal.input.json")
        dataset = dataset_for(payload)
        from lgax_core.store import DemoStore

        runner = FixtureRunner(status="held")
        execution = runner(payload["request"], {payload["product"]["model_id"]: "1.0"}, DemoStore(dataset))
        execution["output"]["questions"] = ["실제 사용 조건은 무엇인가요?"]
        execution["output"]["unresolved"] = ["실제 사용 조건 미확인"]
        execution["output"]["needs"][0]["uncertainties"] = ["실제 사용 조건 미확인"]
        with TemporaryDirectory() as temp:
            result = module.probe({"dataset": dataset, "execution": execution}, Path(temp) / "case.sqlite")
            self.assertTrue(result["r06_final_output_verified"], result)
            self.assertEqual(result["execution_kind"], "fixture")
            self.assertEqual(result["model_generations"], 0)
            self.assertTrue(result["sqlite_reopen_preserved_output"])


if __name__ == "__main__":
    unittest.main()
