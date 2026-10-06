"""Replay PM raw responses; preserve historical failures and distinguish them from new runs."""
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evals/core-semantic/replay_reviews.py"
REPLAY = runpy.run_path(str(SCRIPT))
ROUND2 = ROOT / "evals/pm-review/20261005-round2"
LEGACY = ROUND2 / "live-lg-final"
WORKSPACE = ROUND2 / "api-live/workspace-live.json"


def read(path):
    return json.loads(path.read_text("utf-8"))


class RecordedSemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.workspace = read(WORKSPACE)
        self.execution = deepcopy(self.workspace["first"]["output"]["planning_execution"])

    def test_original_two_stored_runs_keep_same_hold_decisions_without_modification(self):
        original = deepcopy(self.workspace)
        for name in ("first", "second"):
            execution = self.workspace[name]["output"]["planning_execution"]
            replay = REPLAY["replay_execution"](execution)
            self.assertEqual(replay["review_calls"], 1)
            review = replay["reviews"][0]
            self.assertTrue(review["binding_verified"])
            self.assertEqual(review["snapshot_binding"], "original_reviewed_snapshots")
            self.assertEqual(review["current_validation"]["decision"], review["recorded_decision"])
            self.assertEqual(review["current_validation"]["decision"]["action"], "hold")
            self.assertFalse(replay["meaning_quality_scored"])
        self.assertEqual(self.workspace, original)

    def test_all_five_original_rejected_reports_still_reject_with_complete_snapshot_hashes(self):
        reasons = []
        original_reasons = []
        for name in ("development-normal", "normal", "changed_exclusion", "synonym"):
            execution = read(LEGACY / f"{name}.json")
            original = deepcopy(execution)
            replay = REPLAY["replay_execution"](execution)
            for review in replay["reviews"]:
                self.assertTrue(review["binding_verified"])
                self.assertEqual(review["snapshot_binding"], "hash_verified_successful_stage_reconstruction")
                self.assertEqual(review["current_validation"]["status"], "rejected")
                reasons.append(review["current_validation"]["error"]["details"]["reason"])
                original_reasons.append(review["recorded_validation"]["error"]["details"]["reason"])
            self.assertEqual(execution, original)
        self.assertCountEqual(reasons, ["candidate_quote_not_literal"] * 3 + ["semantic_review_schema"] * 2)
        self.assertCountEqual(original_reasons, ["candidate_quote_not_literal"] * 3 +
                              ["exclusion_pair_or_literal_condition"] * 2)

    def test_early_holds_without_review_are_kept_in_denominator(self):
        for name in ("negation", "ambiguous_mode", "conflicting_conditions"):
            replay = REPLAY["replay_execution"](read(LEGACY / f"{name}.json"))
            self.assertEqual(replay["original_status"], "held")
            self.assertEqual(replay["recorded_model_calls"], 2)
            self.assertEqual(replay["review_calls"], 0)
            self.assertFalse(replay["meaning_quality_scored"])

    def test_changed_input_candidates_raw_response_or_saved_report_cannot_be_rebound(self):
        mutations = (
            lambda x: x["semantic_reviews"][0]["reviewed_input"]["request"].update(target_customer="altered"),
            lambda x: x["semantic_reviews"][0]["reviewed_output"]["concepts"][0].update(title="altered"),
            lambda x: x["model_calls"][-1]["request_context"].update(revision_count=True),
            lambda x: x["model_calls"][-1].update(raw_response="{}"),
            lambda x: x["semantic_reviews"][0]["report"].update(questions=["altered"]),
            lambda x: x["semantic_reviews"][0]["decision"].update(action="accept"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = deepcopy(self.execution)
                mutation(altered)
                with self.assertRaises(ValueError):
                    REPLAY["replay_execution"](altered)

    def test_legacy_reconstruction_cannot_use_failed_later_retry_to_repair_original_quote(self):
        execution = read(LEGACY / "normal.json")
        original = REPLAY["replay_execution"](execution)
        execution["model_calls"][-1]["generated"]["data"]["result"]["concepts"][0]["title"] = "altered later retry"
        self.assertEqual(REPLAY["replay_execution"](execution), original)
        # Changing the successful generation that preceded review must fail its full output hash.
        execution["model_calls"][2]["generated"]["data"]["result"]["concepts"][0]["title"] = "altered original"
        with self.assertRaises(ValueError):
            REPLAY["replay_execution"](execution)

    def test_missing_token_measurements_are_null_and_failed_calls_are_counted(self):
        execution = read(LEGACY / "normal.json")
        replay = REPLAY["replay_execution"](execution)
        self.assertEqual(replay["recorded_model_calls"], 6)
        self.assertEqual(replay["recorded_token_totals_including_failed_calls"],
                         {"prompt_eval_count": 13479, "eval_count": 9008})
        del execution["model_calls"][-1]["metadata"]["eval_count"]
        replay = REPLAY["replay_execution"](execution)
        self.assertIsNone(replay["recorded_token_totals_including_failed_calls"]["eval_count"])
        self.assertEqual(replay["recorded_model_calls"], 6)

    def test_combined_report_retains_nine_runs_all_calls_and_actual_source_hashes(self):
        paths = sorted(path for path in LEGACY.glob("*.json") if path.name != "summary.json") + [WORKSPACE]
        replay = REPLAY["replay_files"](paths)
        self.assertEqual(len(replay["executions"]), 9)
        self.assertEqual(sum(record["recorded_model_calls"] for record in replay["executions"]), 39)
        self.assertEqual(sum(record["review_calls"] for record in replay["executions"]), 7)
        self.assertEqual(replay["new_model_calls"], 0)
        self.assertFalse(replay["baseline_comparison_complete"])
        self.assertTrue(all(len(source["sha256"]) == 64 for source in replay["sources"]))
        self.assertEqual([record["run_id"] for record in replay["executions"][-2:]],
                         [self.workspace[name]["run"]["id"] for name in ("first", "second")])
        with self.assertRaises(ValueError):
            REPLAY["replay_files"]([WORKSPACE, WORKSPACE])

    def test_cli_never_overwrites_original_or_prior_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("preserved", encoding="utf-8")
            command = [sys.executable, "-X", "utf8", str(SCRIPT), "--record", str(WORKSPACE), "--output", str(output)]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(b"Use a fresh output file", completed.stderr)
            self.assertEqual(output.read_text("utf-8"), "preserved")
            self.assertEqual(read(WORKSPACE), self.workspace)


if __name__ == "__main__":
    unittest.main()
