"""Field isolation on retained real sources and actual normal-r2 model wording.

The item below is a draft snapshot of the 2026-10-07 normal-r2 output, including
its independently reported mistakes. Stub patches test transport/contract
boundaries only; they never represent accepted semantic quality or new reviews.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.errors import DomainError
from lgax_core.public_planning import PublicPlanner, source_facts
from lgax_core.public_repair import repair_public_brief, validate_feedback

PACK = (Path(__file__).resolve().parents[1] / "data/research/r8-public-official-expansion-20261007"
        / "bundles/dishwasher.development.research-bundle.json")
REVIEW = "LGE-R8-REVIEW-752651"
MANUAL = "DUE6BGL2E-MANUAL-D12"


def observed_draft(bundle):
    # Text copied from actual normal-r2 output; this snapshot intentionally
    # preserves the false cleaning-function attribution for repair regression.
    problem = {"id": "problem-1", "title": "사용 중 발생하는 물비린냄새로 인한 재사용 중단",
               "description": "1개월 사용 후 컵과 그릇에서 물비린내가 발생하여 식기세척기를 3개월간 사용 후 다시 손세척으로 전환함.",
               "source_ids": [REVIEW], "counter_source_ids": [],
               "scope_caveat": "구매 모델이 명시되지 않아 특정 SKU의 결함으로 확정할 수 없음. '회전날개 청소' 언급은 해당 모델의 기능 존재를 시사하나, 냄새 원인은 미확인임."}
    comparison = {"id": "comparison-1", "problem_id": "problem-1", "product": "LG DUE6BGL2E",
                  "existing_response": "회전날개 청소 기능 언급 및 식기 배열 안내 제공",
                  "remaining_burden": "1개월 사용 후 컵/그릇에서 물비린냄새 발생으로 재사용 중단 및 손세척 전환",
                  "source_ids": [REVIEW, MANUAL],
                  "comparison_limits": ["구매 모델이 명시되지 않아 특정 SKU의 결함으로 확정할 수 없음", "냄새 원인은 미확인임"]}
    after = ["냄새 발생 시점에 즉시 '냄새 원인 진단' 메뉴를 통해 잔류물 위치를 확인함",
             "진단 결과에 따라 필터 및 배수구 청소 절차를 안내받음",
             "청소 후 냄새 제거 여부를 확인하고 재사용 여부를 결정함"]
    concept = {"id": "concept-1", "title": "냄새 원인 진단 및 잔류물 제거 안내 강화", "problem_ids": ["problem-1"],
               "target_user": "다리가 아파 설거지를 편하게 하고자 식기세척기를 구매한 사용자",
               "use_context": "1개월 사용 후 컵과 그릇에서 물비린냄새가 느껴지는 상황",
               "before_steps": ["식기세척기 사용 후 컵과 그릇에서 물비린냄새를 감지함",
                                "회전날개 청소 기능을 수행했으나 냄새가 지속됨", "식기세척기 사용을 중단하고 손세척로 전환함"],
               "after_steps": deepcopy(after),
               "mechanism": "냄새 발생 시점을 기준으로 잔류물 축적 위치를 추정하고, 해당 부위의 청소 절차를 단계별로 안내하는 가상 시나리오",
               "proposed_changes": deepcopy(after), "source_ids": [REVIEW, MANUAL],
               "assumptions": ["냄새의 원인이 잔류물 축적에 있을 수 있다는 가설", "진단 메뉴가 냄새 원인을 정확히 식별할 수 있다는 가설"],
               "validation_questions": ["냄새 발생 시점에 잔류물이 실제로 축적되었는지 확인 가능한가?",
                                        "진단 메뉴가 냄새 원인을 정확히 식별할 수 있는가?"],
               "visual_scenes": [{"title": "냄새 원인 진단 화면", "before": "사용자가 컵에서 물비린냄새를 느끼고 불만을 표출함",
                                  "after": "사용자가 진단 메뉴를 통해 잔류물 위치를 확인하고 청소 절차를 안내받음"},
                                 {"title": "청소 절차 안내 화면", "before": "사용자가 회전날개 청소만 수행하고 냄새가 지속됨",
                                  "after": "사용자가 필터 및 배수구 청소 절차를 단계별로 안내받음"}], "status": "draft"}
    return {"schema_version": "1.0", "brief_id": "TEST-ONLY-observed-normal-r2", "run_id": "TEST-ONLY-r2-run",
            "bundle_id": bundle["bundle_id"], "revision": 0, "previous_brief_id": None, "status": "partial",
            "product_group": bundle["product_group"], "analysis_scope": bundle["analysis_scope"],
            "goal": "실제 고객 자료에서 아직 남은 사용 부담을 발견하고 구체적인 개선 경험을 기획하기",
            "constraints": ["기존 기능을 새로운 발명으로 제안하지 않기"],
            "problems": [problem], "comparisons": [comparison], "concepts": [concept], "source_facts": source_facts(bundle),
            "uncertainties": ["냄새 원인은 미확인임"], "summaries": {"positive": [], "negative": [], "mixed": []},
            "relations": [{"from_id": REVIEW, "to_id": "problem-1", "relation": "supports", "source_ids": [REVIEW], "inferred": True},
                          {"from_id": "problem-1", "to_id": "concept-1", "relation": "proposes",
                           "source_ids": [REVIEW, MANUAL], "inferred": True}],
            "runtime": {"independent_semantic_quality_verified": False,
                        "selected_source_ids": [REVIEW, MANUAL, "LGE-R8-REVIEW-800073"]}}


def request(kind="Comparison", fields=None):
    return {"item_kind": kind, "item_id": kind.lower() + "-1", "fields": fields or ["existing_response"],
            "message": "사용자의 관리 행동은 제품 기능이 아니며 청소와 냄새 발생의 전후 순서는 미확인입니다. 지적된 필드만 수정하세요."}


class PublicRepairTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        self.previous = observed_draft(self.bundle)

    def test_complete_feedback_and_snapshot_validation_precede_every_model_call(self):
        invalid = [[], [request(), request()], [request(fields=["id"])], [request(fields=["existing_response"] * 2)],
                   [{**request(), "message": "a" * 501}], [{**request(), "extra": "no"}],
                   [{**request(), "item_id": "missing"}], [request()] * 5,
                   [{**request(), "item_kind": "Unknown"}], [request("Concept", ["problem_ids"])]]
        calls = []
        planner = PublicPlanner(lambda prompt, schema: calls.append(prompt))
        for feedback in invalid:
            with self.subTest(feedback=feedback), self.assertRaises(ValueError):
                planner.repair(self.bundle, self.previous, feedback)
        for key, value in (("bundle_id", "other"), ("analysis_scope", "exact_model"),
                           ("previous_brief_id", "unexpected-parent"), ("source_facts", [])):
            previous = deepcopy(self.previous)
            previous[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                planner.repair(self.bundle, previous, [request()])
        self.assertEqual(calls, [])

    def test_patch_preserves_unrequested_items_fields_facts_and_parent_while_filtering_only_removed_relations(self):
        before = deepcopy(self.previous)
        calls = []
        new_sources = [REVIEW, "LGE-R8-REVIEW-800073"]

        def contract_patch(prompt, schema):
            calls.append((prompt, schema))
            return {"patch": {"source_ids": new_sources, "status": "needs_sources"}}

        feedback = [request("Concept", ["source_ids", "status"])]
        feedback[0]["message"] += " 출처 선택 경계 검사에 LGE-R8-REVIEW-800073을 명시적으로 포함합니다."
        result = PublicPlanner(contract_patch).repair(self.bundle, self.previous, feedback)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["problems"], before["problems"])
        self.assertEqual(result["comparisons"], before["comparisons"])
        for key, value in before["concepts"][0].items():
            if key not in {"source_ids", "status"}:
                self.assertEqual(result["concepts"][0][key], value)
        self.assertEqual(result["relations"][0], before["relations"][0])
        expected = deepcopy(before["relations"][1])
        expected["source_ids"] = [REVIEW]
        self.assertEqual(result["relations"][1], expected)  # A new source is never added to the edge.
        self.assertEqual(result["source_facts"], before["source_facts"])
        self.assertEqual(result["summaries"], before["summaries"])
        self.assertEqual(result["constraints"], before["constraints"])
        self.assertEqual(result["goal"], before["goal"])
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["previous_brief_id"], before["brief_id"])
        self.assertNotEqual(result["brief_id"], before["brief_id"])
        self.assertEqual(self.previous, before)
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "accepted")
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])
        self.assertEqual(result["runtime"]["execution_kind"], "public_research_field_repair")
        self.assertIn("관리 행동은 제품의 자동 청소 기능이 아닙니다", calls[0][0])
        self.assertIn("조치 전후 순서와 실패 여부를 만들지", calls[0][0])
        self.assertIn("공식 관리 근거 없이 청소·분해 절차를 만들거나", calls[0][0])
        self.assertEqual(calls[0][1]["properties"]["patch"]["required"], ["source_ids", "status"])

    def test_bad_patch_is_never_retried_and_never_deletes_the_original_item(self):
        for patch in ({"existing_response": "changed", "id": "changed"},
                      {"source_ids": ["unknown-source"]},
                      {"status": "supported"},
                      {"after_steps": ["새 센서를 탑재하여 잔류물 위치를 확인함"]}):
            kind = "Comparison" if "existing_response" in patch else "Concept"
            fields = [field for field in patch if field != "id"]
            previous = deepcopy(self.previous)
            previous["constraints"].append("하드웨어 변경 불가")
            calls = []

            def rejected_patch(prompt, schema, observed=calls, response=patch):
                observed.append(prompt)
                return {"patch": response}

            with self.subTest(patch=patch):
                result = repair_public_brief(rejected_patch, self.bundle, previous, [request(kind, fields)])
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["problems"], previous["problems"])
                self.assertEqual(result["comparisons"], previous["comparisons"])
                self.assertEqual(result["concepts"], previous["concepts"])
                self.assertEqual(result["relations"], previous["relations"])
                self.assertEqual(result["status"], "needs_sources")
                self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "failed")
                self.assertTrue(result["runtime"]["item_issues"])

    def test_one_failed_item_does_not_undo_another_patch_or_expose_provider_causes(self):
        calls = []
        corrected = "고객은 회전날개 등을 관리하며 사용했다고 진술함. 공식 발췌는 식기 배열만 안내하며 냄새 해결 여부는 미확인임."

        def partly_unavailable(prompt, schema):
            calls.append(prompt)
            if len(calls) == 1:
                return {"patch": {"existing_response": corrected}}
            raise DomainError("MODEL_UNAVAILABLE", "private-provider-message", {
                "reason": "timeout", "endpoint": "http://127.0.0.1:18875/private", "token": "private-token"})

        feedback = [request(), request("Concept", ["before_steps"])]
        result = repair_public_brief(partly_unavailable, self.bundle, self.previous, feedback)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["comparisons"][0]["existing_response"], corrected)
        self.assertEqual(result["concepts"], self.previous["concepts"])
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertEqual([row["status"] for row in result["runtime"]["repair_outcomes"]], ["accepted", "failed"])
        record = result["runtime"]["model_calls"][1]
        self.assertEqual(record["error_code"], "MODEL_UNAVAILABLE")
        self.assertEqual(record["error_reason"], "timeout")
        for private in ("private-provider-message", "127.0.0.1", "private-token"):
            self.assertNotIn(private, json.dumps(result))
        validate_feedback(self.bundle, self.previous, feedback)

    def test_repair_context_uses_only_item_sources_and_explicit_named_catalog_source(self):
        # The actual repaired concept cites only the smell review; the earlier
        # run also selected D12 and an unrelated positive review. Reusing that
        # old selection must not silently reintroduce those sources.
        previous = deepcopy(self.previous)
        previous["concepts"][0]["source_ids"] = [REVIEW]
        previous["relations"][1]["source_ids"] = [REVIEW]
        self.assertIn(MANUAL, previous["runtime"]["selected_source_ids"])
        for explicit in (False, True):
            calls = []

            def context_probe(prompt, schema, observed=calls):
                observed.append(json.loads(prompt.split("분석할 데이터(JSON):\n", 1)[1]))
                return {"patch": {"status": "needs_sources"}}

            feedback = [request("Concept", ["status"])]
            if explicit:
                feedback[0]["message"] += f" 공식 발췌 {MANUAL}도 함께 확인하세요."
            with self.subTest(explicit=explicit):
                result = repair_public_brief(context_probe, self.bundle, previous, feedback)
                expected = [REVIEW, MANUAL] if explicit else [REVIEW]
                self.assertEqual([source["source_id"] for source in calls[0]["sources"]], expected)
                self.assertEqual(result["runtime"]["selected_source_ids"], sorted(expected))
                self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "accepted")
                self.assertEqual(result["source_facts"], source_facts(self.bundle))
                for source in calls[0]["sources"]:
                    original = next(row for row in self.bundle["sources"] if row["source_id"] == source["source_id"])
                    self.assertEqual(source["text"], original["text"])
                    self.assertEqual(source["facts"], original["facts"])


if __name__ == "__main__":
    unittest.main()
