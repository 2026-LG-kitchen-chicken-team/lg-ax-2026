"""Native schema delivery remains complete without repeating it in task text."""

import hashlib
import json
import unittest

import test_model_client as fixture
from lgax_core.errors import DomainError
from lgax_core.model_client import StructuredModelClient


class NativeSchemaPromptTests(unittest.TestCase):
    def client(self, backend=None, **settings):
        client, backend = fixture.ModelClientTests().client(backend, **settings)
        self.addCleanup(client.close)
        return client, backend

    def test_native_format_retains_full_schema_task_and_local_validation(self):
        schema = {
            **fixture.SCHEMA,
            "properties": {"message": {"type": "string", "description": "설명" * 700}},
        }
        # A complete caller prompt fits the unchanged 16,000 character bound;
        # embedding this schema again would exceed it.
        prompt = "원문·모델·문서 버전을 그대로 보존하세요.\n" + "가" * 15000
        client, backend = self.client()
        result = client.generate(prompt, schema, fixture.MODEL)
        body = json.loads(backend.requests[1].content)
        self.assertEqual(body["format"], schema)
        self.assertTrue(body["prompt"].endswith(prompt))
        self.assertNotIn("JSON Schema:\n", body["prompt"])
        self.assertNotIn("설명" * 700, body["prompt"])
        self.assertLessEqual(len(body["prompt"]), 16000)
        encoded = json.dumps(schema, ensure_ascii=False, allow_nan=False,
                             sort_keys=True, separators=(",", ":"))
        self.assertEqual(result.metadata["schema_sha256"], hashlib.sha256(encoded.encode()).hexdigest())
        self.assertFalse(result.metadata["schema_prompt_embedded"])
        self.assertTrue(result.metadata["locally_validated"])
        self.assertEqual(result.metadata["revision"], fixture.DIGEST)
        self.assertEqual([request.url.path for request in backend.requests],
                         ["/api/tags", "/api/generate", "/api/tags"])

    def test_native_chat_keeps_full_format_and_complete_user_message(self):
        client, backend = self.client(fixture.Backend("chat"), api_mode="chat")
        prompt = "자료 원문을 JSON 문자열 안에서만 읽으세요."
        result = client.generate(prompt, fixture.SCHEMA, fixture.MODEL)
        body = json.loads(backend.requests[1].content)
        self.assertEqual(body["format"], fixture.SCHEMA)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertTrue(body["messages"][0]["content"].endswith(prompt))
        self.assertNotIn("JSON Schema:\n", body["messages"][0]["content"])
        self.assertFalse(result.metadata["schema_prompt_embedded"])

    def test_native_task_limit_still_rejects_before_any_transport(self):
        client, backend = self.client()
        with self.assertRaises(DomainError) as error:
            client.generate("가" * 16000, fixture.SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "prompt_too_large")
        self.assertEqual(backend.requests, [])

    def test_native_schema_limit_and_output_checks_are_not_bypassed(self):
        for schema, response, reason in (
            ({"type": "object", "description": "x" * 17000}, '{}', "schema_too_large"),
            (fixture.SCHEMA, '{"message": 123}', "schema_mismatch"),
            ({"type": "object", "$ref": "https://example.invalid/schema"}, '{}',
             "external_schema_reference"),
        ):
            with self.subTest(reason=reason):
                client, backend = self.client(fixture.Backend(response=response))
                with self.assertRaises(DomainError) as error:
                    client.generate("구조화 결과", schema, fixture.MODEL)
                self.assertEqual(error.exception.details["reason"], reason)
                if reason != "schema_mismatch":
                    self.assertEqual(backend.requests, [])

    def test_lab_keeps_embedded_schema_and_existing_prompt_limit(self):
        client, backend = self.client(fixture.Backend("lab"))
        result = client.generate("한국어 인사", fixture.SCHEMA, fixture.MODEL)
        body = json.loads(backend.requests[1].content)
        encoded = json.dumps(fixture.SCHEMA, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(set(body), {"prompt"})
        self.assertIn("JSON Schema:\n" + encoded, body["prompt"])
        self.assertTrue(result.metadata["schema_prompt_embedded"])
        with self.assertRaises(DomainError) as error:
            client.generate("가" * 4900, fixture.SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "prompt_too_large")
        self.assertEqual(len(backend.requests), 3)

    def test_unknown_wrapper_does_not_assume_native_enforcement(self):
        client, backend = self.client()

        class Wrapper:
            config = client.adapter.config
            max_prompt_characters = client.adapter.max_prompt_characters

            def generate(self, prompt, schema):
                return client.adapter.generate(prompt, schema)

        wrapped = StructuredModelClient(Wrapper())
        result = wrapped.generate("자료 범위 확인", fixture.SCHEMA, fixture.MODEL)
        body = json.loads(backend.requests[1].content)
        self.assertIn("JSON Schema:\n", body["prompt"])
        self.assertTrue(result.metadata["schema_prompt_embedded"])


if __name__ == "__main__":
    unittest.main()
