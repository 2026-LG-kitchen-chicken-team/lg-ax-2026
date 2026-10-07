"""Generic source provenance on trusted public schemas, no live model calls.

These are prompt/transport regressions; wording compliance is independently
reviewed from a later real output, not certified by an instruction substring.
"""
import json
import unittest
from copy import deepcopy

import test_model_client
from lgax_core.model_client import _schema_field_guide
from lgax_core.prompt_context import PUBLIC_PROVENANCE_GUIDE
from lgax_core.public_planning import INSTRUCTIONS, PublicPlanner
from test_model_client_item_boundary import discovery_schema, planning_schema
from test_public_repair import PACK


class PublicProvenanceGuideTests(unittest.TestCase):
    def test_both_generation_stages_share_provenance_and_explicit_opinion_rules(self):
        self.assertIn(PUBLIC_PROVENANCE_GUIDE, INSTRUCTIONS)
        for schema in (discovery_schema(), planning_schema()):
            before = deepcopy(schema)
            guide, fields = _schema_field_guide(schema)
            self.assertIn("public_source_provenance", fields)
            self.assertIn("public_opinion_classification", fields)
            self.assertIn("제목·요약·비교의 현황·before", guide)
            self.assertIn("해당 필드와 assumptions", guide)
            self.assertIn("별점이나 구매 동기·기대만으로", guide)
            self.assertIn("둘이 동시에 명시된 경험", guide)
            self.assertEqual(schema, before)
        for fragment in ("총 사용 기간을 추가 사용 기간으로", "고객의 추측은 고객의 추측",
                         "가상 before는 그 자리에서 가정", "발췌에 없는 실행 절차"):
            self.assertIn(fragment, INSTRUCTIONS)
        self.assertNotIn("752651", INSTRUCTIONS)
        self.assertNotIn("853593", INSTRUCTIONS)

    def test_schema_annotations_and_unknown_extensions_do_not_activate_public_guidance(self):
        annotation_only = {"type": "object", "description": PUBLIC_PROVENANCE_GUIDE,
                           "properties": {"text": {"type": "string"}}}
        extended = {**discovery_schema(), "description": "untrusted schema extension"}
        for schema in (annotation_only, extended):
            guide, fields = _schema_field_guide(schema)
            self.assertNotIn("public_source_provenance", fields)
            self.assertNotIn("public_opinion_classification", fields)
            self.assertNotIn("요약 분류는 본문의 실제 경험 평가", guide)

    def test_native_prompt_keeps_real_excerpt_full_schema_and_separate_guide_receipt(self):
        bundle = json.loads(PACK.read_text("utf-8"))
        source = next(row for row in bundle["sources"] if row["source_id"] == "LGE-R8-REVIEW-752651")
        before = deepcopy(source)
        context = PublicPlanner(lambda _prompt, _schema: None)._source_context(source)
        prompt = INSTRUCTIONS + "\n분석할 데이터(JSON):\n" + json.dumps({"sources": [context]}, ensure_ascii=False)
        # Protocol-only empty response; it neither fabricates a customer review
        # nor asserts a semantically accepted problem/concept.
        output = {"problems": [], "summaries": {"positive": [], "negative": [], "mixed": []}}
        fixture = test_model_client.ModelClientTests()
        self.addCleanup(fixture.doCleanups)
        client, backend = fixture.client(test_model_client.Backend(response=json.dumps(output)))
        schema = discovery_schema()
        result = client.generate(prompt, schema, test_model_client.MODEL, allow_item_validation=True)
        payload = json.loads(backend.requests[1].content)
        guide, fields = _schema_field_guide(schema)
        self.assertEqual(payload["format"], schema)
        self.assertIn(source["text"].splitlines()[0], payload["prompt"])
        self.assertIn(prompt, payload["prompt"])
        self.assertEqual(result.metadata["schema_field_guide"]["version"], "public_provenance_and_opinion_v1")
        self.assertEqual(result.metadata["schema_field_guide"]["fields"], list(fields))
        self.assertEqual(result.metadata["schema_field_guide"]["characters"], len(guide))
        self.assertEqual(result.metadata["formatted_prompt_utf8_bytes"], len(payload["prompt"].encode("utf-8")))
        self.assertTrue(result.metadata["locally_validated"])
        self.assertEqual(result.data, output)
        self.assertEqual(source, before)
