"""Deterministic Gmail transport through the installed Codex CLI app server.

No model turn, shell tool, copied OAuth credential, or repository code runs in
the connector process. The fixed mail broker owns the permitted operations.
"""
from __future__ import annotations

import base64
import json
import queue
import re
import subprocess
import threading
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

GMAIL_APP = "connector_2128aebfecb84f64a069897515042a44"
TOOLS = frozenset({"gmail.get_profile", "gmail.send_email", "gmail.read_email",
                   "gmail.search_email_ids", "gmail.read_email_thread"})


class ConnectorError(RuntimeError):
    pass


def _unwrap(value):
    if value.get("isError"):
        raise ConnectorError("Gmail connector refused the fixed operation")
    result = value.get("structuredContent")
    if not isinstance(result, dict):
        texts = [row["text"] for row in value.get("content", []) if row.get("type") == "text"]
        if len(texts) != 1:
            raise ConnectorError("Gmail response requires structured metadata")
        result = json.loads(texts[0])
    return result


def _message(row):
    """Only normalize the documented connector's snake_case Gmail aliases."""
    aliases = {"thread_id": "threadId", "label_ids": "labelIds", "internal_date": "internalDate",
               "history_id": "historyId", "mime_type": "mimeType", "base64_url_content": "data"}
    if isinstance(row, dict):
        return {aliases.get(key, key): _message(value) for key, value in row.items()}
    if isinstance(row, list):
        return [_message(value) for value in row]
    return row


class CodexGmailTransport:
    supports_custom_message_id = False

    def __init__(self, *, executable, workspace, timeout_seconds=90):
        from services.automation.isolation import _plain_directory, regular_file
        from services.automation.pm import protected_path

        self.executable = str(Path(executable).resolve(strict=True))
        regular_file(Path(self.executable), maximum=512 * 1024 * 1024)
        self.workspace = protected_path(Path(workspace)).resolve(strict=True)
        _plain_directory(self.workspace, "fixed connector workspace")
        if any(self.workspace.iterdir()):
            raise ConnectorError("Gmail connector workspace must be empty and outside checkouts")
        if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 120:
            raise ConnectorError("Bounded Gmail timeout required")
        self.timeout_seconds = timeout_seconds
        self._process = None
        self._counter = 0
        self._queue = queue.Queue()
        self._lock = threading.RLock()
        self._thread = None

    def _start(self):
        if self._process is not None:
            if self._process.poll() is not None:
                raise ConnectorError("Gmail app server stopped; current delivery may be unknown")
            return
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        self._process = subprocess.Popen([self.executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", cwd=self.workspace, creationflags=flags)
        def receive():
            for line in self._process.stdout:
                try:
                    self._queue.put(json.loads(line))
                except json.JSONDecodeError:
                    self._queue.put({"protocol_error": True})
        threading.Thread(target=receive, daemon=True).start()
        self._rpc("initialize", {"clientInfo": {"name": "lgax-fixed-mail-broker", "version": "1.0"}})
        self._write({"method": "initialized", "params": {}})
        config = {"features.shell_tool": False, "features.web_search": False,
                  "apps._default.enabled": False, f"apps.{GMAIL_APP}.enabled": True,
                  f"apps.{GMAIL_APP}.default_tools_enabled": False}
        for tool in TOOLS:
            config[f"apps.{GMAIL_APP}.tools.{tool.split('.', 1)[1]}.enabled"] = True
        start = self._rpc("thread/start", {"cwd": str(self.workspace), "sandbox": "read-only",
            "approvalPolicy": "never", "ephemeral": True, "config": config})
        self._thread = start["thread"]["id"]
        installed = self._rpc("app/installed", {"threadId": self._thread, "forceRefresh": True})
        if not any(row.get("id") == GMAIL_APP and row.get("enabled") and row.get("callable")
                   for row in installed.get("apps", [])):
            raise ConnectorError("Gmail is not callable under the fixed CLI mail policy")

    def _write(self, value):
        self._process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _rpc(self, method, params):
        self._counter += 1
        request_id = self._counter
        self._write({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                value = self._queue.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                if self._process.poll() is not None:
                    raise ConnectorError("Gmail app server exited before receipt")
                continue
            if value.get("protocol_error"):
                raise ConnectorError("Gmail app server protocol changed")
            if value.get("id") == request_id and "method" not in value:
                if "error" in value:
                    raise ConnectorError("Fixed Gmail RPC refused; inspect private operational state")
                return value["result"]
            if "id" in value and "method" in value:
                # Never silently approve an unexpected permission or login request.
                self._write({"id": value["id"], "error": {"code": -32601,
                    "message": "Fixed mail broker cannot approve interactive requests"}})
                raise ConnectorError("Gmail requires interactive authentication or approval")
        raise ConnectorError("Gmail operation timed out; reconcile before any repeat send")

    def _call(self, tool, arguments):
        if tool not in TOOLS:
            raise ConnectorError("Tool is outside the mail transport allowlist")
        with self._lock:
            self._start()
            return _unwrap(self._rpc("mcpServer/tool/call", {"threadId": self._thread,
                "server": "codex_apps", "tool": tool, "arguments": arguments}))

    def request(self, method, route, body=None, params=None):
        params = params or {}
        if method == "GET" and route == "profile":
            row = self._call("gmail.get_profile", {})
            return {"emailAddress": row.get("email", row.get("emailAddress"))}
        if method == "GET" and route == "messages":
            if set(params) - {"q", "maxResults", "pageToken"}:
                raise ConnectorError("Unexpected search parameters")
            row = self._call("gmail.search_email_ids", {"query": params.get("q", ""),
                "max_results": min(100, params.get("maxResults", 10)),
                "next_page_token": params.get("pageToken", "")})
            ids = row.get("ids", row.get("messages", row.get("message_ids", [])))
            if not isinstance(ids, list):
                raise ConnectorError("Gmail search metadata shape changed")
            messages = [{"id": item} if isinstance(item, str) else _message(item) for item in ids]
            return {"messages": messages, "nextPageToken": row.get("next_page_token", row.get("nextPageToken"))}
        match = re.fullmatch(r"messages/([0-9a-f]{10,100})", route)
        if method == "GET" and match:
            return _message(self._call("gmail.read_email", {"message_id": match[1],
                "format": params.get("format", "full")}))
        match = re.fullmatch(r"threads/([0-9a-f]{10,100})", route)
        if method == "GET" and match:
            return _message(self._call("gmail.read_email_thread", {"thread_id": match[1]}))
        if method == "POST" and route == "messages/send" and isinstance(body, dict) and set(body) == {"raw"}:
            raw = base64.urlsafe_b64decode(body["raw"] + "=" * (-len(body["raw"]) % 4))
            if len(raw) > 128 * 1024:
                raise ConnectorError("Fixed notification exceeded size bound")
            message = BytesParser(policy=policy.default).parsebytes(raw)
            if message.is_multipart() or message.get_content_type() != "text/plain" or message.get("Cc") or message.get("Bcc"):
                raise ConnectorError("Only a single plain-text assignment notification is allowed")
            headers = ["To", "From", "Subject"]
            if any(len(message.get_all(name, [])) != 1 for name in headers):
                raise ConnectorError("Notification requires one fixed recipient, sender, and subject")
            payload = {"to": str(message["To"]), "from_address": str(message["From"]),
                "subject": str(message["Subject"]), "payload": {"mime_type": "text/plain",
                    "body": {"content": message.get_content()}},
                "response_fields": ["id", "thread_id", "label_ids"]}
            return _message(self._call("gmail.send_email", payload))
        raise ConnectorError("Gmail route is outside the deterministic mail allowlist")

    def close(self):
        with self._lock:
            if self._process is not None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self._process = None
                self._thread = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
