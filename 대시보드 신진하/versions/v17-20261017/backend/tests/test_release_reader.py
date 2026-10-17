"""Synthetic artifact/HTTP tests; no user session, model or product DB is read."""
import hashlib
import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from backend import release_reader as module
from backend.release_reader import ReleaseReadError, ReleaseReader
from backend.release_server import ReleaseHTTPServer

TS = "2026-10-16T04:00:00Z"
NOW = datetime.fromisoformat(TS.replace("Z", "+00:00")).timestamp()
TOKEN = "test-only-release-view-01234567890123456789"
BUSINESS = {"session_id": "business-session", "turn_id": "business-turn", "request_key": "request-key"}


def fake_install(root):
    path = root / "product-doctor.py"
    path.write_text("# Synthetic immutable product marker; never executed.\n", encoding="utf-8")
    manifest = {"format": "codex-product-install-v1", "skills": sorted(module.SKILLS),
                "files": [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
    raw = json.dumps(manifest).encode()
    (root / "product-install.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def event(eid="event-1", *, kind="request", phase="point", prompt="prompt-b", ts=TS, detail=None, call=None, session="native-session"):
    return {"v": 1, "id": eid, "ts": ts, "ts_basis": "codex_log", "src": "codex", "hook": "UserPromptSubmit",
            "session": session, "prompt_id": prompt, "agent_id": None, "actor": "main", "tool": None, "call": call,
            "kind": kind, "node": "main", "op": None, "ops": [], "phase": phase, "basis": "observed", "detail": detail or {}}


def product_snapshot(binding=None):
    joined = BUSINESS if binding is None else binding
    return {"available": True, "read_at": TS, "binding": joined, "binding_status": "unverified_native_session",
            "request": {**joined, "status": "working", "question": "PRIVATE_QUESTION"},
            "turn": {"turn_id": joined["turn_id"], "status": "working", "revision_count": 0, "result_version": None, "valid": False, "created_at": TS},
            "results": 1, "candidates": [{"result_version": 1, "created_at": TS, "status": "needs_input", "counts": {"concepts": 2}, "prompt": "PRIVATE_CANDIDATE"}],
            "workflow_events": [], "evidence_delivered": None, "evidence_reviews": None, "cancelled": False,
            "latest_export": {"name": "PRIVATE_EXPORT.json", "path": "C:/PRIVATE_PATH", "created_at": TS}}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install_sha256 = fake_install(self.root)
        self.out = self.root / "runtime-data" / "agent-office"
        self.reader = ReleaseReader(self.root, clock=lambda: NOW + 10)

    def tearDown(self):
        self.temp.cleanup()

    def lines(self, events, tail=b""):
        self.out.mkdir(parents=True, exist_ok=True)
        raw = b"".join(json.dumps(e).encode() + b"\n" for e in events)
        (self.out / "events.jsonl").write_bytes(raw + tail)

    def db(self, data):
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "snapshot.json").write_text(json.dumps(data), encoding="utf-8")

    def live(self, events, db=None, written=TS):
        self.out.mkdir(parents=True, exist_ok=True)
        data = {"kind": "lgax-agent-office-live", "version": 1, "written_at": written, "events": events, "db": db}
        raw = "/* agent-office observe.py writes this file; do not edit. */\nwindow.LGAX_OFFICE_LIVE = " + json.dumps(data) + ";\n"
        (self.out / "live.js").write_text(raw, encoding="utf-8")


class ReaderTests(Fixture):
    def test_installed_empty_workspace_is_waiting_without_creating_files(self):
        result = self.reader.snapshot()
        self.assertEqual("waiting_for_session", result["source"]["observer_status"])
        self.assertEqual([], result["events"])
        self.assertIsNone(result["source"]["source_updated_at"])
        self.assertFalse(self.out.exists())

    def test_missing_install_is_not_fake_waiting_or_a_created_folder(self):
        with self.assertRaises(ReleaseReadError) as caught:
            ReleaseReader(self.root / "missing").snapshot()
        self.assertEqual("not_installed", caught.exception.code)
        self.assertFalse((self.root / "missing").exists())
        with self.assertRaises(ReleaseReadError) as caught:
            ReleaseReader.from_env({}).snapshot()
        self.assertEqual("not_configured", caught.exception.code)

    def test_changed_base_manifest_or_file_is_not_claimed_official_release(self):
        (self.root / "product-doctor.py").write_text("changed", encoding="utf-8")
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("release_mismatch", caught.exception.code)

    def test_json_live_is_data_only_and_duplicate_events_deduplicate(self):
        actual = event(detail={"command": "PRIVATE_COMMAND", "business_binding": BUSINESS})
        self.lines([actual])
        self.live([actual], product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual(1, len(result["events"]))
        self.assertEqual("observing", result["source"]["observer_status"])
        self.assertEqual("matched", result["db"]["binding_status"])
        self.assertEqual("prompt-b", result["events"][0]["prompt_id"])

    def test_javascript_after_or_before_json_is_rejected_never_executed(self):
        self.live([])
        path = self.out / "live.js"
        path.write_text(path.read_text() + "globalThis.evil = true;", encoding="utf-8")
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("schema_error", caught.exception.code)

    def test_malformed_complete_jsonl_is_error_but_partial_tail_is_ignored(self):
        self.lines([event()], b'{"id":"unfinished"')
        self.assertEqual(1, len(self.reader.snapshot()["events"]))
        self.lines([event()], b'{broken}\n')
        with self.assertRaises(ReleaseReadError):
            self.reader.snapshot()

    def test_raw_commands_questions_tokens_and_absolute_paths_are_removed(self):
        actual = event(detail={"business_binding": BUSINESS, "command": "PRIVATE_COMMAND", "stdout": "PRIVATE_OUTPUT", "token": "PRIVATE_TOKEN",
                               "reason": "Bearer PRIVATE_TOKEN", "host": "https://private.example/?key=PRIVATE_TOKEN", "area": "C:/PRIVATE_PATH",
                               "programs": ["python", "PRIVATE_PROGRAM"], "duration_ms": 12}, call="call-id")
        actual.update(prompt="PRIVATE_PROMPT", reasoning="PRIVATE_REASONING", output="PRIVATE_OUTPUT", path="C:/PRIVATE_PATH")
        self.lines([actual])
        self.db(product_snapshot())
        encoded = json.dumps(self.reader.snapshot())
        self.assertNotIn("PRIVATE_", encoded)
        self.assertNotIn("command", encoded)
        self.assertNotIn("C:/", encoded)
        self.assertIn("python", encoded)

    def test_other_native_session_does_not_join_global_latest_db(self):
        self.lines([event("old", session="old-native", detail={"business_binding": BUSINESS}),
                    event("new", session="new-native", ts="2026-10-16T04:00:01Z")])
        self.db(product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual("unmatched", result["db"]["binding_status"])
        self.assertIsNone(result["db"]["binding"])
        self.assertNotIn("results", result["db"])

    def test_new_request_b_is_not_replaced_by_late_a_end_or_cancel(self):
        events = [event("request-a", prompt="prompt-a", ts="2026-10-16T03:59:58Z"),
                  event("request-b", prompt="prompt-b", ts="2026-10-16T04:00:00Z"),
                  event("call-b", kind="tool", phase="start", call="call-b", ts="2026-10-16T04:00:01Z"),
                  event("late-a-end", kind="tool", phase="end", prompt="prompt-a", call="call-a", ts="2026-10-16T04:00:02Z", detail={"business_binding": BUSINESS}),
                  event("late-a-cancel", kind="turn_cancelled", prompt="prompt-a", ts="2026-10-16T04:00:03Z")]
        self.lines(events)
        self.db(product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual("observing", result["source"]["observer_status"])
        self.assertEqual("unmatched", result["db"]["binding_status"])
        events.append(event("end-b", kind="turn_end", ts="2026-10-16T04:00:04Z"))
        # A turn end closes the request, but an unmatched tool end must remain
        # unknown rather than pretending that an explicit call succeeded.
        events.append(event("call-b-end", kind="tool", phase="end", call="call-b", ts="2026-10-16T04:00:04.100000Z"))
        self.lines(events)
        self.assertEqual("recorded", self.reader.snapshot()["source"]["observer_status"])

    def test_timestamps_sort_by_instant_not_optional_fraction_string(self):
        self.lines([event("first", ts="2026-10-16T04:00:00Z"), event("second", ts="2026-10-16T04:00:00.100000Z")])
        result = self.reader.snapshot()
        self.assertEqual(["first", "second"], [e["id"] for e in result["events"]])
        self.assertTrue(result["source"]["source_updated_at"].endswith("00.100000Z"))

    def test_missing_new_prompt_is_not_a_wildcard_for_old_prompt(self):
        self.lines([event("request-a", prompt="prompt-a", ts="2026-10-16T03:59:59Z"),
                    event("request-b", prompt=None, ts=TS),
                    event("late-a", prompt="prompt-a", kind="turn_cancelled", ts="2026-10-16T04:00:01Z", detail={"business_binding": BUSINESS})])
        self.db(product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual("unmatched", result["db"]["binding_status"])
        self.assertEqual("observing", result["source"]["observer_status"])

    def test_event_window_without_request_anchor_does_not_guess_current_binding(self):
        self.lines([event("isolated-tool-end", kind="tool", phase="end", detail={"business_binding": BUSINESS})])
        self.db(product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual("unmatched", result["db"]["binding_status"])
        self.assertEqual("recorded", result["source"]["observer_status"])

    def test_more_recent_fractional_snapshot_wins(self):
        proof = event(detail={"business_binding": BUSINESS})
        live_db = product_snapshot()
        live_db["results"] = 1
        self.live([proof], live_db)
        separate = product_snapshot()
        separate.update(read_at="2026-10-16T04:00:00.100000Z", results=2)
        self.db(separate)
        self.assertEqual(2, self.reader.snapshot()["db"]["results"])

    def test_older_open_record_is_recorded_not_live_on_every_poll(self):
        self.lines([event()])
        first = self.reader.snapshot()
        later = ReleaseReader(self.root, clock=lambda: NOW + 130).snapshot()
        self.assertEqual("recorded", later["source"]["observer_status"])
        self.assertEqual(first["source"]["source_updated_at"], later["source"]["source_updated_at"])
        self.assertNotEqual(first["source"]["observed_at"], later["source"]["observed_at"])

    def test_files_bytes_and_runtime_listing_are_unchanged(self):
        self.lines([event()])
        paths = [p for p in self.root.rglob("*") if p.is_file()]
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in paths}
        self.reader.snapshot()
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_manifest_path_escape_is_rejected_without_reading_outside(self):
        manifest = {"format": "codex-product-install-v1", "skills": sorted(module.SKILLS), "files": [{"path": "../outside", "sha256": "0" * 64}]}
        raw = json.dumps(manifest).encode()
        (self.root / "product-install.json").write_bytes(raw)
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("unsafe_path", caught.exception.code)

    def test_runtime_symlink_is_rejected(self):
        self.out.mkdir(parents=True)
        outside = self.root / "outside.json"
        outside.write_text("PRIVATE_OUTSIDE", encoding="utf-8")
        try:
            (self.out / "snapshot.json").symlink_to(outside)
        except OSError:
            self.skipTest("이 Windows 계정은 symlink 생성을 허용하지 않습니다.")
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("unsafe_path", caught.exception.code)


class InstalledVersionTests(Fixture):
    def test_release_follows_the_installed_judge_setup_without_a_pin(self):
        result = self.reader.snapshot()
        self.assertIsNone(result["source"]["release"])  # a plain install does not name its release
        self.assertEqual(self.install_sha256, result["source"]["product_install_sha256"])
        mark = self.root / "runtime-data" / "judge-setup.json"
        mark.parent.mkdir(parents=True, exist_ok=True)
        for release, expected in (("product-v0.16.4", "product-v0.16.4"), ("product-v0.17.0", "product-v0.17.0"), ("latest; rm", None)):
            mark.write_text(json.dumps({"release": release, "engine": "codex"}), encoding="utf-8")
            self.assertEqual(expected, self.reader.snapshot()["source"]["release"])

    def test_portable_install_names_its_engine_and_reinstalled_observer_files_are_allowed(self):
        observer = self.root / "web" / "prototypes" / "agent-office" / "observe.py"
        observer.parent.mkdir(parents=True)
        observer.write_text("# installed observer", encoding="utf-8")
        doctor = self.root / "product-doctor.py"
        files = [{"path": p.relative_to(self.root).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in (doctor, observer)]
        record = {"format": "portable-product-install-v1", "engine": "claude", "skills": sorted(module.SKILLS), "files": files}
        (self.root / "product-install.json").write_text(json.dumps(record), encoding="utf-8")
        observer.write_text("# refreshed by office.py install", encoding="utf-8")
        claude = {**event(), "src": "claude", "hook": "UserPromptSubmit"}
        self.lines([claude])
        result = self.reader.snapshot()
        self.assertEqual("claude", result["source"]["engine"])
        self.assertEqual(1, len(result["events"]))
        doctor.write_text("changed product file", encoding="utf-8")
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("release_mismatch", caught.exception.code)
        record["format"] = "unknown-install"
        (self.root / "product-install.json").write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(ReleaseReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("release_mismatch", caught.exception.code)

    def test_a_delivered_role_result_continues_the_same_request(self):
        ask = event("ask", prompt="prompt-a")
        delegate = event("delegate", kind="delegate", prompt="prompt-a", detail={"launched_agent_id": "current-child"})
        handback = event("handback", kind="handback_delivered", prompt="prompt-b", detail={"from_agent_id": "current-child"})
        bound = event("save", kind="shell", prompt="prompt-b", detail={"business_binding": BUSINESS})
        self.lines([ask, delegate, handback, bound])
        self.db(product_snapshot())
        result = self.reader.snapshot()
        self.assertEqual("matched", result["db"]["binding_status"])
        self.assertEqual("observing", result["source"]["observer_status"])
        self.assertEqual(("native-session", {"prompt-a", "prompt-b"}),
                         module.selected_native(result["events"])[:2])
        other = event("other", prompt="prompt-c", ts="2026-10-16T04:00:01Z")
        self.lines([ask, delegate, handback, bound, {**other, "kind": "request"}])
        self.assertEqual("unmatched", self.reader.snapshot()["db"]["binding_status"])

    def test_late_old_child_and_unverified_notification_cannot_bind_new_request(self):
        for continuation, detail in [("handback_delivered", {"from_agent_id": "child-a"}), ("notification", {})]:
            with self.subTest(continuation=continuation):
                self.lines([
                    event("request-a", prompt="a"),
                    event("delegate-a", kind="delegate", prompt="a", detail={"launched_agent_id": "child-a"}),
                    event("request-b", prompt="b", ts="2026-10-16T04:00:01Z"),
                    event("late-a", kind=continuation, prompt="late-a", ts="2026-10-16T04:00:02Z", detail=detail),
                    event("save-a", kind="shell", prompt="late-a", ts="2026-10-16T04:00:03Z", detail={"business_binding": BUSINESS}),
                ])
                self.db(product_snapshot())
                snapshot = self.reader.snapshot()
                self.assertEqual(("native-session", {"b"}), module.selected_native(snapshot["events"])[:2])
                self.assertEqual("unmatched", snapshot["db"]["binding_status"])
                self.assertNotIn("candidates", snapshot["db"])

    def test_null_prompt_is_not_proof_of_old_subagent_parentage(self):
        child = {**event("late-child", kind="subagent", phase="start", prompt=None, ts="2026-10-16T04:00:03Z"),
                 "agent_id": "child-a", "actor": "product_evidence_reviewer", "node": "product_evidence_reviewer"}
        self.lines([event("request-a", prompt="a"),
                    event("delegate-a", kind="delegate", prompt="a", detail={"launched_agent_id": "child-a"}),
                    event("request-b", prompt=None, ts="2026-10-16T04:00:01Z"), child,
                    event("late-a", kind="handback_delivered", prompt="late-a", ts="2026-10-16T04:00:04Z", detail={"from_agent_id": "child-a"}),
                    event("save-a", kind="shell", prompt="late-a", ts="2026-10-16T04:00:05Z", detail={"business_binding": BUSINESS})])
        self.db(product_snapshot())
        snapshot = self.reader.snapshot()
        self.assertEqual(("native-session", {None}), module.selected_native(snapshot["events"])[:2])
        self.assertEqual("unmatched", snapshot["db"]["binding_status"])
        self.assertNotIn("candidates", snapshot["db"])


class HTTPTests(Fixture):
    def setUp(self):
        super().setUp()
        self.dist = self.root / "ui-dist"
        (self.dist / "assets").mkdir(parents=True)
        self.index = self.dist / "index.html"
        self.index.write_text('<html><head><title>Factory</title></head><body><div id="root"></div><script type="module" src="/assets/ui.js"></script></body></html>', encoding="utf-8")
        (self.dist / "assets" / "ui.js").write_text("/* synthetic UI asset */", encoding="utf-8")
        self.server = ReleaseHTTPServer(("127.0.0.1", 0), self.reader, TOKEN, ("https://approved.example",), self.dist)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(self, path, *, origin=None, token=None, method="GET", headers=None):
        combined = {}
        if origin is not None:
            combined["Origin"] = origin
        if token is not None:
            combined["Authorization"] = "Bearer " + token
        combined.update(headers or {})
        req = urllib.request.Request(self.base + path, headers=combined, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read(), response.headers

    def test_api_auth_and_origin_still_apply(self):
        self.assertEqual(401, self.request("/api/harness/snapshot")[0])
        status, body, headers = self.request("/api/harness/snapshot", token=TOKEN, origin="https://approved.example")
        self.assertEqual(200, status)
        self.assertEqual("waiting_for_session", json.loads(body)["source"]["observer_status"])
        self.assertEqual("https://approved.example", headers["Access-Control-Allow-Origin"])
        self.assertEqual(403, self.request("/api/harness/snapshot", token=TOKEN, origin="https://other.example")[0])

    def test_local_index_bootstrap_is_only_in_memory_and_no_cors(self):
        before = self.index.read_bytes()
        status, body, headers = self.request("/")
        self.assertEqual(200, status)
        bootstrap = json.loads(re.search(rb'id="ax-release-bootstrap">(.*?)</script>', body).group(1))
        self.assertEqual(TOKEN, bootstrap["token"])
        self.assertEqual(self.base, bootstrap["url"])
        self.assertEqual("lgax_local_release_connection", bootstrap["kind"])
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual("same-origin", headers["Cross-Origin-Resource-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(before, self.index.read_bytes())
        for path in self.root.rglob("*"):
            if path.is_file():
                self.assertNotIn(TOKEN.encode(), path.read_bytes())

    def test_localhost_bootstrap_matches_validated_host_and_csp_self(self):
        host = f"localhost:{self.server.server_port}"
        status, body, _ = self.request("/", headers={"Host": host})
        self.assertEqual(200, status)
        bootstrap = json.loads(re.search(rb'id="ax-release-bootstrap">(.*?)</script>', body).group(1))
        self.assertEqual("http://" + host, bootstrap["url"])

    def test_cross_origin_index_or_script_cannot_obtain_bootstrap(self):
        for path in ("/", "/assets/ui.js"):
            status, body, headers = self.request(path, origin="https://approved.example")
            self.assertEqual(403, status)
            self.assertNotIn(TOKEN.encode(), body)
            self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual(403, self.request("/", headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "script"})[0])

    def test_dns_rebinding_host_is_rejected_for_index_and_api(self):
        for path in ("/", "/api/harness/snapshot"):
            status, body, _ = self.request(path, token=TOKEN, headers={"Host": "attacker.example"})
            self.assertEqual(403, status)
            self.assertNotIn(TOKEN.encode(), body)

    def test_static_traversal_unlisted_path_and_symlink_are_rejected(self):
        for path in ("/%2e%2e/product-install.json", "/assets/%2e%2e/index.html", "/product-install.json"):
            self.assertIn(self.request(path)[0], (400, 404))
        outside = self.root / "private.txt"
        outside.write_text("PRIVATE_CONTENT", encoding="utf-8")
        try:
            (self.dist / "assets" / "escape.txt").symlink_to(outside)
        except OSError:
            return  # The mandatory encoded traversal checks above still ran.
        self.assertEqual(400, self.request("/assets/escape.txt")[0])

    def test_static_asset_get_works_and_post_is_read_only(self):
        status, body, headers = self.request("/assets/ui.js")
        self.assertEqual(200, status)
        self.assertIn(b"synthetic UI", body)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual(405, self.request("/api/harness/snapshot", token=TOKEN, method="POST")[0])

    def test_only_known_index_view_query_is_allowed(self):
        self.assertEqual(200, self.request("/?view=harness")[0])
        self.assertEqual(200, self.request("/?view=team")[0])
        self.assertEqual(400, self.request("/?view=unknown")[0])
        self.assertEqual(400, self.request("/?view=harness&path=private")[0])
        self.assertEqual(400, self.request("/api/harness/snapshot?view=harness", token=TOKEN)[0])

    def test_bootstrap_json_cannot_close_script_tag(self):
        prior = self.server._token
        self.server._token = "x" * 32 + "</script><img/onerror=alert(1)>"
        try:
            status, body, _ = self.request("/")
            self.assertEqual(200, status)
            self.assertNotIn(b"<img/onerror", body)
            bootstrap = json.loads(re.search(rb'id="ax-release-bootstrap">(.*?)</script>', body).group(1))
            self.assertEqual(self.server._token, bootstrap["token"])
        finally:
            self.server._token = prior


if __name__ == "__main__":
    unittest.main()
