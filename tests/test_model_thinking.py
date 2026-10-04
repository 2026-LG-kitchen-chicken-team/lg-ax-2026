"""Explicit operator setting reaches transport; default/fixed adapter stays unchanged."""
import json
import unittest

import test_model_client as fixture
from lgax_core.errors import DomainError
from lgax_core.model_client import StructuredModelClient


class ThinkingSettingsTests(unittest.TestCase):
    def test_explicit_thinking_reaches_ollama_and_receipt(self):
        backend = fixture.Backend()
        client, backend = fixture.ModelClientTests().client(backend, thinking=True, max_output_tokens=4096,
                                                   context_tokens=8192)
        with client:
            result = client.generate("구조화 답변", fixture.SCHEMA, fixture.MODEL)
        self.assertIs(json.loads(backend.requests[1].content)["think"], True)
        self.assertIs(result.metadata["thinking_enabled"], True)
        self.assertEqual(result.metadata["generation_settings"]["num_predict"], 4096)

    def test_fixed_lab_cannot_silently_ignore_thinking(self):
        client, backend = fixture.ModelClientTests().client(fixture.Backend("lab"), thinking=True)
        with client, self.assertRaises(DomainError) as error:
            client.generate("응답", fixture.SCHEMA, fixture.MODEL)
        self.assertEqual(error.exception.details["reason"], "lab_thinking_is_fixed_off")
        self.assertEqual(len(backend.requests), 1)  # identity check only, no generation

    def test_environment_rejects_ambiguous_thinking_values(self):
        env = {"LGAX_MODEL_ADAPTER": "ollama", "LGAX_MODEL_ENDPOINT": "http://127.0.0.1:18864",
               "LGAX_MODEL_ID": fixture.MODEL, "LGAX_MODEL_DIGEST": fixture.DIGEST, "LGAX_MODEL_THINK": "yes"}
        with self.assertRaises(DomainError) as error:
            StructuredModelClient.from_env(env)
        self.assertEqual(error.exception.details["reason"], "invalid_model_environment")

    def test_environment_parses_true_and_false_explicitly(self):
        env = {"LGAX_MODEL_ADAPTER": "ollama", "LGAX_MODEL_ENDPOINT": "http://127.0.0.1:18864",
               "LGAX_MODEL_ID": fixture.MODEL, "LGAX_MODEL_DIGEST": fixture.DIGEST}
        for value, expected in (("true", True), ("false", False)):
            with StructuredModelClient.from_env({**env, "LGAX_MODEL_THINK": value}) as client:
                self.assertIs(client.adapter.config.thinking, expected)

    def test_default_does_not_enable_thinking(self):
        client, backend = fixture.ModelClientTests().client()
        with client:
            result = client.generate("응답", fixture.SCHEMA, fixture.MODEL)
        self.assertIs(json.loads(backend.requests[1].content)["think"], False)
        self.assertIs(result.metadata["thinking_enabled"], False)
