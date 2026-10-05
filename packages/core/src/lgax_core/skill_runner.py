"""Validated reusable Skill execution; unregistered reasoning remains unimplemented.

Only evidence_lookup has a production handler today. Registering a fixture is
explicit test plumbing, not proof that a planning/model backend is implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator
from lgax_contracts import CONTRACT_VERSION, load_schema

from .errors import DomainError
from .store import DemoStore

SKILL_IDS = ("evidence_lookup", "need_extract", "product_compare", "concept_draft", "review_revision")
EXECUTION_KINDS = ("deterministic", "live_model", "fixture")


def _array(items: dict, **constraints) -> dict:
    return {"type": "array", "items": items, **constraints}


def _object(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required, "additionalProperties": False}


def _ref(name: str) -> dict:
    return {"$ref": f"#/$defs/{name}"}


def schema_for(skill_id: str, direction: str) -> dict:
    """Return a standalone schema with definitions from the canonical contract."""
    if skill_id not in SKILL_IDS or direction not in ("input", "output"):
        raise ValueError("Unknown Skill or schema direction")
    ids = _array({"type": "string", "minLength": 1}, uniqueItems=True)
    texts = _array({"type": "string", "minLength": 1}, uniqueItems=True)
    need_list = _array(_ref("Need"), uniqueItems=True)
    gap_list = _array(_ref("Gap"), uniqueItems=True)
    concept_list = _array(_ref("Concept"), maxItems=3, uniqueItems=True)
    common = {"model_id": _ref("ID"), "document_version": {"type": "string", "minLength": 1}}
    input_fields = {
        "evidence_lookup": {"query": {"type": "string", "minLength": 1, "maxLength": 500},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        "need_extract": {"review_evidence_ids": {**ids, "minItems": 1}},
        "product_compare": {"needs": {**need_list, "minItems": 1},
                            "feature_ids": ids, "evidence_ids": {**ids, "minItems": 1}},
        "concept_draft": {"needs": {**need_list, "minItems": 1}, "gaps": {**gap_list, "minItems": 1},
                          "constraints": texts, "max_concepts": {"type": "integer", "minimum": 1, "maximum": 3}},
        "review_revision": {"needs": need_list, "gaps": gap_list, "concepts": concept_list,
                            "violations": texts, "changed_evidence_ids": ids,
                            "revision_count": {"type": "integer", "minimum": 0, "maximum": 2}},
    }
    result_fields = {
        "evidence_lookup": {"query": {"type": "string"}, "items": _array(_ref("Evidence")),
                            "total": {"type": "integer", "minimum": 0},
                            "search_method": {"const": "literal_token_count"}},
        "need_extract": {"needs": need_list,
                         "desired_outcomes": _array(_object({"need_id": _ref("ID"),
                                                             "desired_outcome": {"type": "string", "minLength": 1}})),
                         "unresolved": texts},
        "product_compare": {"gaps": gap_list, "unresolved": texts},
        "concept_draft": {"concepts": concept_list, "hold_reasons": texts,
                          "no_candidate_reasons": _array({"type": "string", "minLength": 1,
                                                          "pattern": r"\S"}, uniqueItems=True)},
        "review_revision": {"needs": need_list, "gaps": gap_list, "concepts": concept_list,
                            "changes": _array(_object({"field": {"type": "string", "minLength": 1},
                                                       "reason": {"type": "string", "minLength": 1},
                                                       "evidence_ids": ids})),
                            "unresolved": texts,
                            "revision_count": {"type": "integer", "minimum": 1, "maximum": 2}},
    }
    if direction == "input":
        properties = {**common, **input_fields[skill_id]}
        optional = {"evidence_lookup": {"limit"}, "concept_draft": {"max_concepts"}}.get(skill_id, set())
        schema = _object(properties, [key for key in properties if key not in optional])
    else:
        data = _object({**common, "skill_id": {"const": skill_id}, "contract_version": {"const": CONTRACT_VERSION},
                        "execution_kind": {"enum": list(EXECUTION_KINDS)},
                        "backend_id": {"type": "string", "minLength": 1},
                        "source_kind": {"const": "synthetic"},
                        "result": _object(result_fields[skill_id],
                                           ["concepts", "hold_reasons"] if skill_id == "concept_draft" else None),
                         "sources": _array(_ref("Evidence"))})
        schema = {"oneOf": [_object({"ok": {"const": True}, "data": data}),
                            _object({"ok": {"const": False}, "error": _ref("Error")})]}
    canonical = deepcopy(load_schema()["$defs"])
    canonical["ID"] = deepcopy(canonical["Need"]["properties"]["id"])
    definitions: dict[str, dict] = {}

    def include_refs(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/$defs/"):
                name = reference.removeprefix("#/$defs/")
                if name not in definitions:
                    definitions[name] = canonical[name]
                    include_refs(canonical[name])
            for child in value.values():
                include_refs(child)
        elif isinstance(value, list):
            for child in value:
                include_refs(child)

    include_refs(schema)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"urn:lgax:skill:{skill_id}:{direction}:1", **schema,
            "$defs": definitions}


@dataclass(frozen=True)
class Handler:
    callback: Callable[[dict[str, Any], DemoStore], dict[str, Any]]
    backend_id: str
    execution_kind: str


class SkillRuntime:
    """One execution contract shared by local CLI and future API/MCP calls."""

    def __init__(self, store: DemoStore | None = None):
        self.store = store if store is not None else DemoStore()
        self._handlers = {"evidence_lookup": Handler(self._lookup, "demo-store:literal-token-count", "deterministic")}
        self._records: list[dict[str, Any]] = []

    @property
    def records(self) -> list[dict[str, Any]]:
        """Detached local observations, never trusted model/collector evidence."""
        return deepcopy(self._records)

    def register_handler(self, skill_id: str, handler: Callable, *, backend_id: str,
                         execution_kind: str, replace: bool = False) -> None:
        """Explicit developer integration; inputs never select/import arbitrary code.

        execution_kind describes the registered backend. A fixture must be marked
        fixture. Live-model registration still needs real execution evidence in
        the caller's run log; this registry does not authenticate that assertion.
        """
        if skill_id not in SKILL_IDS or execution_kind not in EXECUTION_KINDS:
            raise ValueError("Unknown Skill or execution kind")
        if not callable(handler) or not isinstance(backend_id, str) or not backend_id.strip():
            raise ValueError("A callable handler and nonempty backend_id are required")
        if skill_id in self._handlers and not replace:
            raise ValueError("Handler already registered; use explicit replace=True")
        self._handlers[skill_id] = Handler(handler, backend_id, execution_kind)

    def catalog(self) -> list[dict[str, Any]]:
        return [{"skill_id": name, "handler_registered": name in self._handlers,
                 "backend_id": self._handlers[name].backend_id if name in self._handlers else None,
                 "execution_kind": self._handlers[name].execution_kind if name in self._handlers else None,
                 "status": "available" if name in self._handlers else "NOT_IMPLEMENTED"} for name in SKILL_IDS]

    @staticmethod
    def _validate(skill_id: str, direction: str, value: Any) -> None:
        errors = sorted(Draft202012Validator(schema_for(skill_id, direction)).iter_errors(value),
                        key=lambda error: str(list(error.absolute_path)))
        if errors:
            raise DomainError("VALIDATION_FAILED", "Skill 입출력 스키마가 맞지 않습니다.",
                              {"skill_id": skill_id, "direction": direction,
                               "paths": [list(error.absolute_path) for error in errors[:8]]})

    @staticmethod
    def _ids(items: list[dict], label: str) -> dict[str, dict]:
        indexed = {item["id"]: item for item in items}
        if len(indexed) != len(items):
            raise DomainError("VALIDATION_FAILED", "중복 객체 ID입니다.", {"field": label})
        return indexed

    def _evidence(self, evidence_id: str, payload: dict, source_type: str | None = None) -> dict:
        evidence = self.store.get_evidence(evidence_id)["data"]["evidence"]
        if evidence["model_id"] != payload["model_id"]:
            raise DomainError("VALIDATION_FAILED", "다른 모델의 근거를 연결할 수 없습니다.",
                              {"evidence_id": evidence_id, "field": "model_id"})
        if evidence["document_version"] != payload["document_version"]:
            raise DomainError("VALIDATION_FAILED", "다른 문서 버전의 근거를 연결할 수 없습니다.",
                              {"evidence_id": evidence_id, "field": "document_version"})
        if source_type and evidence["source_type"] != source_type:
            raise DomainError("VALIDATION_FAILED", "리뷰 근거가 필요합니다.", {"evidence_id": evidence_id})
        return evidence

    def _check_objects(self, payload: dict, objects: dict, allowed_evidence: set[str] | None = None) -> set[str]:
        """Check canonical IDs/relations and source identity, not semantic quality."""
        used: set[str] = set()
        needs = self._ids(objects.get("needs", []), "needs")
        gaps = self._ids(objects.get("gaps", []), "gaps")
        concepts = self._ids(objects.get("concepts", []), "concepts")
        features = {feature["id"]: feature for feature in self.store.bootstrap()["data"]["features"]}
        for collection in (needs, gaps, concepts):
            for item in collection.values():
                if "model_id" in item and item["model_id"] != payload["model_id"]:
                    raise DomainError("VALIDATION_FAILED", "객체 모델 ID가 다릅니다.", {"id": item["id"]})
                for evidence_id in item.get("evidence_ids", []):
                    self._evidence(evidence_id, payload)
                    if allowed_evidence is not None and evidence_id not in allowed_evidence:
                        raise DomainError("VALIDATION_FAILED", "입력 문맥에 없는 근거입니다.", {"evidence_id": evidence_id})
                    used.add(evidence_id)
        for gap in gaps.values():
            if gap["need_id"] not in needs:
                raise DomainError("VALIDATION_FAILED", "Gap의 Need 참조가 없습니다.", {"gap_id": gap["id"]})
            for feature_id in gap["feature_ids"]:
                feature = features.get(feature_id)
                if not feature or (feature["model_id"], feature["document_version"]) != (
                        payload["model_id"], payload["document_version"]):
                    raise DomainError("VALIDATION_FAILED", "다른 모델/버전 또는 없는 기능입니다.",
                                      {"feature_id": feature_id})
                for evidence_id in feature["evidence_ids"]:
                    self._evidence(evidence_id, payload)
                    if allowed_evidence is not None and evidence_id not in allowed_evidence:
                        raise DomainError("VALIDATION_FAILED", "기능 근거가 입력 문맥에 없습니다.",
                                          {"evidence_id": evidence_id})
                    used.add(evidence_id)
        for concept in concepts.values():
            if any(gap_id not in gaps for gap_id in concept["gap_ids"]):
                raise DomainError("VALIDATION_FAILED", "Concept의 Gap 참조가 없습니다.", {"concept_id": concept["id"]})
        return used

    def _context(self, skill_id: str, payload: dict) -> set[str]:
        # The actual store distinguishes a bad model/version from a valid empty search.
        self.store.search_evidence("__skill_context_validation__", payload["model_id"], payload["document_version"], 1)
        used = self._check_objects(payload, payload)
        for field in ("evidence_ids", "review_evidence_ids", "changed_evidence_ids"):
            for evidence_id in payload.get(field, []):
                self._evidence(evidence_id, payload, "review" if field == "review_evidence_ids" else None)
                used.add(evidence_id)
        if skill_id == "product_compare":
            features = {item["id"]: item for item in self.store.bootstrap()["data"]["features"]}
            for feature_id in payload["feature_ids"]:
                feature = features.get(feature_id)
                if not feature or (feature["model_id"], feature["document_version"]) != (
                        payload["model_id"], payload["document_version"]):
                    raise DomainError("VALIDATION_FAILED", "다른 모델/버전 또는 없는 기능입니다.",
                                      {"feature_id": feature_id})
                for evidence_id in feature["evidence_ids"]:
                    self._evidence(evidence_id, payload)
                    used.add(evidence_id)
        return used

    def _lookup(self, payload: dict, _store: DemoStore) -> dict:
        result = self.store.search_evidence(payload["query"], payload["model_id"],
                                            payload["document_version"], payload.get("limit", 10))["data"]
        return {key: result[key] for key in ("query", "items", "total", "search_method")}

    def execute(self, skill_id: str, payload: Any, *, retry_of: str | None = None) -> dict[str, Any]:
        """Execute once. Explicit retries link the same input, at most twice.

        Records are separate from the stable output envelope. Invalid inputs are
        omitted, so unexpected fields (including credentials) are not persisted.
        Handler-internal model calls/retries require separate collector evidence.
        """
        record = {"record_version": 1, "run_id": f"skill-{uuid4().hex}", "skill_id": skill_id,
                  "started_at": datetime.now(UTC).isoformat(),
                  "contract_version": CONTRACT_VERSION, "input": None, "input_sha256": None,
                  "retry_of": retry_of, "retry_count": 0, "automatic_retries": 0,
                  "tool": {"backend_id": None, "execution_kind": None, "called": False},
                  "stage": "input_validation", "trusted_collector_verified": False}
        try:
            if skill_id not in SKILL_IDS:
                raise DomainError("INVALID_ARGUMENT", "등록된 Skill ID가 아닙니다.", {"skill_id": skill_id})
            self._validate(skill_id, "input", payload)
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
            record["input"] = deepcopy(payload)
            record["input_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            record["stage"] = "retry_validation"
            if retry_of is not None:
                previous = next((item for item in self._records if item["run_id"] == retry_of), None)
                if (previous is None or previous["skill_id"] != skill_id
                        or previous["input_sha256"] != record["input_sha256"]
                        or previous["stage"] in ("input_validation", "retry_validation")
                        or previous["decision"]["status"] not in ("failed", "held")
                        or previous["retry_count"] >= 2
                        or any(item["retry_of"] == retry_of and item["retry_count"] > 0
                               for item in self._records)):
                    raise DomainError("INVALID_ARGUMENT", "같은 입력의 미해결 실행에 최대 두 번 순차 재시도할 수 있습니다.", {})
                record["retry_count"] = previous["retry_count"] + 1
            response = self._execute_once(skill_id, payload, record)
        except DomainError as error:
            response = error.response()
        result = response.get("data", {}).get("result", {})
        reasons = list(result.get("hold_reasons", [])) + list(result.get("unresolved", []))
        reasons += [f"insufficient_evidence:{gap['id']}" for gap in result.get("gaps", [])
                    if gap["support_status"] == "insufficient_evidence"]
        error = response.get("error")
        if error and error["code"] == "INSUFFICIENT_EVIDENCE":
            reasons.append(error["message"])
        record["decision"] = {"status": "held" if reasons else "succeeded" if response["ok"] else "failed",
                              "hold_reasons": reasons}
        record["output"] = deepcopy(response)
        record["error"] = deepcopy(error)
        record["finished_at"] = datetime.now(UTC).isoformat()
        self._records.append(record)
        return response

    def _execute_once(self, skill_id: str, payload: Any, record: dict) -> dict[str, Any]:
        if skill_id not in SKILL_IDS:
            return DomainError("INVALID_ARGUMENT", "등록된 Skill ID가 아닙니다.", {"skill_id": skill_id}).response()
        try:
            self._validate(skill_id, "input", payload)
            record["stage"] = "context_validation"
            context = self._context(skill_id, payload)
            record["stage"] = "handler_selection"
            handler = self._handlers.get(skill_id)
            if handler is None:
                raise DomainError("NOT_IMPLEMENTED", "이 업무의 실제 판단 handler는 아직 구현되지 않았습니다.",
                                  {"skill_id": skill_id, "handler_registered": False,
                                   "implemented": [item["skill_id"] for item in self.catalog() if item["handler_registered"]]})
            record["tool"].update(backend_id=handler.backend_id, execution_kind=handler.execution_kind)
            record["stage"] = "revision_budget"
            if skill_id == "review_revision" and payload["revision_count"] >= 2:
                raise DomainError("INSUFFICIENT_EVIDENCE", "최대 두 번 수정한 뒤에는 미해결 판단을 보류합니다.",
                                  {"skill_id": skill_id, "revision_count": payload["revision_count"]})
            record["stage"] = "handler_call"
            record["tool"]["called"] = True
            result = handler.callback(deepcopy(payload), self.store)
            record["stage"] = "output_validation"
            response = {"ok": True, "data": {"skill_id": skill_id, "contract_version": CONTRACT_VERSION,
                        "execution_kind": handler.execution_kind, "backend_id": handler.backend_id,
                        "model_id": payload["model_id"], "document_version": payload["document_version"],
                        "source_kind": "synthetic", "result": result, "sources": []}}
            self._validate(skill_id, "output", response)
            if skill_id == "evidence_lookup":
                item_ids = [item["id"] for item in result["items"]]
                if (len(set(item_ids)) != len(item_ids) or result["query"] != payload["query"]
                        or result["total"] < len(item_ids) or len(item_ids) > payload.get("limit", 10)):
                    raise DomainError("VALIDATION_FAILED", "조회 결과의 요청/개수/중복 조건이 다릅니다.", {})
                for item in result["items"]:
                    if item != self._evidence(item["id"], payload):
                        raise DomainError("VALIDATION_FAILED", "조회 원문 내용 또는 위치가 달라졌습니다.", {"evidence_id": item["id"]})
                used = {item["id"] for item in result["items"]}
            else:
                objects = {**payload, **{key: result[key] for key in ("needs", "gaps", "concepts") if key in result}}
                used = self._check_objects(payload, objects, context)
                if skill_id == "need_extract":
                    extracted = self._ids(result["needs"], "needs")
                    outcome_ids = [item["need_id"] for item in result["desired_outcomes"]]
                    if len(set(outcome_ids)) != len(outcome_ids) or set(outcome_ids) != set(extracted):
                        raise DomainError("VALIDATION_FAILED", "각 니즈에 대응하는 희망 결과가 필요합니다.", {})
                if skill_id == "concept_draft" and len(result["concepts"]) > payload.get("max_concepts", 3):
                    raise DomainError("VALIDATION_FAILED", "요청한 콘셉트 상한을 초과했습니다.", {})
                if (skill_id == "concept_draft" and not result["concepts"]
                        and not result["hold_reasons"] and not result.get("no_candidate_reasons")):
                    raise DomainError("VALIDATION_FAILED", "후보가 없으면 정상 종료 또는 보류 사유를 남겨야 합니다.", {})
                if skill_id == "product_compare":
                    expected_needs = {need["id"] for need in payload["needs"]}
                    if {gap["need_id"] for gap in result["gaps"]} != expected_needs:
                        raise DomainError("VALIDATION_FAILED", "각 입력 니즈의 대조 또는 근거 부족 판단이 필요합니다.", {})
                if skill_id == "need_extract" and not result["needs"] and not result["unresolved"]:
                    raise DomainError("VALIDATION_FAILED", "니즈를 추출하지 못했다면 이유를 남겨야 합니다.", {})
                if skill_id == "review_revision":
                    if result["revision_count"] != payload["revision_count"] + 1:
                        raise DomainError("VALIDATION_FAILED", "수정 횟수는 실행마다 한 번 증가해야 합니다.", {})
                    for change in result["changes"]:
                        for evidence_id in change["evidence_ids"]:
                            self._evidence(evidence_id, payload)
                            if evidence_id not in context:
                                raise DomainError("VALIDATION_FAILED", "수정 근거가 입력 문맥에 없습니다.", {})
                            used.add(evidence_id)
            response["data"]["sources"] = [self._evidence(evidence_id, payload) for evidence_id in sorted(used)]
            self._validate(skill_id, "output", response)
            record["stage"] = "completed"
            return response
        except DomainError as error:
            return error.response()
        except Exception as error:  # noqa: BLE001 -- isolate arbitrary registered backend failures without secrets
            # Do not expose raw provider errors, credentials or request contents.
            return DomainError("MODEL_UNAVAILABLE", "Skill handler 실행에 실패했습니다.",
                               {"skill_id": skill_id, "error_type": type(error).__name__}).response()


def cli_main(skill_id: str) -> int:
    """Repeatable JSON file interface, with no API keys or implicit backend import."""
    parser = argparse.ArgumentParser(description=f"Execute the {skill_id} Skill")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trace-output", type=Path,
                        help="Separate run record; defaults to OUTPUT.trace.json. Must not exist.")
    args = parser.parse_args()
    trace_output = args.trace_output or Path(str(args.output) + ".trace.json")
    paths = [args.input, args.output, trace_output]
    if (len({path.resolve() for path in paths}) != len(paths)
            or args.output.exists() or trace_output.exists()):
        result = DomainError("INVALID_ARGUMENT", "입력은 보존하고 출력·실행 기록은 서로 다른 새 파일이어야 합니다.", {}).response()
        print(json.dumps(result, ensure_ascii=True), file=sys.stderr)
        return 2
    runtime = SkillRuntime()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = runtime.execute(skill_id, payload)
    except (OSError, ValueError, UnicodeError):
        result = DomainError("INVALID_ARGUMENT", "UTF-8 JSON 입력 파일을 읽을 수 없습니다.", {}).response()
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        trace_output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves earlier evidence. A partial write is an
        # I/O failure, not successful persistence of a complete run.
        with trace_output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"records": runtime.records, "cli_error": result.get("error") if not runtime.records else None},
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError:
        print(json.dumps(DomainError("INVALID_ARGUMENT", "출력 또는 실행 기록을 저장하지 못했습니다.", {}).response()),
              file=sys.stderr)
        return 2
    return 0 if result["ok"] else 2
