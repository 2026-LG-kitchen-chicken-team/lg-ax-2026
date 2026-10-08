"""Offline regression of WEB's original W1 response and copied revision fields.

The revision fixture below is explicitly a TEST ONLY reconstruction, not the
unreceived full revision response. Caller stubs prove guards and item isolation,
never model quality, deployment or acceptance.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.public_planning import PublicPlanner, source_facts
from lgax_core.public_repair import repair_public_brief

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evals/core-manual-quality/20261008/r9-web-w1-residuals"


class PublicHardwareConstraintTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ARTIFACT / "run-5ccd95da.job-response.json").read_text())["result"]
        self.revision_fields = json.loads((ARTIFACT / "results.json").read_text())["runs"][1]
        self.bundle = json.loads((ROOT / "data/research/r9-public-runtime-20261008/fridge.research-bundle.json").read_text())
        ids = self.original["runtime"]["user_selected_source_ids"]
        self.bundle["sources"] = [source for source in self.bundle["sources"] if source["source_id"] in ids]
        self.previous = deepcopy(self.original)
        self.previous.update(brief_id="TEST-ONLY-W1-revision-fields", run_id="TEST-ONLY-W1-fixture",
                             source_facts=source_facts(self.bundle))
        self.previous["constraints"] = deepcopy(self.revision_fields["constraints"])
        for field in ("mechanism", "proposed_changes"):
            self.previous["concepts"][0][field] = deepcopy(self.revision_fields[field])

    def feedback(self, fields):
        return [{"item_kind": "Concept", "item_id": "concept-1", "fields": fields,
                 "message": "TEST ONLY: 하드웨어 변경 없이 개선 조건과 구조 변경 충돌 검사"}]

    def invoke(self, constraints, healthy_neighbor=False):
        discovery = {"problems": deepcopy(self.original["problems"]),
                     "summaries": deepcopy(self.original["summaries"])}
        plan = {key: deepcopy(self.original[key]) for key in ("comparisons", "concepts", "uncertainties")}
        if healthy_neighbor:
            healthy = deepcopy(plan["concepts"][0])
            healthy.update(id="TEST-ONLY-neighbor", title="TEST ONLY: 웹 확인 안내",
                           mechanism="고객이 용기와 수납 공간을 확인하는 웹 안내 가설",
                           proposed_changes=["웹 안내 화면 제공"], after_steps=["고객지원에 확인 요청"],
                           visual_scenes=[{"title": "TEST ONLY: 웹 안내", "before": "고객이 확인 요청",
                                           "after": "공식 정보 확인 필요 범위 표시"}])
            plan["concepts"].append(healthy)
        calls = []

        def stub(prompt, schema):
            context = json.loads(prompt.split("분석할 데이터(JSON):\n", 1)[1])
            if "batch" in context:
                calls.append("discover")
                return deepcopy(discovery)
            if "rejected_fields" in context:
                calls.append("repair_fields")
                return {"patch": deepcopy(context["rejected_fields"])}  # Unchanged failed patch.
            calls.append("plan")
            return deepcopy(plan)

        result = PublicPlanner(stub).run(self.bundle, self.original["goal"], constraints)
        return result, calls, plan

    def test_structural_change_is_rejected_without_erasing_healthy_neighbor_or_original_response(self):
        result, calls, original_plan = self.invoke(self.revision_fields["constraints"], healthy_neighbor=True)
        self.assertEqual(calls, ["discover", "plan", "repair_fields"])
        self.assertEqual(len(result["concepts"]), 1)
        self.assertEqual(result["concepts"][0]["mechanism"], original_plan["concepts"][1]["mechanism"])
        self.assertEqual(result["comparisons"], self.original["comparisons"])
        self.assertEqual(result["runtime"]["model_calls"][1]["response"], original_plan)
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 1)
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])

    def test_field_repair_rejects_actual_copied_structural_change_and_preserves_parent(self):
        fields = ["mechanism", "proposed_changes"]
        patch = {field: deepcopy(self.revision_fields[field]) for field in fields}
        before = deepcopy(self.previous)
        result = repair_public_brief(lambda prompt, schema: {"patch": deepcopy(patch)},
                                     self.bundle, self.previous, self.feedback(fields))
        self.assertEqual(result["concepts"], before["concepts"])
        self.assertEqual(result["summaries"], before["summaries"])
        self.assertEqual(result["source_facts"], before["source_facts"])
        self.assertEqual(self.previous, before)
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "failed")
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 1)
        self.assertEqual(result["status"], "needs_sources")
        codes = [issue["code"] for row in result["runtime"]["item_issues"] for issue in row.get("issues", [])]
        self.assertIn("explicit_no_hardware_constraint", codes)

    def test_local_negation_does_not_hide_another_structural_change(self):
        cases = [
            ("냉동실 전면 턱 높이 재설계", False),
            (self.revision_fields["mechanism"], False),
            ("새 부품 추가 없이 냉동실 턱 높이를 재설계한다", False),
            ("턱 높이를 변경하지 않고, 새 센서를 탑재한다", False),
            ("새 센서를 탑재하지 않고 웹 안내를 제공한다", True),
            ("냉동실 턱 높이를 재설계하지 않고 고객지원에 확인 요청한다", True),
            ("기존 턱 구조 변경 없이 웹 안내를 제공한다", True),
            ("부품 추가 불가이며 고객지원에 문의한다", True),
            ("슬라이드 용기 호환성을 확인하는 웹 안내 가설", True),
        ]
        for text, accepted in cases:
            with self.subTest(text=text):
                result = repair_public_brief(lambda prompt, schema, value=text: {"patch": {"after_steps": [value]}},
                                             self.bundle, self.previous, self.feedback(["after_steps"]))
                self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"],
                                 "accepted" if accepted else "failed")
                if not accepted:
                    self.assertEqual(result["concepts"], self.previous["concepts"])

    def test_original_hardware_direction_is_not_banned_without_that_user_constraint(self):
        result, calls, _ = self.invoke(self.original["constraints"])
        self.assertEqual(calls, ["discover", "plan"])
        self.assertEqual(result["concepts"], self.original["concepts"])
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 0)
