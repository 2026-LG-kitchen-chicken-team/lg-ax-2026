"""Artifact assembly only. Actual frozen sources; no accepted or model-generated brief fixture."""
import json
import unittest
from copy import deepcopy

from lgax_core.guides import (
    build_concept_guide,
    build_official_guide,
    build_official_reference_guide,
    render_guide_html,
    render_guide_markdown,
)
from test_public_planning import real_bundle


def contract_only_draft(bundle):
    """Unapproved test-only draft for presentation fields, never evidence of planning quality."""
    return {
        "schema_version": "1.0", "brief_id": "test-artifact-brief", "bundle_id": bundle["bundle_id"],
        "run_id": "test-artifact-run", "revision": 0, "previous_brief_id": None, "status": "needs_sources",
        "product_group": bundle["product_group"], "analysis_scope": bundle["analysis_scope"],
        "goal": "TEST ONLY: 원문과 제안 표시 구분 검사", "constraints": [],
        "problems": [{"id": "test-problem", "title": "TEST ONLY 출처 연결", "description": bundle["sources"][0]["text"],
                      "source_ids": [bundle["sources"][0]["source_id"]], "counter_source_ids": [],
                      "scope_caveat": "TEST ONLY: 의미 판정이나 시장 수요를 검증하지 않음"}],
        "comparisons": [], "concepts": [{
            "id": "test-concept", "title": "TEST ONLY 문서 구성", "problem_ids": ["test-problem"],
            "target_user": "TEST ONLY 사용자", "use_context": "TEST ONLY 출처 조회",
            "before_steps": ["TEST ONLY 기존 화면"], "after_steps": ["TEST ONLY 제안 화면"],
            "mechanism": "TEST ONLY: 표시용 계약 입력이며 실제 제품 제안으로 승인되지 않음", "proposed_changes": [],
            "source_ids": [bundle["sources"][1]["source_id"]], "assumptions": ["TEST ONLY 미확인 가정"],
            "validation_questions": ["TEST ONLY 확인 질문"],
            "visual_scenes": [{"title": "TEST ONLY 장면", "before": "TEST ONLY 현재", "after": "TEST ONLY 제안"}],
            "status": "needs_sources",
        }], "source_facts": [{"source_id": source["source_id"], "facts": deepcopy(source["facts"])}
                             for source in bundle["sources"]], "uncertainties": ["TEST ONLY: 독립 품질 미검증"],
        "summaries": {"positive": [], "negative": [], "mixed": []}, "relations": [],
        "runtime": {"execution_kind": "test_only_artifact_input", "independent_semantic_quality_verified": False,
                    "endpoint": "http://private.example"},
    }


class ResearchGuideTests(unittest.TestCase):
    def setUp(self):
        self.bundle = real_bundle()

    def test_official_guide_preserves_actual_manual_only_and_does_not_rewrite_settings(self):
        guide = build_official_guide(self.bundle, "MW23FDI")
        self.assertEqual(guide["guide_kind"], "official_excerpt")
        self.assertEqual(guide["sources"], [self.bundle["sources"][1]])
        self.assertIsNone(guide["proposal"])
        self.assertIn("발췌", guide["notice"])
        self.assertIn("전체 정식 설명서를 대체하지", guide["notice"])
        self.assertEqual(guide["sources"][0]["facts"], self.bundle["sources"][1]["facts"])
        self.assertEqual(guide["sources"][0]["locator"], self.bundle["sources"][1]["locator"])
        self.assertIn("200 W", render_guide_html(guide))
        self.assertNotIn("100 W", render_guide_html(guide))
        guide["sources"][0]["facts"][0]["text"] = "local artifact edit"
        self.assertNotEqual(guide["sources"][0]["facts"], self.bundle["sources"][1]["facts"])

    def test_missing_model_or_unofficial_manual_is_not_substituted(self):
        for model in ("MW20GDN", "", "UNKNOWN"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                build_official_guide(self.bundle, model)
        changed = deepcopy(self.bundle)
        changed["sources"][1]["url"] = "https://example.com/manual"
        with self.assertRaises(ValueError):
            build_official_guide(changed, "MW23FDI")

    def test_concept_draft_is_separate_and_copies_proposal_and_actual_sources(self):
        brief = contract_only_draft(self.bundle)
        guide = build_concept_guide(self.bundle, brief, "test-concept")
        official = build_official_guide(self.bundle, "MW23FDI")
        self.assertEqual(guide["guide_kind"], "concept_draft")
        self.assertNotEqual(guide["guide_kind"], official["guide_kind"])
        self.assertFalse(guide["independent_quality_verified"])
        self.assertEqual(guide["proposal"], brief["concepts"][0])
        self.assertEqual(guide["sources"], self.bundle["sources"])
        self.assertNotIn("private.example", json.dumps(guide))
        rendered = render_guide_html(guide)
        self.assertIn("가상 제품 기획 설명서 · 초안", rendered)
        self.assertLess(rendered.index("제안하는 사용 과정"), rendered.index("실제 근거 원문 · 제안과 구분"))
        self.assertIn("TEST ONLY 제안 화면", rendered)
        changed = deepcopy(brief)
        changed["source_facts"][1]["facts"][0]["text"] = "not the actual source"
        with self.assertRaises(ValueError):
            build_concept_guide(self.bundle, changed, "test-concept")
        with self.assertRaises(ValueError):
            build_concept_guide(self.bundle, brief, "missing-concept")

    def test_external_proposal_text_is_escaped_in_html_and_markdown(self):
        brief = contract_only_draft(self.bundle)
        brief["concepts"][0]["title"] = '<img src=x onerror="alert(1)">'
        brief["concepts"][0]["after_steps"] = ["</article><script>alert(2)</script>"]
        guide = build_concept_guide(self.bundle, brief, "test-concept")
        for output in (render_guide_html(guide), render_guide_markdown(guide)):
            self.assertNotIn("<img src=x", output)
            self.assertNotIn("<script>", output)
            self.assertIn("&lt;img src=x", output)
            self.assertIn("&lt;/article&gt;&lt;script&gt;", output)
        self.assertEqual(guide["sources"], self.bundle["sources"])

    def test_unconfirmed_model_can_be_an_official_reference_without_becoming_an_exact_model_guide(self):
        changed = deepcopy(self.bundle)
        source = changed["sources"][1]
        source["page_model"] = None
        source["metadata"] = {"applicability": "shared manual; exact SKU unconfirmed",
                              "continuation_pages": [43], "native_unit_caution": "50 7 is not a verified unit"}
        with self.assertRaises(ValueError):
            build_official_guide(changed, "MW23FDI")
        guide = build_official_reference_guide(changed, [source["source_id"]])
        self.assertIsNone(guide["sources"][0]["page_model"])
        self.assertEqual(guide["sources"], [source])
        self.assertFalse(guide["exact_sku_applicability_confirmed"])
        for output in (render_guide_html(guide), render_guide_markdown(guide)):
            self.assertIn("페이지 모델 미확인", output)
            self.assertIn("shared manual; exact SKU unconfirmed", output)
            self.assertIn("자료에 표시된 참조 쪽 · 같은 절/단계 미확인", output)
            self.assertNotIn("연속 페이지:", output)
            self.assertIn("같은 작업의 순서나 이어지는 단계로 확정하지 않습니다", output)
            self.assertIn("50 7 is not a verified unit", output)

    def test_official_question_answer_roles_and_selection_are_not_silently_substituted(self):
        changed = deepcopy(self.bundle)
        source = changed["sources"][1]
        source.update({"source_type": "qa", "source_role": "customer_question"})
        with self.assertRaises(ValueError):
            build_official_reference_guide(changed, [source["source_id"]])
        source["source_role"] = "official_answer"
        guide = build_official_reference_guide(changed, [source["source_id"]])
        self.assertEqual(guide["sources"], [source])
        self.assertIn("작성 역할: 공식 답변", render_guide_markdown(guide))
        for ids in ([], ["missing"], [source["source_id"], "missing"], [source["source_id"]] * 2,
                    [changed["sources"][0]["source_id"]]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                build_official_reference_guide(changed, ids)

    def test_official_reference_domain_and_escaped_metadata_are_checked(self):
        changed = deepcopy(self.bundle)
        source = changed["sources"][1]
        source["url"] = "https://lge.com.example.com/manual"
        with self.assertRaises(ValueError):
            build_official_reference_guide(changed, [source["source_id"]])
        source["url"] = self.bundle["sources"][1]["url"]
        source["metadata"] = {"applicability": "<script>alert(2)</script>"}
        guide = build_official_reference_guide(changed, [source["source_id"]])
        for output in (render_guide_html(guide), render_guide_markdown(guide)):
            self.assertNotIn("<script>", output)
            self.assertIn("&lt;script&gt;", output)
        guide["sources"][0]["metadata"]["applicability"] = "local edit"
        self.assertEqual(source["metadata"]["applicability"], "<script>alert(2)</script>")


if __name__ == "__main__":
    unittest.main()
