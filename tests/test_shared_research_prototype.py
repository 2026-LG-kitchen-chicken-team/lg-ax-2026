"""Shared transport boundaries only: no reviews, model generation, or live servers."""

import asyncio
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import httpx
from lgax_core.errors import DomainError
from lgax_core.model_client import ModelConfig
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shared_research_prototype_under_test", ROOT / "scripts/serve_shared_research_prototype.py"
)
assert SPEC is not None and SPEC.loader is not None
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)

ORIGIN = "https://prototype.example.test"
SIGNING_KEY = b"transport-test-key-never-used-for-serving-0001"
SESSION_A = "a" * 32
SESSION_B = "b" * 32


class SessionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = SHARED.SessionRegistry(SIGNING_KEY)

    def test_signed_sessions_have_distinct_editor_principals(self):
        token_a = self.registry.token(SESSION_A)
        token_b = self.registry.token(SESSION_B)
        principal_a = self.registry.authenticate("Bearer " + token_a)
        principal_b = self.registry.authenticate("Bearer " + token_b)
        self.assertNotEqual(token_a, token_b)
        self.assertNotEqual(principal_a.id, principal_b.id)
        self.assertEqual(principal_a.id, "shared-prototype." + SESSION_A)
        self.assertEqual(principal_b.id, "shared-prototype." + SESSION_B)
        self.assertEqual((principal_a.role, principal_b.role), ("editor", "editor"))

    def test_forged_malformed_and_non_ascii_signatures_are_unauthorized(self):
        token = self.registry.token(SESSION_A)
        signature = token.split(".")[2]
        changed_signature = ("0" if signature[0] != "0" else "1") + signature[1:]
        invalid = [
            None, "", token, "Bearer " + SESSION_A,
            "Bearer v0." + SESSION_A + "." + signature,
            "Bearer v1." + SESSION_B + "." + signature,
            "Bearer v1." + SESSION_A + "." + changed_signature,
            "Bearer v1." + SESSION_A + "." + "é" * 64,
            "Bearer v1." + SESSION_A + "." + signature.upper(),
            "Bearer " + token + ".extra",
        ]
        for authorization in invalid:
            with self.subTest(authorization=authorization), self.assertRaises(DomainError) as caught:
                self.registry.authenticate(authorization)
            self.assertEqual(caught.exception.code, "UNAUTHORIZED")
        with self.assertRaises(ValueError):
            SHARED.SessionRegistry(b"short")


class RecordingBackend:
    """Metadata-only mock; it never creates a PlanningBrief or customer material."""

    def __init__(self, registry):
        self.registry = registry
        self.calls = []
        self.model_calls = 0
        self.hold_next_model = False
        self.hold_all_models = False
        self.active_models = 0
        self.peak_active_models = 0
        self.model_started = asyncio.Event()
        self.model_release = asyncio.Event()

    async def __call__(self, scope, receive, send):
        headers = Headers(scope=scope)
        try:
            principal = self.registry.authenticate(headers.get("authorization"))
        except DomainError:
            return await JSONResponse(
                {"error": {"code": "UNAUTHORIZED"}}, status_code=401
            )(scope, receive, send)
        body = await Request(scope, receive).body()
        self.calls.append({
            "path": scope["path"], "query_string": scope["query_string"],
            "headers": dict(headers), "body": body, "principal_id": principal.id,
        })
        if scope["method"] == "POST" and scope["path"] == "/api/research/planning-runs":
            self.model_calls += 1
            self.active_models += 1
            self.peak_active_models = max(self.peak_active_models, self.active_models)
            try:
                if self.hold_next_model or self.hold_all_models:
                    self.hold_next_model = False
                    self.model_started.set()
                    await self.model_release.wait()
            finally:
                self.active_models -= 1
        return await JSONResponse({
            "mock_transport_only": True, "principal_id": principal.id,
            "path": scope["path"], "received_bytes": len(body),
        })(scope, receive, send)


class SharedGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.static = Path(self.temp.name) / "static"
        self.static.mkdir()
        (self.static / "index.html").write_text(
            "<!doctype html><title>Transport test only</title><h1>Static boundary</h1>",
            encoding="utf-8",
        )
        self.registry = SHARED.SessionRegistry(SIGNING_KEY)
        self.backend = RecordingBackend(self.registry)
        self.app = SHARED.SharedGateway(
            self.backend, self.registry, self.static, ORIGIN, "test-release",
            queue_path=Path(self.temp.name) / "queue.sqlite3",
        )
        await self.app.queue.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN
        )
        self.token = self.registry.token(SESSION_A)

    async def asyncTearDown(self):
        self.backend.model_release.set()
        await self.app.queue.close()
        await self.client.aclose()

    def headers(self, *, post=False):
        result = {"Authorization": "Bearer " + self.token}
        if post:
            result["Origin"] = ORIGIN
        return result

    async def test_signed_cookie_is_stable_and_other_browser_is_a_distinct_principal(self):
        first = await self.client.get("/api/prototype/session")
        self.assertEqual(first.status_code, 200)
        token_a = first.json()["token"]
        principal_a = self.registry.authenticate("Bearer " + token_a)
        self.assertTrue(first.json()["shared_prototype"])
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(first.headers["referrer-policy"], "no-referrer")
        cookie = first.headers["set-cookie"].lower()
        for attribute in ("httponly", "secure", "samesite=strict"):
            self.assertIn(attribute, cookie)
        repeated = await self.client.get("/api/prototype/session")
        self.assertEqual(repeated.json()["token"], token_a)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN
        ) as other:
            second = await other.get("/api/prototype/session")
            token_b = second.json()["token"]
            principal_b = self.registry.authenticate("Bearer " + token_b)
            self.assertNotEqual(principal_a.id, principal_b.id)
            own_a = await self.client.get(
                "/api/research/bundles", headers={"Authorization": "Bearer " + token_a}
            )
            own_b = await other.get(
                "/api/research/bundles", headers={"Authorization": "Bearer " + token_b}
            )
        self.assertEqual(own_a.json()["principal_id"], principal_a.id)
        self.assertEqual(own_b.json()["principal_id"], principal_b.id)
        self.assertNotEqual(own_a.json()["principal_id"], own_b.json()["principal_id"])
        # A bootstrap cookie alone does not replace the API's explicit Bearer credential.
        unauthenticated = await self.client.get("/api/research/bundles")
        self.assertEqual(unauthenticated.status_code, 401)

    async def test_unsigned_victim_session_cookie_cannot_bootstrap_victim_identity(self):
        response = await self.client.get(
            "/api/prototype/session", headers={"Cookie": SHARED.COOKIE + "=" + SESSION_B}
        )
        self.assertEqual(response.status_code, 200)
        issued = response.json()["token"]
        principal = self.registry.authenticate("Bearer " + issued)
        self.assertNotEqual(issued, self.registry.token(SESSION_B))
        self.assertNotEqual(principal.id, "shared-prototype." + SESSION_B)
        self.assertEqual(self.client.cookies.get(SHARED.COOKIE), issued)
        self.assertNotIn(SIGNING_KEY.decode(), response.text)
        self.assertEqual(self.backend.calls, [])

    async def test_exact_host_origin_and_post_origin_are_enforced_before_backend(self):
        invalid_headers = [
            {"Host": "prototype.example.test.evil.test"},
            {"Host": "prototype.example.test:443"},
            {"Origin": ORIGIN + ".evil.test"},
            {"Origin": "http://prototype.example.test"},
            {"Origin": ORIGIN + "/"},
        ]
        for extras in invalid_headers:
            with self.subTest(extras=extras):
                denied = await self.client.get(
                    "/api/research/bundles", headers={**self.headers(), **extras}
                )
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(denied.json()["error"]["code"], "FORBIDDEN")
        missing_origin = await self.client.post(
            "/api/research/planning-runs", headers=self.headers(), json={}
        )
        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(self.backend.calls, [])
        accepted = await self.client.post(
            "/api/research/guides", headers=self.headers(post=True), json={}
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(len(self.backend.calls), 1)

    async def test_unshared_workspace_docs_and_ollama_paths_never_reach_backend(self):
        blocked = (
            "/api/workspace/projects", "/docs", "/docs/oauth2-redirect", "/openapi.json",
            "/redoc", "/api/generate", "/api/chat", "/ollama", "/ollama/api/generate",
        )
        for path in blocked:
            with self.subTest(path=path):
                response = await self.client.get(path, headers=self.headers())
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.backend.calls, [])
        static = await self.client.get("/")
        self.assertEqual(static.status_code, 200)
        self.assertIn("Static boundary", static.text)
        health = await self.client.get("/health")
        self.assertEqual(health.json(), {
            "status": "ok", "prototype": True, "release": "test-release",
            "scheduled_shutdown": False, "serving_parallelism": 4,
        })

    async def test_research_get_normalizes_loopback_headers_and_preserves_auth_and_query(self):
        response = await self.client.get("/api/research/bundles?limit=2", headers={
            **self.headers(), "Origin": ORIGIN, "X-LGAX-Client": "web",
            "X-Forwarded-Host": "untrusted.example", "X-Forwarded-Proto": "http",
        })
        self.assertEqual(response.status_code, 200)
        received = self.backend.calls[-1]
        self.assertEqual(received["headers"]["host"], "127.0.0.1")
        self.assertEqual(received["headers"]["origin"], "http://127.0.0.1:5175")
        self.assertEqual(received["headers"]["authorization"], "Bearer " + self.token)
        self.assertEqual(received["headers"]["x-lgax-client"], "web")
        self.assertNotIn("x-forwarded-host", received["headers"])
        self.assertNotIn("x-forwarded-proto", received["headers"])
        self.assertEqual(received["query_string"], b"limit=2")
        no_auth = await self.client.get("/api/research/bundles")
        self.assertEqual(no_auth.status_code, 401)

    async def test_non_ascii_forged_signature_returns_401_instead_of_500(self):
        malformed = ("Bearer v1." + SESSION_A + "." + "é" * 64).encode("utf-8")
        response = await self.client.get(
            "/api/research/bundles", headers=[(b"authorization", malformed)]
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")
        self.assertEqual(self.backend.calls, [])

    async def test_four_planning_posts_run_together_and_fifth_waits_while_reads_are_available(self):
        self.backend.hold_all_models = True
        sessions = [SESSION_A, SESSION_B, "c" * 32, "d" * 32, "e" * 32]
        jobs = []
        try:
            for session in sessions:
                response = await self.client.post("/api/research/planning-runs", headers={
                    "Authorization": "Bearer " + self.registry.token(session), "Origin": ORIGIN,
                }, json={})
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.json()["poll_after_ms"], 1000)
                jobs.append(response.json()["job_id"])

            async def four_started():
                while self.backend.model_calls < 4:
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(four_started(), timeout=3)
            self.assertEqual((self.backend.active_models, self.backend.peak_active_models), (4, 4))
            for index, session in enumerate(sessions):
                state = await self.client.get("/api/prototype/jobs/" + jobs[index], headers={
                    "Authorization": "Bearer " + self.registry.token(session),
                })
                self.assertEqual(state.json()["status"], "running" if index < 4 else "queued")
                self.assertEqual(state.json()["queue_position"], 0 if index < 4 else 1)
            duplicate = await self.client.post(
                "/api/research/planning-runs", headers=self.headers(post=True), json={}
            )
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(duplicate.json()["error"]["code"], "JOB_ALREADY_ACTIVE")
            self.assertEqual(self.backend.model_calls, 4)
            read = await asyncio.wait_for(self.client.get(
                "/api/research/bundles", headers=self.headers()
            ), timeout=3)
            guide = await asyncio.wait_for(self.client.post(
                "/api/research/guides", headers=self.headers(post=True), json={}
            ), timeout=3)
            self.assertEqual((read.status_code, guide.status_code), (200, 200))
        finally:
            self.backend.model_release.set()

        async def finished():
            snapshots = [self.app.queue.get(job_id, "shared-prototype." + session)
                         for job_id, session in zip(jobs, sessions, strict=True)]
            while any(snapshot["status"] in {"running", "queued"} for snapshot in snapshots):
                await asyncio.sleep(0.01)
                snapshots = [self.app.queue.get(job_id, "shared-prototype." + session)
                             for job_id, session in zip(jobs, sessions, strict=True)]
            return snapshots

        completed = await asyncio.wait_for(finished(), timeout=3)
        self.assertEqual(self.backend.model_calls, 5)
        self.assertEqual(self.backend.peak_active_models, 4)
        for snapshot, session in zip(completed, sessions, strict=True):
            self.assertEqual(snapshot["status"], "completed")
            self.assertIsNone(snapshot["queue_position"])
            self.assertEqual(snapshot["result"], {
                "mock_transport_only": True, "principal_id": "shared-prototype." + session,
                "path": "/api/research/planning-runs", "received_bytes": 2,
            })
        later = await self.client.post(
            "/api/research/planning-runs", headers=self.headers(post=True), json={}
        )
        self.assertEqual(later.status_code, 202)

    async def test_chunked_and_false_content_length_cannot_bypass_actual_body_limit(self):
        async def oversized_chunks():
            yield b"x" * 32768
            yield b"y" * 32768
            yield b"z"

        chunked = await self.client.post(
            "/api/research/planning-runs", headers=self.headers(post=True),
            content=oversized_chunks(),
        )
        self.assertEqual(chunked.status_code, 413)
        self.assertEqual(chunked.json()["error"]["code"], "INVALID_ARGUMENT")
        falsely_short = await self.client.post(
            "/api/research/planning-runs", headers={**self.headers(post=True), "Content-Length": "1"},
            content=b"x" * 65537,
        )
        self.assertEqual(falsely_short.status_code, 413)
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.backend.model_calls, 0)
        self.assertEqual(self.backend.active_models, 0)

    async def test_current_job_lookup_recovers_lost_acceptance_and_exposes_only_own_latest(self):
        missing = await self.client.get('/api/prototype/jobs/current', headers=self.headers())
        self.assertEqual(missing.status_code, 404)
        self.backend.hold_next_model = True
        accepted = await self.client.post('/api/research/planning-runs',
                                          headers=self.headers(post=True), json={})
        self.assertEqual(accepted.status_code, 202)
        await asyncio.wait_for(self.backend.model_started.wait(), timeout=3)
        other_headers = {'Authorization': 'Bearer ' + self.registry.token(SESSION_B)}
        other = await self.client.post('/api/research/planning-runs',
                                       headers={**other_headers, 'Origin': ORIGIN}, json={})
        self.assertEqual(other.status_code, 202)
        recovered = await self.client.get('/api/prototype/jobs/current', headers=self.headers())
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual((recovered.json()['job_id'], recovered.json()['status']),
                         (accepted.json()['job_id'], 'running'))
        self.assertEqual(recovered.headers['cache-control'], 'no-store')
        other_current = await self.client.get('/api/prototype/jobs/current', headers=other_headers)
        self.assertEqual(other_current.json()['job_id'], other.json()['job_id'])
        self.assertNotEqual(other_current.json()['job_id'], recovered.json()['job_id'])
        empty_owner = await self.client.get('/api/prototype/jobs/current', headers={
            'Authorization': 'Bearer ' + self.registry.token('c' * 32),
        })
        self.assertEqual(empty_owner.status_code, 404)
        self.assertNotIn('result', empty_owner.json())
        unauthenticated = await self.client.get('/api/prototype/jobs/current')
        self.assertEqual(unauthenticated.status_code, 401)
        self.backend.model_release.set()

        async def latest_completed():
            while True:
                response = await self.client.get('/api/prototype/jobs/current', headers=self.headers())
                if response.json()['status'] == 'completed':
                    return response.json()
                await asyncio.sleep(0.01)

        completed = await asyncio.wait_for(latest_completed(), timeout=3)
        self.assertEqual(completed['job_id'], accepted.json()['job_id'])
        self.assertEqual(completed['result']['principal_id'], 'shared-prototype.' + SESSION_A)
        self.assertEqual(self.backend.model_calls, 2)

    async def test_exact_body_limit_is_replayed_byte_for_byte_once_to_backend(self):
        body = b"x" * 32768 + b"y" * 32768

        async def exact_chunks():
            yield body[:32768]
            yield body[32768:]

        response = await self.client.post(
            "/api/research/guides", headers=self.headers(post=True), content=exact_chunks()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["received_bytes"], 65536)
        self.assertEqual(len(self.backend.calls), 1)
        self.assertEqual(self.backend.calls[0]["body"], body)


class ResidentOllamaAdapterTests(unittest.TestCase):
    def adapter(self, requests):
        def respond(request):
            requests.append({
                "method": request.method, "path": request.url.path,
                "body": json.loads(request.content) if request.content else None,
            })
            # The real adapter consumes iter_raw(); keep this transport response unread.
            content = json.dumps({"mock_transport_only": True}).encode("utf-8")
            return httpx.Response(
                200, stream=httpx.ByteStream(content), headers={"Content-Type": "application/json"}
            )

        config = ModelConfig("http://127.0.0.1:19191", "test-model:q4", "a" * 64)
        return SHARED.ResidentOllamaAdapter(
            config, transport=httpx.MockTransport(respond), clock=lambda: 0
        )

    def test_generate_and_chat_force_residency_without_mutating_caller_body(self):
        requests = []
        with self.adapter(requests) as adapter:
            for path in ("/api/generate", "/api/chat"):
                with self.subTest(path=path):
                    body = {"keep_alive": "5m", "options": {"num_ctx": 4096}, "stream": False}
                    original = deepcopy(body)
                    response = adapter._request("POST", path, 1, body)
                    self.assertEqual(response, {"mock_transport_only": True})
                    self.assertEqual(body, original)
                    self.assertEqual(requests[-1]["body"], {**original, "keep_alive": -1})
        self.assertEqual(len(requests), 2)

    def test_get_and_other_post_requests_keep_original_method_path_and_body(self):
        requests = []
        with self.adapter(requests) as adapter:
            adapter._request("GET", "/api/tags", 1)
            original = {"keep_alive": "5m", "scope": "transport-test"}
            adapter._request("POST", "/other", 1, original)
        self.assertEqual(requests, [
            {"method": "GET", "path": "/api/tags", "body": None},
            {"method": "POST", "path": "/other", "body": original},
        ])
        self.assertEqual(original, {"keep_alive": "5m", "scope": "transport-test"})


if __name__ == "__main__":
    unittest.main()
