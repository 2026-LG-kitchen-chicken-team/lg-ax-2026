"""Explicit team prototype serving, independent of an AI/SSH session lifetime."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
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
SHARED_MODEL_ID = 'qwen3.8:27b-q4_K_M'
SHARED_MANIFEST_SHA = '25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e'
SHARED_GGUF_SHA = 'f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d'
SHARED_GGUF_BYTES = 16810714464
SHARED_PARAMS_SHA = '448d29437397713495b408d51b4ccbc5ba95240a7583643efb2304921950b111'


def _model_failure(reason):
    return DomainError('MODEL_UNAVAILABLE', '고정한 모델의 안전한 호출·revision 확인을 완료하지 못했습니다.',
                       {'reason': reason})


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


class ResidentLlamaAdapter(OllamaAdapter):
    """Serving-only native transport; the launcher verifies binary and GGUF bytes.

    Inherit bounded HTTP, native/local schema validation, and ModelConfig budgets.
    Local manifest/params and GGUF identity plus real /props are checked on both
    sides of each generation; /api/tags is never fabricated.
    """

    def __init__(self, config, model_store: Path, **kwargs):
        if (config.endpoint != 'http://127.0.0.1:18875' or config.model_id != SHARED_MODEL_ID
                or config.expected_digest != SHARED_MANIFEST_SHA
                or config.context_tokens != 16384 or config.api_mode != 'generate' or config.thinking):
            raise DomainError('INVALID_ARGUMENT', '공유 llama.cpp의 고정 모델 설정을 확인해 주세요.',
                              {'reason': 'shared_native_configuration_mismatch'})
        self.model_store = Path(model_store)
        if not self.model_store.is_absolute():
            raise ValueError('An absolute, launcher-verified model store is required')
        self.model_path = self.model_store / 'blobs' / ('sha256-' + SHARED_GGUF_SHA)
        self.model_alias = config.model_id + '@' + config.expected_digest
        super().__init__(config, **kwargs)

    @staticmethod
    def _identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    @classmethod
    def _small_pinned_file(cls, path, digest):
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 8192:
            raise _model_failure('invalid_service_identity')
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            # Cross-API ctime differs on Windows; descriptor and path are each
            # independently stable, with device/inode/size/mtime matched.
            if cls._identity(before)[:4] != cls._identity(opened)[:4]:
                raise _model_failure('service_identity_changed')
            raw = stream.read(8193)
            if cls._identity(opened) != cls._identity(os.fstat(stream.fileno())):
                raise _model_failure('service_identity_changed')
        if (cls._identity(before) != cls._identity(path.lstat()) or len(raw) > 8192
                or hashlib.sha256(raw).hexdigest() != digest):
            raise _model_failure('model_revision_mismatch')
        return json.loads(raw), cls._identity(before)

    def _verify_pin(self, deadline):
        try:
            manifest_path = (self.model_store / 'manifests' / 'registry.ollama.ai' / 'library'
                             / 'qwen3.8' / '27b-q4_K_M')
            manifest, manifest_identity = self._small_pinned_file(manifest_path, SHARED_MANIFEST_SHA)
            model_layers = [layer for layer in manifest['layers']
                            if layer.get('mediaType') == 'application/vnd.ollama.image.model']
            params_layers = [layer for layer in manifest['layers']
                             if layer.get('mediaType') == 'application/vnd.ollama.image.params']
            if (len(model_layers) != 1 or model_layers[0].get('digest') != 'sha256:' + SHARED_GGUF_SHA
                    or model_layers[0].get('size') != SHARED_GGUF_BYTES
                    or len(params_layers) != 1 or params_layers[0].get('digest') != 'sha256:' + SHARED_PARAMS_SHA):
                raise _model_failure('model_revision_mismatch')
            params, params_identity = self._small_pinned_file(
                self.model_store / 'blobs' / ('sha256-' + SHARED_PARAMS_SHA), SHARED_PARAMS_SHA)
            if params != {'min_p': 0, 'presence_penalty': 0, 'repeat_penalty': 1,
                          'temperature': 1, 'top_k': 20, 'top_p': 0.95}:
                raise _model_failure('model_revision_mismatch')
            info = self.model_path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != SHARED_GGUF_BYTES):
                raise _model_failure('invalid_service_identity')
            identity = [manifest_identity, params_identity, self._identity(info)]
        except DomainError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise _model_failure('invalid_service_identity') from None
        props = self._request('GET', '/props', deadline)
        settings = props.get('default_generation_settings')
        if (props.get('model_alias') != self.model_alias
                or props.get('model_path') != str(self.model_path)
                or type(props.get('total_slots')) is not int or props['total_slots'] != 4
                or not isinstance(settings, dict) or type(settings.get('n_ctx')) is not int
                or settings['n_ctx'] != self.config.context_tokens or props.get('is_sleeping') is not False):
            raise _model_failure('unexpected_service')
        return {'native_model_alias': self.model_alias, 'native_parallelism': 4,
                'gguf_sha256': SHARED_GGUF_SHA, 'params_sha256': SHARED_PARAMS_SHA,
                'model_files_identity_sha256': hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
                'pin_scope': 'local_manifest_params_and_file_identity_plus_native_props',
                'gguf_byte_verification': 'launcher_required'}

    @staticmethod
    def _render_prompt(prompt):
        # Exact one-user, no-tool, think=false branch of Ollama v0.34.0
        # model/renderers/qwen35.go (Qwen3.5 and Qwen3.8 both emit this prefill).
        return ('<|im_start|>user\n' + prompt.strip() + '<|im_end|>\n'
                '<|im_start|>assistant\n<think>\n\n</think>\n\n')

    def _native_settings(self):
        config = self.config
        return {'temperature': config.temperature, 'seed': 42,
                'n_predict': config.max_output_tokens,
                'top_k': 20 if config.top_k is None else config.top_k,
                'top_p': 0.95 if config.top_p is None else config.top_p,
                'min_p': 0 if config.min_p is None else config.min_p,
                'repeat_penalty': 1, 'presence_penalty': 0, 'frequency_penalty': 0}

    def _generate(self, prompt, schema, deadline):
        started = self._clock()
        rendered = self._render_prompt(prompt)
        budget = self.prompt_budget
        if (len(rendered) > budget.max_characters
                or len(rendered.encode('utf-8')) > budget.max_utf8_bytes):
            raise DomainError('INVALID_ARGUMENT', '모델 호출 설정·입력·스키마가 유효하지 않습니다.',
                              {'reason': 'prompt_too_large'})
        native = self._request('POST', '/completion', deadline, {
            'prompt': rendered, 'json_schema': schema, 'stream': False,
            'cache_prompt': True, **self._native_settings(),
        })
        if native.get('model') != self.model_alias:
            raise _model_failure('response_model_mismatch')
        if native.get('stop') is not True or native.get('stop_type') not in {'eos', 'word', 'limit'}:
            raise _model_failure('generation_incomplete')
        if type(native.get('truncated')) is not bool or not isinstance(native.get('content'), str):
            raise _model_failure('invalid_transport_response')
        counts = [native.get('tokens_evaluated'), native.get('tokens_predicted')]
        timings = native.get('timings')
        if (any(type(value) is not int or value < 0 for value in counts) or not isinstance(timings, dict)):
            raise _model_failure('invalid_transport_response')
        for name in ('prompt_n', 'predicted_n'):
            if type(timings.get(name)) is not int or timings[name] < 0:
                raise _model_failure('invalid_transport_response')
        if (timings['predicted_n'] != counts[1] or timings['prompt_n'] > counts[0]
                or counts[0] > self.config.context_tokens or counts[1] > self.config.max_output_tokens):
            raise _model_failure('invalid_transport_response')
        for name in ('prompt_ms', 'predicted_ms'):
            value = timings.get(name)
            if (type(value) not in (int, float)
                    or not 0 <= value <= self.config.timeout_seconds * 1000):
                raise _model_failure('invalid_transport_response')
        slot = native.get('id_slot')
        if type(slot) is not int or not 0 <= slot < 4:
            raise _model_failure('invalid_transport_response')
        self._native_metrics = {'native_id_slot': slot, 'native_stop_type': native['stop_type'],
            'native_prompt_processed_count': timings['prompt_n'],
            'native_prompt_eval_duration_ns': round(timings['prompt_ms'] * 1000000),
            'native_eval_duration_ns': round(timings['predicted_ms'] * 1000000),
            'total_duration_basis': 'completion_http_wall_time',
            'prompt_eval_count_basis': 'native_tokens_evaluated_full_prompt_including_cache'}
        return {'model': self.config.model_id, 'response': native['content'], 'done': True,
                'done_reason': 'length' if native['truncated'] or native['stop_type'] == 'limit' else 'stop',
                'prompt_eval_count': counts[0], 'eval_count': counts[1],
                'total_duration': round((self._clock() - started) * 1000000000)}

    def generate(self, prompt, schema):
        result = super().generate(prompt, schema)
        result['metadata'].update({'adapter': 'llama.cpp', 'transport_api': '/completion',
            'prompt_template': 'ollama-v0.34.0-qwen35-single-user-think-false',
            'native_generation_settings': self._native_settings(), **self._native_metrics})
        return result


class ResidentPlanner:
    def __init__(self, model_store: Path | None = None):
        self.model_store = model_store

    def _client(self):
        with StructuredModelClient.from_env() as configured:
            config = configured.adapter.config
        engine = os.environ.get('LGAX_SHARED_MODEL_ENGINE', 'ollama')
        if engine == 'ollama':
            return StructuredModelClient(ResidentOllamaAdapter(config))
        if engine != 'llama.cpp' or self.model_store is None:
            raise DomainError('INVALID_ARGUMENT', '공유 모델 엔진 설정을 확인해 주세요.')
        return StructuredModelClient(ResidentLlamaAdapter(config, self.model_store))

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
                    if (self.queue.path.parent / 'draining').exists():
                        raise DomainError('PROTOTYPE_UPDATING', '서버 업데이트 중입니다. 잠시 후 다시 요청해 주세요.')
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
    workspace = ResearchWorkspace(state / 'research.sqlite3', research_bundle_paths(root),
                                  ResidentPlanner(Path(config['model_store'])))
    backend = create_workspace_app(state / 'workspace.sqlite3', registry, research_workspace=workspace)
    app = SharedGateway(backend, registry, root / 'apps/web/dist', config['public_origin'], config['release'],
                        queue_path=state / 'queue.sqlite3')
    uvicorn.run(app, host='127.0.0.1', port=18980, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
