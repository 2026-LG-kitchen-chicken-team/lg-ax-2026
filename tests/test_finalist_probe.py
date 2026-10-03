import copy
import unittest

from scripts.finalist_probe import screen_space, solve, verify_schedule


class FinalistProbeTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            {"id": "a", "duration": 3, "resources": ["person", "oven"], "after": []},
            {"id": "b", "duration": 2, "resources": ["oven"], "after": []},
            {"id": "c", "duration": 4, "resources": ["person"], "after": ["a"]},
        ]
        self.product = {"market": "US", "unit": "inch", "width": 10, "side_gap": 1,
                        "height": 20, "top_gap": 2, "open_width": 15}
        self.space = {"market": "US", "unit": "inch", "width_limit": 12,
                      "height_limit": 22, "open_width_limit": 15}

    def test_schedule_attains_precedence_lower_bound_in_any_input_order(self):
        for tasks in [self.tasks, self.tasks[::-1]]:
            result = solve(tasks, ["person", "oven"])
            self.assertEqual(result["makespan"], 7)  # a -> c requires at least seven units.
            self.assertEqual(verify_schedule(tasks, result), [])

    def test_impossible_deadline_does_not_turn_into_a_success(self):
        result = solve(self.tasks, ["person", "oven"], deadline=6)
        self.assertEqual(result["status"], "deadline_unmet")
        self.assertEqual(verify_schedule(self.tasks, result), [])

    def test_missing_duration_resource_and_cycle_are_not_invented(self):
        tasks = copy.deepcopy(self.tasks)
        tasks[0]["duration"] = None
        self.assertEqual(solve(tasks, ["person", "oven"])["status"], "needs_duration")
        self.assertEqual(solve(self.tasks, ["person"])["status"], "unavailable_resource")
        tasks = copy.deepcopy(self.tasks)
        tasks[0]["after"] = ["c"]
        self.assertEqual(solve(tasks, ["person", "oven"])["status"], "dependency_cycle")

    def test_verifier_rejects_removed_or_disguised_task(self):
        result = solve(self.tasks, ["person", "oven"])
        result["schedule"].pop()
        self.assertIn("task_set", verify_schedule(self.tasks, result))
        result = solve(self.tasks, ["person", "oven"])
        result["schedule"][0]["resources"] = []
        self.assertIn("resources", verify_schedule(self.tasks, result))

    def test_verifier_catches_overlap_and_wrong_makespan(self):
        result = solve(self.tasks, ["person", "oven"])
        task_b = next(p for p in result["schedule"] if p["id"] == "b")
        task_b.update(start=0, end=2)
        result["makespan"] = 1
        errors = verify_schedule(self.tasks, result)
        self.assertIn("resource_overlap", errors)
        self.assertIn("makespan", errors)

    def test_fit_boundary_does_not_certify_installation(self):
        result = screen_space(self.product, self.space)
        self.assertEqual(result["status"], "limited_screen_pass")
        self.assertFalse(result["installation_approval"])
        self.space["width_limit"] = 11.99
        self.assertEqual(screen_space(self.product, self.space)["status"], "reject_constraints")

    def test_missing_or_incompatible_measurements_are_held(self):
        del self.space["open_width_limit"]
        self.assertEqual(screen_space(self.product, self.space)["status"], "hold_missing_information")
        self.space["unit"] = "mm"
        self.assertEqual(screen_space(self.product, self.space)["status"], "hold_unit_mismatch")
        self.space["market"] = "KR"
        self.assertEqual(screen_space(self.product, self.space)["status"], "hold_market_mismatch")


if __name__ == "__main__":
    unittest.main()
