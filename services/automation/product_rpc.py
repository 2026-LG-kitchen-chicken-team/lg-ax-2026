"""Fixed product-model file RPC; guests receive no network or credentials.

Only the deployed host relay calls the existing loopback model proxy. Guest
files are inert bounded requests, never commands or admission/approval proofs.
Every generation is durably reserved before dispatch; ambiguous cost is held.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import stat
import time
from collections.abc import Callable
from pathlib import Path

import httpx

MAX_REQUESTS = 40
MODEL = "qwen3:8b"
DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
MAX_REQUEST = 65536
MAX_RESPONSE = 2 * 1024 * 1024
IDENTITY = re.compile(r"product-[0-9a-f]{40}")


class RPCError(ValueError):
    """Sanitized fixed protocol failure; never disclose response/auth contents."""


class RPCReadUnstable(RPCError):
    """Only an ordinary bounded mailbox's atomic file identity changed."""


def encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RPCError("duplicate protocol field")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise RPCError("invalid bounded protocol JSON") from None
    return value


def plain_parents(path: Path) -> None:
    if not path.is_absolute():
        raise RPCError("absolute fixed protocol path required")
    for parent in path.parents:
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & 0x400):
            raise RPCError("linked protocol parent refused")


def read_file(path: Path, maximum: int) -> bytes:
    # Exact fixed filename only, with no links/reparse/hard-link dereference.
    plain_parents(path)
    info = path.lstat()
    def ordinary(row, links=(1,)):
        if (not stat.S_ISREG(row.st_mode) or row.st_nlink not in links or row.st_size > maximum or
                getattr(row, "st_file_attributes", 0) & 0x400):
            raise RPCError("protocol file is not bounded ordinary bytes")
    ordinary(info)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) |
                         getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        ordinary(opened)
        if (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev):
            raise RPCReadUnstable("atomic mailbox identity changed while opening")
        if (opened.st_ino, opened.st_dev, opened.st_nlink, opened.st_size, opened.st_mtime_ns) != (
                info.st_ino, info.st_dev, 1, info.st_size, info.st_mtime_ns):
            raise RPCError("protocol file replaced while opening")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    # Linux may unlink the old, previously single-link inode during rename.
    # Those bytes are discarded only if the current mailbox is a different
    # ordinary single-link inode. Added hard links are never transient.
    ordinary(after, links=(0, 1))
    ordinary(final)
    if len(raw) > maximum or (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns) != (
            info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns):
        raise RPCError("protocol bytes changed or exceeded limit")
    if (final.st_ino, final.st_dev) != (info.st_ino, info.st_dev):
        raise RPCReadUnstable("atomic mailbox identity changed after reading")
    if after.st_nlink != 1:
        raise RPCError("protocol file link identity changed")
    if (final.st_size, final.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
        raise RPCError("protocol bytes changed or exceeded limit")
    return raw


def write_file(path: Path, value, *, enabled=None) -> None:
    # A fixed temp name permits atomic Windows/Linux exchange. Never follow an
    # existing target/temp link placed by the guest.
    plain_parents(path)
    if path.exists() or path.is_symlink():
        read_file(path, MAX_RESPONSE * 4)
    temporary = path.with_suffix(".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise RPCError("unexpected protocol temporary file")
    raw = encode(value)
    with temporary.open("xb") as stream:
        stream.write(raw)
    started = time.monotonic()
    while True:
        if enabled is not None and not enabled():
            raise RPCError("OFF prevented atomic product response delivery")
        try:
            temporary.replace(path)
            return
        except PermissionError as exc:
            # Windows readers may briefly deny delete-sharing while the guest
            # reads the prior response. Retry only the exchange, never dispatch.
            # Recheck exact temp bytes and link boundaries on every retry.
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32} or time.monotonic() - started >= 1:
                raise
            if read_file(temporary, len(raw)) != raw:
                raise RPCError("atomic protocol temporary bytes changed") from None
            plain_parents(path)
            if path.exists() or path.is_symlink():
                read_file(path, MAX_RESPONSE * 4)
            time.sleep(0.01)


def mailbox_paths(artifacts: Path, kind: str, sequence: int) -> tuple[Path, Path]:
    """Only forty fixed identities in each direction, never arbitrary paths."""
    if kind not in {"request", "response"}:
        raise RPCError("mailbox direction outside fixed allowlist")
    if type(sequence) is not int or not 1 <= sequence <= MAX_REQUESTS:
        raise RPCError("sequence exceeds fixed mailbox bound")
    return (artifacts / f"product-{kind}-{sequence:02d}.json",
            artifacts / f"product-{kind}-{sequence:02d}.ready")


def response_paths(artifacts: Path, sequence: int) -> tuple[Path, Path]:
    return mailbox_paths(artifacts, "response", sequence)


def request_paths(artifacts: Path, sequence: int) -> tuple[Path, Path]:
    return mailbox_paths(artifacts, "request", sequence)


def write_mailbox(artifacts: Path, kind: str, sequence: int, value, *, enabled) -> None:
    """Publish complete immutable bytes, then a zero-byte readiness marker.

    Link publication is atomic and refuses any existing target on Windows and
    POSIX. The guest does not open the response until the temporary hard link
    has been removed and the ordinary single-link bytes have been rechecked.
    There is no response replacement, delivery retry, or upstream replay.
    """
    path, ready = mailbox_paths(artifacts, kind, sequence)
    temporary = path.with_suffix(".tmp")
    for target in (path, ready, temporary):
        plain_parents(target)
        if target.exists() or target.is_symlink():
            raise RPCError("immutable mailbox identity already exists")
    raw = encode(value)
    maximum = MAX_REQUEST if kind == "request" else MAX_RESPONSE * 2
    if len(raw) > maximum:
        raise RPCError("immutable mailbox exceeded fixed bound")
    if not enabled():
        raise RPCError("OFF prevented immutable mailbox preparation")
    with temporary.open("xb") as stream:
        stream.write(raw)
    if read_file(temporary, maximum) != raw:
        raise RPCError("immutable mailbox temporary bytes changed")
    if not enabled():
        raise RPCError("OFF prevented immutable mailbox publication")
    # os.link never replaces an existing file, including a planted symlink.
    os.link(temporary, path, follow_symlinks=False)
    temporary.unlink()
    if read_file(path, maximum) != raw:
        raise RPCError("immutable mailbox published bytes changed")
    plain_parents(ready)
    if not enabled():
        raise RPCError("OFF prevented immutable mailbox readiness")
    with ready.open("xb"):
        pass


def write_response(artifacts: Path, sequence: int, value, *, enabled) -> None:
    write_mailbox(artifacts, "response", sequence, value, enabled=enabled)


def write_request(artifacts: Path, sequence: int, value) -> None:
    write_mailbox(artifacts, "request", sequence, value, enabled=lambda: True)


def positive(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise RPCError("invalid fixed execution bound")
    return value


def checked_settings(settings):
    if (not isinstance(settings, dict) or set(settings) != {"temperature", "seed", "num_ctx", "num_predict"} or
            settings["temperature"] != 0 or type(settings["temperature"]) not in {int, float} or
            settings["seed"] != 42 or type(settings["seed"]) is not int):
        raise RPCError("fixed generation settings required")
    positive(settings["num_ctx"], 32768)
    positive(settings["num_predict"], min(8192, settings["num_ctx"] - 512))
    return dict(settings)


def checked_request(value, run_id, sequence, settings):
    required = {"schema_version", "run_id", "sequence", "method", "path", "body", "request_sha256"}
    if (not isinstance(value, dict) or set(value) != required or value["schema_version"] != 1 or
            value["run_id"] != run_id or type(value["sequence"]) is not int or value["sequence"] != sequence):
        raise RPCError("request identity/order mismatch")
    original = {key: value[key] for key in required - {"request_sha256"}}
    if sha(encode(original)) != value["request_sha256"]:
        raise RPCError("request digest mismatch")
    route = (value["method"], value["path"])
    if route == ("GET", "/api/tags"):
        if value["body"] is not None:
            raise RPCError("tags payload refused")
        return False
    if route != ("POST", "/api/generate"):
        raise RPCError("model route outside fixed whitelist")
    body = value["body"]
    if (not isinstance(body, dict) or set(body) != {"model", "prompt", "format", "stream", "think", "options", "keep_alive"}
            or body["model"] != MODEL or body["stream"] is not False or body["think"] is not False or
            body["keep_alive"] != "5m" or body["options"] != settings or
            not isinstance(body["prompt"], str) or not 1 <= len(body["prompt"].encode()) <= 45000 or
            not isinstance(body["format"], dict) or len(encode(body["format"])) > 16384):
        raise RPCError("generation differs from fixed bounded model contract")
    pending = [body["format"]]
    inspected = 0
    while pending:
        node = pending.pop()
        inspected += 1
        if inspected > 4000:
            raise RPCError("schema complexity exceeds bound")
        if isinstance(node, dict):
            if any(key in node and (not isinstance(node[key], str) or not node[key].startswith("#"))
                   for key in ("$ref", "$dynamicRef", "$recursiveRef")):
                raise RPCError("external schema reference refused")
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return True


class ProxyEndpoint:
    """Existing host proxy only; credential ownership remains in that service."""
    def __init__(self, *, transport=None):
        self.transport = transport

    def __call__(self, method, path, body):
        if (method, path) not in {("GET", "/api/tags"), ("POST", "/api/generate")}:
            raise RPCError("upstream route refused")
        with (httpx.Client(transport=self.transport, trust_env=False, follow_redirects=False,
                          timeout=httpx.Timeout(190, connect=5)) as client,
              client.stream(method, "http://127.0.0.1:18873" + path, json=body) as response):
            if response.status_code != 200:
                raise RPCError("product model service unavailable")
            raw = bytearray()
            for part in response.iter_bytes():
                raw.extend(part)
                if len(raw) > MAX_RESPONSE:
                    raise RPCError("upstream response exceeded bound")
        return bytes(raw)


class FileRelay:
    """Trusted host dispatcher, with durable reservation and no replay."""
    def __init__(self, artifacts: Path, journal: Path, run_id: str, *, settings: dict,
                 max_generations: int, max_tokens: int, enabled: Callable[[], bool], upstream=None, origin=None,
                 allow_generation=True):
        if IDENTITY.fullmatch(run_id) is None:
            raise RPCError("fixed product run identity required")
        plain_parents(request_paths(artifacts, 1)[0])
        # Journal parents are created by the trusted caller, never from a guest
        # requested path. Check before resolve so links cannot be hidden.
        plain_parents(journal)
        self.artifacts, self.journal, self.run_id = artifacts, journal, run_id
        if self.journal.is_relative_to(self.artifacts) or self.artifacts.is_relative_to(self.journal.parent):
            raise RPCError("private relay journal must be outside guest mounts")
        self.settings = checked_settings(settings)
        self.max_generations, self.max_tokens = positive(max_generations, 12), positive(max_tokens, 1000000)
        self.enabled, self.upstream = enabled, upstream or ProxyEndpoint()
        if type(allow_generation) is not bool:
            raise RPCError("explicit trusted generation permission required")
        self.allow_generation = allow_generation
        self.origin = json.loads(encode(origin or {}))
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        self.state = decode(read_file(self.journal, 16 * 1024 * 1024)) if self.journal.exists() else {
            "schema_version": 1, "run_id": run_id, "settings": self.settings, "approved_origin": self.origin,
            "allow_generation": self.allow_generation,
            "max_generations": max_generations, "max_tokens": max_tokens, "generations": 0, "tokens": 0, "requests": []}
        if (self.state.get("run_id") != run_id or self.state.get("settings") != self.settings or
                self.state.get("max_generations") != max_generations or self.state.get("max_tokens") != max_tokens or
                self.state.get("approved_origin") != self.origin or self.state.get("allow_generation") != self.allow_generation):
            raise RPCError("relay journal identity/limits changed")
        self.failure = self.state.get("failure")
        if any(row.get("state") != "completed" and not (
                row.get("state") == "cancelled_before_dispatch" and row.get("dispatch_started") is False and
                row.get("usage_unknown") is False) for row in self.state["requests"]):
            self.failure = self.state["failure"] = "ambiguous_reserved_request"
            self.state["tokens"] = self.max_tokens
        self._save()

    def _save(self):
        write_file(self.journal, self.state)

    def step(self):
        if self.failure:
            raise RPCError("relay halted; explicit operator recovery required")
        if not self.enabled():
            raise RPCError("product execution is OFF")
        rows = self.state["requests"]
        if rows:
            prior, prior_ready = request_paths(self.artifacts, rows[-1]["sequence"])
            if not prior_ready.exists() or read_file(prior_ready, 0) != b"":
                raise RPCError("processed request readiness changed")
            previous = decode(read_file(prior, MAX_REQUEST))
            if previous.get("request_sha256") != rows[-1]["request_sha256"] or previous != rows[-1]["request"]:
                raise RPCError("processed request mutated")
            if rows[-1]["state"] != "completed":
                raise RPCError("ambiguous reserved request cannot be replayed")
        if len(rows) >= MAX_REQUESTS:
            return False
        sequence = len(rows) + 1
        request_path, ready = request_paths(self.artifacts, sequence)
        if not ready.exists() and not ready.is_symlink():
            return False
        if read_file(ready, 0) != b"":
            raise RPCError("immutable request readiness marker changed")
        value = decode(read_file(request_path, MAX_REQUEST))
        generation = checked_request(value, self.run_id, len(rows) + 1, self.settings)
        if generation and not self.allow_generation:
            raise RPCError("zero-model guard cannot request a generation")
        if len(rows) >= MAX_REQUESTS or (generation and (self.state["generations"] >= self.max_generations or
                                              self.state["tokens"] >= self.max_tokens)):
            raise RPCError("product request/generation/token bound exhausted")
        row = {"sequence": sequence, "request_sha256": value["request_sha256"], "request": value,
               "state": "reserved", "generation": generation, "dispatch_started": False}
        rows.append(row)
        if generation:
            self.state["generations"] += 1
        self._save()  # A crash after here never causes a second upstream call.
        started = time.monotonic()
        try:
            if not self.enabled():
                row.update(state="cancelled_before_dispatch", usage_unknown=False)
                self._save()
                raise RPCError("OFF cancelled reservation before any upstream call")
            row["dispatch_started"] = True
            self._save()
            # Saving the dispatch intent itself may span a mode change.
            if not self.enabled():
                row.update(state="cancelled_before_dispatch", dispatch_started=False, usage_unknown=False)
                self._save()
                raise RPCError("OFF cancelled dispatch before any upstream call")
            raw = self.upstream(value["method"], value["path"], value["body"])
            if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE:
                raise RPCError("actual upstream bytes missing/bounded")
            row.update(response_sha256=sha(raw), response_base64=base64.b64encode(raw).decode())
            self._save()  # Invalid completions are actual failure evidence too.
            result = decode(raw)
            if generation:
                if (result.get("model") != MODEL or result.get("done") is not True or not isinstance(result.get("response"), str)
                        or any(type(result.get(key)) is not int or result[key] < 0 for key in ("prompt_eval_count", "eval_count"))):
                    raise RPCError("actual model completion/token usage missing")
                row["usage"] = {key: result[key] for key in ("prompt_eval_count", "eval_count")}
                self.state["tokens"] += sum(row["usage"].values())
            else:
                selected = [entry for entry in result.get("models", []) if entry.get("name") == MODEL]
                if len(selected) != 1 or selected[0].get("digest") != DIGEST:
                    raise RPCError("actual fixed model digest unavailable")
            row.update(state="completed", response_sha256=sha(raw), response_base64=base64.b64encode(raw).decode(),
                       elapsed_seconds=round(time.monotonic() - started, 6))
            self._save()
            if not self.enabled() or self.state["tokens"] > self.max_tokens:
                raise RPCError("OFF or actual product token bound exceeded")
            write_response(self.artifacts, sequence, {"schema_version": 1, "run_id": self.run_id,
                "sequence": sequence, "request_sha256": value["request_sha256"], "response_sha256": sha(raw),
                "response_base64": row["response_base64"]}, enabled=self.enabled)
        except Exception as exc:  # noqa: BLE001 - retain an ambiguous cost, disclose no endpoint/private response.
            self.failure = type(exc).__name__
            self.state["failure"] = self.failure
            if generation and "usage" not in row and row["dispatch_started"]:
                self.state["tokens"] = self.max_tokens
                row["usage_unknown"] = True
            self._save()
            raise RPCError("actual product relay failed; no replay or fabricated completion") from None
        return True


class FileTransport(httpx.BaseTransport):
    """Guest transport backed by real host dispatch, never a mock response."""
    def __init__(self, artifacts: Path, run_id: str, *, timeout_seconds=195, poll_seconds=0.05):
        if (IDENTITY.fullmatch(run_id) is None or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300 or
                not math.isfinite(poll_seconds) or not 0 < poll_seconds <= 1):
            raise RPCError("bounded guest transport settings required")
        self.artifacts, self.run_id, self.sequence = artifacts, run_id, 0
        self.timeout_seconds, self.poll_seconds = timeout_seconds, poll_seconds

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (request.url.scheme != "http" or request.url.host != "127.0.0.1" or request.url.port != 18873 or request.url.query or
                request.url.username or request.url.password or request.url.fragment):
            raise httpx.TransportError("only the fixed virtual loopback product endpoint is allowed")
        if self.sequence >= MAX_REQUESTS:
            raise httpx.TransportError("fixed product request count exhausted")
        self.sequence += 1
        raw = request.read()
        body = decode(raw) if raw else None
        value = {"schema_version": 1, "run_id": self.run_id, "sequence": self.sequence,
                 "method": request.method, "path": request.url.path, "body": body}
        value["request_sha256"] = sha(encode(value))
        if len(encode(value)) > MAX_REQUEST:
            raise httpx.TransportError("bounded product request exceeded")
        write_request(self.artifacts, self.sequence, value)
        started = time.monotonic()
        while time.monotonic() - started < self.timeout_seconds:
            path, ready = response_paths(self.artifacts, self.sequence)
            if ready.exists() or ready.is_symlink():
                if read_file(ready, 0) != b"":
                    raise RPCError("immutable mailbox readiness marker changed")
                response = decode(read_file(path, MAX_RESPONSE * 2))
                if response.get("sequence") != self.sequence:
                    raise httpx.TransportError("immutable response sequence changed")
                if response.get("sequence") == self.sequence:
                    if (set(response) != {"schema_version", "run_id", "sequence", "request_sha256", "response_sha256", "response_base64"}
                            or type(response.get("schema_version")) is not int or response.get("schema_version") != 1
                            or type(response.get("sequence")) is not int or response.get("run_id") != self.run_id or
                            response.get("request_sha256") != value["request_sha256"]):
                        raise httpx.TransportError("product response identity changed")
                    try:
                        data = base64.b64decode(response["response_base64"], validate=True)
                    except (ValueError, TypeError):
                        raise httpx.TransportError("invalid actual response bytes") from None
                    if len(data) > MAX_RESPONSE or sha(data) != response["response_sha256"]:
                        raise httpx.TransportError("product response bytes changed")
                    # The application adapter uses client.stream()/iter_raw().
                    # ``content=`` eagerly consumes a bytes response and makes
                    # iter_raw fail with StreamConsumed on the first pin read.
                    return httpx.Response(200, stream=httpx.ByteStream(data), request=request,
                        headers={"content-length": str(len(data)), "content-type": "application/json"})
            time.sleep(self.poll_seconds)
        raise httpx.ReadTimeout("bounded actual product relay timeout", request=request)
