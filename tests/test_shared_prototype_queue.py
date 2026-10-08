"""Durable four-worker transport tests; no customer data or actual model generation."""

import asyncio
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import httpx
from lgax_core.errors import DomainError
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shared_prototype_queue_under_test", ROOT / "scripts/serve_shared_research_prototype.py"
)
assert SPEC is not None and SPEC.loader is not None
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)

ORIGIN = "https://prototype.example.test"
SIGNING_KEY = b"queue-test-signing-key-not-a-serving-credential-0001"


def transport_payload(goal):
    """These identifiers are mock transport labels, not sources or a planning fixture."""
    return {
        "bundle_id": "transport-test-bundle", "goal": goal,
        "constraints": ["TEST ONLY: queue transport metadata"],
    }


class BarrierBackend:
    """Expose genuinely overlapping mock processing and independently releasable slots."""

    def __init__(self, registry):
        self.registry = registry
        self.entries = []
        self.reads = []
        self.started = {}
        self.releases = {}
        self.fail_goals = set()
        self.active_count = 0
        self.peak_active_count = 0
        self.start_order = []

    def started_event(self, goal):
        return self.started.setdefault(goal, asyncio.Event())

    def release(self, goal):
        self.releases.setdefault(goal, asyncio.Event()).set()

    async def __call__(self, scope, receive, send):
        headers = Headers(scope=scope)
        try:
            principal = self.registry.authenticate(headers.get("authorization"))
        except DomainError:
            return await JSONResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "Mock authentication rejection"}},
                status_code=401,
            )(scope, receive, send)
        raw = await Request(scope, receive).body()
        if scope["method"] != "POST" or scope["path"] != "/api/research/planning-runs":
            self.reads.append({"path": scope["path"], "owner_id": principal.id})
            return await JSONResponse({
                "mock_transport_only": True, "path": scope["path"], "owner_id": principal.id,
            })(scope, receive, send)
        payload = json.loads(raw)
        goal = payload["goal"]
        self.entries.append({
            "owner_id": principal.id, "payload": payload, "body": raw,
            "headers": dict(headers),
        })
        self.active_count += 1
        self.peak_active_count = max(self.peak_active_count, self.active_count)
        self.start_order.append(goal)
        self.started_event(goal).set()
        try:
            await self.releases.setdefault(goal, asyncio.Event()).wait()
            if goal in self.fail_goals:
                return await JSONResponse({"error": {
                    "code": "MODEL_UNAVAILABLE", "message": "Mock processing failed",
                }}, status_code=422)(scope, receive, send)
            return await JSONResponse({
                "mock_transport_only": True, "owner_id": principal.id, "goal": goal,
                "constraints": payload["constraints"],
            }, status_code=201)(scope, receive, send)
        finally:
            self.active_count -= 1


class SharedPrototypeQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.static = self.root / "static"
        self.static.mkdir()
        (self.static / "index.html").write_text(
            "<!doctype html><title>Queue transport test only</title>", encoding="utf-8"
        )
        self.registry = SHARED.SessionRegistry(SIGNING_KEY)
        self.tokens = [self.registry.token(f"{index + 1:032x}") for index in range(8)]
        self.apps = []
        self.backend = BarrierBackend(self.registry)
        self.app = await self.make_app(self.backend, self.root / "jobs.sqlite3")
        self.client = self.make_client(self.app)

    async def asyncTearDown(self):
        await self.client.aclose()
        for app in reversed(self.apps):
            await app.queue.close()

    async def make_app(self, backend, path, *, start=True):
        app = SHARED.SharedGateway(
            backend, self.registry, self.static, ORIGIN, "queue-test-release",
            queue_path=path, worker_count=4, queue_capacity=8,
        )
        self.apps.append(app)
        if start:
            await app.queue.start()
        return app

    async def close_app(self, app):
        await app.queue.close()
        self.apps.remove(app)

    def make_client(self, app):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN)

    def headers(self, owner=0, *, post=False):
        result = {"Authorization": "Bearer " + self.tokens[owner]}
        if post:
            result["Origin"] = ORIGIN
        return result

    def owner_id(self, owner):
        return self.registry.authenticate("Bearer " + self.tokens[owner]).id

    async def submit(self, goal, owner=0, *, client=None):
        response = await (client or self.client).post(
            "/api/research/planning-runs", headers=self.headers(owner, post=True),
            json=transport_payload(goal),
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        job = response.json()
        self.assertIsInstance(job["job_id"], str)
        self.assertTrue(job["job_id"])
        self.assertIn(job["status"], {"queued", "running"})
        self.assertIs(type(job["queue_position"]), int)
        self.assertGreaterEqual(job["queue_position"], 0)
        self.assertEqual(job["poll_after_ms"], 1000)
        self.assertNotIn("result", job)
        self.assertNotIn("error", job)
        for private_field in ("body", "owner_id", "authorization", "token"):
            self.assertNotIn(private_field, job)
        return job

    async def job(self, job_id, owner=0, *, client=None):
        response = await (client or self.client).get(
            "/api/prototype/jobs/" + job_id, headers=self.headers(owner)
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        value = response.json()
        self.assertEqual(value["job_id"], job_id)
        self.assertEqual(value["poll_after_ms"], 1000)
        return value

    async def terminal(self, job_id, owner=0, *, client=None):
        async def poll():
            while True:
                value = await self.job(job_id, owner, client=client)
                if value["status"] in {"completed", "failed"}:
                    return value
                await asyncio.sleep(0.01)

        result = await asyncio.wait_for(poll(), timeout=5)
        self.assertIsNone(result["queue_position"])
        return result

    async def started(self, backend, *goals):
        await asyncio.wait_for(asyncio.gather(
            *(backend.started_event(goal).wait() for goal in goals)
        ), timeout=5)

    async def test_four_independent_sessions_overlap_and_results_remain_owner_scoped(self):
        goals = [f"parallel-owner-{owner}" for owner in range(4)]
        accepted = await asyncio.gather(*(self.submit(goal, owner) for owner, goal in enumerate(goals)))
        self.assertEqual(len({row["job_id"] for row in accepted}), 4)
        await self.started(self.backend, *goals)
        self.assertEqual(self.backend.active_count, 4)
        self.assertEqual(self.backend.peak_active_count, 4)
        self.assertEqual(len(self.backend.entries), 4)
        for owner, (goal, row) in enumerate(zip(goals, accepted, strict=True)):
            running = await self.job(row["job_id"], owner)
            self.assertEqual((running["status"], running["queue_position"]), ("running", 0))
            other = await self.client.get(
                "/api/prototype/jobs/" + row["job_id"], headers=self.headers((owner + 1) % 4)
            )
            self.assertIn(other.status_code, {403, 404})
            self.assertNotIn("result", other.json())
            entry = next(entry for entry in self.backend.entries if entry["payload"]["goal"] == goal)
            self.assertEqual(entry["owner_id"], self.owner_id(owner))
            self.assertEqual(entry["payload"], transport_payload(goal))
            self.assertEqual(entry["headers"]["host"], "127.0.0.1")
            self.assertEqual(entry["headers"]["origin"], "http://127.0.0.1:5175")
            self.assertEqual(entry["headers"]["authorization"], "Bearer " + self.tokens[owner])
        missing_auth = await self.client.get("/api/prototype/jobs/" + accepted[0]["job_id"])
        self.assertEqual(missing_auth.status_code, 401)
        self.assertNotIn("result", missing_auth.json())
        # These operations must finish while every processing slot is still blocked.
        read = await asyncio.wait_for(self.client.get(
            "/api/research/bundles", headers=self.headers()
        ), timeout=3)
        guide = await asyncio.wait_for(self.client.post(
            "/api/research/guides", headers=self.headers(post=True), json={}
        ), timeout=3)
        self.assertEqual((read.status_code, guide.status_code), (200, 200))
        self.assertEqual(self.backend.active_count, 4)
        for goal in goals:
            self.backend.release(goal)
        completed = await asyncio.gather(*(
            self.terminal(row["job_id"], owner) for owner, row in enumerate(accepted)
        ))
        for owner, value in enumerate(completed):
            self.assertEqual(value["status"], "completed")
            self.assertEqual(value["result"], {
                "mock_transport_only": True, "owner_id": self.owner_id(owner),
                "goal": goals[owner], "constraints": transport_payload(goals[owner])["constraints"],
            })
            denied = await self.client.get(
                "/api/prototype/jobs/" + value["job_id"], headers=self.headers((owner + 1) % 4)
            )
            self.assertIn(denied.status_code, {403, 404})
            self.assertNotIn("result", denied.json())
        self.assertEqual(self.backend.active_count, 0)

    async def test_fifth_and_sixth_jobs_wait_in_fifo_order_without_exceeding_four_slots(self):
        goals = [f"fifo-{owner}" for owner in range(6)]
        await asyncio.gather(*(self.submit(goals[owner], owner) for owner in range(4)))
        await self.started(self.backend, *goals[:4])
        fifth = await self.submit(goals[4], 4)
        sixth = await self.submit(goals[5], 5)
        self.assertEqual((fifth["status"], fifth["queue_position"]), ("queued", 1))
        self.assertEqual((sixth["status"], sixth["queue_position"]), ("queued", 2))
        self.assertEqual(len(self.backend.entries), 4)
        self.backend.release(goals[0])
        await self.started(self.backend, goals[4])
        waiting = await self.job(sixth["job_id"], 5)
        self.assertEqual((waiting["status"], waiting["queue_position"]), ("queued", 1))
        self.assertFalse(self.backend.started_event(goals[5]).is_set())
        self.backend.release(goals[4])
        await self.started(self.backend, goals[5])
        self.assertEqual(self.backend.start_order[-2:], goals[4:])
        self.assertEqual(self.backend.peak_active_count, 4)
        for goal in goals:
            self.backend.release(goal)
        self.assertEqual((await self.terminal(fifth["job_id"], 4))["status"], "completed")
        self.assertEqual((await self.terminal(sixth["job_id"], 5))["status"], "completed")

    async def test_one_failed_job_does_not_fail_other_three_and_its_slot_is_reused(self):
        goals = [f"failure-isolation-{owner}" for owner in range(4)]
        self.backend.fail_goals.add(goals[0])
        accepted = await asyncio.gather(*(self.submit(goal, owner) for owner, goal in enumerate(goals)))
        await self.started(self.backend, *goals)
        self.backend.release(goals[0])
        failed = await self.terminal(accepted[0]["job_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"]["code"], "MODEL_UNAVAILABLE")
        self.assertIsInstance(failed["error"]["message"], str)
        self.assertNotIn("result", failed)
        self.assertEqual(self.backend.active_count, 3)
        replacement = await self.submit("replacement-after-failure", 4)
        await self.started(self.backend, "replacement-after-failure")
        self.assertEqual(self.backend.active_count, 4)
        self.assertEqual(self.backend.peak_active_count, 4)
        for goal in [*goals[1:], "replacement-after-failure"]:
            self.backend.release(goal)
        successes = await asyncio.gather(*(
            self.terminal(accepted[owner]["job_id"], owner) for owner in range(1, 4)
        ), self.terminal(replacement["job_id"], 4))
        self.assertEqual([value["status"] for value in successes], ["completed"] * 4)
        self.assertEqual(len(self.backend.entries), 5)

    async def test_invalid_auth_origin_and_actual_body_limit_start_zero_processing(self):
        missing_auth = await self.client.post(
            "/api/research/planning-runs", headers={"Origin": ORIGIN},
            json=transport_payload("rejected-missing-auth"),
        )
        self.assertEqual(missing_auth.status_code, 401)
        forged = await self.client.post(
            "/api/research/planning-runs", headers={
                "Origin": ORIGIN, "Authorization": "Bearer v1." + "1" * 32 + "." + "0" * 64,
            }, json=transport_payload("rejected-forged-auth"),
        )
        self.assertEqual(forged.status_code, 401)
        for origin in (None, "https://another.example.test"):
            headers = self.headers()
            if origin is not None:
                headers["Origin"] = origin
            rejected = await self.client.post(
                "/api/research/planning-runs", headers=headers,
                json=transport_payload("rejected-origin"),
            )
            self.assertEqual(rejected.status_code, 403)

        async def too_large_chunks():
            yield b"x" * 32768
            yield b"y" * 32769

        oversized = await self.client.post(
            "/api/research/planning-runs", headers=self.headers(post=True), content=too_large_chunks()
        )
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(self.backend.entries, [])
        self.assertEqual(self.backend.peak_active_count, 0)

    async def test_same_principal_concurrent_duplicate_posts_are_not_executed_twice(self):
        responses = await asyncio.gather(*(
            self.client.post("/api/research/planning-runs", headers=self.headers(post=True),
                             json=transport_payload("one-active-owner"))
            for _ in range(2)
        ))
        self.assertEqual(sorted(response.status_code for response in responses), [202, 409])
        accepted = next(response.json() for response in responses if response.status_code == 202)
        rejected = next(response.json() for response in responses if response.status_code == 409)
        self.assertEqual(rejected["error"]["code"], "JOB_ALREADY_ACTIVE")
        await self.started(self.backend, "one-active-owner")
        changed_duplicate = await self.client.post(
            "/api/research/planning-runs", headers=self.headers(post=True),
            json=transport_payload("different-payload-same-active-owner"),
        )
        self.assertEqual(changed_duplicate.status_code, 409)
        self.assertEqual(len(self.backend.entries), 1)
        self.backend.release("one-active-owner")
        self.assertEqual((await self.terminal(accepted["job_id"]))["status"], "completed")
        self.assertEqual(len(self.backend.entries), 1)

    async def test_queued_sqlite_job_resumes_once_after_recreation_with_exact_saved_body(self):
        path = self.root / "queued-restart.sqlite3"
        before_backend = BarrierBackend(self.registry)
        before = await self.make_app(before_backend, path, start=False)
        payload = transport_payload("queued-before-start")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        queued = before.queue.enqueue(self.owner_id(0), body, client="web")
        self.assertEqual((queued["status"], queued["queue_position"]), ("queued", 1))
        self.assertEqual(before_backend.entries, [])
        await self.close_app(before)
        resumed_backend = BarrierBackend(self.registry)
        resumed = await self.make_app(resumed_backend, path)
        async with self.make_client(resumed) as client:
            await self.started(resumed_backend, payload["goal"])
            running = await self.job(queued["job_id"], client=client)
            self.assertEqual(running["status"], "running")
            duplicate = await client.post(
                "/api/research/planning-runs", headers=self.headers(post=True), json=payload
            )
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(len(resumed_backend.entries), 1)
            self.assertEqual(resumed_backend.entries[0]["body"], body)
            self.assertEqual(resumed_backend.entries[0]["owner_id"], self.owner_id(0))
            resumed_backend.release(payload["goal"])
            completed = await self.terminal(queued["job_id"], client=client)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["result"]["goal"], payload["goal"])
            for _ in range(2):
                self.assertEqual((await self.job(queued["job_id"], client=client))["status"], "completed")
            self.assertEqual(len(resumed_backend.entries), 1)

    async def test_crash_snapshot_marks_running_interrupted_without_automatic_reexecution(self):
        path = self.root / "running-before-crash.sqlite3"
        original_backend = BarrierBackend(self.registry)
        original = await self.make_app(original_backend, path)
        async with self.make_client(original) as client:
            queued = await self.submit("running-at-crash", client=client)
            await self.started(original_backend, "running-at-crash")
            self.assertEqual((await self.job(queued["job_id"], client=client))["status"], "running")
            snapshot = self.root / "crash-snapshot.sqlite3"
            source = sqlite3.connect(path)
            destination = sqlite3.connect(snapshot)
            try:
                # SQLite's backup preserves the crash state without inventing/changing schema rows.
                source.backup(destination)
            finally:
                destination.close()
                source.close()
        await self.close_app(original)
        recovered_backend = BarrierBackend(self.registry)
        recovered = await self.make_app(recovered_backend, snapshot)
        async with self.make_client(recovered) as client:
            interrupted = await self.terminal(queued["job_id"], client=client)
            self.assertEqual(interrupted["status"], "failed")
            self.assertEqual(interrupted["error"]["code"], "SERVER_RESTARTED")
            self.assertNotIn("result", interrupted)
            self.assertEqual(recovered_backend.entries, [])
            self.assertEqual(recovered_backend.active_count, 0)
            repeated = await self.job(queued["job_id"], client=client)
            self.assertEqual(repeated, interrupted)
            self.assertEqual(recovered_backend.entries, [])


if __name__ == "__main__":
    unittest.main()
