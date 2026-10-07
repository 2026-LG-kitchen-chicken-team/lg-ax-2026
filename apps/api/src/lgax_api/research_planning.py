"""Authenticated actual-public-source planning; no implicit model calls or fixtures."""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Body, Request
from jsonschema import ValidationError
from lgax_contracts.research import validate_planning_brief, validate_research_bundle
from lgax_core.errors import DomainError


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
        return json.loads(self._row(run_id, principal)[3])

    def create_run(self, payload: dict, principal) -> dict:
        principal.require_write()
        if set(payload) - {"bundle_id", "goal", "constraints", "previous_run_id"}:
            raise DomainError("INVALID_ARGUMENT", "허용된 기획 입력만 보내 주세요.")
        bundle_id = _identifier(payload.get("bundle_id"))
        bundle = self.get_bundle(bundle_id)
        goal, constraints = payload.get("goal"), payload.get("constraints")
        if (not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 1000
                or not isinstance(constraints, list) or len(constraints) > 32
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
        try:
            brief = self.planner.run(bundle, goal.strip(), [item.strip() for item in constraints], previous)
            validate_planning_brief(brief)
        except DomainError:
            raise
        except ValidationError as error:
            raise DomainError("CONTRACT_MISMATCH", "기획 결과가 공통 규격과 다릅니다.") from error
        except Exception as error:
            raise DomainError("MODEL_UNAVAILABLE", "모델 실행을 완료하지 못했습니다.") from error
        if (brief["bundle_id"] != bundle_id or brief["product_group"] != bundle["product_group"]
                or brief["analysis_scope"] != bundle["analysis_scope"]
                or brief["goal"] != goal.strip() or brief["constraints"] != [item.strip() for item in constraints]
                or brief["previous_brief_id"] != (previous["brief_id"] if previous else None)
                or brief["revision"] != (previous["revision"] + 1 if previous else 0)
                or brief["source_facts"] != [{"source_id": source["source_id"], "facts": source["facts"]} for source in bundle["sources"]]):
            raise DomainError("CONTRACT_MISMATCH", "기획 결과의 자료·사실·조건·수정 버전이 다릅니다.")
        run_id = _identifier(brief["run_id"])
        # Public provenance never exports provider endpoints or private diagnostics.
        safe_keys = {"model", "model_id", "model_digest", "source_commit", "duration_seconds", "call_count", "execution_kind", "selected_source_ids", "omitted_source_count", "warnings", "repair_count", "validation_issues"}
        brief["runtime"] = {key: value for key, value in brief["runtime"].items() if key in safe_keys}
        brief["runtime"]["bundle_sha256"] = self.digests[bundle_id]
        with self.connect() as connection:
            connection.execute("INSERT INTO research_runs VALUES (?, ?, ?, ?, ?)", (run_id, principal.id, bundle_id, self.digests[bundle_id], json.dumps(brief, ensure_ascii=False)))
        return brief


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
    def create_run(request: Request, payload: dict = Body(...)):
        return configured().create_run(payload, request.state.principal)

    @router.get("/planning-runs/{run_id}")
    def run(request: Request, run_id: str):
        return configured().get_run(run_id, request.state.principal)

    return router
