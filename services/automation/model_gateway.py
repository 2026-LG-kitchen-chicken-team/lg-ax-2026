"""Authenticated, bounded access to the already running LG model; no GPU control."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import httpx
from fastapi import Depends
from fastapi.responses import JSONResponse

from services.automation.state import ControlError

MODEL = "qwen3:8b"
DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
UPSTREAM = "http://127.0.0.1:18864"


def checked_payload(body):
    if not isinstance(body, dict) or set(body) - {"model", "prompt", "stream", "think", "format", "options", "keep_alive"}:
        raise ControlError("only structured LG model generation is allowed", 422)
    if "keep_alive" in body and body["keep_alive"] != "5m":
        raise ControlError("only the existing five-minute model retention is allowed", 422)
    if body.get("model") != MODEL or body.get("stream") is not False or type(body.get("think")) is not bool:
        raise ControlError("pinned model, explicit thinking and non-streaming required", 422)
    if not isinstance(body.get("prompt"), str) or not 1 <= len(body["prompt"].encode()) <= 45000:
        raise ControlError("prompt exceeds the shared model limit", 422)
    if body.get("format") != "json" and not isinstance(body.get("format"), dict):
        raise ControlError("JSON or JSON Schema output required", 422)
    options = body.get("options")
    if not isinstance(options, dict) or set(options) != {"temperature", "seed", "num_ctx", "num_predict"}:
        raise ControlError("explicit reproducible generation options required", 422)
    if options["temperature"] != 0 or type(options["seed"]) is not int:
        raise ControlError("fixed deterministic generation settings required", 422)
    for name, maximum in (("num_ctx", 32768), ("num_predict", 8192)):
        if type(options[name]) is not int or not 1 <= options[name] <= maximum:
            raise ControlError(f"{name} exceeds shared limits", 422)
    return body


class Gateway:
    def __init__(self, config, transport=None):
        if config.get("upstream", UPSTREAM) != UPSTREAM or config.get("digest", DIGEST) != DIGEST:
            raise ValueError("the gateway cannot target another service or unverified model")
        self.config = config
        self.lock = threading.Lock()
        self.transport = transport

    def call(self, method, path, payload=None):
        try:
            with (httpx.Client(timeout=httpx.Timeout(180, connect=5), trust_env=False,
                               follow_redirects=False, transport=self.transport) as client,
                  client.stream(method, UPSTREAM + path, json=payload) as response):
                if response.status_code != 200:
                    raise ControlError("LG model service unavailable", 503)
                raw = bytearray()
                for part in response.iter_bytes():
                    raw.extend(part)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ControlError("model response exceeds limit", 502)
                return json.loads(raw)
        except (httpx.HTTPError, ValueError):
            raise ControlError("LG model request failed; no fabricated output returned", 503) from None

    def tags(self):
        value = self.call("GET", "/api/tags")
        models = [m for m in value.get("models", []) if m.get("name") == MODEL and m.get("digest") == DIGEST]
        if len(models) != 1:
            raise ControlError("pinned model digest is unavailable", 503)
        return {"models": models}

    def generate(self, account, body):
        checked_payload(body)
        if not self.lock.acquire(blocking=False):
            raise ControlError("LG shared model is busy; retry explicitly later", 429)
        started = time.monotonic()
        try:
            self.tags()
            value = self.call("POST", "/api/generate", body)
            self.tags()
            if value.get("model") != MODEL or value.get("done") is not True or not isinstance(value.get("response"), str):
                raise ControlError("model returned incomplete or mismatched output", 502)
            log = self.config.get("metadata_log")
            if log:
                path = Path(log)
                path.parent.mkdir(parents=True, exist_ok=True)
                record = {"account": str(account), "model": MODEL, "digest": DIGEST,
                          "prompt_sha256": hashlib.sha256(body["prompt"].encode()).hexdigest(),
                          "elapsed_seconds": round(time.monotonic() - started, 3),
                          "prompt_eval_count": value.get("prompt_eval_count"), "eval_count": value.get("eval_count"),
                          "options": body["options"], "think": body["think"]}
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            return value
        finally:
            self.lock.release()


def install_gateway(app, config, authenticate):
    gateway = Gateway(config)
    app.state.model_gateway = gateway
    authenticated = Depends(authenticate)

    @app.get("/v1/model/api/tags")
    def tags(account=authenticated):
        return gateway.tags()

    @app.post("/v1/model/api/generate")
    def generate(body: dict, account=authenticated):
        if config.get("enabled") is not True:
            return JSONResponse(status_code=503, content={"error": "shared model access disabled"})
        return gateway.generate(account, body)
