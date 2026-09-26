import unittest
from scripts.scenario_spike import examples, inspect


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.caps, self.cases = examples()

    def test_valid_flow(self):
        self.assertEqual(inspect(self.cases["valid"], self.caps), [])

    def test_dependency_and_resource_conflict(self):
        result = inspect(self.cases["dependency_and_overlap"], self.caps)
        self.assertIn("heat:dependency_not_finished", result)
        self.assertIn("heat+second:resource_overlap", result)

    def test_unknown_capability(self):
        self.assertIn("heat:unsupported_action", inspect(self.cases["unsupported"], self.caps))

    def test_missing_dependency(self):
        self.cases["valid"][1]["after"] = ["missing"]
        self.assertIn("heat:missing_dependency", inspect(self.cases["valid"], self.caps))

    def test_cycles(self):
        self.cases["valid"][0]["after"] = ["heat"]
        self.assertIn("dependency_cycle", inspect(self.cases["valid"], self.caps))

    def test_boundary_is_not_overlap(self):
        self.cases["valid"].append({"id":"later", "device":"oven", "action":"heat", "start":25, "duration":5})
        self.assertEqual(inspect(self.cases["valid"], self.caps), [])

    def test_invalid_time(self):
        self.cases["valid"][0]["duration"] = -1
        self.assertIn("load:invalid_time", inspect(self.cases["valid"], self.caps))

    def test_empty_flow(self):
        self.assertEqual(inspect([], self.caps), ["empty_or_invalid_flow"])

    def test_model_shaped_invalid_output(self):
        self.cases["valid"][0]["duration"] = "five"
        self.assertEqual(inspect(self.cases["valid"], self.caps), ["invalid_time_schema"])

    def test_nonfinite_time(self):
        self.cases["valid"][0]["duration"] = float("nan")
        self.assertEqual(inspect(self.cases["valid"], self.caps), ["invalid_time_schema"])


if __name__ == "__main__":
    unittest.main()
