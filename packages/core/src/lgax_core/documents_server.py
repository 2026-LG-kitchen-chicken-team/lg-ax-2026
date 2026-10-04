"""Explicit local document endpoint; existing public/demo/workspace API remains unchanged."""

import argparse
import hmac
import json
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .documents import MAX_BYTES, DocumentRepository
from .errors import DomainError


def create_app(repository: DocumentRepository, token: str):
    if len(token) < 32:
        raise ValueError("Local document token must have at least 32 characters")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def authorize(request: Request, call_next):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + token):
            return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED"}}, status_code=401)
        if request.headers.get("origin") is not None:
            return JSONResponse({"ok": False, "error": {"code": "INVALID_ORIGIN"}}, status_code=403)
        return await call_next(request)

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        status = 404 if error.code in {"INVALID_DOCUMENT_ID", "INVALID_MODEL_ID", "INVALID_EVIDENCE_ID"} else 400
        return JSONResponse({"ok": False, "error": {"code": error.code, "message": error.message,
                                                    "details": error.details}}, status_code=status)

    @app.get("/health")
    def health():
        return {"ok": True, "scope": "local_document_registration", "analysis_implemented": False}

    @app.post("/api/documents/{document_id}")
    async def upload(document_id: str, request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise DomainError("INVALID_DOCUMENT", "PDF 허용 크기를 초과했습니다.", {})
        # Run the bounded extraction off the async event loop.
        from starlette.concurrency import run_in_threadpool
        record = await run_in_threadpool(repository.upload, document_id, bytes(data))
        return {"ok": True, "data": record}

    @app.get("/api/documents/{document_id}")
    def metadata(document_id: str):
        return {"ok": True, "data": repository.metadata(document_id)}

    @app.get("/api/documents/{document_id}/original")
    def original(document_id: str):
        return Response(repository.original(document_id), media_type="application/pdf")

    @app.get("/api/evidence/search")
    def search(q: str, model_id: str | None = None, document_version: str | None = None, limit: int = 10):
        return repository.store().search_evidence(q, model_id, document_version, limit)

    @app.get("/api/evidence/{evidence_id}")
    def evidence(evidence_id: str):
        return repository.store().get_evidence(evidence_id)

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--extractor-python", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18880)
    args = parser.parse_args()
    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    if not args.token_file.exists():
        args.token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    token = args.token_file.read_text(encoding="utf-8").strip()
    repository = DocumentRepository(args.directory, json.loads(args.plan.read_text(encoding="utf-8")),
                                    args.extractor_python)
    uvicorn.run(create_app(repository, token), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
