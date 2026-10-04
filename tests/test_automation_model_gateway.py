import json
import unittest

import httpx

from services.automation.model_gateway import DIGEST, MODEL, Gateway, checked_payload
from services.automation.state import ControlError


def payload():
    return {"model": MODEL, "prompt": "실제 구조화 검사", "stream": False, "think": False, "keep_alive": "5m",
            "format": {"type": "object"}, "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 256}}


class ModelGatewayTests(unittest.TestCase):
    def test_exact_generation_settings_and_verified_digest(self):
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": MODEL, "digest": DIGEST}]})
            return httpx.Response(200, json={"model": MODEL, "done": True, "response": '{"ok":true}'})

        result = Gateway({}, httpx.MockTransport(respond)).generate("ginaginaring", payload())
        self.assertEqual(json.loads(requests[1].content), payload())
        self.assertTrue(result["done"])
        self.assertEqual(str(requests[1].url), "http://127.0.0.1:18864/api/generate")

    def test_wrong_revision_rejects_before_generation(self):
        calls = []

        def respond(request):
            calls.append(request.url.path)
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": "wrong"}]})

        with self.assertRaises(ControlError):
            Gateway({}, httpx.MockTransport(respond)).generate("jeongiryang", payload())
        self.assertEqual(calls, ["/api/tags"])

    def test_busy_is_bounded_and_explicit(self):
        gateway = Gateway({})
        gateway.lock.acquire()
        with self.assertRaises(ControlError) as raised:
            gateway.generate("unknownamed", payload())
        self.assertEqual(raised.exception.status, 429)

    def test_forbidden_settings(self):
        changes = [{"model": "another"}, {"url": "http://elsewhere"}, {"stream": True}, {"think": "false"}, {"keep_alive": "forever"},
                   {"prompt": "x" * 45001}, {"options": {"num_predict": 9000}}]
        for change in changes:
            with self.subTest(change=list(change)), self.assertRaises(ControlError):
                checked_payload({**payload(), **change})

    def test_cannot_change_upstream_or_digest(self):
        for config in ({"upstream": "http://127.0.0.1:11434"}, {"digest": "wrong"}):
            with self.assertRaises(ValueError):
                Gateway(config)

    def test_failed_http_never_fabricates_response(self):
        with self.assertRaises(ControlError):
            Gateway({}, httpx.MockTransport(lambda _r: httpx.Response(503))).tags()

    def test_partial_model_response_rejected(self):
        def respond(request):
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": DIGEST}]} if request.url.path.endswith("tags")
                                  else {"model": MODEL, "done": False, "response": ""})
        with self.assertRaises(ControlError):
            Gateway({}, httpx.MockTransport(respond)).generate("choigilung", payload())

    def test_revision_change_during_generation_rejects_output(self):
        tag_reads = []

        def respond(request):
            if request.url.path.endswith("tags"):
                tag_reads.append(True)
                return httpx.Response(200, json={"models": [{"name": MODEL, "digest": DIGEST if len(tag_reads) == 1 else "changed"}]})
            return httpx.Response(200, json={"model": MODEL, "done": True, "response": "{}"})
        with self.assertRaises(ControlError):
            Gateway({}, httpx.MockTransport(respond)).generate("jeongiryang", payload())
