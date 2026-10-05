"""Real file protocol + fixture upstream tests, never a live product model claim."""
import base64
import copy
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient

from services.automation import product_rpc
from services.automation.product_rpc import (
    DIGEST,
    MAX_REQUESTS,
    MODEL,
    FileRelay,
    FileTransport,
    ProxyEndpoint,
    RPCError,
    RPCReadUnstable,
    checked_request,
    checked_settings,
    decode,
    encode,
    read_file,
    request_paths,
    response_paths,
    sha,
    write_file,
    write_request,
    write_response,
)

RUN = "product-" + "a" * 40
RESPONSE = "legacy-response-fixture.json"
REQUEST = "legacy-request-fixture.json"
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

    def test_actual_application_stream_lifecycle_reads_pins_generation_and_reuses_client(self):
        # Fixture upstream only. Exercise the application's actual iter_raw()
        # consumption, which plain client.get() roundtrips cannot cover.
        def scheduled_fixture_upstream(method, path, body):
            self.calls.append((method, path, body))
            # ModelConfig's single end-to-end deadline spans tags/generate/tags.
            # Reproduce scheduling delay exceeding the previous two seconds.
            time.sleep(0.8)
            return completion() if method == "POST" else encode({"models": [{"name": MODEL, "digest": DIGEST}]})
        relay = self.relay(upstream=scheduled_fixture_upstream)
        stop, failures = threading.Event(), []

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
            # One application deadline covers three durable file exchanges.
            # Leave room for Windows filesystem/AV scheduling in CI fixtures.
            config = ModelConfig("http://127.0.0.1:18873", MODEL, DIGEST, timeout_seconds=10,
                                 max_output_tokens=SETTINGS["num_predict"], context_tokens=SETTINGS["num_ctx"])
            with StructuredModelClient(OllamaAdapter(config, transport=FileTransport(
                    self.artifacts, RUN, timeout_seconds=10, poll_seconds=0.005))) as client:
                for _ in range(2):
                    result = client.generate("Fixture application input", {"type": "object"}, MODEL)
                    self.assertEqual(result.data, {"fixture": True})
                    self.assertEqual(result.metadata["pin_verification"], "before_and_after_generation")
                    self.assertEqual(result.metadata["prompt_eval_count"], 11)
                    self.assertEqual(result.metadata["eval_count"], 7)
        finally:
            stop.set()
            thread.join(3)
            self.assertFalse(failures, "fixture relay failure must not be obscured by a client deadline")
        self.assertFalse(failures)
        self.assertEqual([path for _, path, _ in self.calls], ["/api/tags", "/api/generate", "/api/tags"] * 2)
        self.assertEqual(relay.state["generations"], 2)
        self.assertEqual(relay.state["tokens"], 36)

    def test_processed_identical_request_not_replayed_and_mutation_rejected(self):
        relay = self.relay()
        value = request()
        write_request(self.artifacts, value["sequence"], value)
        self.assertTrue(relay.step())
        self.assertFalse(relay.step())
        self.assertFalse(self.relay().step())
        self.assertEqual(len(self.calls), 1)
        value["body"]["prompt"] = "Changed after execution"
        value["request_sha256"] = sha(encode({key: data for key, data in value.items() if key != "request_sha256"}))
        request_paths(self.artifacts, value["sequence"])[0].write_bytes(encode(value))
        with self.assertRaises(RPCError):
            relay.step()
        self.assertEqual(len(self.calls), 1)

    def test_immutable_delivery_never_replaces_previous_response_or_replays_upstream(self):
        relay = self.relay()
        original = Path.replace
        def reject_response_exchange(source, target):
            if source.parent == self.artifacts and source.name.startswith("product-response-"):
                raise AssertionError("immutable responses must not replace a polled file")
            return original(source, target)
        with patch.object(Path, "replace", reject_response_exchange):
            write_request(self.artifacts, 1, request())
            self.assertTrue(relay.step())
            first, ready = response_paths(self.artifacts, 1)
            original_bytes = first.read_bytes()
            self.assertEqual(ready.read_bytes(), b"")
            value = request(2, method="GET", path="/api/tags")
            value["body"] = None
            value["request_sha256"] = sha(encode({k: v for k, v in value.items() if k != "request_sha256"}))
            write_request(self.artifacts, value["sequence"], value)
            self.assertTrue(relay.step())
            self.assertEqual(first.read_bytes(), original_bytes)
            self.assertTrue(response_paths(self.artifacts, 2)[1].exists())
            self.assertFalse(relay.step())
            self.assertFalse(self.relay().step())
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(relay.state["tokens"], 18)

    def test_existing_immutable_response_identity_is_never_overwritten_or_replayed(self):
        for selected in ("response", "ready", "temp"):
            with self.subTest(selected=selected):
                artifacts = self.root / selected
                artifacts.mkdir()
                target, ready = response_paths(artifacts, 1)
                planted = {"response": target, "ready": ready, "temp": target.with_suffix(".tmp")}[selected]
                planted.write_bytes(b"planted")
                calls = []
                relay = FileRelay(artifacts, self.private / (selected + ".json"), RUN, settings=SETTINGS,
                    max_generations=2, max_tokens=100, enabled=lambda: self.on,
                    upstream=lambda *args, recorded=calls: recorded.append(args) or completion())
                write_request(artifacts, 1, request())
                with self.assertRaises(RPCError):
                    relay.step()
                self.assertEqual(planted.read_bytes(), b"planted")
                self.assertEqual(len(calls), 1)
                self.assertEqual(relay.state["tokens"], 18)
                with self.assertRaises(RPCError):
                    relay.step()
                self.assertEqual(len(calls), 1)

    def test_atomic_retry_refuses_changed_temp_bytes_and_off_before_delivery(self):
        for mode in ("tampered", "off"):
            with self.subTest(mode=mode):
                directory = self.root / mode
                directory.mkdir()
                destination = directory / RESPONSE
                original = Path.replace

                def refused_reader(source, target, selected=mode, expected=destination, replace=original):
                    if source == expected.with_suffix(".tmp"):
                        if selected == "tampered":
                            source.write_bytes(b"{}")
                        else:
                            self.on = False
                        error = PermissionError("fixture sharing denial")
                        error.winerror = 5
                        raise error
                    return replace(source, target)
                self.on = True
                with patch.object(product_rpc.os, "name", "nt"), patch.object(Path, "replace", refused_reader), \
                        self.assertRaises(RPCError):
                    write_file(destination, {"fixture": "unchanged source"}, enabled=lambda: self.on)
                self.assertFalse(destination.exists())

    def test_only_bounded_ordinary_atomic_read_replacement_is_transient(self):
        target = self.artifacts / RESPONSE
        replacement = self.artifacts / "replacement.json"
        original = Path.lstat
        for mode in ("ordinary", "inplace", "oversize", "hardlink"):
            with self.subTest(mode=mode):
                target.write_bytes(b"old")
                replacement.write_bytes(b"new" if mode != "oversize" else b"x" * 50)
                alias = self.artifacts / "alias-replacement"
                if mode == "hardlink":
                    os.link(replacement, alias)
                samples = []

                def exchange_at_final(path, *, selected=mode, observed=samples):
                    if path == target:
                        observed.append(True)
                        if len(observed) == 2:
                            if selected == "inplace":
                                path.write_bytes(b"same-inode-mutation")
                            else:
                                replacement.replace(path)
                    return original(path)
                with patch.object(Path, "lstat", exchange_at_final), self.assertRaises(RPCError) as caught:
                    read_file(target, 30)
                self.assertEqual(isinstance(caught.exception, RPCReadUnstable), mode == "ordinary")
                if alias.exists():
                    alias.unlink()
                if replacement.exists():
                    replacement.unlink()
                target.unlink()

    def test_published_request_replacement_fails_before_any_reservation_or_upstream(self):
        relay = self.relay()
        write_request(self.artifacts, 1, request())
        original, first = product_rpc.read_file, [True]

        def atomic_read(path, maximum):
            if path == request_paths(self.artifacts, 1)[0] and first[0]:
                first[0] = False
                raise RPCReadUnstable("fixture ordinary atomic exchange")
            return original(path, maximum)
        with patch.object(product_rpc, "read_file", atomic_read):
            with self.assertRaises(RPCReadUnstable):
                relay.step()
            self.assertEqual(relay.state["requests"], [])
            self.assertFalse(self.calls)
        self.assertEqual(relay.state["generations"], 0)

    @unittest.skipIf(os.name == "nt", "Linux permits replacing an inode while its reader is still open")
    def test_linux_atomic_exchange_discards_old_unlinked_descriptor_without_relaxing_hardlinks(self):
        target = self.artifacts / RESPONSE
        replacement = self.artifacts / "replacement.json"
        target.write_bytes(b"old")
        replacement.write_bytes(b"new")
        original, calls = os.fstat, []

        def exchange_before_second_fstat(descriptor):
            calls.append(True)
            if len(calls) == 2:
                replacement.replace(target)
            return original(descriptor)
        with patch.object(product_rpc.os, "fstat", exchange_before_second_fstat), self.assertRaises(RPCReadUnstable):
            read_file(target, 30)
        self.assertEqual(read_file(target, 30), b"new")

    def test_published_response_replacement_is_fatal_without_request_rewrite(self):
        value = request()
        response = {"schema_version": 1, "run_id": RUN, "sequence": 1, "request_sha256": value["request_sha256"],
                    "response_sha256": sha(completion()), "response_base64": base64.b64encode(completion()).decode()}
        write_response(self.artifacts, 1, response, enabled=lambda: True)
        original = product_rpc.read_file
        def unstable(path, maximum):
            if path == response_paths(self.artifacts, 1)[0]:
                raise RPCReadUnstable("fixture illegal exchange after immutable publication")
            return original(path, maximum)
        transport = FileTransport(self.artifacts, RUN, timeout_seconds=1, poll_seconds=0.001)
        with patch.object(product_rpc, "read_file", unstable), patch.object(
                product_rpc, "write_request", wraps=product_rpc.write_request) as writes:
            with self.assertRaises(RPCReadUnstable):
                transport.handle_request(httpx.Request("POST", "http://127.0.0.1:18873/api/generate", json=generation()))
            self.assertEqual(writes.call_count, 1)
        self.assertFalse(self.calls)


    def test_fixed_response_names_and_request_limit_refuse_noncanonical_identity(self):
        for value in (0, 41, True, "1", 1.0, None):
            with self.subTest(value=value), self.assertRaises(RPCError):
                response_paths(self.artifacts, value)
        self.assertEqual(response_paths(self.artifacts, 40)[0].name, "product-response-40.json")
        transport = FileTransport(self.artifacts, RUN, timeout_seconds=0.01)
        transport.sequence = MAX_REQUESTS
        with self.assertRaises(httpx.TransportError):
            transport.handle_request(httpx.Request("GET", "http://127.0.0.1:18873/api/tags"))
        self.assertFalse(request_paths(self.artifacts, 1)[0].exists())

    def test_response_is_not_read_before_ready_or_from_another_sequence(self):
        value = request()
        envelope = {"schema_version": 1, "run_id": RUN, "sequence": 1,
            "request_sha256": value["request_sha256"], "response_sha256": sha(completion()),
            "response_base64": base64.b64encode(completion()).decode()}
        target, ready = response_paths(self.artifacts, 1)
        # A future response and a fully written-but-not-published current response
        # are never polled while waiting for current sequence readiness.
        write_response(self.artifacts, 2, {"invalid": "future fixture"}, enabled=lambda: True)
        target.write_bytes(encode(envelope))
        original, reads = product_rpc.read_file, []
        def tracked(path, maximum):
            reads.append(path)
            return original(path, maximum)
        def publish_ready():
            time.sleep(0.03)
            with ready.open("xb"):
                pass
        thread = threading.Thread(target=publish_ready)
        thread.start()
        try:
            with patch.object(product_rpc, "read_file", tracked):
                actual = FileTransport(self.artifacts, RUN, timeout_seconds=1, poll_seconds=0.005).handle_request(
                    httpx.Request("POST", "http://127.0.0.1:18873/api/generate", json=generation()))
                self.assertEqual(actual.read(), completion())
        finally:
            thread.join(2)
        self.assertEqual([p for p in reads if p.name.startswith("product-response-")], [ready, target])
        self.assertFalse(self.calls)

    def test_atomic_no_replace_publication_hides_intermediate_hardlink_from_reader(self):
        value = request()
        envelope = {"schema_version": 1, "run_id": RUN, "sequence": 1,
            "request_sha256": value["request_sha256"], "response_sha256": sha(completion()),
            "response_base64": base64.b64encode(completion()).decode()}
        target, ready = response_paths(self.artifacts, 1)
        original, observed = os.link, []
        def link_and_observe(source, destination, **kwargs):
            original(source, destination, **kwargs)
            self.assertEqual(target.stat().st_nlink, 2)
            self.assertFalse(ready.exists())
            observed.append(True)
        with patch.object(product_rpc.os, "link", link_and_observe):
            write_response(self.artifacts, 1, envelope, enabled=lambda: True)
        self.assertEqual(observed, [True])
        self.assertEqual(target.stat().st_nlink, 1)
        self.assertFalse(target.with_suffix(".tmp").exists())
        self.assertEqual(read_file(ready, 0), b"")
        self.assertEqual(decode(read_file(target, 10000)), envelope)
        with self.assertRaises(RPCError):
            write_response(self.artifacts, 1, envelope, enabled=lambda: True)

    def test_tampered_publication_or_off_after_link_has_no_ready_marker(self):
        for selected in ("tamper", "off"):
            with self.subTest(selected=selected):
                artifacts = self.root / ("publish-" + selected)
                artifacts.mkdir()
                target, ready = response_paths(artifacts, 1)
                original = os.link
                def altered(source, destination, link=original, mode=selected, dest=target, **kwargs):
                    link(source, destination, **kwargs)
                    if mode == "tamper":
                        dest.write_bytes(b"changed actual bytes")
                    else:
                        self.on = False
                self.on = True
                with patch.object(product_rpc.os, "link", altered), self.assertRaises(RPCError):
                    write_response(artifacts, 1, {"actual": "fixture"}, enabled=lambda: self.on)
                self.assertFalse(ready.exists())

    def test_ready_marker_and_response_links_and_identity_remain_fatal(self):
        value = request()
        envelope = {"schema_version": 1, "run_id": RUN, "sequence": 1,
            "request_sha256": value["request_sha256"], "response_sha256": sha(completion()),
            "response_base64": base64.b64encode(completion()).decode()}
        for selected in ("ready_nonempty", "ready_hardlink", "response_hardlink", "wrong_sequence", "boolean_sequence", "wrong_run", "wrong_request"):
            with self.subTest(selected=selected):
                artifacts = self.root / ("verify-" + selected)
                artifacts.mkdir()
                target, ready = response_paths(artifacts, 1)
                forged = copy.deepcopy(envelope)
                if selected == "wrong_sequence": forged["sequence"] = 2
                if selected == "boolean_sequence": forged["sequence"] = True
                if selected == "wrong_run": forged["run_id"] = "product-" + "b" * 40
                if selected == "wrong_request": forged["request_sha256"] = "f" * 64
                write_response(artifacts, 1, forged, enabled=lambda: True)
                if selected == "ready_nonempty": ready.write_bytes(b"changed")
                if selected == "ready_hardlink": os.link(ready, artifacts / "alias")
                if selected == "response_hardlink": os.link(target, artifacts / "alias")
                with self.assertRaises((RPCError, httpx.TransportError)):
                    FileTransport(artifacts, RUN, timeout_seconds=0.1).handle_request(
                        httpx.Request("POST", "http://127.0.0.1:18873/api/generate", json=generation()))
                self.assertFalse(self.calls)

    def test_completed_request_mutation_or_deletion_blocks_next_dispatch(self):
        for mode in ("bytes", "deleted", "marker_deleted", "marker_changed"):
            with self.subTest(mode=mode):
                artifacts = self.root / ("prior-" + mode)
                artifacts.mkdir()
                calls = []
                relay = FileRelay(artifacts, self.private / ("prior-" + mode + ".json"), RUN, settings=SETTINGS,
                    max_generations=2, max_tokens=100, enabled=lambda: True,
                    upstream=lambda *args, recorded=calls: recorded.append(args) or completion())
                write_request(artifacts, 1, request())
                relay.step()
                write_request(artifacts, 2, request(2))
                prior, ready = request_paths(artifacts, 1)
                if mode == "bytes": prior.write_bytes(b"{}")
                if mode == "deleted": prior.unlink()
                if mode == "marker_deleted": ready.unlink()
                if mode == "marker_changed": ready.write_bytes(b"changed")
                with self.assertRaises((RPCError, OSError)):
                    relay.step()
                self.assertEqual(len(calls), 1)
                self.assertEqual(relay.state["tokens"], 18)
                self.assertEqual(relay.state["generations"], 1)
                self.assertEqual(len(relay.state["requests"]), 1)

    def test_all_forty_fixed_exchanges_finish_without_accessing_sequence_41(self):
        relay = self.relay()
        original, inspected = product_rpc.mailbox_paths, []
        def fixed_names(artifacts, kind, sequence):
            inspected.append((kind, sequence))
            self.assertLessEqual(sequence, MAX_REQUESTS)
            return original(artifacts, kind, sequence)
        with patch.object(product_rpc, "mailbox_paths", fixed_names):
            for sequence in range(1, MAX_REQUESTS + 1):
                value = request(sequence, method="GET", path="/api/tags")
                value["body"] = None
                value["request_sha256"] = sha(encode({k: v for k, v in value.items() if k != "request_sha256"}))
                write_request(self.artifacts, sequence, value)
                self.assertTrue(relay.step())
            self.assertFalse(relay.step())
            self.assertFalse(self.relay().step())
        self.assertEqual(len(self.calls), MAX_REQUESTS)
        self.assertEqual(relay.state["tokens"], 0)
        self.assertEqual(relay.state["generations"], 0)
        self.assertEqual(len(list(self.artifacts.iterdir())), MAX_REQUESTS * 4)
        self.assertTrue(all(sequence <= MAX_REQUESTS for _, sequence in inspected))
        self.assertFalse(any(path.suffix == ".tmp" for path in self.artifacts.iterdir()))
        with self.assertRaises(RPCError):
            write_request(self.artifacts, 41, request(41))

    def test_reserved_unknown_cost_restart_never_replays(self):
        relay = self.relay()
        value = request()
        relay.state["requests"] = [{"sequence": 1, "request_sha256": value["request_sha256"], "request": value,
                                     "state": "reserved", "generation": True}]
        relay.state["generations"] = 1
        relay._save()
        write_request(self.artifacts, value["sequence"], value)
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
                for fixture in request_paths(self.artifacts, 1):
                    if fixture.exists(): fixture.unlink()
                relay = self.relay(upstream=lambda *_args, raw=raw: raw)
                write_request(self.artifacts, 1, request())
                with self.assertRaises(RPCError):
                    relay.step()
                self.assertEqual(relay.state["tokens"], 100)
                self.assertTrue(relay.state["requests"][0]["usage_unknown"])
                self.assertFalse(response_paths(self.artifacts, 1)[0].exists())
                with self.assertRaises(RPCError):
                    self.relay().step()

    def test_off_before_call_and_during_completion_never_delivers(self):
        relay = self.relay()
        self.on = False
        write_request(self.artifacts, 1, request())
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
        self.assertFalse(response_paths(self.artifacts, 1)[0].exists())

    def test_off_during_durable_reservation_cancels_before_any_upstream_call(self):
        relay = self.relay()
        save = relay._save

        def save_and_turn_off():
            save()
            if relay.state["requests"]:
                self.on = False
        relay._save = save_and_turn_off
        write_request(self.artifacts, 1, request())
        with self.assertRaises(RPCError):
            relay.step()
        self.assertFalse(self.calls)
        self.assertEqual(relay.state["tokens"], 0)
        row = decode(read_file(self.private / "relay.json", 100000))["requests"][0]
        self.assertEqual(row["state"], "cancelled_before_dispatch")
        self.assertFalse(row["dispatch_started"])
        self.assertFalse(row["usage_unknown"])
        self.assertFalse(response_paths(self.artifacts, 1)[0].exists())
        restarted = self.relay()
        self.assertEqual(restarted.state["tokens"], 0)
        with self.assertRaises(RPCError):
            restarted.step()
        self.assertFalse(self.calls)

    def test_generation_limit_survives_restart_and_actual_token_overage_holds(self):
        relay = self.relay(max_generations=1)
        write_request(self.artifacts, 1, request())
        relay.step()
        write_request(self.artifacts, 2, request(2))
        with self.assertRaises(RPCError):
            self.relay(max_generations=1).step()
        self.assertEqual(len(self.calls), 1)
        (self.private / "relay.json").unlink()
        response_paths(self.artifacts, 1)[0].unlink()
        response_paths(self.artifacts, 1)[1].unlink()
        request_paths(self.artifacts, 1)[0].unlink()
        request_paths(self.artifacts, 1)[1].unlink()
        write_request(self.artifacts, 1, request())
        with self.assertRaises(RPCError):
            self.relay(max_tokens=10).step()
        self.assertFalse(response_paths(self.artifacts, 1)[0].exists())

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
        value = request(method="GET", path="/api/tags")
        value["body"] = None
        value["request_sha256"] = sha(encode({key: data for key, data in value.items() if key != "request_sha256"}))
        write_request(self.artifacts, value["sequence"], value)
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
        self.assertFalse(request_paths(self.artifacts, 1)[0].exists())

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
        write_response(self.artifacts, 1, response, enabled=lambda: True)
        transport = FileTransport(self.artifacts, RUN, timeout_seconds=0.05)
        with self.assertRaises(httpx.TransportError):
            transport.handle_request(httpx.Request("POST", "http://127.0.0.1:18873/api/generate", json=generation()))

    def test_config_or_origin_change_cannot_reset_reserved_accounting(self):
        relay = self.relay()
        write_request(self.artifacts, 1, request())
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
