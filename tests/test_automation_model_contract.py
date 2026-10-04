"""Existing core client against the real gateway contract with a simulated upstream."""

import json
import tempfile
import unittest
from pathlib import Path

import httpx
from lgax_core.errors import DomainError
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient

from services.automation.model_gateway import DIGEST, MODEL, Gateway
from services.automation.state import ControlError

SCHEMA = {"type": "object", "properties": {"message": {"type": "string"}},
          "required": ["message"], "additionalProperties": False}


class SharedModelContractTests(unittest.TestCase):
    def make_client(self, upstream, gateway_config=None):
        gateway = Gateway(gateway_config or {}, httpx.MockTransport(upstream))
        local_requests = []

        def local_proxy(request):
            local_requests.append(request)
            try:
                if request.method == "GET" and request.url.path == "/api/tags":
                    value = gateway.tags()
                elif request.method == "POST" and request.url.path == "/api/generate":
                    value = gateway.generate("unknownamed", json.loads(request.content))
                else:
                    return httpx.Response(404)
                return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value, ensure_ascii=False).encode()),
                                      headers={"Content-Type": "application/json"})
            except ControlError as failure:
                return httpx.Response(failure.status, json={"error": str(failure)})

        client = StructuredModelClient(OllamaAdapter(
            ModelConfig("http://127.0.0.1:18873", MODEL, DIGEST, max_output_tokens=512),
            transport=httpx.MockTransport(local_proxy)))
        self.addCleanup(client.close)
        return client, gateway, local_requests

    @staticmethod
    def normal_response(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": DIGEST}]})
        return httpx.Response(200, json={"model": MODEL, "done": True, "done_reason": "stop",
                                         "response": '{"message":"구조화 응답"}', "eval_count": 7,
                                         "prompt_eval_count": 12, "total_duration": 1_000_000})

    def test_existing_client_full_payload_survives_gateway_and_pins_before_and_after(self):
        upstream_requests = []

        def respond(request):
            upstream_requests.append(request)
            return self.normal_response(request)

        client, _gateway, requests = self.make_client(respond)
        result = client.generate("상품기획 근거를 구조화해줘", SCHEMA, MODEL)
        self.assertEqual(result.data, {"message": "구조화 응답"})
        self.assertEqual(result.metadata["revision"], DIGEST)
        self.assertEqual(result.metadata["pin_verification"], "before_and_after_generation")
        self.assertTrue(result.metadata["locally_validated"])
        self.assertEqual([r.url.path for r in requests], ["/api/tags", "/api/generate", "/api/tags"])
        generation = next(r for r in upstream_requests if r.method == "POST")
        payload = json.loads(generation.content)
        self.assertEqual(payload["keep_alive"], "5m")
        self.assertEqual(payload["format"], SCHEMA)
        self.assertEqual(payload["options"], {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 512})
        self.assertEqual(str(generation.url), "http://127.0.0.1:18864/api/generate")
        self.assertEqual([r.url.path for r in upstream_requests],
                         ["/api/tags", "/api/tags", "/api/generate", "/api/tags", "/api/tags"])

    def test_changed_digest_after_generation_never_becomes_success_or_valid_metadata_log(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "metadata.jsonl"

            def respond(request):
                calls.append(request)
                if request.url.path == "/api/tags" and len([r for r in calls if r.url.path == "/api/tags"]) >= 3:
                    return httpx.Response(200, json={"models": [{"name": MODEL, "digest": "b" * 64}]})
                return self.normal_response(request)

            client, gateway, _requests = self.make_client(respond, {"metadata_log": str(log)})
            with self.assertRaises(DomainError) as failure:
                client.generate("사후 pin 변경 검사", SCHEMA, MODEL)
            self.assertEqual(failure.exception.code, "MODEL_UNAVAILABLE")
            self.assertFalse(log.exists())
            self.assertFalse(gateway.lock.locked())
            self.assertEqual(sum(r.method == "POST" for r in calls), 1)

    def test_gateway_busy_response_reaches_existing_core_as_failure_without_generation(self):
        calls = []

        def respond(request):
            calls.append(request)
            return self.normal_response(request)

        client, gateway, _requests = self.make_client(respond)
        gateway.lock.acquire()
        self.addCleanup(gateway.lock.release)
        with self.assertRaises(DomainError) as failure:
            client.generate("동시 GPU 작업 검사", SCHEMA, MODEL)
        self.assertEqual(failure.exception.code, "MODEL_UNAVAILABLE")
        self.assertEqual(sum(r.method == "POST" for r in calls), 0)


if __name__ == "__main__":
    unittest.main()
