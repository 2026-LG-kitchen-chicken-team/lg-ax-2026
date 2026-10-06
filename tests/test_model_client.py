"""Structured output, pinned revisions and private transport boundaries."""

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from lgax_core.errors import DomainError
from lgax_core.model_client import LabModelAdapter, ModelConfig, OllamaAdapter, StructuredModelClient, main

MODEL = "qwen3:8b"
DIGEST = "a" * 64
SOURCE = "b" * 64
SCHEMA = {
    "type": "object", "properties": {"message": {"type": "string"}},
    "required": ["message"], "additionalProperties": False,
}


def json_response(value, status=200):
    # Keep the stream unread, as a real network response would be.
    content = json.dumps(value, ensure_ascii=False).encode()
    return httpx.Response(status, stream=httpx.ByteStream(content), headers={"Content-Type": "application/json"})


class Backend:
    def __init__(self, kind="ollama", response='{"message":"한국어 응답"}'):
        self.kind, self.response = kind, response
        self.requests = []
        self.health_count = 0
        self.before_digest = self.after_digest = DIGEST
        self.source = self.after_source = SOURCE
        self.model = MODEL
        self.done = True
        self.done_reason = "stop"
        self.status = "ready"
        self.models = [MODEL]
        self.output_digest = DIGEST
        self.override = None

    def __call__(self, request):
        self.requests.append(request)
        if self.override:
            response = self.override(request)
            if response is not None:
                return response
        if request.method == "GET":
            self.health_count += 1
            digest = self.before_digest if self.health_count == 1 else self.after_digest
            if self.kind == "lab":
                self.assert_path(request, "/health")
                return json_response({
                    "service": "lgax-private-lab", "generation_status": self.status, "models": self.models,
                    "expected_model_digest": digest,
                    "source_sha256": self.source if self.health_count == 1 else self.after_source,
                })
            self.assert_path(request, "/api/tags")
            return json_response({"models": [{"name": name, "digest": digest} for name in self.models]})
        self.assert_path(request, "/generate" if self.kind == "lab" else
                         "/api/chat" if self.kind == "chat" else "/api/generate")
        value = {"model": self.model, "response": self.response, "done": self.done,
                 "prompt_eval_count": 31, "eval_count": 7,
                 "total_duration_ns" if self.kind == "lab" else "total_duration": 1000000}
        if self.kind == "lab":
            value["verified_model_digest"] = self.output_digest
        else:
            value["done_reason"] = self.done_reason
        if self.kind == "chat":
            value["message"] = {"role": "assistant", "content": value.pop("response"),
                                "thinking": "모의 추론: 최종 JSON과 별도"}
        return json_response(value)

    @staticmethod
    def assert_path(request, expected):
        if request.url.path != expected:
            raise AssertionError("Unexpected backend route")


class ModelClientTests(unittest.TestCase):
    def client(self, backend=None, **kwargs):
        backend = Backend() if backend is None else backend
        config = ModelConfig("http://127.0.0.1:18865" if backend.kind == "lab" else "http://127.0.0.1:18864",
                             MODEL, DIGEST, **kwargs)
        adapter = (LabModelAdapter if backend.kind == "lab" else OllamaAdapter)(
            config, transport=httpx.MockTransport(backend),
        )
        client = StructuredModelClient(adapter)
        self.addCleanup(client.close)
        return client, backend

    def assert_failure(self, client, reason, code=None, prompt="인사해줘", schema=SCHEMA, model=MODEL):
        with self.assertRaises(DomainError) as error:
            client.generate(prompt, schema, model)
        self.assertEqual(error.exception.details["reason"], reason)
        if code:
            self.assertEqual(error.exception.code, code)
        return error.exception

    def test_ollama_native_schema_korean_data_and_revision_metadata(self):
        client, backend = self.client()
        result = client.generate("짧은 인사", SCHEMA, MODEL)
        self.assertEqual(result.data, {"message": "한국어 응답"})
        self.assertEqual(result.as_dict()["metadata"]["revision"], DIGEST)
        self.assertEqual(result.metadata["revision_kind"], "ollama_manifest_digest")
        self.assertTrue(result.metadata["backend_schema_enforced"])
        self.assertTrue(result.metadata["locally_validated"])
        self.assertEqual(result.metadata["eval_count"], 7)
        self.assertEqual(result.metadata["total_duration_ns"], 1000000)
        payload = json.loads(backend.requests[1].content)
        self.assertEqual(payload["format"], SCHEMA)
        self.assertEqual(payload["model"], MODEL)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual([r.url.path for r in backend.requests], ["/api/tags", "/api/generate", "/api/tags"])
        self.assertNotIn("endpoint", result.metadata)

    def test_explicit_output_and_context_budget_reaches_backend_and_receipt(self):
        client, backend = self.client(max_output_tokens=1024, context_tokens=8192)
        result = client.generate("인사", SCHEMA, MODEL)
        options = json.loads(backend.requests[1].content)["options"]
        self.assertEqual(options, {"temperature": 0, "seed": 42, "num_predict": 1024, "num_ctx": 8192})
        self.assertEqual(result.metadata["generation_settings"], options)
        self.assertEqual(result.metadata["done_reason"], "stop")

    def test_invalid_generation_budgets_fail_before_model_call(self):
        for kwargs in [{"max_output_tokens": True}, {"max_output_tokens": 0},
                       {"max_output_tokens": 8193}, {"context_tokens": 32769},
                       {"context_tokens": False}, {"max_output_tokens": 1024, "context_tokens": 1024}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(DomainError) as error:
                self.client(**kwargs)
            self.assertEqual(error.exception.details["reason"], "invalid_generation_budget")

    def test_thinking_sampling_is_sent_and_recorded_without_changing_defaults(self):
        client, backend = self.client(thinking=True, temperature=0.6, top_p=0.95, top_k=20, min_p=0)
        result = client.generate("인사", SCHEMA, MODEL)
        payload = json.loads(backend.requests[1].content)
        self.assertTrue(payload["think"])
        self.assertEqual(payload["options"], {"temperature": 0.6, "seed": 42, "num_ctx": 4096,
                                              "num_predict": 256, "top_p": 0.95, "top_k": 20, "min_p": 0})
        self.assertEqual(result.metadata["generation_settings"], payload["options"])
        copied = client.adapter.config.ollama_options()
        copied["temperature"] = 2
        self.assertEqual(client.adapter.config.temperature, 0.6)

    def test_chat_thinking_and_final_content_are_separate_with_same_schema_and_pins(self):
        client, backend = self.client(Backend("chat"), api_mode="chat", thinking=True, temperature=0.6)
        result = client.generate("한국어로 인사", SCHEMA, MODEL)
        body = json.loads(backend.requests[1].content)
        self.assertNotIn("prompt", body)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn("한국어로 인사", body["messages"][0]["content"])
        self.assertTrue(body["think"])
        self.assertEqual(body["format"], SCHEMA)
        self.assertEqual(result.data, {"message": "한국어 응답"})
        self.assertEqual(result.metadata["transport_api"], "/api/chat")
        self.assertEqual([r.url.path for r in backend.requests], ["/api/tags", "/api/chat", "/api/tags"])

    def test_empty_chat_content_never_substitutes_thinking_or_falls_back(self):
        client, backend = self.client(Backend("chat", response=""), api_mode="chat", thinking=True)
        self.assert_failure(client, "invalid_json", "VALIDATION_FAILED")
        self.assertEqual(sum(r.method == "POST" for r in backend.requests), 1)

    def test_unsupported_chat_mode_and_fixed_lab_are_rejected(self):
        for mode in (None, "other", [], {}):
            with self.subTest(mode=mode), self.assertRaises(DomainError):
                self.client(api_mode=mode)
        client, backend = self.client(Backend("lab"), api_mode="chat")
        self.assert_failure(client, "lab_api_is_fixed", "INVALID_ARGUMENT")
        self.assertTrue(all(r.method == "GET" for r in backend.requests))

    def test_invalid_sampling_is_rejected_before_transport(self):
        for kwargs in ({"temperature": True}, {"temperature": float("nan")}, {"temperature": 2.1},
                       {"temperature": -1}, {"temperature": None}, {"top_p": 0}, {"top_p": 1.1},
                       {"top_p": float("inf")}, {"top_k": True}, {"top_k": 20.0}, {"top_k": -1},
                       {"min_p": -0.1}, {"min_p": "0"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(DomainError) as error:
                self.client(**kwargs)
            self.assertEqual(error.exception.details["reason"], "invalid_sampling_setting")

    def test_lab_rejects_sampling_overrides_before_generation(self):
        for kwargs in ({"temperature": 0.6}, {"top_p": 0.95}, {"top_k": 20}, {"min_p": 0}):
            with self.subTest(kwargs=kwargs):
                client, backend = self.client(Backend("lab"), **kwargs)
                self.assert_failure(client, "lab_sampling_is_fixed", "INVALID_ARGUMENT")
                self.assertTrue(all(request.method == "GET" for request in backend.requests))

    def test_sampling_environment_preserves_explicit_settings_and_rejects_malformed(self):
        values = {"LGAX_MODEL_ADAPTER": "ollama", "LGAX_MODEL_ENDPOINT": "http://127.0.0.1:18864",
                  "LGAX_MODEL_ID": MODEL, "LGAX_MODEL_DIGEST": DIGEST,
                  "LGAX_MODEL_TEMPERATURE": "0.6", "LGAX_MODEL_TOP_P": "0.95",
                  "LGAX_MODEL_TOP_K": "20", "LGAX_MODEL_MIN_P": "0"}
        with StructuredModelClient.from_env(values) as client:
            self.assertEqual(client.adapter.config.ollama_options()["top_k"], 20)
            self.assertEqual(client.adapter.config.temperature, 0.6)
        for key, value in (("LGAX_MODEL_TOP_K", "20.0"), ("LGAX_MODEL_TOP_P", "nan"),
                           ("LGAX_MODEL_TEMPERATURE", "")):
            with self.subTest(key=key), self.assertRaises(DomainError):
                StructuredModelClient.from_env({**values, key: value})

    def test_fixed_lab_does_not_silently_ignore_requested_budget(self):
        client, backend = self.client(Backend("lab"), max_output_tokens=1024, context_tokens=8192)
        self.assert_failure(client, "lab_generation_budget_is_fixed", "INVALID_ARGUMENT")
        self.assertTrue(all(request.method == "GET" for request in backend.requests))

    def test_budget_environment_is_parsed_and_bad_values_rejected(self):
        values = {"LGAX_MODEL_ADAPTER": "ollama", "LGAX_MODEL_ENDPOINT": "http://127.0.0.1:18864",
                  "LGAX_MODEL_ID": MODEL, "LGAX_MODEL_DIGEST": DIGEST,
                  "LGAX_MODEL_MAX_OUTPUT_TOKENS": "1024", "LGAX_MODEL_CONTEXT_TOKENS": "8192"}
        with StructuredModelClient.from_env(values) as client:
            self.assertEqual(client.adapter.config.max_output_tokens, 1024)
            self.assertEqual(client.adapter.config.context_tokens, 8192)
        with self.assertRaises(DomainError):
            StructuredModelClient.from_env({**values, "LGAX_MODEL_MAX_OUTPUT_TOKENS": "nan"})

    def test_lab_existing_prompt_only_api_has_honest_constraint_metadata(self):
        client, backend = self.client(Backend("lab"))
        result = client.generate("인사", SCHEMA, MODEL)
        self.assertFalse(result.metadata["backend_schema_enforced"])
        self.assertEqual(result.metadata["constraint_mode"], "prompt_and_local_validation")
        self.assertEqual(result.metadata["service_source_sha256"], SOURCE)
        payload = json.loads(backend.requests[1].content)
        self.assertEqual(set(payload), {"prompt"})
        self.assertIn(json.dumps(SCHEMA, ensure_ascii=False, sort_keys=True, separators=(",", ":")), payload["prompt"])
        self.assertEqual([r.url.path for r in backend.requests], ["/health", "/generate", "/health"])

    def test_whole_json_fence_only_and_backticks_inside_json_string(self):
        for text, expected_format in [
            ('  ```json\n{"message":"안녕"}\n```  ', "whole_json_fence"),
            ('```\n{"message":"안녕"}\n```', "whole_json_fence"),
            ('{"message":"문자열 속 ```json 표시"}', "plain_json"),
        ]:
            with self.subTest(text=text):
                client, _ = self.client(Backend(response=text))
                result = client.generate("인사", SCHEMA, MODEL)
                self.assertEqual(result.metadata["response_format"], expected_format)

    def test_malformed_extra_text_and_fake_fences_are_not_repaired(self):
        outputs = [
            "설명: {\"message\":\"안녕\"}", '{"message":"안녕"} 뒤 설명',
            '{"message":"안녕",}', '{"message":"안녕"}{"message":"다시"}',
            '```json {"message":"안녕"}```', '```python\n{"message":"안녕"}\n```',
            '```json\n{"message":"안녕"}\n```\n설명',
            '```json\n{"message":"안녕"}\n```\n```json\n{}\n```',
        ]
        for text in outputs:
            with self.subTest(text=text):
                client, _ = self.client(Backend(response=text))
                with self.assertRaises(DomainError) as error:
                    client.generate("인사", SCHEMA, MODEL)
                self.assertEqual(error.exception.code, "VALIDATION_FAILED")

    def test_duplicate_keys_and_non_finite_json_are_rejected(self):
        for text in ['{"message":"첫째","message":"둘째"}', '{"value":NaN}',
                     '{"value":Infinity}', '{"value":-Infinity}', '{"value":1e400}']:
            with self.subTest(text=text):
                client, _ = self.client(Backend(response=text))
                self.assert_failure(client, "invalid_json", "VALIDATION_FAILED", schema={"type": "object"})

    def test_schema_mismatch_including_extra_properties_and_known_formats(self):
        for text in ['{}', '{"message":12}', '{"message":"안녕","unexpected":true}']:
            client, _ = self.client(Backend(response=text))
            self.assert_failure(client, "schema_mismatch", "VALIDATION_FAILED")
        client, _ = self.client(Backend(response='{"date":"2026-99-99"}'))
        self.assert_failure(client, "schema_mismatch", schema={
            "type": "object", "properties": {"date": {"type": "string", "format": "date"}},
        })

    def test_local_refs_and_array_outputs_work(self):
        client, _ = self.client(Backend(response='[{"message":"안녕"}]'))
        schema = {"$defs": {"entry": SCHEMA}, "type": "array", "items": {"$ref": "#/$defs/entry"}}
        self.assertEqual(client.generate("인사", schema, MODEL).data, [{"message": "안녕"}])

    def test_bad_input_schema_model_and_external_refs_do_not_call_backend(self):
        cases = [
            ("empty_prompt", {"prompt": " "}),
            ("requested_model_mismatch", {"model": "another:latest"}),
            ("invalid_schema", {"schema": {"type": "not-a-json-type"}}),
            ("invalid_schema", {"schema": []}),
            ("external_schema_reference", {"schema": {"$ref": "https://secret.invalid/schema"}}),
            ("external_schema_reference", {"schema": {"$defs": {"x": {"$dynamicRef": "other.json"}}}}),
            ("schema_too_large", {"schema": {"description": "x" * 17000}}),
        ]
        for reason, kwargs in cases:
            with self.subTest(reason=reason):
                client, backend = self.client()
                self.assert_failure(client, reason, "INVALID_ARGUMENT", **kwargs)
                self.assertEqual(backend.requests, [])

    def test_lab_total_formatted_prompt_limit_before_cost(self):
        client, backend = self.client(Backend("lab"))
        self.assert_failure(client, "prompt_too_large", "INVALID_ARGUMENT", prompt="가" * 4900)
        self.assertEqual(backend.requests, [])

    def test_missing_ambiguous_and_changed_revision_before_generation(self):
        for kind in ["lab", "ollama"]:
            for models, digest, reason in [
                ([], DIGEST, "model_missing_or_ambiguous"),
                ([MODEL, MODEL], DIGEST, "model_missing_or_ambiguous"),
                ([MODEL], "c" * 64, "model_revision_mismatch"),
            ]:
                with self.subTest(kind=kind, models=models, digest=digest):
                    backend = Backend(kind)
                    backend.models, backend.before_digest = models, digest
                    client, _ = self.client(backend)
                    self.assert_failure(client, reason, "MODEL_UNAVAILABLE")
                    self.assertEqual(len(backend.requests), 1)

    def test_lab_not_ready_and_output_digest_mismatch(self):
        for status in ["model_not_downloaded", "unavailable", "model_revision_changed"]:
            backend = Backend("lab")
            backend.status = status
            client, _ = self.client(backend)
            reason = "model_revision_mismatch" if status == "model_revision_changed" else "model_missing_or_unavailable"
            self.assert_failure(client, reason, "MODEL_UNAVAILABLE")
            self.assertEqual(len(backend.requests), 1)
        backend = Backend("lab")
        backend.output_digest = "c" * 64
        client, _ = self.client(backend)
        self.assert_failure(client, "model_revision_mismatch")

    def test_model_revision_change_during_generation_is_not_accepted(self):
        for kind in ["lab", "ollama"]:
            backend = Backend(kind)
            backend.after_digest = "c" * 64
            client, _ = self.client(backend)
            self.assert_failure(client, "model_revision_mismatch", "MODEL_UNAVAILABLE")
            self.assertEqual(len(backend.requests), 3)
        backend = Backend("lab")
        backend.after_source = "c" * 64
        client, _ = self.client(backend)
        self.assert_failure(client, "service_identity_changed", "MODEL_UNAVAILABLE")

    def test_wrong_response_model_incomplete_and_truncated_output(self):
        for key, value, reason in [("model", "wrong:8b", "response_model_mismatch"),
                                   ("done", False, "generation_incomplete"),
                                   ("done_reason", "length", "output_truncated")]:
            backend = Backend()
            setattr(backend, key, value)
            client, _ = self.client(backend)
            self.assert_failure(client, reason, "MODEL_UNAVAILABLE")

    def test_http_failure_body_and_transport_exception_do_not_leak(self):
        for handler, reason in [
            (lambda _r: json_response({"password": "never-log-this"}, 503), "http_error"),
            (lambda _r: (_ for _ in ()).throw(httpx.ReadTimeout("never-log-this")), "timeout"),
            (lambda _r: (_ for _ in ()).throw(httpx.ConnectError("never-log-this")), "transport_error"),
        ]:
            backend = Backend()
            backend.override = handler
            client, _ = self.client(backend)
            error = self.assert_failure(client, reason, "MODEL_UNAVAILABLE")
            self.assertNotIn("never-log-this", json.dumps(error.response()))
            self.assertIsNone(error.__cause__)

    def test_redirect_is_refused_without_following(self):
        backend = Backend()
        backend.override = lambda _r: httpx.Response(302, headers={"Location": "https://untrusted.invalid/"})
        client, _ = self.client(backend)
        error = self.assert_failure(client, "http_error", "MODEL_UNAVAILABLE")
        self.assertEqual(error.details["status"], 302)
        self.assertEqual(len(backend.requests), 1)

    def test_oversized_response_with_or_without_length_and_compression(self):
        responses = [
            httpx.Response(200, stream=httpx.ByteStream(b"x" * 1025)),
            httpx.Response(200, stream=httpx.ByteStream(b"x"), headers={"Content-Length": "1025"}),
            httpx.Response(200, stream=httpx.ByteStream(b"x"), headers={"Content-Encoding": "gzip"}),
        ]
        for response in responses:
            backend = Backend()
            backend.override = lambda _r, response=response: response
            client, _ = self.client(backend, max_response_bytes=1024)
            reason = "unsupported_response_encoding" if response.headers.get("content-encoding") else "response_too_large"
            self.assert_failure(client, reason, "MODEL_UNAVAILABLE")

    def test_invalid_transport_json_utf8_and_duplicate_keys(self):
        for raw in [b"not json", b'[]', b'{"models":[],"models":[]}', b'{"secret":"\xff"}']:
            backend = Backend()
            backend.override = lambda _r, raw=raw: httpx.Response(200, stream=httpx.ByteStream(raw))
            client, _ = self.client(backend)
            self.assert_failure(client, "invalid_transport_response", "MODEL_UNAVAILABLE")

    def test_one_deadline_covers_health_generation_and_second_health(self):
        backend = Backend()
        ticks = iter([0, 0.1, 0.2, 0.3, 0.5])
        adapter = OllamaAdapter(ModelConfig("http://127.0.0.1:18864", MODEL, DIGEST, timeout_seconds=0.4),
                                transport=httpx.MockTransport(backend), clock=lambda: next(ticks))
        client = StructuredModelClient(adapter)
        self.addCleanup(client.close)
        self.assert_failure(client, "timeout", "MODEL_UNAVAILABLE")
        self.assertEqual(len(backend.requests), 1)

    def test_unsafe_endpoints_missing_pins_and_bad_limits_are_refused(self):
        unsafe = ["http://localhost:18864", "http://192.168.1.2:18864", "http://example.com:18864",
                  "http://127.0.0.1", "http://127.0.0.1:0", "http://127.0.0.1:18864/api",
                  "http://user:secret@127.0.0.1:18864", "http://127.0.0.1:18864?secret=x",
                  "http://127.0.0.1:18864#secret", "file:///tmp/test", " http://127.0.0.1:18864"]
        for endpoint in unsafe:
            with self.subTest(endpoint=endpoint), self.assertRaises(DomainError) as error:
                ModelConfig(endpoint, MODEL, DIGEST)
            self.assertEqual(error.exception.details["reason"], "unsafe_endpoint")
            self.assertNotIn("secret", str(error.exception.response()))
        for changes in [{"expected_digest": "latest"}, {"model_id": " "}, {"timeout_seconds": float("nan")},
                        {"timeout_seconds": 301}, {"max_response_bytes": 0}, {"max_response_bytes": True}]:
            kwargs = {"endpoint": "http://127.0.0.1:18864", "model_id": MODEL, "expected_digest": DIGEST, **changes}
            with self.subTest(changes=changes), self.assertRaises(DomainError):
                ModelConfig(**kwargs)
        self.assertEqual(ModelConfig("http://[::1]:18864/", MODEL, DIGEST).endpoint, "http://[::1]:18864")

    def test_environment_requires_explicit_adapter_endpoint_model_and_digest(self):
        env = {"LGAX_MODEL_ADAPTER": "lab", "LGAX_MODEL_ENDPOINT": "http://127.0.0.1:18865",
               "LGAX_MODEL_ID": MODEL, "LGAX_MODEL_DIGEST": DIGEST}
        with StructuredModelClient.from_env(env) as client:
            self.assertIsInstance(client.adapter, LabModelAdapter)
        for changed in [{}, {**env, "LGAX_MODEL_DIGEST": ""}, {**env, "LGAX_MODEL_ADAPTER": "cloud"},
                        {**env, "LGAX_MODEL_TIMEOUT_SECONDS": "secret"}]:
            with self.assertRaises(DomainError) as error:
                StructuredModelClient.from_env(changed)
            self.assertEqual(error.exception.code, "INVALID_ARGUMENT")
            self.assertNotIn("secret", str(error.exception.response()))

    def test_closed_client_fails_safely(self):
        client, _ = self.client()
        client.close()
        self.assert_failure(client, "client_closed", "MODEL_UNAVAILABLE")


class ModelClientCLITests(unittest.TestCase):
    def invoke(self, backend, extra=()):
        # Exercise parsing, file input/output, pin checks and the real adapter with no network or GPU.
        real_client = httpx.Client

        def routed_client(*args, **kwargs):
            return real_client(*args, **{**kwargs, "transport": httpx.MockTransport(backend)})

        with TemporaryDirectory(prefix="lgax-model-cli-") as directory:
            base = Path(directory)
            prompt, schema, output = base / "prompt.txt", base / "schema.json", base / "result.json"
            prompt.write_text("한국어 인사를 JSON으로 작성하세요.", encoding="utf-8")
            schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
            argv = ["--adapter", backend.kind, "--endpoint", "http://127.0.0.1:18865",
                    "--model", MODEL, "--digest", DIGEST,
                    "--prompt-file", str(prompt), "--schema-file", str(schema), "--output", str(output), *extra]
            console = StringIO()
            with patch("lgax_core.model_client.httpx.Client", side_effect=routed_client), redirect_stdout(console):
                status = main(argv)
            receipt = json.loads(output.read_text("utf-8")) if output.exists() else None
            return status, receipt, json.loads(console.getvalue())

    def test_cli_explicit_budget_reaches_generation_and_validated_output_receipt(self):
        backend = Backend()
        status, receipt, console = self.invoke(backend, ["--max-output-tokens", "1024", "--context-tokens", "8192"])
        self.assertEqual(status, 0)
        options = json.loads(backend.requests[1].content)["options"]
        self.assertEqual(options, {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 1024})
        self.assertEqual(receipt["data"], {"message": "한국어 응답"})
        self.assertEqual(receipt["metadata"]["generation_settings"], options)
        self.assertTrue(receipt["metadata"]["locally_validated"])
        self.assertEqual(console, {"ok": True, "locally_validated": True, "adapter": "ollama"})

    def test_cli_defaults_match_sdk_and_do_not_read_from_env_budget_settings(self):
        backend = Backend()
        with patch.dict("os.environ", {"LGAX_MODEL_MAX_OUTPUT_TOKENS": "8193", "LGAX_MODEL_CONTEXT_TOKENS": "1"}):
            status, receipt, _ = self.invoke(backend)
        self.assertEqual(status, 0)
        options = json.loads(backend.requests[1].content)["options"]
        self.assertEqual(options["num_predict"], 256)
        self.assertEqual(options["num_ctx"], 4096)
        self.assertEqual(receipt["metadata"]["generation_settings"], options)

    def test_cli_rejects_invalid_or_unsupported_lab_budget_without_generation_or_output(self):
        cases = [
            ("ollama", ["--max-output-tokens", "31"], "invalid_generation_budget"),
            ("ollama", ["--context-tokens", "32769"], "invalid_generation_budget"),
            ("ollama", ["--max-output-tokens", "1024", "--context-tokens", "1024"], "invalid_generation_budget"),
            ("lab", ["--max-output-tokens", "1024", "--context-tokens", "8192"], "lab_generation_budget_is_fixed"),
        ]
        for kind, extra, reason in cases:
            with self.subTest(kind=kind, reason=reason):
                backend = Backend(kind)
                status, receipt, console = self.invoke(backend, extra)
                self.assertEqual(status, 1)
                self.assertIsNone(receipt)
                self.assertEqual(console["error"]["code"], "INVALID_ARGUMENT")
                self.assertEqual(console["error"]["details"]["reason"], reason)
                self.assertTrue(all(request.method == "GET" for request in backend.requests))
                if reason == "invalid_generation_budget":
                    self.assertEqual(backend.requests, [])


if __name__ == "__main__":
    unittest.main()
