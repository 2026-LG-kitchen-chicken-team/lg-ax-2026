"""Loopback GET bridge for an installed product folder, not the development queue."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import stat
import urllib.parse
from pathlib import Path, PurePosixPath

from .harness_server import HarnessHTTPServer, HarnessHandler
from .release_reader import ReleaseReadError, ReleaseReader


class ReleaseHTTPServer(HarnessHTTPServer):
    """Optional local UI; its bootstrap never reaches a public Site or disk."""
    def __init__(self, address, reader, token, allowed_origins=(), ui_dist=None):
        self.ui_dist = Path(ui_dist) if ui_dist else None
        if self.ui_dist is not None:
            if not self.ui_dist.is_absolute() or not self.ui_dist.is_dir() or self.ui_dist.is_symlink() or getattr(self.ui_dist.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("로컬 UI의 명시된 정적 폴더를 확인하세요.")
            self.ui_dist = self.ui_dist.resolve()
        super().__init__(address, reader, token, allowed_origins)
        self.RequestHandlerClass = ReleaseHandler


class ReleaseHandler(HarnessHandler):
    server: ReleaseHTTPServer

    def host_allowed(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def local_reply(self, status, raw=b"", content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        # No Access-Control-Allow-Origin on any local HTML/static response,
        # including error responses to a configured public Site Origin.
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def local_error(self, status, code):
        messages = {"origin_denied": "로컬 화면은 같은 출처에서만 읽을 수 있습니다.", "not_found": "지원하지 않는 정적 파일입니다.",
                    "invalid_request": "허용되지 않은 정적 파일 요청입니다.", "host_denied": "허용되지 않은 로컬 호스트입니다.",
                    "unavailable": "로컬 화면을 읽을 수 없습니다."}
        raw = json.dumps({"code": code, "error": messages[code]}, ensure_ascii=False).encode("utf-8")
        self.local_reply(status, raw)

    def static_origin_allowed(self):
        origin = self.headers.get("Origin")
        if origin is not None:
            return origin == "http://" + self.headers.get("Host", "")
        # Navigation can omit Origin; a cross-site script/image/frame must not
        # obtain the bootstrap. CORP and frame-ancestors add browser enforcement.
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.headers.get("Sec-Fetch-Mode") == "navigate" and self.headers.get("Sec-Fetch-Dest") == "document"
        return True

    def do_GET(self):
        if not self.host_allowed():
            return self.local_error(403, "host_denied")
        try:
            parsed = urllib.parse.urlsplit(self.path)
        except ValueError:
            return self.local_error(400, "invalid_request")
        if parsed.path == "/health" or parsed.path.startswith("/api/"):
            return super().do_GET()
        if self.server.ui_dist is None:
            return self.local_error(404, "not_found")
        if not self.static_origin_allowed():
            return self.local_error(403, "origin_denied")
        allowed_view = (parsed.path in ("/", "/index.html") and urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) in ([('view', 'harness')], [('view', 'team')]))
        if (parsed.query and not allowed_view) or parsed.fragment:
            return self.local_error(400, "invalid_request")
        try:
            decoded = urllib.parse.unquote(parsed.path, errors="strict")
            relative = "index.html" if decoded == "/" else decoded.removeprefix("/")
            parts = PurePosixPath(relative)
            if not relative or "\\" in relative or ":" in relative or "\x00" in relative or parts.is_absolute() or ".." in parts.parts or parts.as_posix() != relative:
                return self.local_error(400, "invalid_request")
            if relative != "index.html" and not relative.startswith("assets/") and relative not in ("favicon.svg", "favicon.ico"):
                return self.local_error(404, "not_found")
            path = self.server.ui_dist
            for component in parts.parts:
                path = path / component
                if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                    return self.local_error(400, "invalid_request")
            if not path.resolve().is_relative_to(self.server.ui_dist) or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024 or path.suffix == ".map":
                return self.local_error(404, "not_found")
            raw = path.read_bytes()
            if relative == "index.html":
                html = raw.decode("utf-8")
                payload = {"kind": "lgax_local_release_connection", "url": "http://" + self.headers["Host"], "token": self.server._token}
                encoded = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
                script = '<script type="application/json" id="ax-release-bootstrap">' + encoded + '</script>'
                html = html.replace("</head>", script + "</head>", 1) if "</head>" in html else script + html
                raw = html.encode("utf-8")
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix in (".html", ".css", ".js", ".mjs", ".svg"):
                content_type += "; charset=utf-8"
            return self.local_reply(200, raw, content_type)
        except (OSError, ValueError, UnicodeError):
            return self.local_error(503, "unavailable")

    def do_OPTIONS(self):
        if not self.host_allowed():
            return self.local_error(403, "host_denied")
        if self.path != "/api/harness/snapshot":
            return self.local_error(403, "origin_denied")
        return super().do_OPTIONS()


def main():
    parser = argparse.ArgumentParser(description="KITCHEN AX installed product observer reader")
    parser.add_argument("--port", type=int, default=8033)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("포트는 1~65535 범위여야 합니다.")
    try:
        reader = ReleaseReader.from_env()
        # Require an intact installed product (its own install record) before accepting connections.
        # No observation/session artifacts are read or created by this check.
        reader._verify()
        origins = tuple(o.strip().rstrip("/") for o in os.environ.get("AX_HARNESS_ALLOWED_ORIGINS", "").split(",") if o.strip())
        server = ReleaseHTTPServer(("127.0.0.1", args.port), reader, os.environ.get("AX_HARNESS_VIEW_TOKEN", ""), origins,
                                   os.environ.get("AX_RELEASE_UI_DIST") or None)
    except (ValueError, OSError, ReleaseReadError):
        parser.exit(2, "제품 배포본·조회 연결 설정을 확인하세요. 개인 경로와 토큰은 출력하지 않습니다.\n")
    print(f"KITCHEN AX release observer reader: http://127.0.0.1:{args.port}; GET only, no AI or observer process is started.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
