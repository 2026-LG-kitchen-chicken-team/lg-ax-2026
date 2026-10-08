"""Native transport mock regressions: no live server or model execution.

The sparse GGUF placeholder verifies only file identity/size checks. Production
GGUF byte verification belongs to the launcher; these tests assert no such claim.
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from lgax_core.errors import DomainError
from lgax_core.model_client import ModelConfig, StructuredModelClient

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shared_llama_under_test", ROOT / "scripts/serve_shared_research_prototype.py"
)
assert SPEC is not None and SPEC.loader is not None
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)

# Exact public registry manifest, not a fabricated native /props revision.
MANIFEST = b'{"schemaVersion":2,"mediaType":"application/vnd.docker.distribution.manifest.v2+json","config":{"mediaType":"application/vnd.docker.container.image.v1+json","digest":"sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f","size":215},"layers":[{"mediaType":"application/vnd.ollama.image.projector","digest":"sha256:ac3714bfdddeca31351f2752bf1a63f266f4df87c0b68c895e44945ca704448e","size":931146016,"from":"mmproj-qwen3.8-27b-bf16.gguf"},{"mediaType":"application/vnd.ollama.image.model","digest":"sha256:f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d","size":16810714464},{"mediaType":"application/vnd.ollama.image.license","digest":"sha256:4c6a8e842ef0d8504549facfb03f1273a8d0022991519bc1888522cc1a5517d1","size":11345},{"mediaType":"application/vnd.ollama.image.params","digest":"sha256:448d29437397713495b408d51b4ccbc5ba95240a7583643efb2304921950b111","size":92}]}'
PARAMS = b'{"min_p":0,"presence_penalty":0,"repeat_penalty":1,"temperature":1,"top_k":20,"top_p":0.95}\n'
SCHEMA = {"type": "object", "properties": {"answer": {"type": "integer"}},
          "required": ["answer"], "additionalProperties": False}


class SharedLlamaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name)
        self.manifest_path = (self.store / "manifests/registry.ollama.ai/library/qwen3.8/27b-q4_K_M")
        self.manifest_path.parent.mkdir(parents=True)
        self.manifest_path.write_bytes(MANIFEST)
        blobs = self.store / "blobs"
        blobs.mkdir()
        self.params_path = blobs / ("sha256-" + SHARED.SHARED_PARAMS_SHA)
        self.params_path.write_bytes(PARAMS)
        self.model_path = blobs / ("sha256-" + SHARED.SHARED_GGUF_SHA)
        with self.model_path.open("wb") as stream:
            stream.truncate(SHARED.SHARED_GGUF_BYTES)
        self.config = ModelConfig("http://127.0.0.1:18875", SHARED.SHARED_MODEL_ID,
                                  SHARED.SHARED_MANIFEST_SHA, context_tokens=16384,
                                  max_output_tokens=4096, max_response_bytes=262144)
        self.alias = self.config.model_id + "@" + self.config.expected_digest
        self.props = {"model_alias": self.alias, "model_path": str(self.model_path),
                      "total_slots": 4, "is_sleeping": False,
                      "default_generation_settings": {"n_ctx": 16384}}
        self.native = {"model": self.alias, "content": '{"answer":7}', "stop": True,
                       "stop_type": "eos", "truncated": False, "id_slot": 2,
                       "tokens_evaluated": 100, "tokens_predicted": 8,
                       "timings": {"prompt_n": 20, "predicted_n": 8,
                                   "prompt_ms": 1.5, "predicted_ms": 2.5}}
        self.requests = []
        self.after_props = None
        self.after_completion = None

    def adapter(self, config=None):
        def respond(request):
            self.requests.append((request.method, request.url.path,
                                  json.loads(request.content) if request.content else None))
            if request.method == "GET" and request.url.path == "/props":
                payload = self.props
                if self.after_props is not None and len(self.requests) > 1:
                    payload = self.after_props
            elif request.method == "POST" and request.url.path == "/completion":
                payload = self.native
                if self.after_completion:
                    self.after_completion()
            else:
                raise AssertionError("No Ollama, chat, load, or other route is allowed")
            return httpx.Response(200, stream=httpx.ByteStream(json.dumps(payload).encode()),
                                  headers={"Content-Type": "application/json"})

        return SHARED.ResidentLlamaAdapter(config or self.config, self.store,
                                          transport=httpx.MockTransport(respond), clock=lambda: 0)

    def test_real_public_pins_native_schema_template_sampling_and_full_prompt_usage(self):
        self.assertEqual(hashlib.sha256(MANIFEST).hexdigest(), SHARED.SHARED_MANIFEST_SHA)
        self.assertEqual(hashlib.sha256(PARAMS).hexdigest(), SHARED.SHARED_PARAMS_SHA)
        original = deepcopy(SCHEMA)
        with StructuredModelClient(self.adapter()) as client:
            result = client.generate("원 근거 그대로\n", SCHEMA, self.config.model_id)
        self.assertEqual(result.data, {"answer": 7})
        self.assertEqual(SCHEMA, original)
        self.assertEqual([request[:2] for request in self.requests],
                         [("GET", "/props"), ("POST", "/completion"), ("GET", "/props")])
        body = self.requests[1][2]
        self.assertEqual(body["json_schema"], original)
        self.assertFalse(body["stream"])
        self.assertTrue(body["cache_prompt"])
        self.assertTrue(body["prompt"].startswith("<|im_start|>user\n"))
        self.assertTrue(body["prompt"].endswith("<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"))
        self.assertIn("요청:\n원 근거 그대로", body["prompt"])
        self.assertEqual((body["temperature"], body["seed"], body["n_predict"],
                          body["top_k"], body["top_p"], body["min_p"]), (0, 42, 4096, 20, 0.95, 0))
        meta = result.metadata
        self.assertEqual((meta["adapter"], meta["transport_api"]), ("llama.cpp", "/completion"))
        self.assertEqual((meta["prompt_eval_count"], meta["eval_count"]), (100, 8))
        self.assertEqual(meta["native_prompt_processed_count"], 20)
        self.assertEqual(meta["native_id_slot"], 2)
        self.assertEqual(meta["native_eval_duration_ns"], 2500000)
        self.assertFalse(meta["schema_prompt_embedded"])
        self.assertEqual(meta["constraint_mode"], "native_schema_and_local_validation")
        self.assertEqual(meta["gguf_byte_verification"], "launcher_required")

    def test_explicit_sampling_preserved(self):
        with self.adapter(replace(self.config, top_k=7, top_p=0.8, min_p=0.1, temperature=0.2)) as adapter:
            adapter.generate("text", SCHEMA)
        self.assertEqual(tuple(self.requests[1][2][key] for key in ("top_k", "top_p", "min_p", "temperature")),
                         (7, 0.8, 0.1, 0.2))

    def test_unverified_props_rejected_before_any_generation(self):
        for field, value in (("model_alias", "different"), ("model_path", "/different.gguf"),
                             ("total_slots", 1), ("total_slots", True), ("is_sleeping", True),
                             ("default_generation_settings", {"n_ctx": 65536}),
                             ("default_generation_settings", {"n_ctx": True})):
            with self.subTest(field=field, value=value):
                props = deepcopy(self.props)
                props[field] = value
                with patch.object(self, "props", props), self.adapter() as adapter:
                    with self.assertRaises(DomainError):
                        adapter.generate("text", SCHEMA)
                self.assertTrue(all(request[0] == "GET" for request in self.requests))
                self.requests.clear()

    def test_modified_local_manifest_or_params_reject_before_http(self):
        for path, original in ((self.manifest_path, MANIFEST), (self.params_path, PARAMS)):
            with self.subTest(path=path.name):
                path.write_bytes(original + b" ")
                with self.adapter() as adapter, self.assertRaises(DomainError):
                    adapter.generate("text", SCHEMA)
                self.assertEqual(self.requests, [])
                path.write_bytes(original)

    def test_after_generation_props_or_model_file_change_fails_closed(self):
        self.after_props = {**self.props, "total_slots": 1}
        with self.adapter() as adapter, self.assertRaises(DomainError):
            adapter.generate("text", SCHEMA)
        self.assertEqual(len(self.requests), 3)
        self.requests.clear()
        self.after_props = None
        self.after_completion = lambda: self.model_path.touch()
        with self.adapter() as adapter, self.assertRaises(DomainError) as caught:
            adapter.generate("text", SCHEMA)
        self.assertEqual(caught.exception.details["reason"], "service_identity_changed")

    def test_terminal_identity_truncation_and_missing_usage_are_not_accepted(self):
        invalid = [{"model": "other"}, {"truncated": True}, {"stop_type": "limit"},
                   {"stop": False}, {"stop_type": "none"}, {"tokens_evaluated": None},
                   {"tokens_predicted": True}, {"id_slot": 4},
                   {"timings": {"prompt_n": 20, "predicted_n": 9, "prompt_ms": 1, "predicted_ms": 1}},
                   {"timings": {"prompt_n": 20, "predicted_n": 8, "prompt_ms": 1e300, "predicted_ms": 1}}]
        for changes in invalid:
            with self.subTest(changes=changes):
                with patch.object(self, "native", {**self.native, **changes}), self.adapter() as adapter:
                    with self.assertRaises(DomainError):
                        adapter.generate("text", SCHEMA)
                self.requests.clear()

    def test_local_schema_validation_and_original_response_bound_remain_enforced(self):
        self.native["content"] = '{"answer":"not an integer"}'
        with StructuredModelClient(self.adapter()) as client, self.assertRaises(DomainError) as caught:
            client.generate("text", SCHEMA, self.config.model_id)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.native["content"] = "x" * 270000
        self.requests.clear()
        with self.adapter() as adapter, self.assertRaises(DomainError) as caught:
            adapter.generate("text", SCHEMA)
        self.assertEqual(caught.exception.details["reason"], "response_too_large")

    def test_wire_prompt_budget_includes_chatml_and_rejects_before_completion(self):
        with self.adapter() as adapter, self.assertRaises(DomainError) as caught:
            adapter.generate("x" * 24000, SCHEMA)
        self.assertEqual(caught.exception.details["reason"], "prompt_too_large")
        self.assertEqual([request[:2] for request in self.requests], [("GET", "/props")])

    def test_mismatched_engine_configuration_fails_before_transport(self):
        for changes in ({"thinking": True}, {"context_tokens": 8192}, {"api_mode": "chat"},
                        {"endpoint": "http://127.0.0.1:18874"}, {"expected_digest": "a" * 64}):
            with self.subTest(changes=changes), self.assertRaises(DomainError):
                self.adapter(replace(self.config, **changes))
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
