"""Contract wording cannot change schema, evidence, output or finite budgets."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

import test_model_client as fixture
from lgax_core.errors import DomainError
from lgax_core.model_client import StructuredModelClient
from lgax_core.prompt_context import model_context


ENUMS = {
    "polarity": ["complaint", "positive", "conflicting", "irrelevant", "uncertain"],
    "duplication": ["distinct", "duplicate", "uncertain"],
    "support_status": ["supported", "unsupported", "insufficient_evidence"],
    "support_basis": ["explicit_supported", "explicit_unsupported", "unmentioned", "conflicting"],
    "resolution": ["resolved", "remaining", "unknown"],
}
SCHEMA = {
    "type": "object", "properties": {key: {"enum": values} for key, values in ENUMS.items()},
    "required": list(ENUMS), "additionalProperties": False,
}
# These schema-valid labels are intentionally not repaired by the adapter.
OUTPUT = {"polarity": "positive", "duplication": "duplicate", "support_status": "supported",
          "support_basis": "explicit_supported", "resolution": "remaining"}


class SchemaFieldGuideTests(unittest.TestCase):
    def client(self, backend=None, **settings):
        client, backend = fixture.ModelClientTests().client(backend, **settings)
        self.addCleanup(client.close)
        return client, backend

    def generated(self, schema=SCHEMA, output=OUTPUT, kind="ollama", prompt="원문 자료는 요청에만 있습니다."):
        client, backend = self.client(fixture.Backend(kind, response=json.dumps(output, ensure_ascii=False)),
                                      **({"api_mode": "chat"} if kind == "chat" else {}))
        frozen = copy.deepcopy(schema)
        result = client.generate(prompt, schema, fixture.MODEL)
        body = json.loads(backend.requests[1].content)
        formatted = body["messages"][0]["content"] if kind == "chat" else body["prompt"]
        self.assertEqual(schema, frozen)
        self.assertEqual(result.data, output)
        self.assertTrue(formatted.endswith("요청:\n" + prompt))
        self.assertEqual(result.metadata["formatted_prompt_characters"], len(formatted))
        self.assertEqual(result.metadata["formatted_prompt_utf8_bytes"], len(formatted.encode()))
        self.assertEqual(result.metadata["formatted_prompt_sha256"], hashlib.sha256(formatted.encode()).hexdigest())
        encoded = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(result.metadata["schema_sha256"], hashlib.sha256(encoded.encode()).hexdigest())
        if kind != "lab":
            self.assertEqual(body["format"], schema)
        return result, formatted, body

    def test_native_enum_meanings_are_explicit_with_separate_byte_receipt(self):
        result, formatted, _ = self.generated()
        receipt = result.metadata["schema_field_guide"]
        self.assertEqual(receipt["fields"], list(ENUMS))
        self.assertIn("complaint=명시 불편/미충족 요구", formatted)
        self.assertIn("positive=불편 없는 칭찬", formatted)
        self.assertIn("distinct=기존 기능이 제공하지 않는 작동/행동", formatted)
        self.assertIn("duplicate=원문에 명시된 기존 작동/행동과 동일", formatted)
        self.assertIn("일부 구성 공유나 기능 미지원만으로 duplicate라 하지 마세요", formatted)
        self.assertIn("고객 희망 결과의 해결 여부와 별개", formatted)
        self.assertNotIn("mixed=", formatted)
        guide = "판정값 안내:" + formatted.split("판정값 안내:", 1)[1].split("요청:\n", 1)[0]
        self.assertEqual(receipt["characters"], len(guide))
        self.assertEqual(receipt["utf8_bytes"], len(guide.encode()))
        self.assertEqual(receipt["sha256"], hashlib.sha256(guide.encode()).hexdigest())
        self.assertFalse(result.metadata["schema_prompt_embedded"])

    def test_chat_lab_and_unknown_wrapper_receive_same_guide_without_schema_change(self):
        receipts = []
        for kind in ("ollama", "chat", "lab"):
            with self.subTest(kind=kind):
                result, formatted, body = self.generated(kind=kind)
                receipts.append(result.metadata["schema_field_guide"])
                self.assertLess(formatted.index("판정값 안내:"), formatted.index("요청:\n"))
                if kind == "lab":
                    self.assertEqual(set(body), {"prompt"})
                    self.assertIn("JSON Schema:\n", formatted)
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(receipts[0], receipts[2])
        client, backend = self.client(fixture.Backend(response=json.dumps(OUTPUT)))

        class Wrapper:
            config = client.adapter.config
            max_prompt_characters = client.adapter.max_prompt_characters

            def generate(self, prompt, schema):
                return client.adapter.generate(prompt, schema)

        result = StructuredModelClient(Wrapper()).generate("資料", SCHEMA, fixture.MODEL)
        formatted = json.loads(backend.requests[1].content)["prompt"]
        self.assertTrue(result.metadata["schema_prompt_embedded"])
        self.assertEqual(result.metadata["schema_field_guide"], receipts[0])
        self.assertIn("JSON Schema:\n", formatted)

    def test_unknown_reordered_mixed_or_renamed_contracts_get_no_guessed_meaning(self):
        for name, values in (("polarity", list(reversed(ENUMS["polarity"]))),
                             ("polarity", ENUMS["polarity"] + ["mixed"]),
                             ("polarity", ["complaint", "positive"]),
                             ("sentiment", ENUMS["polarity"]),
                             ("duplication", ["duplicate", "distinct", "uncertain"])):
            with self.subTest(field=name, values=values):
                schema = {"type": "object", "properties": {name: {"enum": values}},
                          "required": [name], "additionalProperties": False}
                result, formatted, _ = self.generated(schema, {name: values[0]})
                self.assertEqual(result.metadata["schema_field_guide"]["fields"], [])
                self.assertEqual(result.metadata["schema_field_guide"]["characters"], 0)
                self.assertNotIn("판정값 안내:", formatted)

    def test_annotation_data_cannot_activate_contract_guide(self):
        schema = {**fixture.SCHEMA, "default": SCHEMA, "examples": [SCHEMA],
                  "x-untrusted": SCHEMA, "additionalProperties": False}
        result, formatted, _ = self.generated(schema, {"message": "정상"})
        self.assertEqual(result.metadata["schema_field_guide"]["fields"], [])
        self.assertNotIn("판정값 안내:", formatted)

    def test_nested_schema_children_deduplicate_fields_in_stable_order(self):
        schema = {**fixture.SCHEMA, "$defs": {"late": SCHEMA},
                  "properties": {"message": {"type": "string"}, "optional": {
                      "type": "array", "items": SCHEMA}},
                  "allOf": [{"properties": {"duplication": {"enum": ENUMS["duplication"]}}}],
                  "if": {"properties": {"polarity": {"enum": ENUMS["polarity"]}}},
                  "then": True, "else": False}
        result, formatted, _ = self.generated(schema, {"message": "정상"})
        self.assertEqual(result.metadata["schema_field_guide"]["fields"], list(ENUMS))
        for field in ENUMS:
            self.assertEqual(formatted.count(field + ": "), 1)

    def test_guide_does_not_accept_invalid_enum_or_change_pin_checks(self):
        client, backend = self.client(fixture.Backend(response=json.dumps({**OUTPUT, "polarity": "mixed"})))
        with self.assertRaises(DomainError) as error:
            client.generate("원문", SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "schema_mismatch")
        self.assertEqual([r.url.path for r in backend.requests], ["/api/tags", "/api/generate", "/api/tags"])
        client, backend = self.client(fixture.Backend(response=json.dumps(OUTPUT)))
        backend.after_digest = "c" * 64
        with self.assertRaises(DomainError) as error:
            client.generate("원문", SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "model_revision_mismatch")

    def test_guide_is_charged_to_unchanged_native_and_lab_prompt_guards(self):
        for kind, length in (("ollama", 15900), ("lab", 3900)):
            with self.subTest(kind=kind):
                client, backend = self.client(fixture.Backend(kind, response=json.dumps(OUTPUT)))
                with self.assertRaises(DomainError) as error:
                    client.generate("가" * length, SCHEMA, fixture.MODEL)
                self.assertEqual(error.exception.details["reason"], "prompt_too_large")
                self.assertEqual(backend.requests, [])

    def test_recorded_fridge_and_microwave_inputs_fit_with_guide_and_complete_evidence(self):
        root = Path(__file__).resolve().parents[1] / "evals/web/20261006/web-rebalance-r2"
        found = set()

        def find(node, stage):
            if isinstance(node, dict):
                for call in node.get("model_calls", []):
                    if call.get("skill_id") == stage and "request_context" in call:
                        yield call
                for key, value in node.items():
                    if key != "model_calls":
                        yield from find(value, stage)
            elif isinstance(node, list):
                for child in node:
                    yield from find(child, stage)

        for case, folder, stage in (("fridge", "e2e-fridge", "concept_draft"),
                                    ("microwave", "e2e-microwave-retry", "semantic_review")):
            for path in (root / folder).glob("stored-run-*.json"):
                data = json.loads(path.read_text("utf-8-sig"))
                for call in find(data, stage):
                    before = call["request_context"]
                    prefix, raw = call["prompt"].split("DATA_JSON:\n", 1)
                    self.assertEqual(json.loads(raw), before)
                    projected = model_context(before)
                    prompt = prefix + "DATA_JSON:\n" + json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
                    client, backend = self.client(fixture.Backend(response="{}"))
                    with self.assertRaises(DomainError) as error:
                        client.generate(prompt, call["schema"], fixture.MODEL)
                    # The actual formatter reaches transport within the guard;
                    # this deliberately empty fixture output fails validation.
                    self.assertEqual(error.exception.details["reason"], "schema_mismatch")
                    body = json.loads(backend.requests[1].content)
                    self.assertLessEqual(len(body["prompt"]), 16000, case)
                    self.assertLessEqual(len(body["prompt"].encode()), 45000, case)
                    self.assertEqual(body["format"], call["schema"])
                    self.assertTrue(body["prompt"].endswith(prompt))
                    for key in set(before) - {"quality_context"}:
                        self.assertEqual(projected[key], before[key], key)
                    for expected, actual in zip(before["quality_context"]["concept_lineage"]["candidates"],
                                                projected["quality_context"]["concept_lineage"]["candidates"], strict=True):
                        self.assertEqual(actual["links"], expected["links"])
                    found.add(case)
        self.assertEqual(found, {"fridge", "microwave"})


if __name__ == "__main__":
    unittest.main()
