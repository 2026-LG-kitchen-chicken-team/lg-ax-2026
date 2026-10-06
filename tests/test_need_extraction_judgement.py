"""Need reasoning preserves evidence/unknowns/questions, without fabricating a complaint."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core import DemoStore
from lgax_core.skill_runner import SkillRuntime

ROOT = Path(__file__).resolve().parents[1]


class NeedJudgementTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()
        self.payload = json.loads((ROOT / "skills/need_extract/examples/input.json").read_text("utf-8"))
        self.ids = self.payload["review_evidence_ids"]

    def valid(self):
        return {
            "needs": [],
            "desired_outcomes": [],
            "unresolved": [],
            "review_assessments": [
                {
                    "evidence_id": eid,
                    "polarity": "uncertain",
                    "reason": "원문만으로 현재 사용 불편인지 확인 요청인지 구분할 수 없다.",
                }
                for eid in self.ids
            ],
            "uncertainty_assessments": [
                {
                    "evidence_id": eid,
                    "reason": "현재 사용 조건의 확인이 필요하다.",
                    "missing_information": ["실제 사용 조건"],
                    "questions": ["이 리뷰에서 확인하려는 사용 조건은 무엇인가요?"],
                }
                for eid in self.ids
            ],
            "questions": ["이 리뷰에서 확인하려는 사용 조건은 무엇인가요?"],
        }

    def run_result(self, result):
        runtime = SkillRuntime(self.store)
        runtime.register_handler(
            "need_extract", lambda *_: deepcopy(result), backend_id="test:judgement", execution_kind="fixture"
        )
        return runtime, runtime.execute("need_extract", self.payload)

    def test_valid_uncertain_hold_keeps_all_fields_and_original_review_sources(self):
        result = self.valid()
        before = deepcopy(result)
        runtime, response = self.run_result(result)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["result"], before)
        self.assertEqual(result, before)
        self.assertEqual({e["id"] for e in response["data"]["sources"]}, set(self.ids))
        self.assertEqual(runtime.records[-1]["decision"]["status"], "held")
        for e in response["data"]["sources"]:
            self.assertEqual(e, self.store.get_evidence(e["id"])["data"]["evidence"])

    def test_missing_or_blank_reason_returns_review_id_and_exact_field_feedback(self):
        for value in [None, "", "   "]:
            result = self.valid()
            if value is None:
                result["review_assessments"][0].pop("reason")
            else:
                result["review_assessments"][0]["reason"] = value
            before = deepcopy(result)
            _, response = self.run_result(result)
            self.assertFalse(response["ok"])
            v = response["error"]["details"]["violations"]
            self.assertTrue(
                any(
                    x["code"] == "REVIEW_REASON_MISSING"
                    and x["evidence_id"] == self.ids[0]
                    and x["path"] == "review_assessments/0/reason"
                    for x in v
                )
            )
            self.assertEqual(result, before)

    def test_unknown_fields_and_questions_cannot_be_silently_dropped(self):
        for field in ["reason", "missing_information", "questions"]:
            result = self.valid()
            result["uncertainty_assessments"][0].pop(field)
            _, response = self.run_result(result)
            self.assertFalse(response["ok"])
            self.assertTrue(any(x.get("field") == field for x in response["error"]["details"]["violations"]))

    def test_wrong_review_scope_is_rejected(self):
        result = self.valid()
        result["review_assessments"][0]["evidence_id"] = "MANUAL-001"
        _, response = self.run_result(result)
        self.assertFalse(response["ok"])
        self.assertTrue(
            any(v["code"] == "REVIEW_SCOPE_MISMATCH" for v in response["error"]["details"]["violations"])
        )

    def test_positive_no_need_preserves_reason_and_does_not_invent_pain(self):
        result = self.valid()
        result["uncertainty_assessments"] = []
        result["questions"] = []
        for a in result["review_assessments"]:
            a.update(polarity="positive", reason="원문 판단상 확인된 불편이 없다.")
        runtime, response = self.run_result(result)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["result"]["needs"], [])
        self.assertEqual(runtime.records[-1]["decision"]["status"], "succeeded")

    def test_legacy_metadata_absence_is_not_filled_in(self):
        runtime, response = self.run_result(
            {"needs": [], "desired_outcomes": [], "unresolved": ["자료 미확인"]}
        )
        self.assertTrue(response["ok"], response)
        self.assertNotIn("review_assessments", response["data"]["result"])
        self.assertEqual(runtime.records[-1]["decision"]["status"], "held")

    def test_old_empty_result_has_actionable_model_feedback(self):
        _, response = self.run_result({"needs": [], "desired_outcomes": [], "unresolved": []})
        self.assertFalse(response["ok"])
        details = response["error"]["details"]
        self.assertEqual(details["expected_review_evidence_ids"], self.ids)
        self.assertEqual(details["code"], "EMPTY_NEEDS_WITHOUT_JUDGEMENT")
        self.assertIn("uncertainty_assessments[].questions", details["required_judgement_fields"])

    def test_malformed_ids_return_validation_error_without_crashing(self):
        for target in ["assessment", "need"]:
            result = self.valid()
            if target == "assessment":
                result["review_assessments"][0]["evidence_id"] = {}
            else:
                result["needs"] = [{"evidence_ids": [{}]}]
            _, response = self.run_result(result)
            self.assertFalse(response["ok"], response)
            self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
