"""Real file protocol + fixture upstream tests, never a live product model claim."""
import base64
import copy
import os
import tempfile
import threading
import unittest
from pathlib import Path

import httpx

from services.automation.product_rpc import (
    DIGEST,
    MODEL,
    REQUEST,
    RESPONSE,
    FileRelay,
    FileTransport,
    ProxyEndpoint,
    RPCError,
    checked_request,
    checked_settings,
    decode,
    encode,
    read_file,
    sha,
    write_file,
)

RUN = "product-" + "a" * 40
SETTINGS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 512}


def generation():
    return {"model": MODEL, "prompt": "Fixture product request", "format": {"type": "object"},
            "stream": False, "think": False, "options": SETTINGS, "keep_alive": "5m"}


def request(sequence=1, *, method="POST", path="/api/generate", body=None):
    value = {"schema_version": 1, "run_id": RUN, "sequence": sequence,
             "method": method, "path": path, "body": generation() if body is None else body}
    value["request_sha256"] = sha(encode(value))
    return value


def completion(**changes):
    return encode({"model": MODEL, "done": True, "response": '{"fixture":true}',
                   "prompt_eval_count": 11, "eval_count": 7, **changes})


class ProductRPCTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.artifacts = self.root / "artifacts"
        self.private = self.root / "private"
        self.artifacts.mkdir()
        self.private.mkdir()
        self.calls = []
        self.on = True

    def relay(self, *, upstream=None, **bounds):
        def fixture_upstream(method, path, body):
            self.calls.append((method, path, body))
            return completion() if method == "POST" else encode({"models": [{"name": MODEL, "digest": DIGEST}]})
        return FileRelay(self.artifacts, self.private / "relay.json", RUN, settings=SETTINGS,
                         max_generations=bounds.get("max_generations", 2), max_tokens=bounds.get("max_tokens", 100),
                         enabled=lambda: self.on, upstream=upstream or fixture_upstream,
                         origin={"job_id": "fixture-job"})

    def test_file_transport_relay_roundtrip_keeps_original_bytes_and_usage(self):
        relay = self.relay()
        stop = threading.Event()
        failures = []

        def pump():
            while not stop.is_set():
                try:
                    relay.step()
                except (RPCError, OSError, ValueError) as exc:
                    failures.append(exc)
                    return
                stop.wait(0.005)
        thread = threading.Thread(target=pump)
        thread.start()
        try:
            with httpx.Client(transport=FileTransport(self.artifacts, RUN, timeout_seconds=2, poll_seconds=0.005)) as client:
                tags = client.get("http://127.0.0.1:18873/api/tags")
                response = client.post("http://127.0.0.1:18873/api/generate", json=generation())
            self.assertEqual(tags.json()["models"][0]["digest"], DIGEST)
            self.assertEqual(response.content, completion())
        finally:
            stop.set()
            thread.join(3)
        self.assertFalse(failures)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(relay.state["generations"], 1)
        self.assertEqual(relay.state["tokens"], 18)
        row = relay.state["requests"][1]
        self.assertEqual(base64.b64decode(row["response_base64"]), completion())
        self.assertEqual(row["response_sha256"], sha(completion()))
        self.assertEqual(relay.state["approved_origin"], {"job_id": "fixture-job"})

    def test_processed_identical_request_not_replayed_and_mutation_rejected(self):
        relay = self.relay()
        value = request()
        write_file(self.artifacts / REQUEST, value)
        self.assertTrue(relay.step())
        self.assertFalse(relay.step())
        self.assertFalse(self.relay().step())
        self.assertEqual(len(self.calls), 1)
        value["body"]["prompt"] = "Changed after execution"
        value["request_sha256"] = sha(encode({key: data for key, data in value.items() if key != "request_sha256"}))
        write_file(self.artifacts / REQUEST, value)
        with self.assertRaises(RPCError):
            relay.step()
        self.assertEqual(len(self.calls), 1)

    def test_reserved_unknown_cost_restart_never_replays(self):
        relay = self.relay()
        value = request()
        relay.state["requests"] = [{"sequence": 1, "request_sha256": value["request_sha256"], "request": value,
                                     "state": "reserved", "generation": True}]
        relay.state["generations"] = 1
        relay._save()
        write_file(self.artifacts / REQUEST, value)
        restored = self.relay()
        with self.assertRaises(RPCError):
            restored.step()
        self.assertEqual(restored.state["tokens"], 100)
        self.assertFalse(self.calls)

    def test_unknown_model_tokens_and_unavailable_response_hold_no_fabrication(self):
        for raw in (completion(prompt_eval_count=None), b'{"error":"fixture unavailable"}'):
            with self.subTest(raw=raw):
                journal = self.private / "relay.json"
                if journal.exists():
                    journal.unlink()
                relay = self.relay(upstream=lambda *_args, raw=raw: raw)
                write_file(self.artifacts / REQUEST, request())
                with self.assertRaises(RPCError):
                    relay.step()
                self.assertEqual(relay.state["tokens"], 100)
                self.assertTrue(relay.state["requests"][0]["usage_unknown"])
                self.assertFalse((self.artifacts / RESPONSE).exists())
                with self.assertRaises(RPCError):
                    self.relay().step()

    def test_off_before_call_and_during_completion_never_delivers(self):
        relay = self.relay()
        self.on = False
        write_file(self.artifacts / REQUEST, request())
        with self.assertRaises(RPCError):
            relay.step()
        self.assertFalse(self.calls)
        self.on = True

        def upstream(*_args):
            self.on = False
            return completion()
        relay = self.relay(upstream=upstream)
        with self.assertRaises(RPCError):
            relay.step()
        self.assertEqual(relay.state["tokens"], 18)
        self.assertEqual(relay.state["requests"][0]["state"], "completed")
        self.assertFalse((self.artifacts / RESPONSE).exists())

    def test_generation_limit_survives_restart_and_actual_token_overage_holds(self):
        relay = self.relay(max_generations=1)
        write_file(self.artifacts / REQUEST, request())
        relay.step()
        write_file(self.artifacts / REQUEST, request(2))
        with self.assertRaises(RPCError):
            self.relay(max_generations=1).step()
        self.assertEqual(len(self.calls), 1)
        (self.private / "relay.json").unlink()
        (self.artifacts / RESPONSE).unlink()
        write_file(self.artifacts / REQUEST, request())
        with self.assertRaises(RPCError):
            self.relay(max_tokens=10).step()
        self.assertFalse((self.artifacts / RESPONSE).exists())

    def test_identity_route_schema_settings_and_pin_refused(self):
        for mutate in (
            lambda value: value.update(sequence=2),
            lambda value: value.update(path="/api/pull"),
            lambda value: value["body"].update(model="unapproved-model"),
            lambda value: value["body"].update(think=True),
            lambda value: value["body"].update(format={"$ref": "https://example.invalid/schema"}),
            lambda value: value["body"].update(options={**SETTINGS, "num_predict": 1024}),
        ):
            value = request()
            mutate(value)
            value["request_sha256"] = sha(encode({key: data for key, data in value.items() if key != "request_sha256"}))
            with self.subTest(value=value), self.assertRaises(RPCError):
                checked_request(value, RUN, 1, SETTINGS)
        for settings in ({**SETTINGS, "num_ctx": True}, {**SETTINGS, "temperature": False},
                         {**SETTINGS, "seed": 0}, {**SETTINGS, "num_predict": 32768}):
            with self.subTest(settings=settings), self.assertRaises(RPCError):
                checked_settings(settings)
        write_file(self.artifacts / REQUEST, request(method="GET", path="/api/tags", body=None))
        value = request(method="GET", path="/api/tags")
        value["body"] = None
        value["request_sha256"] = sha(encode({key: data for key, data in value.items() if key != "request_sha256"}))
        write_file(self.artifacts / REQUEST, value)
        with self.assertRaises(RPCError):
            self.relay(upstream=lambda *_args: encode({"models": [{"name": MODEL, "digest": "f" * 64}]})).step()

    def test_fixed_proxy_rejects_redirects_and_never_uses_arbitrary_endpoint(self):
        seen = []

        def endpoint(req):
            seen.append(req.url)
            return httpx.Response(302, headers={"location": "https://example.invalid"})
        proxy = ProxyEndpoint(transport=httpx.MockTransport(endpoint))
        with self.assertRaises(RPCError):
            proxy("POST", "/api/generate", generation())
        self.assertEqual(str(seen[0]), "http://127.0.0.1:18873/api/generate")
        with self.assertRaises(RPCError):
            proxy("POST", "/api/generate?url=other", generation())

    def test_guest_cannot_choose_host_port_or_smuggle_auth_query(self):
        transport = FileTransport(self.artifacts, RUN, timeout_seconds=0.01)
        for url in ("http://127.0.0.1:18874/api/tags", "http://user:password@127.0.0.1:18873/api/tags",
                    "http://127.0.0.1:18873/api/tags?token=secret", "https://example.invalid/api/tags"):
            with self.subTest(url=url), self.assertRaises(httpx.TransportError):
                transport.handle_request(httpx.Request("GET", url))
        self.assertFalse((self.artifacts / REQUEST).exists())

    def test_regular_bytes_preserved_and_link_hardlink_temp_and_duplicate_json_refused(self):
        target = self.artifacts / REQUEST
        target.write_bytes(b"one\r\ntwo\n")
        self.assertEqual(read_file(target, 100), b"one\r\ntwo\n")
        alias = self.artifacts / "alias"
        os.link(target, alias)
        with self.assertRaises(RPCError):
            read_file(target, 100)
        alias.unlink()
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(b"unexpected")
        with self.assertRaises(RPCError):
            write_file(target, {})
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(RPCError):
                decode(data)
        outside = self.private / "linked.json"
        outside.write_bytes(b"outside")
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            return  # Windows without symlink privilege: hard-link boundary still tested.
        with self.assertRaises(RPCError):
            read_file(target, 100)

    def test_guest_modified_response_hash_is_not_accepted(self):
        value = request()
        response = {"schema_version": 1, "run_id": RUN, "sequence": 1, "request_sha256": value["request_sha256"],
                    "response_sha256": "f" * 64, "response_base64": base64.b64encode(completion()).decode()}
        write_file(self.artifacts / RESPONSE, response)
        transport = FileTransport(self.artifacts, RUN, timeout_seconds=0.05)
        with self.assertRaises(httpx.TransportError):
            transport.handle_request(httpx.Request("POST", "http://127.0.0.1:18873/api/generate", json=generation()))

    def test_config_or_origin_change_cannot_reset_reserved_accounting(self):
        relay = self.relay()
        write_file(self.artifacts / REQUEST, request())
        relay.step()
        with self.assertRaises(RPCError):
            FileRelay(self.artifacts, self.private / "relay.json", RUN, settings=copy.deepcopy(SETTINGS),
                      max_generations=3, max_tokens=100, enabled=lambda: True,
                      origin={"job_id": "fixture-job"})
        with self.assertRaises(RPCError):
            FileRelay(self.artifacts, self.private / "relay.json", RUN, settings=SETTINGS,
                      max_generations=2, max_tokens=100, enabled=lambda: True, origin={"job_id": "other-job"})


if __name__ == "__main__":
    unittest.main()
