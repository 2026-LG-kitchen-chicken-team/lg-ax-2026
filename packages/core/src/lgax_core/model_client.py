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
_SCHEMA_FIELD_GUIDES = {
    "polarity": (
        ("complaint", "positive", "conflicting", "irrelevant", "uncertain"),
        "polarity: complaint=명시 불편/미충족 요구; positive=불편 없는 칭찬; "
        "conflicting=자료 상충; irrelevant=요청과 무관; uncertain=원문만으로 판단 불가. "
        "긍정 표현과 명시 불편이 함께 있어도 그 불편을 positive로 바꾸지 마세요.",
    ),
    "duplication": (
        ("distinct", "duplicate", "uncertain"),
        "duplication: distinct=기존 기능이 제공하지 않는 작동/행동; "
        "duplicate=원문에 명시된 기존 작동/행동과 동일; uncertain=자료만으로 비교 불가. "
        "일부 구성 공유나 기능 미지원만으로 duplicate라 하지 마세요.",
    ),
    "support_status": (
        ("supported", "unsupported", "insufficient_evidence"),
        "support_status: supported=현재 기능의 명시적 지원; unsupported=명시적 미지원; "
        "insufficient_evidence=미언급/상충으로 확인 불가.",
    ),
    "support_basis": (
        ("explicit_supported", "explicit_unsupported", "unmentioned", "conflicting"),
        "support_basis: explicit_supported=supported; explicit_unsupported=unsupported; "
        "unmentioned/conflicting=insufficient_evidence. 명시된 현재 기능을 희망 결과가 "
        "충족되지 않았다는 이유로 unmentioned로 바꾸지 마세요.",
    ),
    "resolution": (
        ("resolved", "remaining", "unknown"),
        "resolution: resolved=희망 결과 충족; remaining=확인된 잔여 불편; "
        "unknown=원문만으로 해결 여부 불명. 현재 기능이 supported여도 remaining일 수 있습니다.",
    ),
}


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


def _schema_field_guide(schema: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Explain known enum contracts, without interpreting source facts or outputs."""
    found: set[str] = set()
    pending: list[Any] = [schema]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, (expected, _line) in _SCHEMA_FIELD_GUIDES.items():
                definition = properties.get(name)
                values = definition.get("enum") if isinstance(definition, dict) else None
                if isinstance(values, list) and tuple(values) == expected:
                    found.add(name)
        # Traverse only schema children, never annotation/example/enum data.
        for key in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
            children = node.get(key)
            if isinstance(children, dict):
                pending.extend(children.values())
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(key)
            if isinstance(children, list):
                pending.extend(children)
        for key in ("items", "contains", "additionalProperties", "unevaluatedProperties",
                    "unevaluatedItems", "propertyNames", "not", "if", "then", "else", "contentSchema"):
            child = node.get(key)
            if isinstance(child, dict):
                pending.append(child)
    fields = tuple(name for name in _SCHEMA_FIELD_GUIDES if name in found)
    # Stage control arrays must be described even when the provider receives
    # the schema natively. Never derive instructions from schema annotations.
    properties = schema.get("properties", {})
    result = properties.get("result", {}) if isinstance(properties, dict) else {}
    result_properties = result.get("properties", {}) if isinstance(result, dict) else {}
    array_fields = {
        "unresolved": result_properties.get("unresolved") if isinstance(result_properties, dict) else None,
        **{name: properties.get(name) if isinstance(properties, dict) else None
           for name in ("questions", "hold_reasons", "no_candidate_reasons")},
    }
    stage_control = (
        isinstance(result_properties, dict)
        and bool(set(result_properties) & {"needs", "gaps", "concepts"})
        and all(isinstance(definition, dict) and definition.get("type") == "array"
                and isinstance(definition.get("items"), dict)
                and definition["items"].get("type") == "string"
                for definition in array_fields.values())
    )
    if stage_control:
        fields += tuple(array_fields)
    quality = properties.get("quality_assessments", {}) if isinstance(properties, dict) else {}
    quality_items = quality.get("items", {}) if isinstance(quality, dict) else {}
    quality_properties = quality_items.get("properties", {}) if isinstance(quality_items, dict) else {}
    criterion = quality_properties.get("criterion", {}) if isinstance(quality_properties, dict) else {}
    semantic_citations = (
        isinstance(quality, dict) and quality.get("type") == "array"
        and isinstance(criterion, dict)
        and criterion.get("enum") == ["mechanism", "difference_from_current_features",
                                      "unverified_assumptions", "unsupported_factual_claims"]
        and {"source_quotes", "candidate_quote", "concept_id", "verdict"} <= set(quality_properties)
    )
    if semantic_citations:
        fields += ("difference_source_quotes",)
    if not fields:
        return "", fields
    lines = ["판정값 안내: 값과 reason의 의미를 일치시키고 제공된 원문으로 판단하세요."]
    if found & {"support_status", "support_basis", "resolution"}:
        lines.append("기능 지원은 선택한 현재 기능의 문서상 지원이며, 고객 희망 결과의 해결 여부와 별개입니다.")
    lines.extend(_SCHEMA_FIELD_GUIDES[name][1] for name in fields if name in _SCHEMA_FIELD_GUIDES)
    if stage_control:
        lines.extend((
            "unresolved: 원문에서 확인할 수 없어 현재 판단을 막는 사실을 문장으로 적습니다. "
            "Need ID·필드명·작업 대기 목록이나 확인된 불편을 적는 곳이 아닙니다. 불명 사실이 없으면 [].",
            "questions: 그 불명 사실을 확인할 구체 질문입니다. 판단을 보류할 때는 무엇을 확인할지 묻습니다.",
            "hold_reasons: 현재 판단을 막는 자료 누락·상충의 이유입니다. "
            "불편이 남아 있다는 이유만으로 보류하지 않습니다. 판단 가능하면 [].",
            "no_candidate_reasons: 판단 후 후보가 없거나 필요 없을 때의 이유입니다. "
            "후보 작성 전에는 []. 필요한 자료가 실제 없을 때는 보류·질문을 유지하세요.",
        ))
    if semantic_citations:
        lines.append(
            "difference_from_current_features를 satisfied로 판단하는 같은 quality_assessments 항목의 "
            "source_quotes 안에 각 연결 Gap의 고객 리뷰 최소 1개와 같은 모델·버전 설명서를 함께 원문 인용하세요. "
            "각 연결 Feature의 설명서도 인용하세요. mechanism 등 다른 항목의 리뷰 인용으로 대신 충족하지 않습니다. "
            "원문에 없는 기능 부재를 사실로 단정하지 말고, 자료가 없으면 uncertain과 구체 확인 질문을 남기세요."
        )
    return "\n".join(lines) + "\n\n", fields


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
    temperature: float = 0.0
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    api_mode: str = "generate"

    def __post_init__(self) -> None:
        if not isinstance(self.thinking, bool):
            raise _fail("INVALID_ARGUMENT", "invalid_thinking_setting")
        if not isinstance(self.api_mode, str) or self.api_mode not in {"generate", "chat"}:
            raise _fail("INVALID_ARGUMENT", "invalid_api_mode")
        for name, value, lower, upper in (
            ("temperature", self.temperature, 0, 2),
            ("top_p", self.top_p, 0, 1), ("min_p", self.min_p, 0, 1),
        ):
            if value is None and name != "temperature":
                continue
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not lower <= value <= upper
                    or (name == "top_p" and value == 0)):
                raise _fail("INVALID_ARGUMENT", "invalid_sampling_setting")
        if (self.top_k is not None and (type(self.top_k) is not int or not 0 <= self.top_k <= 1000)):
            raise _fail("INVALID_ARGUMENT", "invalid_sampling_setting")
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

    def ollama_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": self.temperature, "seed": 42,
                                   "num_ctx": self.context_tokens, "num_predict": self.max_output_tokens}
        for name in ("top_p", "top_k", "min_p"):
            value = getattr(self, name)
            if value is not None:
                options[name] = value
        return options


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
            "generation_settings": self.config.ollama_options() if self.adapter_name == "ollama" else {
                "temperature": 0, "num_ctx": self.config.context_tokens,
                "num_predict": self.config.max_output_tokens, "seed": None},
            "done_reason": output.get("done_reason") if isinstance(output.get("done_reason"), str) else None,
            "thinking_enabled": self.config.thinking,
            "transport_api": "/api/" + self.config.api_mode if self.adapter_name == "ollama" else "/generate",
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
        if self.config.api_mode != "generate":
            raise _fail("INVALID_ARGUMENT", "lab_api_is_fixed")
        if self.config.thinking:
            raise _fail("INVALID_ARGUMENT", "lab_thinking_is_fixed_off")
        if (self.config.temperature != 0 or any(getattr(self.config, name) is not None
                                              for name in ("top_p", "top_k", "min_p"))):
            raise _fail("INVALID_ARGUMENT", "lab_sampling_is_fixed")
        if (self.config.max_output_tokens, self.config.context_tokens) != (256, 4096):
            raise _fail("INVALID_ARGUMENT", "lab_generation_budget_is_fixed")
        return self._request("POST", "/generate", deadline, {"prompt": prompt})


class OllamaAdapter(_ModelAdapter):
    """Explicit private Ollama generate/chat calls with native JSON Schema format."""

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
        body = {
            "model": self.config.model_id, "format": schema,
            "stream": False, "think": self.config.thinking,
            "options": self.config.ollama_options(),
            "keep_alive": "5m",
        }
        if self.config.api_mode == "chat":
            body["messages"] = [{"role": "user", "content": prompt}]
        else:
            body["prompt"] = prompt
        response = self._request("POST", "/api/" + self.config.api_mode, deadline, body)
        if self.config.api_mode == "chat":
            message = response.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise _fail("MODEL_UNAVAILABLE", "invalid_transport_response")
            # Only final content is validated as JSON. Thinking is retained in
            # the transport body, never substituted for a missing final answer.
            return {**response, "response": message["content"]}
        return response


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
            sampling = {"temperature": float(values.get("LGAX_MODEL_TEMPERATURE", "0"))}
            for name, parser in (("top_p", float), ("top_k", int), ("min_p", float)):
                key = "LGAX_MODEL_" + name.upper()
                if key in values:
                    sampling[name] = parser(values[key])
        except (ValueError, TypeError):
            raise _fail("INVALID_ARGUMENT", "invalid_model_environment") from None
        config = ModelConfig(values[names[1]], values[names[2]], values[names[3]], timeout, limit,
                             output_tokens, context_tokens, thinking=thinking_setting == "true",
                             api_mode=values.get("LGAX_MODEL_API_MODE", "generate"), **sampling)
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
        guide, guide_fields = _schema_field_guide(schema)
        native_schema = getattr(self.adapter, "backend_schema_enforced", False) is True
        if native_schema:
            # The full schema is already sent as the native format constraint.
            # Retain the caller's complete task/evidence, without a second copy
            # of the schema in the text prompt. Unknown wrappers stay on the
            # conservative embedded-schema path until they forward this flag.
            formatted = (
                "요청에 답하는 JSON 값 하나만 출력하세요. 설명·마크다운·코드 펜스를 출력하지 마세요. "
                "출력은 요청의 native JSON Schema 형식 제약을 충족해야 합니다.\n\n"
                f"{guide}요청:\n{prompt}"
            )
        else:
            formatted = (
                "요청에 답하는 JSON 값 하나만 출력하세요. 설명·마크다운·코드 펜스를 출력하지 마세요. "
                "출력은 아래 JSON Schema를 충족해야 합니다.\n"
                f"JSON Schema:\n{encoded_schema}\n\n{guide}요청:\n{prompt}"
            )
        if len(formatted) > self.adapter.max_prompt_characters:
            raise _fail("INVALID_ARGUMENT", "prompt_too_large", maximum=self.adapter.max_prompt_characters)
        output = self.adapter.generate(formatted, schema)
        data, response_format = _model_json(output["response"], validator)
        return StructuredModelResult(data, {
            **output["metadata"], "schema_sha256": schema_digest,
            "response_format": response_format, "locally_validated": True,
            "schema_prompt_embedded": not native_schema,
            "schema_field_guide": {
                "version": ("enum_and_citation_meanings_v3" if "difference_source_quotes" in guide_fields
                            else "enum_and_hold_meanings_v2" if "unresolved" in guide_fields
                            else "enum_meanings_v1"),
                "fields": list(guide_fields),
                "characters": len(guide), "utf8_bytes": len(guide.encode("utf-8")),
                "sha256": sha256(guide.encode("utf-8")).hexdigest(),
            },
            "formatted_prompt_characters": len(formatted),
            "formatted_prompt_utf8_bytes": len(formatted.encode("utf-8")),
            "formatted_prompt_sha256": sha256(formatted.encode("utf-8")).hexdigest(),
        })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", choices=["lab", "ollama"], required=True)
    parser.add_argument("--api-mode", choices=["generate", "chat"], default="generate")
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
                             max_output_tokens=args.max_output_tokens, context_tokens=args.context_tokens,
                             api_mode=args.api_mode)
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
