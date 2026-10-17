"""Loopback-only JSON HTTP service, Python standard library only.

Run from the project folder: python -m backend.server --port 8032
"""
from __future__ import annotations

import argparse
import json
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import SKILLS, run_stage, validate_context
from .llm_adapter import AdapterError, JsonHttpLLMAdapter
from .repository import RunRepository

MAX_BODY = 4 * 1024 * 1024


class AppServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, address, database):
        super().__init__(address, Handler)
        self.repository = RunRepository(database)
        self.adapter = JsonHttpLLMAdapter()
        self.llm_lock = threading.Lock()
        self.allowed_origins = {origin.strip().rstrip("/") for origin in os.environ.get("AX_ALLOWED_ORIGINS", "").split(",") if origin.strip()}


class Handler(BaseHTTPRequestHandler):
    server: AppServer

    def log_message(self, fmt, *args):
        # Query strings and JSON body can contain user content; do not log either.
        pass

    def origin_allowed(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True  # CLI/native callers; browser callers send Origin.
        if origin in self.server.allowed_origins:
            return True
        parsed = urllib.parse.urlparse(origin)
        return parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "[::1]", "::1")

    def send_json(self, code, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin")
        if origin and self.origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(200 if self.origin_allowed() else 403, {"ok": self.origin_allowed()})

    def do_GET(self):
        if not self.origin_allowed():
            return self.send_json(403, {"error": "허용되지 않은 브라우저 출처입니다."})
        path = urllib.parse.urlparse(self.path).path
        if path in ("/health", "/api/health"):
            return self.send_json(200, {"ok": True, "mode": "local_rules", "executor": "python", "skills": SKILLS,
                                        "llm_configured": self.server.adapter.configured,
                                        "llm_connected": self.server.adapter.last_success,
                                        "llm_scope": "별도 명시 호출의 기획 계획만 지원; /api/stage는 로컬 규칙",
                                        "storage": "local_sqlite"})
        if path == "/api/runs":
            return self.send_json(200, {"runs": self.server.repository.list()})
        if path.startswith("/api/runs/"):
            rid = urllib.parse.unquote(path[len("/api/runs/"):])
            item = self.server.repository.get(rid)
            return self.send_json(200, {"id": rid, "snapshot": item}) if item is not None else self.send_json(404, {"error": "저장된 실행이 없습니다."})
        return self.send_json(404, {"error": "알 수 없는 API 경로입니다."})

    def read_body(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            raise ValueError("Content-Type은 application/json이어야 합니다.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length가 잘못되었습니다.") from exc
        if length <= 0 or length > MAX_BODY:
            raise ValueError("JSON 요청 크기는 1바이트 이상 4 MiB 이하여야 합니다.")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=lambda s: (_ for _ in ()).throw(ValueError("유한 숫자만 허용합니다.")))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("유효한 UTF-8 JSON 요청이어야 합니다.") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON 최상위 값은 객체여야 합니다.")
        return body

    def do_POST(self):
        if not self.origin_allowed():
            return self.send_json(403, {"error": "허용되지 않은 브라우저 출처입니다."})
        try:
            body = self.read_body()
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/stage":
                stage, context = body.get("stage"), body.get("context", {})
                result = run_stage(stage, context)
                skill = next(s["skill"] for s in SKILLS if s["id"] == stage)
                count_key = {"retrieve": "reviews", "structure": "needs", "compare": "comparisons", "concept": "concepts", "validate": "checks"}[stage]
                total = len(result.get(count_key, []))
                return self.send_json(200, {"stage": stage, "skill": skill, "mode": "local_rules", "executor": "python",
                                            "llm_connected": False, "result": result, "processed": total, "total": total})
            if path == "/api/llm/plan":
                context = body.get("context", {})
                validate_context(context)
                with self.server.llm_lock:
                    result = self.server.adapter.plan(context)
                return self.send_json(200, {"mode": "llm_plan", "llm_connected": True, "result": result,
                                            "notice": "LLM 기획 계획입니다. 다섯 단계의 실제 분석·외부 검색·서브 에이전트 실행을 의미하지 않습니다."})
            if path == "/api/runs":
                rid, snapshot = body.get("id"), body.get("snapshot")
                if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_\-.:]{1,100}", rid) or not isinstance(snapshot, dict):
                    raise ValueError("실행 id는 영문·숫자·밑줄·하이픈·점·콜론 1~100자, snapshot은 객체여야 합니다.")
                return self.send_json(200, self.server.repository.put(rid, snapshot))
            return self.send_json(404, {"error": "알 수 없는 API 경로입니다."})
        except AdapterError as exc:
            return self.send_json(502, {"error": str(exc), "llm_connected": False})
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            return self.send_json(400, {"error": "입력 또는 이전 단계 결과의 형식이 맞지 않습니다. JSON 계약과 원문 자료를 확인하세요."})
        except Exception:
            return self.send_json(500, {"error": "로컬 실행기에 오류가 발생했습니다. 원문 자료와 실행 환경을 확인하세요."})


def main():
    parser = argparse.ArgumentParser(description="KITCHEN AX Python local executor")
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parent / "data" / "runs.sqlite3")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    server = AppServer(("127.0.0.1", args.port), args.database)
    print(f"KITCHEN AX local_rules → http://127.0.0.1:{args.port}; LLM calls are opt-in.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
