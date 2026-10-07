"""Authenticated actual-public-source planning; no implicit model calls or fixtures."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Request
from jsonschema import ValidationError
from lgax_contracts.research import validate_planning_brief, validate_research_bundle
from lgax_core.errors import DomainError

_ERROR_CODES = {"INVALID_ARGUMENT", "MODEL_UNAVAILABLE", "VALIDATION_FAILED", "CONTRACT_MISMATCH"}
_ERROR_REASONS = {
    "invalid_schema", "schema_too_large", "external_schema_reference", "invalid_json_fence", "invalid_json",
    "unresolvable_schema", "schema_mismatch", "invalid_thinking_setting", "invalid_api_mode",
    "invalid_sampling_setting", "unsafe_endpoint", "invalid_model_id", "missing_or_invalid_model_pin",
    "invalid_timeout", "invalid_response_limit", "invalid_generation_budget", "timeout", "http_error",
    "unsupported_response_encoding", "response_too_large", "transport_error", "invalid_transport_response",
    "client_closed", "response_model_mismatch", "generation_incomplete", "output_truncated",
    "model_revision_mismatch", "service_identity_changed", "unexpected_service", "model_missing_or_unavailable",
    "model_missing_or_ambiguous", "invalid_service_identity", "lab_api_is_fixed", "lab_thinking_is_fixed_off",
    "lab_sampling_is_fixed", "lab_generation_budget_is_fixed", "missing_model_environment", "unknown_adapter",
    "invalid_model_environment", "requested_model_mismatch", "empty_prompt", "prompt_too_large", "input_file_too_large",
    "contract_schema_mismatch", "run_snapshot_mismatch", "unhandled_exception", "invalid_run_id",
}
_ISSUE_CODES = {
    "quantity_not_in_cited_sources", "expected_time_as_actual_action", "excerpt_as_full_document_absence",
    "document_existence_as_resolution", "item_schema", "unknown_source_id", "problem_requires_customer_source",
    "unknown_counter_source", "draft_has_no_independent_quality_approval", "explicit_no_hardware_constraint",
    "source_not_in_call_context",
}
_ISSUE_FIELDS = {
    "id", "title", "description", "source_ids", "counter_source_ids", "scope_caveat", "problem_id", "product",
    "existing_response", "remaining_burden", "comparison_limits", "problem_ids", "target_user", "use_context",
    "before_steps", "after_steps", "mechanism", "proposed_changes", "assumptions", "validation_questions",
    "visual_scenes", "status",
}


def _safe_cause(code: Any, reason: Any) -> dict:
    result = {}
    if isinstance(code, str) and code in _ERROR_CODES:
        result["error_code"] = code
    if isinstance(reason, str) and reason in _ERROR_REASONS:
        result["error_reason"] = reason
    return result


def public_research_brief(brief: dict, bundle_sha256: str) -> dict:
    """Project every response, including old raw rows, without altering the private snapshot."""
    result = deepcopy(brief)
    raw = brief["runtime"]
    runtime = {"bundle_sha256": bundle_sha256, "independent_semantic_quality_verified": False,
               "market_frequency_estimated": False, "input_source_count": len(brief["source_facts"])}
    for key in ("model_id", "model_digest", "source_commit"):
        value = raw.get(key)
        pattern = r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}" if key == "model_id" else r"[a-f0-9]{40,64}"
        if (isinstance(value, str) and re.fullmatch(pattern, value) and "://" not in value
                and not re.search(r"token|password|secret|bearer", value, re.IGNORECASE)):
            runtime[key] = value
    if (isinstance(raw.get("execution_kind"), str)
            and raw["execution_kind"] in {"public_research_planner", "test_only_contract_stub"}):
        runtime["execution_kind"] = raw["execution_kind"]
    for key in ("context_tokens", "max_output_tokens", "max_model_calls", "max_repairs_per_item",
                "unique_customer_source_count"):
        value = raw.get(key)
        if type(value) is int and value >= 0:
            runtime[key] = value
    source_ids = {source["source_id"] for source in brief["source_facts"]}
    selected = raw.get("selected_source_ids")
    if isinstance(selected, list):
        runtime["selected_source_ids"] = list(dict.fromkeys(value for value in selected
                                                          if isinstance(value, str) and value in source_ids))
        runtime["omitted_source_count"] = len(source_ids) - len(runtime["selected_source_ids"])
    if raw.get("selection_method") == "round_robin_page_model_rating_sort":
        runtime["selection_method"] = raw["selection_method"]
    calls = raw.get("model_calls", [])
    calls = [call for call in calls if isinstance(call, dict)] if isinstance(calls, list) else []
    runtime["call_count"] = len(calls)
    runtime["repair_count"] = sum(call.get("stage") == "repair_fields" for call in calls)
    runtime["model_failures"] = [{"call_index": index, **_safe_cause(call.get("error_code"), call.get("error_reason"))}
                                 for index, call in enumerate(calls) if call.get("status") == "rejected"]
    runtime["validation_issues"] = []
    items = raw.get("item_issues", [])
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        for phase in ("issues", "after_repair"):
            issues = item.get(phase, [])
            for issue in issues if isinstance(issues, list) else []:
                if isinstance(issue, dict) and isinstance(issue.get("code"), str) and issue["code"] in _ISSUE_CODES:
                    projected = {"code": issue["code"], "after_repair": phase == "after_repair"}
                    if isinstance(issue.get("field"), str) and issue["field"] in _ISSUE_FIELDS:
                        projected["field"] = issue["field"]
                    runtime["validation_issues"].append(projected)
    result["runtime"] = runtime
    return result


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value):
        raise DomainError("INVALID_ARGUMENT", "자료·실행 식별자를 확인해 주세요.")
    return value


class EnvResearchPlanner:
    def run(self, bundle: dict, goal: str, constraints: list[str], previous: dict | None = None) -> dict:
        from lgax_core.model_client import StructuredModelClient
        from lgax_core.public_planning import PublicPlanner

        with StructuredModelClient.from_env() as client:
            return PublicPlanner.from_model_client(client).run(bundle, goal, constraints, previous)


class ResearchWorkspace:
    """Operator-loaded immutable sources and principal-owned run snapshots."""

    def __init__(self, db_path: Path, bundle_paths: list[Path], planner: Any = None):
        self.planner = planner
        self.db_path = db_path
        self.bundles: dict[str, dict] = {}
        self.digests: dict[str, str] = {}
        for path in bundle_paths:
            raw = path.read_bytes()
            if len(raw) > 8_000_000:
                raise ValueError("Research bundle exceeds the configured source limit")
            bundle = json.loads(raw)
            validate_research_bundle(bundle)
            bundle_id = _identifier(bundle["bundle_id"])
            if bundle_id in self.bundles:
                raise ValueError("Duplicate research bundle ID")
            self.bundles[bundle_id] = bundle
            self.digests[bundle_id] = sha256(raw).hexdigest()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS research_runs (run_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, bundle_id TEXT NOT NULL, bundle_sha256 TEXT NOT NULL, brief TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS research_attempts (attempt_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, bundle_id TEXT NOT NULL, bundle_sha256 TEXT NOT NULL, status TEXT NOT NULL, request TEXT NOT NULL, run_id TEXT, error_code TEXT, error_reason TEXT, error_type TEXT, rejected_brief TEXT, created_at TEXT NOT NULL, finished_at TEXT)")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_bundles(self) -> dict:
        return {"bundles": [{
            "bundle_id": key, "product_group": bundle["product_group"],
            "analysis_scope": bundle["analysis_scope"], "source_count": len(bundle["sources"]),
            "review_count": sum(source["source_type"] == "review" for source in bundle["sources"]),
            "bundle_sha256": self.digests[key], "collection_manifest": deepcopy(bundle["collection_manifest"]),
        } for key, bundle in self.bundles.items()]}

    def get_bundle(self, bundle_id: str) -> dict:
        bundle = self.bundles.get(_identifier(bundle_id))
        if bundle is None:
            raise DomainError("NOT_FOUND", "등록된 실제 자료를 찾을 수 없습니다.")
        return deepcopy(bundle)

    def _row(self, run_id: str, principal):
        with self.connect() as connection:
            row = connection.execute("SELECT owner_id, bundle_id, bundle_sha256, brief FROM research_runs WHERE run_id = ?", (_identifier(run_id),)).fetchone()
        if row is None or row[0] != principal.id and not principal.admin:
            raise DomainError("NOT_FOUND", "접근 가능한 실행 기록을 찾을 수 없습니다.")
        return row

    def get_run(self, run_id: str, principal) -> dict:
        row = self._row(run_id, principal)
        return public_research_brief(json.loads(row[3]), row[2])

    def _failed_attempt(self, attempt_id: str, error: Exception, code: str, reason: str, brief: Any) -> None:
        """Retain failure state privately; no exception messages or credential details are copied."""
        if isinstance(error, DomainError):
            details = error.details if isinstance(error.details, dict) else {}
            cause = _safe_cause(error.code, details.get("reason"))
            code, reason = cause.get("error_code", code), cause.get("error_reason", reason)
        try:
            rejected = json.dumps(brief, ensure_ascii=False, allow_nan=False) if brief is not None else None
        except (TypeError, ValueError):
            rejected = None
        with self.connect() as connection:
            connection.execute("UPDATE research_attempts SET status = 'failed', error_code = ?, error_reason = ?, error_type = ?, rejected_brief = ?, finished_at = ? WHERE attempt_id = ?",
                               (code, reason, type(error).__name__, rejected, datetime.now(UTC).isoformat(), attempt_id))

    def create_run(self, payload: dict, principal) -> dict:
        principal.require_write()
        if set(payload) - {"bundle_id", "goal", "constraints", "previous_run_id"}:
            raise DomainError("INVALID_ARGUMENT", "허용된 기획 입력만 보내 주세요.")
        bundle_id = _identifier(payload.get("bundle_id"))
        bundle = self.get_bundle(bundle_id)
        goal, constraints = payload.get("goal"), payload.get("constraints")
        if (not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 1000
                or not isinstance(constraints, list) or len(constraints) > 10
                or any(not isinstance(item, str) or not 1 <= len(item.strip()) <= 500 for item in constraints)):
            raise DomainError("INVALID_ARGUMENT", "기획 목적과 제약을 확인해 주세요.")
        previous = None
        if payload.get("previous_run_id") is not None:
            row = self._row(payload["previous_run_id"], principal)
            # Ownership remains exact for revisions, including administrator reads.
            if row[0] != principal.id or row[1] != bundle_id or row[2] != self.digests[bundle_id]:
                raise DomainError("DATASET_MISMATCH", "같은 소유자·자료 버전의 실행에서만 조건을 변경할 수 있습니다.")
            previous = json.loads(row[3])
        if self.planner is None:
            raise DomainError("NOT_IMPLEMENTED", "실제 자료는 연결됐으며 모델 실행 설정을 기다리고 있습니다.")
        normalized_goal, normalized_constraints = goal.strip(), [item.strip() for item in constraints]
        expected_facts = [{"source_id": source["source_id"], "facts": deepcopy(source["facts"])} for source in bundle["sources"]]
        expected_group, expected_scope = bundle["product_group"], bundle["analysis_scope"]
        expected_previous = previous["brief_id"] if previous else None
        expected_revision = previous["revision"] + 1 if previous else 0
        attempt_id = f"attempt-{uuid4().hex}"
        with self.connect() as connection:
            connection.execute("INSERT INTO research_attempts (attempt_id, owner_id, bundle_id, bundle_sha256, status, request, created_at) VALUES (?, ?, ?, ?, 'started', ?, ?)",
                               (attempt_id, principal.id, bundle_id, self.digests[bundle_id],
                                json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()))
        brief = None
        try:
            brief = self.planner.run(bundle, normalized_goal, deepcopy(normalized_constraints), deepcopy(previous))
            validate_planning_brief(brief)
            if (brief["bundle_id"] != bundle_id or brief["product_group"] != expected_group
                    or brief["analysis_scope"] != expected_scope
                    or brief["goal"] != normalized_goal or brief["constraints"] != normalized_constraints
                    or brief["previous_brief_id"] != expected_previous or brief["revision"] != expected_revision
                    or brief["source_facts"] != expected_facts):
                raise DomainError("CONTRACT_MISMATCH", "기획 결과의 자료·사실·조건·수정 버전이 다릅니다.",
                                  {"reason": "run_snapshot_mismatch"})
            try:
                run_id = _identifier(brief["run_id"])
            except DomainError as error:
                raise DomainError("CONTRACT_MISMATCH", "기획 실행 식별자가 규격과 다릅니다.",
                                  {"reason": "invalid_run_id"}) from error
            encoded = json.dumps(brief, ensure_ascii=False, allow_nan=False)
            public = public_research_brief(brief, self.digests[bundle_id])
            with self.connect() as connection:
                connection.execute("INSERT INTO research_runs VALUES (?, ?, ?, ?, ?)",
                                   (run_id, principal.id, bundle_id, self.digests[bundle_id], encoded))
                connection.execute("UPDATE research_attempts SET status = 'completed', run_id = ?, finished_at = ? WHERE attempt_id = ?",
                                   (run_id, datetime.now(UTC).isoformat(), attempt_id))
        except DomainError as error:
            self._failed_attempt(attempt_id, error, "MODEL_UNAVAILABLE", "unhandled_exception", brief)
            raise
        except ValidationError as error:
            self._failed_attempt(attempt_id, error, "CONTRACT_MISMATCH", "contract_schema_mismatch", brief)
            raise DomainError("CONTRACT_MISMATCH", "기획 결과가 공통 규격과 다릅니다.") from error
        except Exception as error:
            self._failed_attempt(attempt_id, error, "MODEL_UNAVAILABLE", "unhandled_exception", brief)
            raise DomainError("MODEL_UNAVAILABLE", "모델 실행을 완료하지 못했습니다.") from error
        return public


def research_router(workspace: ResearchWorkspace | None) -> APIRouter:
    router = APIRouter(prefix="/api/research")

    def configured() -> ResearchWorkspace:
        if workspace is None:
            raise DomainError("NOT_IMPLEMENTED", "실제 연구 자료 연결을 기다리고 있습니다.")
        return workspace

    @router.get("/bundles")
    def bundles():
        return configured().list_bundles()

    @router.get("/bundles/{bundle_id}")
    def bundle(bundle_id: str):
        return configured().get_bundle(bundle_id)

    @router.post("/planning-runs", status_code=201)
    def create_run(request: Request, payload: Annotated[dict, Body()]):
        return configured().create_run(payload, request.state.principal)

    @router.get("/planning-runs/{run_id}")
    def run(request: Request, run_id: str):
        return configured().get_run(run_id, request.state.principal)

    return router
