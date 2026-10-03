"""Public bootstrap API: only synthetic read-only evidence is exposed."""

import argparse

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from lgax_contracts import CONTRACT_VERSION, load_schema
from lgax_core.errors import DomainError, not_implemented
from lgax_core.store import default_store

app = FastAPI(title="LG AX synthetic evidence bootstrap", version=CONTRACT_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False,
)


@app.exception_handler(DomainError)
async def domain_error(request: Request, error: DomainError):
    status = 404 if error.code in {"INVALID_MODEL_ID", "INVALID_EVIDENCE_ID", "INVALID_DOCUMENT_VERSION"} else 422
    return JSONResponse(status_code=status, content=error.response())


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # Do not echo request bodies; future private uploads must not leak in error responses.
    return JSONResponse(status_code=422, content=DomainError(
        "INVALID_ARGUMENT", "요청 형식이 잘못되었습니다.",
        {"fields": [".".join(str(part) for part in e["loc"]) for e in error.errors()]},
    ).response())


@app.get("/health")
def health():
    default_store()
    return {"status": "ok", "phase": "bootstrap", "contract_version": CONTRACT_VERSION, "data": "synthetic-only", "analysis_implemented": False}


@app.get("/api/contract")
def contract():
    return load_schema()


@app.get("/api/bootstrap")
def bootstrap():
    return default_store().bootstrap()


@app.get("/api/products")
def products(product_group: str | None = None):
    return default_store().list_products(product_group)


@app.get("/api/evidence/search")
def search(q: str = Query(min_length=1, max_length=500), model_id: str | None = None,
           document_version: str | None = None, limit: int = Query(default=10, ge=1, le=50)):
    return default_store().search_evidence(q, model_id, document_version, limit)


@app.get("/api/evidence/{evidence_id}")
def evidence(evidence_id: str):
    return default_store().get_evidence(evidence_id)


@app.post("/api/planning-requests", status_code=501)
def planning_requests():
    return not_implemented()


def main():
    parser = argparse.ArgumentParser(description="Run synthetic read-only LG AX API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=18867, type=int)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
