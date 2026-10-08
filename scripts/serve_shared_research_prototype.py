"""Explicit team prototype serving, independent of an AI/SSH session lifetime."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import Principal, TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.errors import DomainError
from lgax_core.model_client import OllamaAdapter, StructuredModelClient
from lgax_core.public_planning import PublicPlanner
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve_research_prototype import research_bundle_paths

COOKIE = 'lgax_prototype_session'
SESSION = re.compile(r'[a-f0-9]{32}')
MAX_REQUEST_BYTES = 65536
MAX_JOB_RESPONSE_BYTES = 2 * 1024 * 1024


class SessionRegistry(TokenRegistry):
    """Only editor credentials for this fresh, public-source prototype store."""
    def __init__(self, signing_key: bytes):
        if len(signing_key) < 32:
            raise ValueError('A private prototype signing key is required')
        self.signing_key = signing_key

    def token(self, session: str) -> str:
        if not SESSION.fullmatch(session):
            raise ValueError('Invalid prototype session')
        digest = hmac.new(self.signing_key, session.encode(), hashlib.sha256).hexdigest()
        return f'v1.{session}.{digest}'

    def authenticate(self, authorization: str | None) -> Principal:
        token = authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
        parts = token.split('.')
        if (len(parts) != 3 or parts[0] != 'v1' or not SESSION.fullmatch(parts[1])
                or not re.fullmatch(r'[a-f0-9]{64}', parts[2])
                or not hmac.compare_digest(token, self.token(parts[1]))):
            raise DomainError('UNAUTHORIZED', '작업실 인증을 확인해 주세요.')
        return Principal('shared-prototype.' + parts[1], 'editor')


class ResidentOllamaAdapter(OllamaAdapter):
    """Override the request's five-minute policy only for this explicit service."""
    def _request(self, method, path, deadline, body=None):
        if method == 'POST' and path in {'/api/generate', '/api/chat'} and body is not None:
            body = {**body, 'keep_alive': -1}
        return super()._request(method, path, deadline, body)


class ResidentPlanner:
    def _client(self):
        with StructuredModelClient.from_env() as configured:
            config = configured.adapter.config
        return StructuredModelClient(ResidentOllamaAdapter(config))

    def run(self, bundle, goal, constraints, previous=None):
        with self._client() as client:
            return PublicPlanner.from_model_client(client, max_model_calls=4, max_problems=1,
                max_prompt_characters=9000, max_source_characters=1000).run(
                    bundle, goal, constraints, previous)

    def repair(self, bundle, previous, feedback):
        with self._client() as client:
            return PublicPlanner.from_model_client(client, max_model_calls=4, max_problems=1,
                max_prompt_characters=9000, max_source_characters=1000).repair(bundle, previous, feedback)


class PlanningJobQueue:
    """Durable, principal-owned serving jobs; unrelated to development workers."""

    def __init__(self, backend, registry, path: Path, worker_count=4, capacity=8):
        if type(worker_count) is not int or not 1 <= worker_count <= 4:
            raise ValueError('At most four serving workers are supported')
        if type(capacity) is not int or capacity < max(8, worker_count):
            raise ValueError('The serving queue must admit at least eight active jobs')
        self.backend, self.registry, self.path = backend, registry, Path(path)
        self.worker_count, self.capacity = worker_count, capacity
        self.wake = asyncio.Event()
        self.workers = []
        self.started = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS prototype_jobs (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT UNIQUE NOT NULL,
                owner_id TEXT NOT NULL, body BLOB NOT NULL, client TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
                result TEXT, error_code TEXT, error_message TEXT,
                created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT)''')
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(prototype_jobs)')}
            for name in ('created_at', 'started_at', 'finished_at'):
                if name not in columns:
                    connection.execute(f'ALTER TABLE prototype_jobs ADD COLUMN {name} TEXT')
            connection.execute('CREATE INDEX IF NOT EXISTS prototype_jobs_active ON prototype_jobs(status, sequence)')
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS prototype_jobs_owner_active ON prototype_jobs(owner_id) WHERE status IN ('queued','running')")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _session(owner_id):
        prefix = 'shared-prototype.'
        if not isinstance(owner_id, str) or not owner_id.startswith(prefix):
            raise ValueError('Invalid serving job owner')
        session = owner_id[len(prefix):]
        if not SESSION.fullmatch(session):
            raise ValueError('Invalid serving job owner')
        return session

    def _public(self, connection, row):
        position = None
        if row['status'] == 'running':
            position = 0
        elif row['status'] == 'queued':
            position = connection.execute("SELECT COUNT(*) FROM prototype_jobs WHERE status='queued' AND sequence<=?", (row['sequence'],)).fetchone()[0]
        result = {'job_id': row['job_id'], 'status': row['status'],
                  'queue_position': position, 'poll_after_ms': 1000}
        for name in ('created_at', 'started_at', 'finished_at'):
            if row[name] is not None:
                result[name] = row[name]
        if row['status'] == 'completed':
            result['result'] = json.loads(row['result'])
        elif row['status'] == 'failed':
            result['error'] = {'code': row['error_code'], 'message': row['error_message']}
        return result

    def enqueue(self, owner_id, body: bytes, client='web'):
        self._session(owner_id)
        if not isinstance(body, bytes) or len(body) > MAX_REQUEST_BYTES:
            raise DomainError('INVALID_ARGUMENT', '입력 크기를 확인해 주세요.')
        # Only request bytes and a bounded, non-credential client label are retained.
        client = client if client in {'web', 'mcp', 'api'} else 'web'
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute("SELECT 1 FROM prototype_jobs WHERE owner_id=? AND status IN ('queued','running')", (owner_id,)).fetchone():
                raise DomainError('JOB_ALREADY_ACTIVE', '이 세션의 기획을 처리 중입니다. 현재 작업을 확인해 주세요.')
            if connection.execute("SELECT COUNT(*) FROM prototype_jobs WHERE status IN ('queued','running')").fetchone()[0] >= self.capacity:
                raise DomainError('QUEUE_FULL', '접수 가능한 기획이 가득 찼습니다. 잠시 뒤 다시 요청해 주세요.')
            job_id = secrets.token_hex(16)
            connection.execute("INSERT INTO prototype_jobs(job_id, owner_id, body, client, status, created_at) VALUES (?, ?, ?, ?, 'queued', ?)", (job_id, owner_id, body, client, datetime.now(UTC).isoformat()))
            row = connection.execute('SELECT * FROM prototype_jobs WHERE job_id=?', (job_id,)).fetchone()
            public = self._public(connection, row)
        self.wake.set()
        return public

    def get(self, job_id, owner_id):
        with self.connect() as connection:
            row = connection.execute('SELECT * FROM prototype_jobs WHERE job_id=? AND owner_id=?', (job_id, owner_id)).fetchone()
            if row is None:
                raise DomainError('NOT_FOUND', '접근 가능한 기획 작업을 찾을 수 없습니다.')
            return self._public(connection, row)

    def current(self, owner_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM prototype_jobs WHERE owner_id=? ORDER BY CASE WHEN status IN ('queued','running') THEN 0 ELSE 1 END, sequence DESC LIMIT 1", (owner_id,)).fetchone()
            if row is None:
                raise DomainError('NOT_FOUND', '접근 가능한 기획 작업을 찾을 수 없습니다.')
            return self._public(connection, row)

    def _claim(self):
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute("SELECT * FROM prototype_jobs WHERE status='queued' ORDER BY sequence LIMIT 1").fetchone()
            if row is not None:
                connection.execute("UPDATE prototype_jobs SET status='running', started_at=? WHERE job_id=? AND status='queued'", (datetime.now(UTC).isoformat(), row['job_id']))
            return row

    def _finish(self, job_id, *, result=None, error=None):
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False) if error is None else None
        with self.connect() as connection:
            connection.execute("UPDATE prototype_jobs SET status=?, result=?, error_code=?, error_message=?, finished_at=? WHERE job_id=? AND status='running'", (
                'completed' if error is None else 'failed', encoded,
                error['code'] if error else None, error['message'] if error else None,
                datetime.now(UTC).isoformat(), job_id))

    async def _execute(self, job):
        token = self.registry.token(self._session(job['owner_id']))
        body = bytes(job['body'])
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'},
                 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
                 'path': '/api/research/planning-runs', 'raw_path': b'/api/research/planning-runs',
                 'root_path': '', 'query_string': b'', 'server': ('127.0.0.1', 18980),
                 'client': ('127.0.0.1', 0), 'headers': [
                     (b'host', b'127.0.0.1'), (b'origin', b'http://127.0.0.1:5175'),
                     (b'authorization', ('Bearer ' + token).encode('ascii')),
                     (b'content-type', b'application/json'),
                     (b'content-length', str(len(body)).encode('ascii')),
                     (b'x-lgax-client', job['client'].encode('ascii'))]}
        delivered, status, complete = False, None, False
        response = bytearray()

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            # A background invocation is independent of the submitting connection.
            await asyncio.Event().wait()

        async def send(message):
            nonlocal status, complete
            if message['type'] == 'http.response.start':
                if status is not None:
                    raise ValueError('Duplicate backend response start')
                status = message['status']
            elif message['type'] == 'http.response.body':
                if status is None or complete:
                    raise ValueError('Invalid backend response framing')
                chunk = message.get('body', b'')
                if len(response) + len(chunk) > MAX_JOB_RESPONSE_BYTES:
                    raise ValueError('Backend response exceeds the serving limit')
                response.extend(chunk)
                complete = not message.get('more_body', False)

        await self.backend(scope, receive, send)
        if not complete or status is None:
            raise ValueError('Incomplete backend response')
        payload = json.loads(response)
        if not isinstance(payload, dict):
            raise ValueError('Invalid backend response shape')
        if 200 <= status < 300 and payload.get('ok') is not False:
            return payload, None
        error = payload.get('error')
        if not isinstance(error, dict) or not all(isinstance(error.get(key), str) for key in ('code', 'message')):
            raise ValueError('Invalid backend error shape')
        return None, {'code': error['code'], 'message': error['message']}

    async def _worker(self):
        while True:
            job = self._claim()
            if job is None:
                self.wake.clear()
                await self.wake.wait()
                continue
            try:
                result, error = await self._execute(job)
                self._finish(job['job_id'], result=result, error=error)
            except asyncio.CancelledError:
                self._finish(job['job_id'], error={'code': 'SERVER_STOPPED',
                    'message': '서버가 종료되어 기획 상태를 확정할 수 없습니다. 자동 재실행하지 않았습니다.'})
                raise
            except Exception:
                self._finish(job['job_id'], error={'code': 'INTERNAL_ERROR',
                    'message': '기획 작업을 완료하지 못했습니다. 자동 재실행하지 않았습니다.'})
            finally:
                self.wake.set()

    async def start(self):
        if self.started:
            return
        with self.connect() as connection:
            connection.execute("UPDATE prototype_jobs SET status='failed', error_code='SERVER_RESTARTED', error_message=?, finished_at=? WHERE status='running'", (
                '서버가 재시작되어 이전 실행 상태를 확정할 수 없습니다. 자동 재실행하지 않았습니다.', datetime.now(UTC).isoformat()))
        self.started = True
        self.workers = [asyncio.create_task(self._worker(), name=f'prototype-inference-{index}')
                        for index in range(self.worker_count)]
        self.wake.set()

    async def close(self):
        self.started = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []


class SharedGateway:
    def __init__(self, backend, registry, static_root: Path, origin: str, release: str,
                 *, queue_path: Path, worker_count=4, queue_capacity=8):
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path not in {'', '/'}:
            raise ValueError('An exact HTTPS public origin is required')
        self.origin = origin.rstrip('/')
        self.host = parsed.netloc
        self.backend, self.registry, self.release = backend, registry, release
        self.static = StaticFiles(directory=static_root, html=True)
        if Path(queue_path).resolve().is_relative_to(Path(static_root).resolve()):
            raise ValueError('The private queue must be outside the served static directory')
        self.queue = PlanningJobQueue(backend, registry, queue_path, worker_count, queue_capacity)

    async def _reply(self, scope, receive, send, code, message, status):
        await JSONResponse({'ok': False, 'error': {'code': code, 'message': message}},
            status_code=status, headers={'Cache-Control': 'no-store'})(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            async def lifespan_receive():
                message = await receive()
                if message['type'] == 'lifespan.shutdown':
                    await self.queue.close()
                return message

            async def lifespan_send(message):
                if message['type'] == 'lifespan.startup.complete':
                    try:
                        await self.queue.start()
                    except Exception:
                        await send({'type': 'lifespan.startup.failed', 'message': 'Serving queue startup failed'})
                        raise
                return await send(message)

            try:
                return await self.backend(scope, lifespan_receive, lifespan_send)
            finally:
                await self.queue.close()
        if scope['type'] != 'http':
            return await self.backend(scope, receive, send)
        headers = Headers(scope=scope)
        if headers.get('host') not in {self.host, '127.0.0.1:18980'}:
            return await self._reply(scope, receive, send, 'FORBIDDEN', '접속 주소를 확인해 주세요.', 403)
        if headers.get('origin') is not None and headers['origin'] != self.origin:
            return await self._reply(scope, receive, send, 'FORBIDDEN', '같은 공유 주소에서 접속해 주세요.', 403)
        path, method = scope['path'], scope['method']
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'} and headers.get('origin') != self.origin:
            return await self._reply(scope, receive, send, 'FORBIDDEN', '공유 화면에서 요청해 주세요.', 403)
        if path == '/api/prototype/session' and method == 'GET':
            cookies = SimpleCookie()
            try:
                cookies.load(headers.get('cookie', ''))
                token = cookies[COOKIE].value if COOKIE in cookies else ''
                self.registry.authenticate('Bearer ' + token)
            except Exception:
                token = self.registry.token(secrets.token_hex(16))
            response = JSONResponse({'token': token, 'shared_prototype': True},
                headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
            response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite='strict')
            return await response(scope, receive, send)
        if path == '/health' and method == 'GET':
            return await JSONResponse({'status': 'ok', 'prototype': True, 'release': self.release,
                'scheduled_shutdown': False, 'serving_parallelism': self.queue.worker_count},
                headers={'Cache-Control': 'no-store'})(scope, receive, send)
        if path.startswith('/api/prototype/jobs/'):
            if method != 'GET':
                return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '지원하지 않는 요청입니다.', 405)
            try:
                principal = self.registry.authenticate(headers.get('authorization'))
                job_id = path.removeprefix('/api/prototype/jobs/')
                if job_id == 'current':
                    job = self.queue.current(principal.id)
                elif SESSION.fullmatch(job_id):
                    job = self.queue.get(job_id, principal.id)
                else:
                    raise DomainError('NOT_FOUND', '접근 가능한 기획 작업을 찾을 수 없습니다.')
            except DomainError as error:
                return await self._reply(scope, receive, send, error.code, error.message,
                                         401 if error.code == 'UNAUTHORIZED' else 404)
            return await JSONResponse(job, headers={'Cache-Control': 'no-store'})(scope, receive, send)
        if path.startswith('/api/research/'):
            if method not in {'GET', 'POST'}:
                return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '지원하지 않는 요청입니다.', 405)
            length = headers.get('content-length', '0')
            if not length.isdecimal() or int(length) > MAX_REQUEST_BYTES:
                return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '입력 크기를 확인해 주세요.', 413)
            backend_receive = receive
            if method == 'POST':
                body = bytearray()
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    chunk = message.get('body', b'')
                    if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                        return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '입력 크기를 확인해 주세요.', 413)
                    body.extend(chunk)
                    if not message.get('more_body', False):
                        break
                delivered = False

                async def replay_body():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                    return await receive()

                backend_receive = replay_body
            normalized = dict(scope)
            normalized['headers'] = [(k, v) for k, v in scope['headers']
                if k.lower() not in {b'host', b'origin', b'x-forwarded-host', b'x-forwarded-proto'}]
            normalized['headers'] += [(b'host', b'127.0.0.1'),
                (b'origin', b'http://127.0.0.1:5175')]
            if method == 'POST' and path == '/api/research/planning-runs':
                try:
                    principal = self.registry.authenticate(headers.get('authorization'))
                    if not self.queue.started:
                        raise DomainError('QUEUE_NOT_READY', '기획 접수 준비를 기다려 주세요.')
                    job = self.queue.enqueue(principal.id, bytes(body), headers.get('x-lgax-client', 'web'))
                except DomainError as error:
                    status = 401 if error.code == 'UNAUTHORIZED' else 409 if error.code == 'JOB_ALREADY_ACTIVE' else 503
                    return await self._reply(scope, receive, send, error.code, error.message, status)
                return await JSONResponse(job, status_code=202,
                    headers={'Cache-Control': 'no-store'})(scope, receive, send)
            return await self.backend(normalized, backend_receive, send)
        if path.startswith('/api/') or path.startswith(('/docs', '/openapi', '/redoc')):
            return await self._reply(scope, receive, send, 'NOT_FOUND', '공유 프로토타입 범위에 없는 기능입니다.', 404)
        if method != 'GET' and method != 'HEAD':
            return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '지원하지 않는 요청입니다.', 405)
        try:
            return await self.static(scope, receive, send)
        except HTTPException as error:
            return await self._reply(scope, receive, send, 'NOT_FOUND', '페이지를 찾을 수 없습니다.', error.status_code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Private serving configuration')
    args = parser.parse_args()
    config = json.loads(args.config.read_text('utf-8'))
    root = Path(config['release_root'])
    state = Path(config['state_dir'])
    state.mkdir(parents=True, exist_ok=True)
    keyfile = state / 'session-signing.key'
    if not keyfile.exists():
        with keyfile.open('xb') as stream:
            stream.write(secrets.token_bytes(32))
        keyfile.chmod(0o600)
    registry = SessionRegistry(keyfile.read_bytes())
    workspace = ResearchWorkspace(state / 'research.sqlite3', research_bundle_paths(root), ResidentPlanner())
    backend = create_workspace_app(state / 'workspace.sqlite3', registry, research_workspace=workspace)
    app = SharedGateway(backend, registry, root / 'apps/web/dist', config['public_origin'], config['release'],
                        queue_path=state / 'queue.sqlite3')
    uvicorn.run(app, host='127.0.0.1', port=18980, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
