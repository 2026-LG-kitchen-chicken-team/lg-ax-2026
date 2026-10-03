"""Authenticated loopback workspace API; separate from the public evidence demo."""

import argparse
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
from lgax_core.store import default_store
from lgax_core.workspace import WorkspaceStore
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .workspace_auth import TokenRegistry

ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


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


def create_workspace_app(db_path: Path, registry: TokenRegistry) -> FastAPI:
    evidence = default_store()
    workspace = WorkspaceStore(db_path, evidence_store=evidence)
    app = FastAPI(title="LG AX authenticated local workspace", version=CONTRACT_VERSION)
    app.state.workspace = workspace
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
                content=DomainError("FORBIDDEN", "허용되지 않은 작업실 출처입니다.").response(),
            )
        if request.method != "OPTIONS" and request.url.path.startswith("/api/workspace"):
            try:
                request.state.principal = registry.authenticate(request.headers.get("authorization"))
                if request.method != "GET":
                    request.state.principal.require_write()
            except DomainError as error:
                return JSONResponse(status_code=error_status(error), content=error.response())
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return JSONResponse(status_code=error_status(error), content=error.response())

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
        result = {"ok": True, "data": data}
        validate(definition, result)
        return result

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "contract_version": CONTRACT_VERSION,
            "authentication": "required",
            "access_boundary": "loopback-only",
            "analysis_implemented": False,
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

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18869)
    args = parser.parse_args()
    uvicorn.run(
        create_workspace_app(args.db, TokenRegistry.from_file(args.credentials)),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
