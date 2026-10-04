"""Pinned, private structured generation. This module contains no planning Agent."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable

from .errors import DomainError

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*\Z", re.DOTALL | re.IGNORECASE)
_SCHEMA_BYTES_LIMIT = 16384


def _fail(code: str, reason: str, **details: Any) -> DomainError:
    messages = {
        "INVALID_ARGUMENT": "모델 호출 설정·입력·스키마가 유효하지 않습니다.",
        "MODEL_UNAVAILABLE": "고정한 모델의 안전한 호출·revision 확인을 완료하지 못했습니다.",
        "VALIDATION_FAILED": "모델 출력이 JSON 형식 또는 요청한 스키마를 충족하지 않습니다.",
    }
    return DomainError(code, messages[code], {"reason": reason, **details})


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def _strict_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant, parse_float=_finite_float)


def _no_remote_schema(uri: str) -> Any:
    raise NoSuchResource(ref=uri)


def _schema_validator(schema: dict[str, Any]) -> tuple[Draft202012Validator, str, str]:
    if not isinstance(schema, dict):
        raise _fail("INVALID_ARGUMENT", "invalid_schema")
    try:
        encoded = json.dumps(schema, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > _SCHEMA_BYTES_LIMIT:
            raise _fail("INVALID_ARGUMENT", "schema_too_large")
        pending: list[Any] = [schema]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                for name in ("$ref", "$dynamicRef", "$recursiveRef"):
                    reference = node.get(name)
                    if reference is not None and (not isinstance(reference, str) or not reference.startswith("#")):
                        raise _fail("INVALID_ARGUMENT", "external_schema_reference")
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        Draft202012Validator.check_schema(schema)
    except DomainError:
        raise
    except (SchemaError, ValueError, TypeError, RecursionError, UnicodeError):
        raise _fail("INVALID_ARGUMENT", "invalid_schema") from None
    validator = Draft202012Validator(schema, format_checker=FormatChecker(), registry=Registry(retrieve=_no_remote_schema))
    return validator, encoded, sha256(encoded.encode()).hexdigest()


def _model_json(response: str, validator: Draft202012Validator) -> tuple[Any, str]:
    text = response.strip()
    response_format = "plain_json"
    if text.startswith("```"):
        matched = _FENCE.fullmatch(text)
        if not matched:
            raise _fail("VALIDATION_FAILED", "invalid_json_fence")
        text, response_format = matched.group(1), "whole_json_fence"
    try:
        data = _strict_json(text)
    except (ValueError, TypeError, RecursionError):
        raise _fail("VALIDATION_FAILED", "invalid_json") from None
    try:
        error = next(validator.iter_errors(data), None)
    except (Unresolvable, ValueError, TypeError, RecursionError):
        # Unresolvable local references and user-defined invalid schema formats must
        # never reveal schema contents or trigger a recovery/model retry here.
        raise _fail("INVALID_ARGUMENT", "unresolvable_schema") from None
    if error is not None:
        raise _fail("VALIDATION_FAILED", "schema_mismatch")
    return data, response_format


@dataclass(frozen=True, slots=True)
class ModelConfig:
    endpoint: str
    model_id: str
    expected_digest: str
    timeout_seconds: float = 120.0
    max_response_bytes: int = 131072
    max_output_tokens: int = 256
    context_tokens: int = 4096
    thinking: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.thinking, bool):
            raise _fail("INVALID_ARGUMENT", "invalid_thinking_setting")
        try:
            parsed = urlsplit(self.endpoint)
            address = ipaddress.ip_address(parsed.hostname or "")
            valid = (
                parsed.scheme in {"http", "https"}
                and address.is_loopback
                and parsed.port is not None and parsed.port > 0
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
                and not any(char.isspace() for char in self.endpoint)
            )
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise _fail("INVALID_ARGUMENT", "unsafe_endpoint")
        if not isinstance(self.model_id, str) or not self.model_id or len(self.model_id) > 128:
            raise _fail("INVALID_ARGUMENT", "invalid_model_id")
        if any(char.isspace() or ord(char) < 32 for char in self.model_id):
            raise _fail("INVALID_ARGUMENT", "invalid_model_id")
        if not isinstance(self.expected_digest, str) or not _DIGEST.fullmatch(self.expected_digest):
            raise _fail("INVALID_ARGUMENT", "missing_or_invalid_model_pin")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 300):
            raise _fail("INVALID_ARGUMENT", "invalid_timeout")
        if (isinstance(self.max_response_bytes, bool) or not isinstance(self.max_response_bytes, int)
                or not 1 <= self.max_response_bytes <= 1048576):
            raise _fail("INVALID_ARGUMENT", "invalid_response_limit")
        if (isinstance(self.context_tokens, bool) or not isinstance(self.context_tokens, int)
                or not 1024 <= self.context_tokens <= 32768
                or isinstance(self.max_output_tokens, bool) or not isinstance(self.max_output_tokens, int)
                or not 32 <= self.max_output_tokens <= 8192
                or self.max_output_tokens > self.context_tokens - 512):
            raise _fail("INVALID_ARGUMENT", "invalid_generation_budget")
        object.__setattr__(self, "endpoint", self.endpoint.rstrip("/"))


@dataclass(frozen=True, slots=True)
class StructuredModelResult:
    data: Any
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"data": self.data, "metadata": self.metadata}


class _ModelAdapter:
    adapter_name = ""
    backend_schema_enforced = False
    max_prompt_characters = 16000

    def __init__(self, config: ModelConfig, *, transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.config, self._clock = config, clock
        self._client = httpx.Client(
            transport=transport, trust_env=False, follow_redirects=False,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, deadline: float, body: dict[str, Any] | None = None) -> dict[str, Any]:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise _fail("MODEL_UNAVAILABLE", "timeout")
        try:
            with self._client.stream(method, self.config.endpoint + path, json=body,
                                     timeout=httpx.Timeout(remaining)) as response:
                if response.status_code != 200:
                    raise _fail("MODEL_UNAVAILABLE", "http_error", status=response.status_code)
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise _fail("MODEL_UNAVAILABLE", "unsupported_response_encoding")
                length = response.headers.get("content-length")
                if length is not None and (not length.isdecimal() or int(length) > self.config.max_response_bytes):
                    raise _fail("MODEL_UNAVAILABLE", "response_too_large")
                raw = bytearray()
                for chunk in response.iter_raw():
                    if self._clock() >= deadline:
                        raise _fail("MODEL_UNAVAILABLE", "timeout")
                    if len(raw) + len(chunk) > self.config.max_response_bytes:
                        raise _fail("MODEL_UNAVAILABLE", "response_too_large")
                    raw.extend(chunk)
                if self._clock() >= deadline:
                    raise _fail("MODEL_UNAVAILABLE", "timeout")
                result = _strict_json(raw.decode("utf-8", errors="strict"))
                if not isinstance(result, dict):
                    raise TypeError("not a response object")
                return result
        except DomainError:
            raise
        except httpx.TimeoutException:
            raise _fail("MODEL_UNAVAILABLE", "timeout") from None
        except httpx.HTTPError:
            raise _fail("MODEL_UNAVAILABLE", "transport_error") from None
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise _fail("MODEL_UNAVAILABLE", "invalid_transport_response") from None
        except RuntimeError:
            raise _fail("MODEL_UNAVAILABLE", "client_closed") from None

    def _verify_pin(self, deadline: float) -> dict[str, Any]:
        raise NotImplementedError

    def _generate(self, prompt: str, schema: dict[str, Any], deadline: float) -> dict[str, Any]:
        raise NotImplementedError

    def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = self._clock()
        deadline = started + self.config.timeout_seconds
        before = self._verify_pin(deadline)
        output = self._generate(prompt, schema, deadline)
        if output.get("model") != self.config.model_id:
            raise _fail("MODEL_UNAVAILABLE", "response_model_mismatch")
        if output.get("done") is not True:
            raise _fail("MODEL_UNAVAILABLE", "generation_incomplete")
        if output.get("done_reason") == "length":
            raise _fail("MODEL_UNAVAILABLE", "output_truncated")
        if not isinstance(output.get("response"), str):
            raise _fail("MODEL_UNAVAILABLE", "invalid_transport_response")
        if self.adapter_name == "lab" and output.get("verified_model_digest") != self.config.expected_digest:
            raise _fail("MODEL_UNAVAILABLE", "model_revision_mismatch")
        after = self._verify_pin(deadline)
        if before != after:
            raise _fail("MODEL_UNAVAILABLE", "service_identity_changed")
        metadata: dict[str, Any] = {
            "adapter": self.adapter_name, "model_id": self.config.model_id,
            "revision": self.config.expected_digest, "revision_kind": "ollama_manifest_digest",
            "pin_verification": "before_and_after_generation",
            "backend_schema_enforced": self.backend_schema_enforced,
            "constraint_mode": "native_schema_and_local_validation" if self.backend_schema_enforced
            else "prompt_and_local_validation",
            "elapsed_ms": round((self._clock() - started) * 1000, 3),
            "generation_settings": {"temperature": 0, "num_ctx": self.config.context_tokens,
                                    "num_predict": self.config.max_output_tokens,
                                    "seed": 42 if self.adapter_name == "ollama" else None},
            "done_reason": output.get("done_reason") if isinstance(output.get("done_reason"), str) else None,
            "thinking_enabled": self.config.thinking,
            **before,
        }
        for name in ("prompt_eval_count", "eval_count"):
            value = output.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                metadata[name] = value
        duration = output.get("total_duration_ns" if self.adapter_name == "lab" else "total_duration")
        if isinstance(duration, int) and not isinstance(duration, bool) and duration >= 0:
            metadata["total_duration_ns"] = duration
        return {"response": output["response"], "metadata": metadata}


class LabModelAdapter(_ModelAdapter):
    """Existing lab /generate accepts only prompt, with fixed qwen3:8b generation."""

    adapter_name = "lab"
    max_prompt_characters = 5000

    def _verify_pin(self, deadline: float) -> dict[str, Any]:
        health = self._request("GET", "/health", deadline)
        if health.get("service") != "lgax-private-lab":
            raise _fail("MODEL_UNAVAILABLE", "unexpected_service")
        if health.get("expected_model_digest") != self.config.expected_digest:
            raise _fail("MODEL_UNAVAILABLE", "model_revision_mismatch")
        if health.get("generation_status") == "model_revision_changed":
            raise _fail("MODEL_UNAVAILABLE", "model_revision_mismatch")
        if health.get("generation_status") != "ready":
            raise _fail("MODEL_UNAVAILABLE", "model_missing_or_unavailable")
        models = health.get("models")
        if not isinstance(models, list) or models.count(self.config.model_id) != 1:
            raise _fail("MODEL_UNAVAILABLE", "model_missing_or_ambiguous")
        source = health.get("source_sha256")
        if not isinstance(source, str) or not _DIGEST.fullmatch(source):
            raise _fail("MODEL_UNAVAILABLE", "invalid_service_identity")
        return {"service_source_sha256": source}

    def _generate(self, prompt: str, schema: dict[str, Any], deadline: float) -> dict[str, Any]:
        if self.config.thinking:
            raise _fail("INVALID_ARGUMENT", "lab_thinking_is_fixed_off")
        if (self.config.max_output_tokens, self.config.context_tokens) != (256, 4096):
            raise _fail("INVALID_ARGUMENT", "lab_generation_budget_is_fixed")
        return self._request("POST", "/generate", deadline, {"prompt": prompt})


class OllamaAdapter(_ModelAdapter):
    """Direct private Ollama /api/generate uses native JSON Schema format."""

    adapter_name = "ollama"
    backend_schema_enforced = True

    def _verify_pin(self, deadline: float) -> dict[str, Any]:
        tags = self._request("GET", "/api/tags", deadline)
        models = tags.get("models")
        if not isinstance(models, list):
            raise _fail("MODEL_UNAVAILABLE", "invalid_transport_response")
        selected = [entry for entry in models if isinstance(entry, dict) and entry.get("name") == self.config.model_id]
        if len(selected) != 1:
            raise _fail("MODEL_UNAVAILABLE", "model_missing_or_ambiguous")
        if selected[0].get("digest") != self.config.expected_digest:
            raise _fail("MODEL_UNAVAILABLE", "model_revision_mismatch")
        return {}

    def _generate(self, prompt: str, schema: dict[str, Any], deadline: float) -> dict[str, Any]:
        return self._request("POST", "/api/generate", deadline, {
            "model": self.config.model_id, "prompt": prompt, "format": schema,
            "stream": False, "think": self.config.thinking,
            "options": {"temperature": 0, "seed": 42, "num_ctx": self.config.context_tokens,
                        "num_predict": self.config.max_output_tokens},
            "keep_alive": "5m",
        })


class StructuredModelClient:
    def __init__(self, adapter: _ModelAdapter) -> None:
        self.adapter = adapter

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> StructuredModelClient:
        values = os.environ if env is None else env
        names = ("LGAX_MODEL_ADAPTER", "LGAX_MODEL_ENDPOINT", "LGAX_MODEL_ID", "LGAX_MODEL_DIGEST")
        if any(not values.get(name) for name in names):
            raise _fail("INVALID_ARGUMENT", "missing_model_environment")
        kind = values[names[0]]
        if kind not in {"lab", "ollama"}:
            raise _fail("INVALID_ARGUMENT", "unknown_adapter")
        try:
            timeout = float(values.get("LGAX_MODEL_TIMEOUT_SECONDS", "120"))
            limit = int(values.get("LGAX_MODEL_MAX_RESPONSE_BYTES", "131072"))
            output_tokens = int(values.get("LGAX_MODEL_MAX_OUTPUT_TOKENS", "256"))
            context_tokens = int(values.get("LGAX_MODEL_CONTEXT_TOKENS", "4096"))
            thinking_setting = values.get("LGAX_MODEL_THINK", "false")
            if thinking_setting not in {"true", "false"}:
                raise ValueError("invalid thinking setting")
        except (ValueError, TypeError):
            raise _fail("INVALID_ARGUMENT", "invalid_model_environment") from None
        config = ModelConfig(values[names[1]], values[names[2]], values[names[3]], timeout, limit,
                             output_tokens, context_tokens, thinking=thinking_setting == "true")
        return cls((LabModelAdapter if kind == "lab" else OllamaAdapter)(config))

    def close(self) -> None:
        self.adapter.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def generate(self, prompt: str, schema: dict[str, Any], model_id: str) -> StructuredModelResult:
        if model_id != self.adapter.config.model_id:
            raise _fail("INVALID_ARGUMENT", "requested_model_mismatch")
        if not isinstance(prompt, str) or not prompt.strip():
            raise _fail("INVALID_ARGUMENT", "empty_prompt")
        validator, encoded_schema, schema_digest = _schema_validator(schema)
        formatted = (
            "요청에 답하는 JSON 값 하나만 출력하세요. 설명·마크다운·코드 펜스를 출력하지 마세요. "
            "출력은 아래 JSON Schema를 충족해야 합니다.\n"
            f"JSON Schema:\n{encoded_schema}\n\n요청:\n{prompt}"
        )
        if len(formatted) > self.adapter.max_prompt_characters:
            raise _fail("INVALID_ARGUMENT", "prompt_too_large", maximum=self.adapter.max_prompt_characters)
        output = self.adapter.generate(formatted, schema)
        data, response_format = _model_json(output["response"], validator)
        return StructuredModelResult(data, {
            **output["metadata"], "schema_sha256": schema_digest,
            "response_format": response_format, "locally_validated": True,
        })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", choices=["lab", "ollama"], required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-output-tokens", type=int, default=256,
                        help="Output limit, 32..8192 tokens (Lab requires 256).")
    parser.add_argument("--context-tokens", type=int, default=4096,
                        help="Context limit, 1024..32768 tokens, with at least 512 reserved for input (Lab requires 4096).")
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--schema-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = ModelConfig(args.endpoint, args.model, args.digest, args.timeout,
                             max_output_tokens=args.max_output_tokens, context_tokens=args.context_tokens)
        if args.prompt_file.stat().st_size > 64000 or args.schema_file.stat().st_size > _SCHEMA_BYTES_LIMIT:
            raise _fail("INVALID_ARGUMENT", "input_file_too_large")
        prompt = args.prompt_file.read_text("utf-8")
        schema = _strict_json(args.schema_file.read_text("utf-8"))
        with StructuredModelClient((LabModelAdapter if args.adapter == "lab" else OllamaAdapter)(config)) as client:
            result = client.generate(prompt, schema, args.model)
        args.output.write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")
    except DomainError as error:
        print(json.dumps(error.response(), ensure_ascii=False))
        return 1
    except (OSError, UnicodeError, ValueError, RecursionError):
        print(json.dumps(_fail("INVALID_ARGUMENT", "input_or_output_file_error").response(), ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "locally_validated": True, "adapter": args.adapter}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
