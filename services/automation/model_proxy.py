"""Loopback-only adapter: credentials stay outside the model worktree."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def serve(config, port=18873):
    base = config["controller_url"].rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("remote model gateway requires direct HTTPS")
    token = Path(config["token_file"]).read_text(encoding="utf-8").strip()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def dispatch(self):
            if self.path not in {"/api/tags", "/api/generate"} or (self.command, self.path) not in {
                    ("GET", "/api/tags"), ("POST", "/api/generate")}:
                self.send_error(404)
                return
            size = self.headers.get("Content-Length", "0")
            if not size.isdecimal() or int(size) > 65536:
                self.send_error(413)
                return
            payload = self.rfile.read(int(size)) if self.command == "POST" else None
            try:
                response = httpx.request(self.command, base + "/v1/model" + self.path, content=payload,
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                                         timeout=190, trust_env=False, follow_redirects=False)
                if 300 <= response.status_code < 400:
                    raise ValueError("redirect forbidden")
                raw = response.content
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError("response too large")
                self.send_response(response.status_code)
            except (httpx.HTTPError, ValueError):
                raw = b'{"error":"shared model connection failed"}'
                self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_GET = dispatch
        do_POST = dispatch

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--port", type=int, default=18873)
    args = parser.parse_args()
    serve(json.loads(Path(args.config).read_text(encoding="utf-8")), args.port)


if __name__ == "__main__":
    main()
