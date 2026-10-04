"""Bearer-authenticated loopback controller; accepts inert approved work packets."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
from pathlib import Path

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from services.automation.state import ACCOUNTS, REPO, ControlError, Store, digest


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or not isinstance(config.get("database"), str):
        raise TypeError("private controller config requires database path")
    digests = config.get("token_digests")
    if (not isinstance(digests, dict) or "jeongiryang" not in digests or
            any(account not in ACCOUNTS or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                for account, value in digests.items())):
        raise ValueError("private config needs valid SHA256 token digests and authenticated PM")
    worker_digests = config.get("worker_token_digests", {})
    if not isinstance(worker_digests, dict) or any(account not in ACCOUNTS or not isinstance(value, str) or
                                                 not re.fullmatch(r"[0-9a-f]{64}", value)
                                                 for account, value in worker_digests.items()):
        raise ValueError("worker token digests must use registered identities and SHA256")
    all_digests = list(digests.values()) + list(worker_digests.values())
    if len(set(all_digests)) != len(all_digests):
        raise ValueError("team members cannot share controller credentials")
    return config


def github_enrollment_identity(github_token):
    if not isinstance(github_token, str) or not 20 <= len(github_token) <= 512 or any(c.isspace() for c in github_token):
        raise ControlError("valid private GitHub credential is required", 422)
    # Fixed destinations only. Disable environment proxies and redirects so the token cannot be redirected.
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False,
                      headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"}) as client:
        try:
            identity = client.get("https://api.github.com/user")
            repository = client.get(f"https://api.github.com/repos/{REPO}")
            if identity.status_code != 200 or repository.status_code != 200:
                raise ControlError("GitHub identity or repository permission verification failed", 403)
            account = identity.json().get("login")
            repo = repository.json()
        except (httpx.HTTPError, ValueError):
            raise ControlError("GitHub verification unavailable; no enrollment performed", 503) from None
    if account not in ACCOUNTS or account == "jeongiryang" or repo.get("full_name") != REPO or repo.get("permissions", {}).get("push") is not True:
        raise ControlError("enrollment requires registered team member GitHub Write access", 403)
    return account


def create_app(config_path=None, *, config=None, store=None, enrollment_verifier=None):
    if config is None:
        config_path = config_path or os.environ.get("LGAX_AUTOMATION_CONFIG")
        if not config_path:
            raise ValueError("private LGAX_AUTOMATION_CONFIG is required; no permissive fallback")
        config = load_config(config_path)
    if store is None:
        store = Store(config["database"], config)
    app = FastAPI(title="LG AX approved development queue", docs_url=None, redoc_url=None)
    app.state.store = store
    verifier = enrollment_verifier or github_enrollment_identity

    @app.exception_handler(ControlError)
    async def control_error(_request, exc):
        return JSONResponse(status_code=exc.status, content={"error": str(exc)})

    @app.middleware("http")
    async def bounded_request(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            # All supported clients send fixed JSON with length; no streaming upload surface.
            length = request.headers.get("content-length")
            if length is None or not length.isdecimal():
                return JSONResponse(status_code=411, content={"error": "bounded Content-Length required"})
            if int(length) > 65536:
                return JSONResponse(status_code=413, content={"error": "request exceeds 64 KiB"})
            if "application/json" not in request.headers.get("content-type", ""):
                return JSONResponse(status_code=415, content={"error": "JSON requests only"})
            if len(await request.body()) > 65536:
                return JSONResponse(status_code=413, content={"error": "request exceeds 64 KiB"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    class Principal(str):
        def __new__(cls, account, operator=False):
            obj = super().__new__(cls, account)
            obj.operator = operator
            return obj

    def actor(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise ControlError("private Bearer authentication required", 401)
        token = authorization[7:]
        if not 20 <= len(token) <= 256:
            raise ControlError("invalid Bearer credential", 401)
        candidate = digest(token)
        matched = None
        for account, registered_digest, operator in store.authentication_credentials():
            if hmac.compare_digest(candidate, registered_digest):
                matched = Principal(account, operator)
        if matched not in ACCOUNTS:
            raise ControlError("invalid Bearer credential", 401)
        return matched

    actor_dependency = Depends(actor)

    def pm_operator(account=actor_dependency):
        if account != "jeongiryang" or not account.operator:
            raise ControlError("PM operator credential required; worker token cannot administer", 403)
        return account

    operator_dependency = Depends(pm_operator)

    @app.get("/health")
    def health():
        return {"service": "lgax-automation", "ok": True}

    @app.post("/v1/enroll")
    def enroll(body: dict):
        if config.get("enable_github_enrollment") is not True:
            raise ControlError("member enrollment is disabled", 403)
        if set(body) != {"github_token"}:
            raise ControlError("enrollment accepts only the private GitHub token", 422)
        return store.enroll(verifier(body["github_token"]))

    @app.get("/v1/status")
    def status(account=actor_dependency):
        return store.status(account)

    @app.get("/v1/operator-status")
    def operator_status(account=actor_dependency):
        # Read-only authentication proof. PM Worker and PM operator credentials
        # must never be interchangeable just because their account name matches.
        return {"account": str(account), "operator": bool(account.operator)}

    @app.post("/v1/mode")
    def mode(body: dict, account=actor_dependency):
        if (body.get("member") is None or body.get("member") != account) and not account.operator:
            raise ControlError("PM operator credential required to change team/other member mode", 403)
        return store.mode(account, body.get("mode"), body.get("member"))

    @app.post("/v1/formal-snapshot")
    def formal_snapshot(body: dict, account=operator_dependency):
        return store.formal_snapshot(account, body)

    @app.post("/v1/jobs")
    def jobs(body: dict, account=operator_dependency):
        return store.register(account, body)

    @app.post("/v1/claim")
    def claim(body: dict, account=actor_dependency):
        if body:
            raise ControlError("claim identity is authenticated, not supplied in JSON", 422)
        return store.claim(account)

    @app.post("/v1/jobs/{job_id}/heartbeat")
    def heartbeat(job_id: str, body: dict, account=actor_dependency):
        return store.heartbeat(account, job_id, body.get("lease_token"))

    @app.post("/v1/jobs/{job_id}/authorize-publish")
    def authorize_publish(job_id: str, body: dict, account=actor_dependency):
        return store.authorize_publish(account, job_id, body.get("lease_token"))

    @app.post("/v1/jobs/{job_id}/finish")
    def finish(job_id: str, body: dict, account=actor_dependency):
        return store.finish(account, job_id, body)

    @app.post("/v1/jobs/{job_id}/reconcile")
    def reconcile(job_id: str, body: dict, account=operator_dependency):
        return store.reconcile(account, job_id, body)

    @app.post("/v1/reservations")
    def reserve(body: dict, account=actor_dependency):
        return store.reserve(account, body)

    @app.post("/v1/reservations/{reservation_id}/heartbeat")
    def reservation_heartbeat(reservation_id: str, body: dict, account=actor_dependency):
        return store.reservation_heartbeat(account, reservation_id, body.get("ttl_seconds", 1800))

    @app.delete("/v1/reservations/{reservation_id}")
    def release(reservation_id: str, account=actor_dependency):
        if account == "jeongiryang" and not account.operator:
            with store.transaction() as db:
                reservation = db.execute("SELECT owner FROM reservations WHERE id=?", (reservation_id,)).fetchone()
                if reservation and reservation[0] != account:
                    raise ControlError("PM worker cannot release another member's reservation", 403)
        return store.release(account, reservation_id)

    if config.get("model_gateway"):
        from services.automation.model_gateway import install_gateway

        install_gateway(app, config["model_gateway"], actor)

    return app


def main():
    parser = argparse.ArgumentParser(description="Run the inert PM-approved automation controller")
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1"))
    parser.add_argument("--port", type=int, default=18871)
    args = parser.parse_args()
    # Keep both request bodies and credentials out of process/access logs.
    uvicorn.run(create_app(args.config), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
