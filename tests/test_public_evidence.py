"""Typed output stubs anchored to collected reviews and the actual P49 excerpt.

These exercise provenance/repair boundaries, not actual-model semantic quality.
No customer source or source fact is authored by these fixtures.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.public_evidence import (
    HYPOTHESIS_LABEL,
    PublicEvidence,
    affected_feedback,
)
from lgax_core.public_planning import PublicPlanner, source_facts
from lgax_core.public_repair import repair_public_brief
from test_public_repair import MANUAL, observed_draft

PACK = Path(__file__).resolve().parents[1] / "data/research/r9-public-runtime-20261008/dishwasher.research-bundle.json"
ODOR = "LGE-R8-REVIEW-752651"
MIXED = "LGE-R8-REVIEW-853593"
POSITIVE = "LGE-R8-REVIEW-800073"
INSTALL = "LGE-R8-REVIEW-645400"
P49 = "D2-DUE-CARE-DW-ODOR-DEVICE-P49"


def span(source, quote, start_at=0):
    start = source["text"].index(quote, start_at)
    return {"quote": quote, "start": start, "end": start + len(quote)}


def claim(source, claim_id, quote, *, kind="observation", polarity="unknown", actor=None,
          role="event", value=None):
    return {"claim_id": claim_id, "source_id": source["source_id"], "kind": kind,
            "anchor": span(source, quote), "actor_anchor": span(source, actor) if actor else None,
            "event_or_duration_role": role, "approximate_value": span(source, value) if value else None,
            "order_anchor": None, "order_status": "unknown", "experienced_polarity": polarity}


class PublicEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(PACK.read_text("utf-8"))
        # The six collected sources selected in PM's normal/condition pair.
        selected = {ODOR, MIXED, POSITIVE, INSTALL, P49, "D2-DUE-CARE-DW-ODOR-FISHY-P49"}
        self.bundle["sources"] = [row for row in self.bundle["sources"] if row["source_id"] in selected]
        self.catalog = {row["source_id"]: row for row in self.bundle["sources"]}
        odor, mixed, positive, install = [self.catalog[eid] for eid in (ODOR, MIXED, POSITIVE, INSTALL)]
        self.records = {"customer_claims": [
            claim(odor, "wife", "집사람이 다리가 많이 아파해서", actor="집사람"),
            claim(odor, "hope", "설거지라도 좀 편하게 했으면 하는 생각에", kind="expectation"),
            claim(odor, "maintenance", "1개월정도 사용하고 회전날개등 깨끗하게 청소하고 사용한다고했는데",
                  role="maintenance_mention", value="1개월정도"),
            claim(odor, "odor", "어느 순간부터 컵, 그릇등에서 물비린내가 나기 시작했습니다.", polarity="negative"),
            claim(odor, "total", "3달 정도 사용하고는 다시 손으로 설거지하고", role="total_use", value="3달 정도"),
            claim(mixed, "convenience", "식세기 처음 써 보는데 너무 편해요.", polarity="positive"),
            claim(mixed, "preparation", "린스랑 세제랑 소금까지 넣어야 된다는 건 좀 당황스럽지만", polarity="negative"),
            claim(mixed, "performance", "건조도 잘 되고 성능은 좋은 것 같습니다", polarity="positive"),
            claim(positive, "satisfied", positive["text"], polarity="positive"),
            claim(install, "intent", "기사가 설치하기 싫은것 같아", kind="customer_inference", actor="기사"),
            claim(install, "return", "반송함.", polarity="negative"),
        ], "official_actions": [self.action()]}

    def action(self):
        source = self.catalog[P49]
        quote = source["text"][source["text"].index("세척조에 잔수가 많나요?"):source["text"].index("제품 내부의 바닥")]
        return {"claim_id": "drain", "source_id": P49, "kind": "conditional_official_action",
                "anchor": span(source, quote), "prerequisite": span(source, "80 ml ~ 100 ml보다 많은 경우"),
                "ordered_steps": [span(source, "제품의 전원을 켜고"), span(source, "전원 버튼을 3초간 눌러"),
                                  span(source, "취소\r\n옵션을 선택하면")],
                "threshold": {"anchor": span(source, "80 ml ~ 100 ml보다 많은 경우"),
                              "comparator_anchor": span(source, "보다 많은 경우"),
                              "unit_anchor": span(source, "ml"), "comparator": "gt"},
                "referenced_chapter": span(source, "제품 관리하기의 세척조 청소하기", source["text"].index("세척조에 잔수가 많나요?"))}

    def ledger(self, records=None):
        return PublicEvidence(self.bundle, records or self.records)

    def test_actor_time_roles_and_unknown_order_are_literal_not_medical_or_temporal_normalization(self):
        before = deepcopy(self.bundle)
        ledger = self.ledger()
        self.assertEqual(ledger.audit["issues"], [])
        context = ledger.consultation_context(ODOR)
        rows = {row["claim_id"]: row for row in context["observations"]}
        self.assertEqual(rows["wife"]["actor_anchor"]["quote"], "집사람")
        self.assertEqual(rows["maintenance"]["approximate_value"]["quote"], "1개월정도")
        self.assertEqual(rows["total"]["approximate_value"]["quote"], "3달 정도")
        self.assertTrue(all(row["order_status"] == "unknown" for row in rows.values()))
        self.assertFalse(context["customer_confirmed"])
        self.assertEqual(context["source_ids"], [ODOR])
        self.assertEqual(self.bundle, before)
        self.assertEqual(source_facts(self.bundle), source_facts(before))

    def test_actual_experience_projection_keeps_mixed_sides_and_does_not_count_hope_or_intent(self):
        projection = self.ledger().summary_projection({ODOR, MIXED, POSITIVE, INSTALL})
        summaries = projection["summaries"]
        self.assertEqual([row["source_ids"] for row in summaries["positive"]], [[POSITIVE]])
        self.assertEqual([row["source_ids"] for row in summaries["mixed"]], [[MIXED]])
        self.assertIn("너무 편해요", summaries["mixed"][0]["text"])
        self.assertIn("당황스럽지만", summaries["mixed"][0]["text"])
        self.assertNotIn("설거지라도", json.dumps(summaries, ensure_ascii=False))
        self.assertNotIn("싫은것", json.dumps(summaries, ensure_ascii=False))
        self.assertFalse(projection["classification_approved"])

    def test_wrong_actor_span_cross_source_and_unanchored_order_reject_locally(self):
        bad = deepcopy(self.records)
        bad["customer_claims"][0]["actor_anchor"]["quote"] = "구매자 관절 질환"
        bad["customer_claims"][2]["order_status"] = "explicit_anchor"
        bad["customer_claims"][3]["source_id"] = POSITIVE
        ledger = self.ledger(bad)
        self.assertEqual(len(ledger.audit["issues"]), 3)
        self.assertEqual(len(ledger.audit["claims"]), 9)
        self.assertEqual(ledger.summary_projection({MIXED})["summaries"]["mixed"][0]["source_ids"], [MIXED])
        self.assertEqual(ledger.audit["raw_candidates"], bad)
        self.assertFalse(ledger.audit["semantic_quality_verified"])

    def test_hope_cannot_be_experienced_positive_and_invalid_record_shapes_are_private(self):
        bad = deepcopy(self.records)
        bad["customer_claims"][1]["experienced_polarity"] = "positive"
        bad["customer_claims"].extend([{"claim_id": [], "source_id": []}, "invalid"])
        ledger = self.ledger(bad)
        self.assertEqual(len(ledger.audit["issues"]), 3)
        self.assertEqual(ledger.summary_projection({ODOR})["unclassified_source_ids"], [ODOR])
        broken = deepcopy(self.records)
        broken["customer_claims"].append(deepcopy(broken["customer_claims"][0]))
        self.assertEqual(sum("ambiguous_claim_id" in row["codes"] for row in self.ledger(broken).audit["issues"]), 2)

    def test_p49_reference_preserves_condition_power_sequence_version_and_chapter_without_sku_approval(self):
        ledger = self.ledger()
        text = ledger.official_reference("drain")
        for literal in ("80 ml ~ 100 ml보다 많은 경우", "제품의 전원을 켜고", "전원 버튼을 3초간 눌러",
                        "취소\r\n옵션을 선택하면", "MFL71959117 Rev.07_030626", "shared DUE6 manual", "세척조 청소하기"):
            self.assertIn(literal, text)
        self.assertIn("실행 안내 아님", text)
        self.assertIn("실행 곤란", text)
        self.assertIsNone(next(row for row in ledger.audit["claims"] if row["claim_id"] == "drain")["provenance"]["purchased_model"])

    def test_out_of_order_official_step_and_customer_official_role_mix_are_rejected(self):
        bad = deepcopy(self.records)
        bad["official_actions"][0]["ordered_steps"].reverse()
        ledger = self.ledger(bad)
        self.assertIn("procedure_order_not_source_order", ledger.audit["issues"][0]["codes"])
        bad = deepcopy(self.records)
        bad["customer_claims"][0]["source_id"] = P49
        self.assertIn("customer_claim_requires_customer_source", self.ledger(bad).audit["issues"][0]["codes"])
        with self.assertRaises(ValueError):
            self.ledger().consultation_context(P49)

    def previous(self):
        previous = observed_draft(self.bundle)
        for collection in ("comparisons", "concepts", "relations"):
            for row in previous[collection]:
                row["source_ids"] = [P49 if eid == MANUAL else eid for eid in row["source_ids"]]
        previous["runtime"]["item_issues"] = [{"kind": "Problem", "item_id": "problem-1", "field": "description",
                                               "code": "independently_reported_time_misreading"}]
        return previous

    def bindings(self):
        return [
            {"item_kind": "Comparison", "item_id": "comparison-1", "field": "existing_response", "claim_ids": ["drain"], "mode": "official_reference"},
            {"item_kind": "Concept", "item_id": "concept-1", "field": "before_steps", "claim_ids": ["odor"], "mode": "observation"},
            {"item_kind": "Concept", "item_id": "concept-1", "field": "target_user", "claim_ids": ["wife"], "mode": "observation"},
            {"item_kind": "Concept", "item_id": "concept-1", "field": "visual_scenes.1.before", "claim_ids": ["maintenance"], "mode": "observation"},
        ]

    def test_two_local_repairs_preserve_healthy_fields_and_keep_other_display_and_problem_issues_visible(self):
        ledger, previous, bindings = self.ledger(), self.previous(), self.bindings()
        before = deepcopy(previous)
        calls = []

        def caller(prompt, schema):
            calls.append((prompt, schema))
            if "existing_response" in schema["properties"]["patch"]["properties"]:
                return {"patch": {"existing_response": ledger.official_reference("drain")}}
            return {"patch": {"before_steps": [self.records["customer_claims"][3]["anchor"]["quote"]]}}

        issues = ledger.field_issues(previous, bindings)
        feedback = affected_feedback(issues[:2], message="지적된 원문 연결 필드만 수정합니다.")
        result = repair_public_brief(caller, self.bundle, previous, feedback, evidence=ledger, field_claims=bindings)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 2)
        self.assertEqual([row["status"] for row in result["runtime"]["repair_outcomes"]], ["accepted", "accepted"])
        self.assertEqual({row["path"] for row in result["runtime"]["residual_field_claim_issues"]}, {"target_user", "visual_scenes.1.before"})
        self.assertEqual(result["status"], "partial")
        for key in ("problems", "summaries", "relations", "source_facts"):
            self.assertEqual(result[key], before[key])
        self.assertEqual(result["runtime"]["inherited_item_issues"], before["runtime"]["item_issues"])
        self.assertEqual(result["previous_brief_id"], before["brief_id"])
        self.assertEqual(result["revision"], 1)
        self.assertEqual(previous, before)
        self.assertEqual(result["concepts"][0]["target_user"], before["concepts"][0]["target_user"])
        again = repair_public_brief(caller, self.bundle, result, feedback, evidence=ledger, field_claims=bindings)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(row["status"] == "failed" for row in again["runtime"]["repair_outcomes"]))

    def test_bad_patch_keeps_original_item_and_inference_cannot_be_displayed_as_observed_history(self):
        ledger, previous = self.ledger(), self.previous()
        feedback = [{"item_kind": "Concept", "item_id": "concept-1", "fields": ["before_steps"], "message": "원문 관찰만 남깁니다."}]
        result = repair_public_brief(lambda prompt, schema: {"patch": {"before_steps": ["청소 실패 후 재발"]}},
                                     self.bundle, previous, feedback, evidence=ledger, field_claims=self.bindings())
        self.assertEqual(result["concepts"], previous["concepts"])
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "failed")
        candidate = deepcopy(previous)
        candidate["concepts"][0]["source_ids"].append(INSTALL)
        candidate["concepts"][0]["before_steps"] = ["기사가 설치하기 싫은것 같아"]
        binding = {"item_kind": "Concept", "item_id": "concept-1", "field": "before_steps", "claim_ids": ["intent"], "mode": "observation"}
        self.assertIn("non_observation_as_customer_history", ledger.field_issues(candidate, [binding])[0]["codes"])

    def test_hypothetical_scene_needs_local_label_and_assumptions_and_declared_detailed_action_is_held(self):
        ledger, candidate = self.ledger(), self.previous()
        binding = {"item_kind": "Concept", "item_id": "concept-1", "field": "visual_scenes.0.after", "claim_ids": ["odor"], "mode": "hypothesis"}
        self.assertTrue(ledger.field_issues(candidate, [binding]))
        candidate["concepts"][0]["visual_scenes"][0]["after"] = HYPOTHESIS_LABEL + "고객이 확인한 기록을 상담에 전달한다."
        self.assertEqual(ledger.field_issues(candidate, [binding]), [])
        candidate["concepts"][0]["assumptions"] = []
        self.assertTrue(ledger.field_issues(candidate, [binding]))
        operational = self.bindings()[0] | {"mode": "conditional_action"}
        self.assertIn("operational_applicability_requires_owner_review", ledger.field_issues(candidate, [operational])[0]["codes"])

    def test_bundle_change_or_bad_binding_blocks_before_any_model_call(self):
        ledger, calls = self.ledger(), []
        planner = PublicPlanner(lambda prompt, schema: calls.append(prompt), evidence=ledger)
        changed = deepcopy(self.bundle)
        changed["sources"][0]["text"] += " "
        with self.assertRaises(ValueError):
            planner.run(changed, "기획", [])
        with self.assertRaises(ValueError):
            planner.repair(self.bundle, self.previous(), affected_feedback(
                ledger.field_issues(self.previous(), self.bindings())[:1], message="수정"),
                field_claims=[self.bindings()[0] | {"field": "id"}])
        self.assertEqual(calls, [])

    def test_opt_in_context_preserves_original_schema_and_keeps_candidate_projection_separate(self):
        ledger, calls = self.ledger(), []

        def caller(prompt, schema):
            calls.append((prompt, schema))
            return {"problems": [], "summaries": {"positive": [], "negative": [], "mixed": []}}

        planner = PublicPlanner(caller, evidence=ledger, max_prompt_characters=12000)
        result = planner.run(self.bundle, "실제 자료에서 문제 발견", [])
        self.assertTrue(calls)
        self.assertEqual(set(calls[0][1]["properties"]), {"problems", "summaries"})
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertEqual(result["summaries"], {"positive": [], "negative": [], "mixed": []})
        self.assertFalse(result["runtime"]["summary_projection_applied"])
        self.assertFalse(result["runtime"]["private_evidence"]["semantic_quality_verified"])


if __name__ == "__main__":
    unittest.main()
