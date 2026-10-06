"""Bounded request envelopes are separate from tokenizer/model quality claims."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import test_model_client as fixture
from lgax_core.errors import DomainError
from lgax_core.model_client import ModelConfig, StructuredModelClient, _OllamaPromptBudget
from lgax_core.planning_agent import _RecordingAdapter
from lgax_core.revision_guard import _CompletionRecorder


class ModelPromptLimitsTests(unittest.TestCase):
    client = fixture.ModelClientTests.client

    def recorded_attempt(self):
        # Original byte record of the 79f31a full ten-review run, including the
        # five actual responses and the sixth, never-dispatched semantic attempt.
        path = Path(__file__).parent / "fixtures/prompt-context/full-122b-semantic-attempt-20261006.json"
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "1cc749eb413ba3397159a84fa6404ccece59102038a25282657baeeb73844e38")
        record = json.loads(raw.decode("utf-8-sig"))
        call = record["model_calls"][-1]
        self.assertEqual(call["skill_id"], "semantic_review")
        self.assertEqual(call["error"]["details"], {"reason": "prompt_too_large", "maximum": 16000})
        self.assertNotIn("generated", call)
        return path, raw, record, call

    def assert_refused(self, client, backend, prompt, maximum, schema=fixture.SCHEMA, byte_limit=None):
        with self.assertRaises(DomainError) as error:
            client.generate(prompt, schema, fixture.MODEL)
        self.assertEqual(error.exception.code, "INVALID_ARGUMENT")
        self.assertEqual(error.exception.details["reason"], "prompt_too_large")
        self.assertEqual(error.exception.details["maximum"], maximum)
        if byte_limit is not None:
            self.assertEqual(error.exception.details["maximum_utf8_bytes"], byte_limit)
            self.assertEqual(error.exception.details["limit"], "utf8_bytes")
        self.assertEqual(backend.requests, [], "oversized requests must fail before pin/model transport")

    def test_actual_full_semantic_attempt_reaches_transport_only_at_explicit_large_context(self):
        path, raw, record, call = self.recorded_attempt()
        before = copy.deepcopy(record)
        self.assertEqual(call["request_context"]["sources"], record["original_input"]["sources"])
        self.assertEqual(len(call["request_context"]["review_assessments"]), 10)
        self.assertTrue(call["request_context"]["feedback"])
        self.assertEqual(record["correction_budget"]["max_revisions"], 2)
        for context in (4096, 8192, 16383):
            with self.subTest(context=context):
                client, backend = self.client(fixture.Backend(response="{}"), context_tokens=context)
                self.assert_refused(client, backend, call["prompt"], 16000, call["schema"])
        for recorder in (None, _RecordingAdapter, _CompletionRecorder):
            with self.subTest(recorder=recorder):
                client, backend = self.client(fixture.Backend(response="{}"),
                                              context_tokens=16384, max_output_tokens=8192)
                captured = {}
                wrapped = client if recorder is None else StructuredModelClient(recorder(client.adapter, captured))
                frozen_schema = copy.deepcopy(call["schema"])
                with self.assertRaises(DomainError) as error:
                    wrapped.generate(call["prompt"], call["schema"], fixture.MODEL)
                # Only MockTransport runs: the unaltered output schema rejects
                # '{}'. Transport reached does not prove a semantic accept.
                self.assertEqual(error.exception.details["reason"], "schema_mismatch")
                body = json.loads(backend.requests[1].content)
                formatted = body["prompt"]
                self.assertGreater(len(formatted), 16000)
                self.assertLessEqual(len(formatted), 24000)
                self.assertLessEqual(len(formatted.encode()), 45000)
                self.assertTrue(formatted.endswith("요청:\n" + call["prompt"]))
                self.assertIn("판정값 안내:", formatted)
                self.assertEqual(json.loads(formatted.split("DATA_JSON:\n", 1)[1]), call["prompt_context"])
                self.assertEqual(body["format"], frozen_schema)
                self.assertEqual(call["schema"], frozen_schema)
                self.assertEqual(body["options"], {"temperature": 0, "seed": 42,
                                                   "num_ctx": 16384, "num_predict": 8192})
                self.assertEqual([request.url.path for request in backend.requests],
                                 ["/api/tags", "/api/generate", "/api/tags"])
                if recorder is not None:
                    self.assertEqual(captured["formatted_prompt"], formatted)
                    self.assertEqual(captured["raw_response"], "{}")
                    self.assertEqual(captured["formatted_prompt_sha256"], hashlib.sha256(formatted.encode()).hexdigest())
        self.assertEqual(record, before, "source, feedback, failed receipt and correction budget are immutable")
        self.assertEqual(path.read_bytes(), raw)

    def test_high_context_character_and_utf8_caps_are_independent_and_include_wrapper(self):
        for recorder in (None, _RecordingAdapter, _CompletionRecorder):
            for prompt, byte_limit in (("x" * 24000, None), ("가" * 15000, 45000), ("😀" * 11300, 45000)):
                with self.subTest(recorder=recorder, byte_limit=byte_limit, character_count=len(prompt)):
                    client, backend = self.client(context_tokens=16384)
                    wrapped = client if recorder is None else StructuredModelClient(recorder(client.adapter, {}))
                    self.assert_refused(wrapped, backend, prompt, 24000, byte_limit=byte_limit)

    def test_full_field_guide_is_charged_to_large_character_envelope(self):
        _, _, _, call = self.recorded_attempt()
        prompt = call["prompt"] + "x" * (24000 - len(call["prompt"]))
        self.assertEqual(len(prompt), 24000)
        client, backend = self.client(context_tokens=16384)
        self.assert_refused(client, backend, prompt, 24000, call["schema"])

    def test_exact_high_context_boundaries_and_chat_path_keep_existing_settings(self):
        for context, kind in ((16384, "ollama"), (32768, "chat")):
            with self.subTest(context=context, kind=kind):
                client, backend = self.client(fixture.Backend(kind), context_tokens=context,
                                              **({"api_mode": "chat"} if kind == "chat" else {}))
                result = client.generate("x", fixture.SCHEMA, fixture.MODEL)
                body = json.loads(backend.requests[1].content)
                prefix = (body["messages"][0]["content"] if kind == "chat" else body["prompt"])[:-1]
                self.assertEqual(result.data, {"message": "한국어 응답"})
                char_prompt = "x" * (24000 - len(prefix))
                byte_available = 45000 - len(prefix.encode())
                byte_prompt = "가" * (byte_available // 3) + "x" * (byte_available % 3)
                character_available = 24000 - len(prefix)
                extra_bytes = byte_available - character_available
                emoji_count = extra_bytes % 2
                hangul_count = (extra_bytes - 3 * emoji_count) // 2
                both_prompt = ("가" * hangul_count + "😀" * emoji_count
                               + "x" * (character_available - hangul_count - emoji_count))
                for prompt, expected_chars, expected_bytes in ((char_prompt, 24000, None),
                                                               (byte_prompt, None, 45000),
                                                               (both_prompt, 24000, 45000)):
                    receipt = client.generate(prompt, fixture.SCHEMA, fixture.MODEL).metadata
                    if expected_chars is not None:
                        self.assertEqual(receipt["formatted_prompt_characters"], expected_chars)
                    if expected_bytes is not None:
                        self.assertEqual(receipt["formatted_prompt_utf8_bytes"], expected_bytes)
                    self.assertLessEqual(receipt["formatted_prompt_characters"], 24000)
                    self.assertLessEqual(receipt["formatted_prompt_utf8_bytes"], 45000)
                    self.assertEqual(receipt["generation_settings"]["num_ctx"], context)
                    self.assertEqual(receipt["generation_settings"]["num_predict"], 256)
                    self.assertEqual(receipt["revision"], fixture.DIGEST)

    def test_large_envelope_does_not_bypass_model_pin_or_requested_model(self):
        backend = fixture.Backend()
        backend.before_digest = "c" * 64
        client, backend = self.client(backend, context_tokens=16384)
        with self.assertRaises(DomainError) as error:
            client.generate("x" * 17000, fixture.SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "model_revision_mismatch")
        self.assertEqual([request.url.path for request in backend.requests], ["/api/tags"])
        client, backend = self.client(context_tokens=16384)
        with self.assertRaises(DomainError) as error:
            client.generate("x" * 17000, fixture.SCHEMA, "another:latest")
        self.assertEqual(error.exception.details["reason"], "requested_model_mismatch")
        self.assertEqual(backend.requests, [])

    def test_unknown_lab_and_incomplete_or_wrong_budget_do_not_expand(self):
        origin, _ = self.client(context_tokens=16384)
        equivalent = ModelConfig(origin.adapter.config.endpoint, fixture.MODEL, fixture.DIGEST,
                                 context_tokens=16384)

        class Wrapper:
            config = origin.adapter.config
            max_prompt_characters = 24000
            backend_schema_enforced = True

            def generate(self, prompt, schema):
                raise AssertionError("an unverified budget must not reach generation")

        bad_budgets = (
            None, {"max_characters": 24000, "max_utf8_bytes": 45000},
            _OllamaPromptBudget(equivalent),
            _OllamaPromptBudget(origin.adapter.config, max_characters=24000.0),
            _OllamaPromptBudget(origin.adapter.config, max_characters=True),
            _OllamaPromptBudget(origin.adapter.config, max_characters=-1),
            _OllamaPromptBudget(origin.adapter.config, max_utf8_bytes=45000.0),
            _OllamaPromptBudget(origin.adapter.config, max_utf8_bytes=True),
            _OllamaPromptBudget(origin.adapter.config, max_utf8_bytes=90000),
        )
        for budget in bad_budgets:
            with self.subTest(budget=budget):
                adapter = Wrapper()
                adapter.prompt_budget = budget
                with self.assertRaises(DomainError) as error:
                    StructuredModelClient(adapter).generate("x" * 17000, fixture.SCHEMA, fixture.MODEL)
                self.assertEqual(error.exception.details, {"reason": "prompt_too_large", "maximum": 16000})
        for native in (False, 1):
            with self.subTest(native=native):
                adapter = Wrapper()
                adapter.prompt_budget = origin.adapter.prompt_budget
                adapter.backend_schema_enforced = native
                with self.assertRaises(DomainError) as error:
                    StructuredModelClient(adapter).generate("x" * 17000, fixture.SCHEMA, fixture.MODEL)
                self.assertEqual(error.exception.details["maximum"], 16000)
        for config in (SimpleNamespace(model_id=fixture.MODEL, context_tokens=16384),
                       ModelConfig(origin.adapter.config.endpoint, fixture.MODEL, fixture.DIGEST,
                                   context_tokens=16383)):
            with self.subTest(config=config):
                adapter = Wrapper()
                adapter.config = config
                adapter.prompt_budget = _OllamaPromptBudget(config)
                with self.assertRaises(DomainError) as error:
                    StructuredModelClient(adapter).generate("x" * 17000, fixture.SCHEMA, fixture.MODEL)
                self.assertEqual(error.exception.details["maximum"], 16000)
        for context in (4096, 16383):
            client, backend = self.client(context_tokens=context)
            self.assert_refused(client, backend, "x" * 16000, 16000)
        client, backend = self.client(fixture.Backend("lab"), context_tokens=16384)
        self.assert_refused(client, backend, "x" * 5000, 5000)

    def test_lower_context_preserves_legacy_character_only_envelope(self):
        client, backend = self.client(context_tokens=8192)
        result = client.generate("가" * 15000, fixture.SCHEMA, fixture.MODEL)
        formatted = json.loads(backend.requests[1].content)["prompt"]
        self.assertLess(len(formatted), 16000)
        self.assertGreater(len(formatted.encode()), 45000)
        self.assertEqual(result.metadata["generation_settings"]["num_ctx"], 8192)


if __name__ == "__main__":
    unittest.main()
