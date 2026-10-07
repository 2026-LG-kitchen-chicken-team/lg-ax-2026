"""Authenticated loopback workspace API; separate from the public evidence demo."""

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from lgax_contracts import CONTRACT_VERSION, validate
from lgax_core.errors import DomainError
from lgax_core.store import DemoStore, default_store
from lgax_core.workspace import WorkspaceStore
from lgax_core.workspace_planning import EnvPlanningRunner, PlanningRunner
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .public_validation import public_validation_details
from .research_planning import EnvResearchPlanner, ResearchWorkspace, research_router
from .trend_configuration import load_trend_runtime
from .workspace_auth import TokenRegistry
from .workspace_bootstrap import workspace_bootstrap
from .workspace_trends import TrendCollector, WorkspaceTrends

ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:5175", "http://localhost:5175"}

_ERROR_MESSAGES = {
    "UNAUTHORIZED": "작업실 인증을 확인해 주세요.",
    "FORBIDDEN": "이 작업을 수행할 권한이 없습니다.",
    "NOT_FOUND": "작업 기록을 찾을 수 없습니다.",
    "INVALID_ARGUMENT": "작업실 입력 값을 확인해 주세요.",
    "INVALID_INPUT": "동향 조회 조건을 확인해 주세요.",
    "INVALID_MODEL_ID": "제품 모델을 확인해 주세요.",
    "INVALID_DOCUMENT_VERSION": "문서 버전을 확인해 주세요.",
    "INVALID_EVIDENCE_ID": "근거 ID를 확인해 주세요.",
    "DATASET_MISMATCH": "저장된 자료 범위와 현재 자료가 다릅니다.",
    "NOT_IMPLEMENTED": "요청한 실행 기능 또는 자료 범위는 아직 지원하지 않습니다.",
    "MODEL_UNAVAILABLE": "판단 모델 실행을 완료하지 못했습니다.",
    "CONNECTION_FAILED": "작업실 처리 중 연결 또는 저장에 실패했습니다.",
    "CONTRACT_MISMATCH": "판단 실행 기록이 공통 규격과 다릅니다.",
    "VALIDATION_FAILED": "판단 결과 검사를 통과하지 못했습니다.",
    "INSUFFICIENT_EVIDENCE": "판단에 필요한 근거가 부족합니다.",
}


def public_error(code: str) -> dict:
    """Never serialize exception messages/details, including adapter diagnostics."""
    if code not in _ERROR_MESSAGES:
        code = "CONTRACT_MISMATCH"
    return DomainError(code, _ERROR_MESSAGES[code]).response()


def public_run(snapshot: dict) -> dict:
    """Keep source/judgement snapshots intact; redact private failure diagnostics.

    The same projection is used for POST, GET and history, including older rows.
    Rejected adapter records remain in the private store, never on the wire.
    """
    result = deepcopy(snapshot)

    output = result.get("output")
    execution = output.get("planning_execution") if isinstance(output, dict) else None
    input_record = execution.get("input") if isinstance(execution, dict) else None
    sources = input_record.get("sources") if isinstance(input_record, dict) else None
    evidence_ids = {item["id"] for item in sources if isinstance(item, dict)
                    and isinstance(item.get("id"), str)} if isinstance(sources, list) else set()
    entities = {"needs": set(), "gaps": set(), "concepts": set()}
    product = input_record.get("product") if isinstance(input_record, dict) else None
    model_id = product.get("model_id") if isinstance(product, dict) else None
    if isinstance(execution, dict):
        declarations = [execution.get("output"), execution.get("rejected_output")]
        for call in execution.get("model_calls", []) if isinstance(execution.get("model_calls"), list) else []:
            data = call.get("data") if isinstance(call, dict) else None
            if isinstance(data, dict):
                declarations.append(data.get("result"))
        for declaration in declarations:
            if not isinstance(declaration, dict):
                continue
            for collection, definition in (("needs", "Need"), ("gaps", "Gap"), ("concepts", "Concept")):
                items = declaration.get(collection)
                for item in items[:100] if isinstance(items, list) else []:
                    if (not isinstance(item, dict) or model_id is None
                            or collection != "concepts" and item.get("model_id") != model_id):
                        continue
                    try:
                        validate(definition, item)
                    except ValidationError:
                        continue
                    if not set(item["evidence_ids"]) <= evidence_ids:
                        continue
                    # Concept has no model_id in the shared contract. Its scope
                    # is the already authorized Gap graph and original sources.
                    if collection == "concepts" and not set(item["gap_ids"]) <= entities["gaps"]:
                        continue
                    entities[collection].add(item["id"])

    def diagnostic_error(value):
        code = value.get("code") if isinstance(value, dict) else None
        projected = public_error(code if isinstance(code, str) else "CONTRACT_MISMATCH")["error"]
        details = public_validation_details(value, evidence_ids, entities) if isinstance(value, dict) else {}
        if details:
            projected["details"] = details
        return projected

    def diagnostics(value):
        if isinstance(value, list):
            return [diagnostics(item) for item in value]
        if isinstance(value, dict):
            if "code" in value and "message" in value:
                return diagnostic_error(value)
            return {key: diagnostics(item) for key, item in value.items()
                    if key != "rejected_execution"}
        return value

    if isinstance(output, dict) and isinstance(output.get("planning_execution"), dict):
        execution = output["planning_execution"]
        # Only diagnostic fields are projected: source text, versions, input,
        # checked judgement, decision and model provenance are not rewritten.
        for key in ("trace", "model_calls"):
            if key in execution:
                execution[key] = diagnostics(execution[key])
        errors = execution.get("errors", [])
        execution["errors"] = [
            diagnostic_error(item)
            for item in (errors if isinstance(errors, list) else [errors])
        ]
        execution.pop("rejected_execution", None)
    return result


def error_status(error: DomainError) -> int:
    return {
        "UNAUTHORIZED": 401,
        "FORBIDDEN": 403,
        "NOT_FOUND": 404,
        "INVALID_MODEL_ID": 404,
        "INVALID_DOCUMENT_VERSION": 404,
        "INVALID_EVIDENCE_ID": 404,
        "DATASET_MISMATCH": 409,
        "NOT_IMPLEMENTED": 501,
    }.get(error.code, 422)


def _load_document_store(path: Path, expected_sha256: str):
    """Pin public canonical snapshot bytes before creating the workspace DB."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("An exact document dataset SHA256 is required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Document dataset SHA256 mismatch")

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate document dataset field")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("Non-finite document dataset value")

    dataset = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                         parse_constant=invalid_constant)
    if not isinstance(dataset, dict):
        raise TypeError("Document dataset must be an object")
    # Import after this module has initialized: the legacy document CLI uses
    # create_workspace_app from here and must keep its existing entry point.
    from lgax_core.document_workspace import WorkspaceDocumentStore

    store = WorkspaceDocumentStore(dataset)
    workspace_bootstrap(store)  # Public-only canonical entities and shared wire contract.
    return store


def create_workspace_app(db_path: Path, registry: TokenRegistry, *,
                         planning_runner: PlanningRunner | None = None,
                         evidence_store: DemoStore | None = None,
                         trend_collector: TrendCollector | None = None,
                         research_workspace: ResearchWorkspace | None = None) -> FastAPI:
    evidence = default_store() if evidence_store is None else evidence_store
    workspace = WorkspaceStore(db_path, evidence_store=evidence, planning_runner=planning_runner)
    trends = WorkspaceTrends(workspace, trend_collector)
    app = FastAPI(title="LG AX authenticated local workspace", version=CONTRACT_VERSION)
    app.state.workspace = workspace
    app.state.review_trends = trends
    app.state.research_workspace = research_workspace
    app.include_router(research_router(research_workspace))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ORIGINS),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-LGAX-Client"],
        allow_credentials=False,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def access(request: Request, call_next):
        if request.headers.get("origin") is not None and request.headers["origin"] not in ORIGINS:
            return JSONResponse(
                status_code=403,
                content=public_error("FORBIDDEN"), headers={"Cache-Control": "no-store"},
            )
        if request.method != "OPTIONS" and request.url.path.startswith(("/api/workspace", "/api/research")):
            try:
                request.state.principal = registry.authenticate(request.headers.get("authorization"))
                if request.method != "GET":
                    request.state.principal.require_write()
            except DomainError as error:
                return JSONResponse(status_code=error_status(error), content=public_error(error.code),
                                    headers={"Cache-Control": "no-store"})
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 -- HTTP boundary must hide private storage/adapter diagnostics.
            return JSONResponse(status_code=500, content=public_error("CONNECTION_FAILED"),
                                headers={"Cache-Control": "no-store"})
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return JSONResponse(status_code=error_status(error), content=public_error(error.code))

    @app.exception_handler(ValidationError)
    async def schema_error(request: Request, error: ValidationError):
        return JSONResponse(
            status_code=422,
            content=DomainError("INVALID_ARGUMENT", "공통 작업실 입력 규격을 확인해 주세요.").response(),
        )

    @app.exception_handler(RequestValidationError)
    async def argument_error(request: Request, error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=DomainError("INVALID_ARGUMENT", "작업실 요청 형식을 확인해 주세요.").response(),
        )

    def wrap(definition, data):
        if definition == "WorkspaceRunResponse":
            data = public_run(data)
        elif definition == "WorkspaceRunsResponse":
            data = {**data, "runs": [public_run(snapshot) for snapshot in data["runs"]]}
        result = {"ok": True, "data": data}
        try:
            validate(definition, result)
        except ValidationError as error:
            raise DomainError("CONTRACT_MISMATCH", _ERROR_MESSAGES["CONTRACT_MISMATCH"]) from error
        return result

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "contract_version": CONTRACT_VERSION,
            "authentication": "required",
            "access_boundary": "loopback-only",
            "analysis_implemented": planning_runner is not None,
            "planning_enabled": planning_runner is not None,
            "research_connected": research_workspace is not None,
            "research_planning_enabled": research_workspace is not None and research_workspace.planner is not None,
        }

    @app.get("/api/workspace/projects")
    def projects(request: Request):
        principal = request.state.principal
        return wrap(
            "WorkspaceProjectsResponse",
            {
                "projects": workspace.list_projects(principal.id, admin=principal.admin),
                "contract_version": CONTRACT_VERSION,
            },
        )

    @app.get("/api/workspace/bootstrap")
    def bootstrap(request: Request):
        # The middleware authenticates GET and returns no-store responses.
        # Do not expose this source store through the synthetic public API.
        return workspace_bootstrap(evidence)

    @app.post("/api/workspace/projects", status_code=201)
    def create_project(request: Request, payload: Annotated[dict, Body()]):
        validate("WorkspaceProjectCreateRequest", payload)
        return wrap(
            "WorkspaceProjectResponse",
            workspace.create_project(
                payload["name"], payload["request"], request.state.principal.id, payload["document_versions"]
            ),
        )

    @app.get("/api/workspace/projects/{project_id}")
    def project(request: Request, project_id: str):
        principal = request.state.principal
        return wrap(
            "WorkspaceProjectResponse", workspace.get_project(project_id, principal.id, admin=principal.admin)
        )

    @app.post("/api/workspace/projects/{project_id}/runs", status_code=201)
    def create_run(request: Request, project_id: str, payload: Annotated[dict, Body()]):
        validate("WorkspaceRunCreateRequest", payload)
        client = request.headers.get("x-lgax-client", "api")
        if client not in {"api", "web", "mcp", "skill"}:
            raise DomainError("INVALID_ARGUMENT", "작업실 클라이언트 종류를 확인해 주세요.")
        principal = request.state.principal
        return wrap(
            "WorkspaceRunResponse",
            workspace.create_run(
                project_id,
                payload["request"],
                principal.id,
                client,
                previous_run_id=payload["previous_run_id"],
                unconfirmed=payload["unconfirmed"],
                admin=principal.admin,
            ),
        )

    @app.get("/api/workspace/projects/{project_id}/runs")
    def runs(request: Request, project_id: str):
        principal = request.state.principal
        return wrap(
            "WorkspaceRunsResponse",
            {
                "runs": workspace.list_runs(project_id, principal.id, admin=principal.admin),
                "contract_version": CONTRACT_VERSION,
            },
        )

    @app.get("/api/workspace/runs/{run_id}")
    def run(request: Request, run_id: str):
        principal = request.state.principal
        return wrap("WorkspaceRunResponse", workspace.get_run(run_id, principal.id, admin=principal.admin))

    @app.get("/api/workspace/projects/{project_id}/evidence")
    def search(
        request: Request,
        project_id: str,
        q: str = Query(min_length=1, max_length=500),
        model_id: str = Query(min_length=1, max_length=100),
        limit: int = Query(10, ge=1, le=50),
    ):
        principal = request.state.principal
        snapshot = workspace.get_project(project_id, principal.id, admin=principal.admin)
        if snapshot["dataset_sha256"] != workspace.dataset_sha256:
            raise DomainError(
                "DATASET_MISMATCH", "프로젝트 생성 이후 자료가 변경됐습니다. 새 프로젝트에서 확인해 주세요."
            )
        if model_id not in snapshot["document_versions"]:
            raise DomainError("INVALID_ARGUMENT", "프로젝트에 선택된 모델만 조회할 수 있습니다.")
        result = evidence.search_evidence(q, model_id, snapshot["document_versions"][model_id], limit)
        return wrap(
            "WorkspaceEvidenceResponse",
            {
                "project_id": project_id,
                "dataset_sha256": snapshot["dataset_sha256"],
                "search": result,
                "contract_version": CONTRACT_VERSION,
            },
        )

    @app.get("/api/workspace/projects/{project_id}/review-trends")
    def review_trends(
        request: Request, project_id: str,
        model_id: str, dataset_version: str, start_date: str, end_date_exclusive: str,
        source_kind: str, source_ids: Annotated[list[str], Query(min_length=1, max_length=50)],
        granularity: str = "month", timezone: str = "Asia/Seoul",
        topic_ids: Annotated[list[str] | None, Query(max_length=50)] = None,
    ):
        principal = request.state.principal
        filters = {"project_id": project_id, "model_id": model_id, "source_ids": source_ids,
                   "dataset_version": dataset_version, "start_date": start_date,
                   "end_date_exclusive": end_date_exclusive, "source_kind": source_kind,
                   "granularity": granularity, "timezone": timezone, "topic_ids": topic_ids or []}
        return wrap("WorkspaceReviewTrendResponse", {
            "aggregate": trends.collect(project_id, filters, principal.id, admin=principal.admin),
            "contract_version": CONTRACT_VERSION,
        })

    @app.get("/api/workspace/projects/{project_id}/review-trends/{aggregate_id}")
    def get_review_trends(request: Request, project_id: str, aggregate_id: str):
        principal = request.state.principal
        return wrap("WorkspaceReviewTrendResponse", {
            "aggregate": trends.get(project_id, aggregate_id, principal.id, admin=principal.admin),
            "contract_version": CONTRACT_VERSION,
        })

    @app.get("/api/workspace/projects/{project_id}/review-trends/{aggregate_id}/evidence")
    def trend_evidence(request: Request, project_id: str, aggregate_id: str,
                       bucket_id: str, topic_id: str,
                       offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=50)):
        principal = request.state.principal
        return wrap("WorkspaceTrendEvidenceResponse", {
            **trends.evidence(project_id, aggregate_id, bucket_id, topic_id, principal.id,
                              offset=offset, limit=limit, admin=principal.admin),
            "contract_version": CONTRACT_VERSION,
        })

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, help="Trusted server-side synthetic dataset; never a request field.")
    parser.add_argument("--document-dataset", type=Path,
                        help="Trusted server-side public document snapshot; never an upload or request field.")
    parser.add_argument("--document-dataset-sha256",
                        help="Exact SHA256 of the document snapshot file bytes, required with its path.")
    parser.add_argument("--trend-metadata", type=Path,
                        help="Explicit server-side sidecar file; never an HTTP/MCP upload or request field.")
    parser.add_argument("--trend-metadata-sha256",
                        help="Exact SHA256 of the sidecar file bytes, distinct from annotation_sha256.")
    parser.add_argument("--allow-candidate-trend-metadata", action="store_true",
                        help="Preview pinned synthetic topic candidates only; does not approve customer data.")
    parser.add_argument("--enable-planning", action="store_true",
                        help="Explicitly allow configured model calls when an authorized run is submitted.")
    parser.add_argument("--research-bundle", action="append", type=Path, default=[],
                        help="Operator-selected actual public ResearchBundle; may be repeated.")
    parser.add_argument("--enable-research-planning", action="store_true",
                        help="Allow manual research planning requests with the configured LG model.")
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18869)
    args = parser.parse_args()
    if args.enable_research_planning and not args.research_bundle:
        parser.error("Actual research bundles are required for research planning.")
    if (args.document_dataset is None) != (args.document_dataset_sha256 is None):
        parser.error("A document dataset path and its exact SHA256 are required together.")
    if args.document_dataset is not None and any((
            args.dataset is not None, args.trend_metadata is not None,
            args.trend_metadata_sha256 is not None, args.allow_candidate_trend_metadata)):
        parser.error("Public document snapshots cannot be combined with synthetic dataset/trend options.")
    try:
        if args.document_dataset is not None:
            evidence = _load_document_store(args.document_dataset, args.document_dataset_sha256)
            collector = None
        else:
            runtime = load_trend_runtime(dataset_path=args.dataset, metadata_path=args.trend_metadata,
                                         metadata_sha256=args.trend_metadata_sha256,
                                         allow_candidate=args.allow_candidate_trend_metadata)
            evidence, collector = runtime.evidence_store, runtime.collector
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, ValidationError, DomainError):
        parser.error("Invalid server-side dataset/sidecar configuration; verify hashes and candidate preview scope.")
    uvicorn.run(
        create_workspace_app(args.db, TokenRegistry.from_file(args.credentials),
                             evidence_store=evidence, trend_collector=collector,
                             planning_runner=EnvPlanningRunner() if args.enable_planning else None,
                             research_workspace=ResearchWorkspace(
                                 args.db.with_name(args.db.stem + ".research.sqlite3"), args.research_bundle,
                                 EnvResearchPlanner() if args.enable_research_planning else None,
                             ) if args.research_bundle else None),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
