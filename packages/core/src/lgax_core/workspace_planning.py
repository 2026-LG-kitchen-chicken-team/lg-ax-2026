"""Explicit workspace planning integration; no client-selected model or endpoint."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from lgax_contracts import validate

from .errors import DomainError
from .judgement_contract import input_digest, review_judgement
from .judgement_contract import schema_for as judgement_schema
from .model_client import StructuredModelClient
from .planning_agent import PlanningAgent
from .store import DemoStore

PlanningRunner = Callable[[dict[str, Any], dict[str, str], DemoStore], dict[str, Any]]


def build_planning_input(request: dict, versions: dict[str, str], store: DemoStore) -> dict:
    """Use all original sources/features of the single authorized model/version."""
    if len(request["model_ids"]) != 1:
        raise DomainError("NOT_IMPLEMENTED", "실제 판단 실행은 단일 모델 범위만 지원합니다.",
                          {"reason": "single_model_required"})
    model = request["model_ids"][0]
    dataset = store.bootstrap()["data"]
    product = next((item for item in dataset["products"] if item["model_id"] == model), None)
    if product is None or product["document_version"] != versions.get(model):
        raise DomainError("NOT_IMPLEMENTED", "제품 원본과 같은 문서 버전에서 판단을 실행해 주세요.",
                          {"reason": "product_document_version_required"})
    scope = (model, versions[model])
    payload = {
        "request": deepcopy(request), "product": deepcopy(product),
        "sources": [deepcopy(item) for item in dataset["evidence"]
                    if (item["model_id"], item["document_version"]) == scope],
        "features": [deepcopy(item) for item in dataset["features"]
                     if (item["model_id"], item["document_version"]) == scope],
        "revision_count": 0, "max_concepts": 3, "changed_evidence_ids": [],
    }
    Draft202012Validator(judgement_schema("input")).validate(payload)
    return payload


def failed_execution(payload: dict, code: str = "MODEL_UNAVAILABLE", *,
                     execution_kind: str = "live_model") -> dict:
    """Exceptions never expose provider URLs, credentials or exception strings."""
    known = {"INVALID_ARGUMENT", "MODEL_UNAVAILABLE", "VALIDATION_FAILED", "CONTRACT_MISMATCH",
             "CONNECTION_FAILED", "NOT_IMPLEMENTED", "INSUFFICIENT_EVIDENCE"}
    if code not in known:
        code = "MODEL_UNAVAILABLE"
    error = {"code": code, "message": "판단 실행을 완료하지 못했습니다. 서버 실행 설정과 근거를 확인해 주세요.",
             "details": {"reason": "workspace_planning_failed"}}
    return {"execution_kind": execution_kind, "original_input": deepcopy(payload),
            "input": deepcopy(payload), "output": None, "decision": None, "status": "failed",
            "trace": [{"stage": "review", "operation": "stop", "inputs": {}, "outputs": {"error": error}}],
            "model_calls": [], "errors": [error]}


class EnvPlanningRunner:
    """Trusted server opt-in; configuration is read only from its environment."""

    def __call__(self, request: dict, versions: dict[str, str], store: DemoStore) -> dict:
        payload = build_planning_input(request, versions, store)
        try:
            with StructuredModelClient.from_env() as client:
                return PlanningAgent(client, store).run(payload)
        except DomainError as error:
            return failed_execution(payload, error.code)
        except Exception:  # noqa: BLE001 -- Provider exceptions can contain credentials; persist only a safe failure.
            return failed_execution(payload)


def planning_run_fields(execution: Any, payload: dict) -> tuple[dict, dict]:
    """Project checked Agent declarations into canonical Run and browser output."""
    if (not isinstance(execution, dict) or execution.get("execution_kind") not in {"fixture", "live_model"}
            or execution.get("original_input") != payload
            or execution.get("status") not in {"completed", "held", "failed"}):
        raise DomainError("CONTRACT_MISMATCH", "판단 실행 기록이 입력·출력 규격과 다릅니다.", {})
    terminal = execution.get("input")
    if not isinstance(terminal, dict):
        raise DomainError("CONTRACT_MISMATCH", "판단의 최종 입력이 없습니다.", {})
    revisions = terminal.get("revision_count")
    expected_terminal = {**payload, "revision_count": revisions}
    if (terminal != expected_terminal or isinstance(revisions, bool) or not isinstance(revisions, int)
            or not 0 <= revisions <= 2):
        raise DomainError("CONTRACT_MISMATCH", "판단 실행의 입력·수정 회차가 맞지 않습니다.", {})
    status = execution["status"]
    declared = execution.get("output")
    if declared is not None:
        Draft202012Validator(judgement_schema("output")).validate(declared)
        if (declared["status"] != status or declared["revision_count"] != revisions
                or declared["model_id"] != payload["product"]["model_id"]
                or declared["document_version"] != payload["product"]["document_version"]
                or declared["input_sha256"] != input_digest(terminal)):
            raise DomainError("CONTRACT_MISMATCH", "판단 결과와 실행 상태가 다릅니다.", {})
    if status == "completed":
        checked = review_judgement(terminal, declared)
        if not checked["valid"] or checked["action"] != "accept":
            raise DomainError("CONTRACT_MISMATCH", "검사를 통과하지 않은 판단을 완료로 저장할 수 없습니다.", {})
    output = declared or {"needs": [], "gaps": [], "concepts": []}
    scoped_evidence = {item["id"] for item in payload["sources"]}
    for item in output["needs"] + output["gaps"]:
        if (item["model_id"] != payload["product"]["model_id"]
                or not set(item["evidence_ids"]).issubset(scoped_evidence)):
            raise DomainError("CONTRACT_MISMATCH", "판단 결과가 프로젝트 원문 범위를 벗어났습니다.", {})
    for item in output["needs"]:
        validate("Need", item)
    for item in output["gaps"]:
        validate("Gap", item)
    concepts = deepcopy(output["concepts"]) if status == "completed" else []
    for item in concepts:
        validate("Concept", item)
    reasons = list(dict.fromkeys([
        *output.get("unresolved", []), *output.get("hold_reasons", []),
        *output.get("no_candidate_reasons", []),
    ]))
    if status != "completed" and not reasons:
        reasons = ["판단이 보류되었거나 실패했습니다. 실행 내역을 확인해 주세요."]
    evidence_ids = list(dict.fromkeys([
        *(item["id"] for item in payload["sources"]),
        *(ref for item in output["needs"] + output["gaps"] + concepts for ref in item["evidence_ids"]),
    ]))
    events = []
    for item in execution.get("trace", []):
        stage = item.get("stage", "review")
        operation = item.get("operation", "planning")
        if (not isinstance(stage, str) or not stage.strip()
                or not isinstance(operation, str) or not operation.strip()):
            raise DomainError("CONTRACT_MISMATCH", "판단 실행 이벤트 규격이 맞지 않습니다.", {})
        events.append({"stage": stage, "tool": operation,
                       "summary": f"{operation} 실행 기록 · {execution['execution_kind']}", "evidence_ids": []})
    fields = {"status": status, "stage": "finished" if status == "completed" else "review",
              "revision_count": revisions, "max_revisions": 2, "concepts": concepts,
              "unresolved": reasons, "evidence_ids": evidence_ids, "events": events}
    browser = {"needs": deepcopy(output["needs"]), "gaps": deepcopy(output["gaps"]),
               "planning_execution": deepcopy(execution)}
    return fields, browser
