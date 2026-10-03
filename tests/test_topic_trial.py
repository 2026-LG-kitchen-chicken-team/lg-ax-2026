import copy
import json
import unittest
from scripts.topic_trial import DATA, assess_concepts, repair_flow, design_completion_ux, execute


class CandidateSkillChecks(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads((DATA / "pilot_inputs.json").read_text(encoding="utf-8"))
        self.sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
        self.known = {s["id"] for s in self.sources["sources"]}

    def test_unknown_source_does_not_establish_a_gap(self):
        item = self.inputs["a4"]
        item["concepts"][0]["source_ids"] = ["fabricated"]
        self.assertEqual(assess_concepts(item, self.known)[0]["decision"], "hold_missing_evidence")

    def test_unverified_competitor_feature_does_not_establish_a_gap(self):
        item = self.inputs["a4"]
        item["features"][0]["source_ids"] = ["fabricated"]
        self.assertTrue(all(r["decision"] == "hold_missing_evidence"
                            for r in assess_concepts(item, self.known)))

    def test_foreign_announcement_is_not_installed_device_support(self):
        rows = assess_concepts(self.inputs["a4"], self.known)
        row = next(r for r in rows if r["id"] == "auto_cycle")
        self.assertEqual(row["decision"], "deprioritize_existing_function")
        self.assertEqual(row["target_coverage"], "unverified")

    def test_human_duration_assumptions_cannot_hide_missed_deadline(self):
        self.inputs["b1"]["deadline"] = 30
        result = repair_flow(self.inputs["b1"])
        self.assertIn("deadline_exceeded", result["after"])
        self.assertEqual(result["status"], "needs_designer_input")

    def test_missing_dependency_is_not_auto_repaired_away(self):
        self.inputs["b1"]["flow"][1]["after"] = ["unknown_task"]
        result = repair_flow(self.inputs["b1"])
        self.assertEqual(result["status"], "needs_designer_input")
        self.assertTrue(any("missing_dependency" in issue for issue in result["after"]))

    def test_device_done_does_not_imply_dishes_ready(self):
        result = design_completion_ux(self.inputs["b5"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["entry"], "ask_readiness")

    def test_ready_event_cannot_override_unfinished_cycle(self):
        self.inputs["b5"].update(cycle_complete=False, readiness="ready")
        result = design_completion_ux(self.inputs["b5"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["entry"], "await_cycle")

    def test_no_response_is_not_approval(self):
        self.inputs["b5"].update(user_available=False, readiness="ready")
        result = design_completion_ux(self.inputs["b5"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["entry"], "await_user")

    def test_replay_has_all_candidates_and_explicit_mode(self):
        original = copy.deepcopy(self.inputs)
        result = execute(self.inputs, self.sources)
        self.assertEqual({r["candidate"] for r in result["runs"]}, {"A4", "B1", "B5"})
        self.assertEqual(result["case_count"], 9)
        self.assertEqual(result["passed"], 9)
        self.assertEqual(self.inputs, original)
        self.assertIn("no_llm_api", result["execution_mode"])


if __name__ == "__main__":
    unittest.main()
