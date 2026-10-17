"""Authenticated loopback GET bridge. No automation operations are exposed."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .harness_reader import HarnessReadError, HarnessReader


class HarnessHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, reader, token, allowed_origins=()):
        if address[0] not in ("127.0.0.1", "::1"):
            raise ValueError("읽기 서버는 loopback 주소에서만 실행할 수 있습니다.")
        if not isinstance(token, str) or not 32 <= len(token) <= 256 or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("환경 변수에 32~256자의 안전한 조회 전용 토큰을 설정하세요.")
        self.reader = reader
        self._token = token
        self.allowed_origins = set()
        for origin in allowed_origins:
            parsed = urllib.parse.urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise ValueError("허용 Origin 설정 형식이 맞지 않습니다.")
            self.allowed_origins.add(origin)
        super().__init__(address, HarnessHandler)


class HarnessHandler(BaseHTTPRequestHandler):
    server: HarnessHTTPServer

    def log_message(self, *_args):
        pass  # Never log tokens, paths, queries, or source content.

    def allowed_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True  # Native clients still require the Bearer token.
        if origin in self.server.allowed_origins:
            return True
        try:
            parsed = urllib.parse.urlsplit(origin)
        except ValueError:
            return False
        return (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
                and not parsed.username and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment)

    def authenticated(self):
        authorization = self.headers.get("Authorization", "")
        value = authorization[7:] if authorization.startswith("Bearer ") else ""
        return hmac.compare_digest(value.encode("utf-8"), self.server._token.encode("utf-8"))

    def reply(self, status, value=None, *, preflight=False):
        raw = b"" if value is None else json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Allow", "GET, OPTIONS")
        if self.headers.get("Origin") and self.allowed_origin():
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Vary", "Origin")
            if preflight:
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization")
                if self.headers.get("Access-Control-Request-Private-Network") == "true":
                    self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def do_OPTIONS(self):
        if not self.allowed_origin():
            return self.reply(403, {"code": "origin_denied", "error": "허용되지 않은 브라우저 출처입니다."})
        if self.headers.get("Access-Control-Request-Method", "GET") != "GET":
            return self.reply(405, {"code": "read_only", "error": "읽기 전용 GET 요청만 허용합니다."})
        headers = self.headers.get("Access-Control-Request-Headers", "")
        if any(h.strip().lower() not in ("authorization",) for h in headers.split(",") if h.strip()):
            return self.reply(403, {"code": "headers_denied", "error": "허용되지 않은 요청 헤더입니다."})
        return self.reply(204, preflight=True)

    def do_GET(self):
        try:
            if not self.allowed_origin():
                return self.reply(403, {"code": "origin_denied", "error": "허용되지 않은 브라우저 출처입니다."})
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.query or parsed.fragment:
                return self.reply(400, {"code": "invalid_request", "error": "조회 경로에 추가 입력을 전달할 수 없습니다."})
            if parsed.path == "/health":
                return self.reply(200, {"service": "kitchen-ax-harness-reader", "ok": True})
            if parsed.path != "/api/harness/snapshot":
                return self.reply(404, {"code": "not_found", "error": "지원하지 않는 조회 경로입니다."})
            if not self.authenticated():
                return self.reply(401, {"code": "unauthorized", "error": "조회 전용 인증이 필요합니다."})
            return self.reply(200, self.server.reader.snapshot())
        except HarnessReadError as exc:
            return self.reply(503, {"code": exc.code, "error": str(exc)})
        except Exception:
            return self.reply(503, {"code": "unavailable", "error": "하네스 조회 연결을 확인할 수 없습니다."})

    def read_only(self):
        self.close_connection = True  # Do not parse or retain a mutation body.
        self.reply(405, {"code": "read_only", "error": "읽기 전용 GET 요청만 허용합니다."})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_TRACE = do_CONNECT = read_only


def main():
    parser = argparse.ArgumentParser(description="KITCHEN AX read-only harness bridge")
    parser.add_argument("--port", type=int, default=8033)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("포트는 1~65535 범위여야 합니다.")
    try:
        reader = HarnessReader.from_env()
        origins = tuple(x.strip().rstrip("/") for x in os.environ.get("AX_HARNESS_ALLOWED_ORIGINS", "").split(",") if x.strip())
        server = HarnessHTTPServer(("127.0.0.1", args.port), reader, os.environ.get("AX_HARNESS_VIEW_TOKEN", ""), origins)
    except (ValueError, HarnessReadError, OSError):
        parser.exit(2, "하네스 조회 설정을 확인하세요. DB 경로와 조회 전용 토큰은 출력하지 않습니다.\n")
    print(f"KITCHEN AX read-only bridge: http://127.0.0.1:{args.port}; actual DB connection is checked only on an authenticated GET.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
