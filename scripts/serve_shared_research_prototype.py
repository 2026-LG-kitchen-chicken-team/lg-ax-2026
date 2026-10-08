"""Explicit team prototype serving, independent of an AI/SSH session lifetime."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import secrets
import sys
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


class SharedGateway:
    def __init__(self, backend, registry, static_root: Path, origin: str, release: str):
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path not in {'', '/'}:
            raise ValueError('An exact HTTPS public origin is required')
        self.origin = origin.rstrip('/')
        self.host = parsed.netloc
        self.backend, self.registry, self.release = backend, registry, release
        self.static = StaticFiles(directory=static_root, html=True)
        self.model_lock = asyncio.Lock()

    async def _reply(self, scope, receive, send, code, message, status):
        await JSONResponse({'ok': False, 'error': {'code': code, 'message': message}},
            status_code=status, headers={'Cache-Control': 'no-store'})(scope, receive, send)

    async def __call__(self, scope, receive, send):
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
                'scheduled_shutdown': False}, headers={'Cache-Control': 'no-store'})(scope, receive, send)
        if path.startswith('/api/research/'):
            if method not in {'GET', 'POST'}:
                return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '지원하지 않는 요청입니다.', 405)
            length = headers.get('content-length', '0')
            if not length.isdecimal() or int(length) > 65536:
                return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '입력 크기를 확인해 주세요.', 413)
            backend_receive = receive
            if method == 'POST':
                body = bytearray()
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    body.extend(message.get('body', b''))
                    if len(body) > 65536:
                        return await self._reply(scope, receive, send, 'INVALID_ARGUMENT', '입력 크기를 확인해 주세요.', 413)
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
                if self.model_lock.locked():
                    return await self._reply(scope, receive, send, 'MODEL_BUSY',
                        '다른 기획을 처리 중입니다. 잠시 뒤 다시 실행해 주세요.', 503)
                async with self.model_lock:
                    return await self.backend(normalized, backend_receive, send)
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
    app = SharedGateway(backend, registry, root / 'apps/web/dist', config['public_origin'], config['release'])
    uvicorn.run(app, host='127.0.0.1', port=18980, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
