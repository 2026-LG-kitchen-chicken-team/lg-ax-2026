"""Synthetic SQLite/HTTP tests only; never connects to an actual team service."""
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from backend.harness_reader import ACCOUNTS, HarnessReadError, HarnessReader
from backend.harness_server import HarnessHTTPServer

NOW = 1_800_000_000.0
TOKEN = "test-only-token-01234567890123456789012345"


def initialize(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
        CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE members(account TEXT PRIMARY KEY,enabled INTEGER NOT NULL);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,packet TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,attempt INTEGER NOT NULL,lease_expires REAL,run_deadline REAL,result TEXT,stop_reason TEXT,lease_hash TEXT);
        CREATE TABLE worker_presence(account TEXT PRIMARY KEY,received_at REAL NOT NULL,reported_at REAL NOT NULL,metadata TEXT NOT NULL);
        CREATE TABLE events(id INTEGER PRIMARY KEY,at REAL NOT NULL,actor TEXT NOT NULL,event TEXT NOT NULL,details TEXT NOT NULL);
        CREATE TABLE identities(account TEXT,token_digest TEXT);
        """)
        tasks = {"P2-CORE-001": {"owner": "unknownamed", "status": "doing", "title": "상품기획 근거 연결 개발"},
                 "P2-WEB-001": {"owner": "choigilung", "status": "pm_review_requested", "title": "웹 작업실 검수"}}
        db.execute("INSERT INTO settings VALUES('mode','on')")
        db.execute("INSERT INTO settings VALUES('formal_snapshot',?)", (json.dumps({"approved_commit": "a" * 40, "tasks": tasks, "approval_reference": "PRIVATE_APPROVAL"}),))
        db.executemany("INSERT INTO members VALUES(?,1)", [(a,) for a in ACCOUNTS])
        packet = {"job_id": "job-live", "task_id": "P2-CORE-001", "owner": "unknownamed", "kind": "implementation",
                  "title": "PACKET_TITLE_MUST_NOT_RETURN", "prompt": "PROMPT_SECRET", "allowed_paths": ["C:/PRIVATE_PATH"],
                  "lease_token": "PRIVATE_LEASE", "validation_commands": [["python", "PRIVATE_COMMAND"]]}
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", ("job-live", json.dumps(packet), "running", NOW - 60, 1,
                   NOW + 60, NOW + 600, json.dumps({"summary": "PRIVATE_RESULT"}), "PRIVATE_REASON", "PRIVATE_HASH"))
        metadata = {"source": "fixed_worker", "engine": "codex", "phase": "model", "job_id": "job-live", "instance_id": "PRIVATE_INSTANCE", "runtime_sha256": "PRIVATE_RUNTIME", "lease_token": "PRIVATE_LEASE"}
        db.execute("INSERT INTO worker_presence VALUES(?,?,?,?)", ("unknownamed", NOW - 10, NOW - 11, json.dumps(metadata)))
        db.execute("INSERT INTO events VALUES(1,?,?,?,?)", (NOW - 2, "unknownamed", "claimed", json.dumps({"job_id": "job-live", "prompt": "PRIVATE_EVENT", "reason": "PRIVATE_REASON"})))
        db.execute("INSERT INTO identities VALUES('unknownamed','PRIVATE_IDENTITY_TOKEN')")
        db.commit()


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        initialize(self.path)
        self.reader = HarnessReader(self.path, clock=lambda: NOW)

    def tearDown(self):
        self.temp.cleanup()

    def sql(self, query, params=()):
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(query, params).fetchall()
            db.commit()
            return rows

    def test_recent_matching_lease_is_supporting_evidence_not_skill(self):
        result = self.reader.snapshot()
        job = result["jobs"][0]
        self.assertEqual("live", job["lease_state"])
        self.assertTrue(job["is_running_confirmed"])
        self.assertEqual("recent_worker_and_live_lease", job["activity_evidence"])
        self.assertEqual(("overview", None), (job["view"], job["stage"]))
        self.assertEqual("상품기획 근거 연결 개발", job["title"])

    def test_db_bytes_and_rows_do_not_change_including_expired_jobs(self):
        self.sql("UPDATE jobs SET lease_expires=?", (NOW - 1,))
        before_bytes = hashlib.sha256(self.path.read_bytes()).hexdigest()
        before_rows = {t: self.sql("SELECT * FROM " + t) for t in ("settings", "members", "jobs", "worker_presence", "events", "identities")}
        first = self.reader.snapshot()
        self.reader.snapshot()
        after_rows = {t: self.sql("SELECT * FROM " + t) for t in before_rows}
        self.assertEqual(before_rows, after_rows)
        self.assertEqual(before_bytes, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual("running", first["jobs"][0]["status"])
        self.assertEqual("expired", first["jobs"][0]["lease_state"])
        self.assertFalse(first["jobs"][0]["is_running_confirmed"])

    def test_live_wal_commits_are_visible_without_mutation(self):
        with closing(sqlite3.connect(self.path)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("UPDATE jobs SET status='review_requested'")
            writer.commit()
            wal = Path(str(self.path) + "-wal")
            before = (self.path.read_bytes(), wal.read_bytes())
            self.assertEqual("review_requested", self.reader.snapshot()["jobs"][0]["status"])
            self.assertEqual(before, (self.path.read_bytes(), wal.read_bytes()))

    def test_source_updated_at_is_not_poll_time(self):
        first = self.reader.snapshot()
        second = HarnessReader(self.path, clock=lambda: NOW + 20).snapshot()
        self.assertNotEqual(first["source"]["observed_at"], second["source"]["observed_at"])
        self.assertEqual(first["source"]["source_updated_at"], second["source"]["source_updated_at"])

    def test_stale_heartbeat_does_not_confirm_running(self):
        self.sql("UPDATE worker_presence SET received_at=?,reported_at=?", (NOW - 180, NOW - 180))
        result = self.reader.snapshot()
        self.assertFalse(result["jobs"][0]["is_running_confirmed"])
        self.assertEqual("stale", next(w for w in result["workers"] if w["owner"] == "unknownamed")["presence"])

    def test_wrong_worker_job_is_not_reused_as_execution_evidence(self):
        metadata = {"source": "fixed_worker", "engine": "codex", "phase": "model", "job_id": "outside-scope"}
        self.sql("UPDATE worker_presence SET metadata=?", (json.dumps(metadata),))
        result = self.reader.snapshot()
        self.assertFalse(result["jobs"][0]["is_running_confirmed"])
        self.assertNotIn("outside-scope", json.dumps(result))

    def test_off_mode_and_disabled_member_do_not_confirm_running(self):
        self.sql("UPDATE settings SET value='off' WHERE key='mode'")
        self.assertFalse(self.reader.snapshot()["jobs"][0]["is_running_confirmed"])
        self.sql("UPDATE settings SET value='on' WHERE key='mode'")
        self.sql("UPDATE members SET enabled=0 WHERE account='unknownamed'")
        self.assertFalse(self.reader.snapshot()["jobs"][0]["is_running_confirmed"])

    def test_future_dates_without_lease_fence_do_not_confirm_running(self):
        self.sql("UPDATE jobs SET lease_hash=NULL")
        result = self.reader.snapshot()
        self.assertEqual("unknown", result["jobs"][0]["lease_state"])
        self.assertFalse(result["jobs"][0]["is_running_confirmed"])

    def test_scope_filter_excludes_nonformal_jobs_and_other_members(self):
        packet = {"job_id": "other", "task_id": "OTHER-PROJECT", "owner": "unknownamed", "kind": "implementation", "title": "PRIVATE_OTHER"}
        self.sql("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", ("other", json.dumps(packet), "running", NOW, 1, NOW + 60, NOW + 60, None, None, None))
        result = self.reader.snapshot()
        self.assertEqual(["job-live"], [j["id"] for j in result["jobs"]])
        limited = HarnessReader(self.path, members=("choigilung",), clock=lambda: NOW).snapshot()
        self.assertFalse(limited["jobs"])
        self.assertEqual(["choigilung"], [m["id"] for m in limited["members"]])
        self.assertNotIn("unknownamed", json.dumps(limited))

    def test_no_raw_sensitive_fields_or_packet_title(self):
        encoded = json.dumps(self.reader.snapshot(), ensure_ascii=False)
        for marker in ("PRIVATE_", "PROMPT_SECRET", "PACKET_TITLE_MUST_NOT_RETURN", "allowed_paths", "validation_commands", "lease_token", "runtime_sha256", "approval_reference", "result", "stop_reason", "token_digest"):
            self.assertNotIn(marker, encoded)

    def test_suspicious_formal_title_is_withheld(self):
        formal = json.loads(self.sql("SELECT value FROM settings WHERE key='formal_snapshot'")[0][0])
        formal["tasks"]["P2-CORE-001"]["title"] = "C:/private/token.txt sk-SECRET"
        self.sql("UPDATE settings SET value=? WHERE key='formal_snapshot'", (json.dumps(formal),))
        result = self.reader.snapshot()
        self.assertEqual("작업 이름 비공개", result["jobs"][0]["title"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_schema_error_is_fixed_and_has_no_path(self):
        self.sql("DROP TABLE worker_presence")
        with self.assertRaises(HarnessReadError) as caught:
            self.reader.snapshot()
        self.assertEqual("schema_error", caught.exception.code)
        self.assertNotIn(str(self.path), str(caught.exception))

    def test_missing_config_does_not_search_or_create_db(self):
        with self.assertRaises(HarnessReadError) as caught:
            HarnessReader.from_env({}).snapshot()
        self.assertEqual("not_configured", caught.exception.code)
        missing = Path(self.temp.name) / "never-create.sqlite3"
        with self.assertRaises(HarnessReadError):
            HarnessReader(missing).snapshot()
        self.assertFalse(missing.exists())

    def test_empty_visible_ledger_has_null_source_update(self):
        self.sql("DELETE FROM jobs")
        self.sql("DELETE FROM worker_presence")
        self.sql("DELETE FROM events")
        self.assertIsNone(self.reader.snapshot()["source"]["source_updated_at"])

    def test_rejects_profile_or_member_scope_expansion(self):
        with self.assertRaises(HarnessReadError):
            HarnessReader(self.path, profile="any-repo")
        with self.assertRaises(HarnessReadError):
            HarnessReader(self.path, members=("stranger",))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "synthetic.sqlite3"
        initialize(cls.path)
        cls.server = HarnessHTTPServer(("127.0.0.1", 0), HarnessReader(cls.path, clock=lambda: NOW), TOKEN, ("https://approved.example",))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def request(self, path="/api/harness/snapshot", *, token=TOKEN, origin="http://localhost:5173", method="GET", headers=None):
        combined = {}
        if token is not None:
            combined["Authorization"] = "Bearer " + token
        if origin is not None:
            combined["Origin"] = origin
        combined.update(headers or {})
        req = urllib.request.Request(self.base + path, headers=combined, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            return response.status, json.loads(body) if body else None, response.headers

    def test_authenticated_get_returns_projection(self):
        status, result, headers = self.request()
        self.assertEqual(200, status)
        self.assertEqual("team_controller_sqlite_readonly", result["source"]["kind"])
        self.assertEqual("no-store", headers["Cache-Control"])

    def test_native_without_origin_still_requires_token(self):
        self.assertEqual(401, self.request(token=None, origin=None)[0])
        self.assertEqual(200, self.request(origin=None)[0])
        self.assertEqual(401, self.request(token="wrong-token")[0])

    def test_unlisted_origin_rejected_even_with_token(self):
        status, _, headers = self.request(origin="https://unlisted.example")
        self.assertEqual(403, status)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual(200, self.request(origin="https://approved.example")[0])

    def test_post_and_other_mutations_are_405(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(405, self.request(method=method)[0])

    def test_options_allows_only_get_and_authorization(self):
        status, _, headers = self.request(method="OPTIONS", token=None, headers={"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
        self.assertEqual(204, status)
        self.assertEqual("GET, OPTIONS", headers["Access-Control-Allow-Methods"])
        self.assertEqual(405, self.request(method="OPTIONS", headers={"Access-Control-Request-Method": "POST"})[0])

    def test_http_cannot_supply_database_or_member_parameters(self):
        self.assertEqual(400, self.request("/api/harness/snapshot?path=C:/private/db&member=any")[0])
        self.assertEqual(404, self.request("/v1/mode")[0])

    def test_health_has_only_minimum_service_status(self):
        status, result, _ = self.request("/health", token=None)
        self.assertEqual(200, status)
        self.assertEqual({"service", "ok"}, set(result))

    def test_server_refuses_nonloopback_bind_and_missing_view_token(self):
        with self.assertRaises(ValueError):
            HarnessHTTPServer(("0.0.0.0", 0), None, TOKEN)
        with self.assertRaises(ValueError):
            HarnessHTTPServer(("127.0.0.1", 0), None, "")


if __name__ == "__main__":
    unittest.main()
