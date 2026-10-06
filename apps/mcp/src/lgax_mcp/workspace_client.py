"""Private workspace proxy: web/MCP share one owner-checked server and database."""

import json
from urllib.parse import urlparse

import httpx
from jsonschema import ValidationError
from lgax_contracts import validate
from lgax_core.errors import DomainError


class WorkspaceClient:
    def __init__(self, url: str, token: str, client_kind: str = "mcp", transport=None):
        parsed = urlparse(url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Workspace client requires an explicit loopback HTTP origin")
        if not 32 <= len(token) <= 256 or any(char.isspace() for char in token):
            raise ValueError("Workspace client requires a credential")
        if client_kind not in {"mcp", "web", "skill", "api"}:
            raise ValueError("Invalid workspace client kind")
        self._url, self._token, self._kind, self._transport = url.rstrip("/"), token, client_kind, transport

    def _request(self, method, path, definition, payload=None, params=None, *, timeout=15):
        try:
            with httpx.Client(
                base_url=self._url,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
                headers={"Authorization": f"Bearer {self._token}", "X-LGAX-Client": self._kind},
            ) as client:
                response = client.request(method, path, json=payload, params=params)
                if len(response.content) > 2_000_000:
                    raise DomainError("CONNECTION_FAILED", "작업실 응답 크기를 확인해 주세요.")
                result = response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            raise DomainError("CONNECTION_FAILED", "공통 작업실 서버에 연결할 수 없습니다.") from None
        if not response.is_success:
            if isinstance(result, dict) and isinstance(result.get("error"), dict):
                error = result["error"]
                raise DomainError(
                    str(error.get("code", "CONNECTION_FAILED")), str(error.get("message", "작업실 요청 실패"))
                )
            raise DomainError("CONNECTION_FAILED", "공통 작업실 서버 요청에 실패했습니다.")
        try:
            validate(definition, result)
        except ValidationError:
            raise DomainError("CONTRACT_MISMATCH", "작업실 응답이 공통 규격과 다릅니다.") from None
        return result

    def list_projects(self):
        return self._request("GET", "/api/workspace/projects", "WorkspaceProjectsResponse")

    def create_project(self, name, request, document_versions):
        payload = {"name": name, "request": request, "document_versions": document_versions}
        validate("WorkspaceProjectCreateRequest", payload)
        return self._request("POST", "/api/workspace/projects", "WorkspaceProjectResponse", payload)

    def get_project(self, project_id):
        self._identifier(project_id)
        return self._request("GET", f"/api/workspace/projects/{project_id}", "WorkspaceProjectResponse")

    def create_run(self, project_id, request, previous_run_id=None, unconfirmed=None):
        self._identifier(project_id)
        payload = {"request": request, "previous_run_id": previous_run_id, "unconfirmed": unconfirmed or []}
        validate("WorkspaceRunCreateRequest", payload)
        return self._request(
            "POST", f"/api/workspace/projects/{project_id}/runs", "WorkspaceRunResponse", payload,
            timeout=300,
        )

    def get_run(self, run_id):
        self._identifier(run_id)
        return self._request("GET", f"/api/workspace/runs/{run_id}", "WorkspaceRunResponse")

    def list_runs(self, project_id):
        self._identifier(project_id)
        return self._request("GET", f"/api/workspace/projects/{project_id}/runs", "WorkspaceRunsResponse")

    def search(self, project_id, q, model_id, limit=10):
        self._identifier(project_id)
        return self._request(
            "GET",
            f"/api/workspace/projects/{project_id}/evidence",
            "WorkspaceEvidenceResponse",
            params={"q": q, "model_id": model_id, "limit": limit},
        )

    @staticmethod
    def _identifier(value):
        import re

        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", value):
            raise DomainError("INVALID_ARGUMENT", "프로젝트/실행 ID 형식을 확인해 주세요.")

    def review_trends(self, filters):
        validate("ReviewTrendRequest", filters)
        self._identifier(filters["project_id"])
        params = {key: value for key, value in filters.items() if key != "project_id"}
        return self._request("GET", f"/api/workspace/projects/{filters['project_id']}/review-trends",
                             "WorkspaceReviewTrendResponse", params=params)

    def get_review_trends(self, project_id, aggregate_id):
        self._identifier(project_id)
        self._identifier(aggregate_id)
        return self._request("GET", f"/api/workspace/projects/{project_id}/review-trends/{aggregate_id}",
                             "WorkspaceReviewTrendResponse")

    def trend_evidence(self, project_id, aggregate_id, bucket_id, topic_id, offset=0, limit=50):
        payload = {"project_id": project_id, "aggregate_id": aggregate_id, "bucket_id": bucket_id,
                   "topic_id": topic_id, "offset": offset, "limit": limit}
        validate("ReviewTrendEvidenceRequest", payload)
        self._identifier(project_id)
        self._identifier(aggregate_id)
        return self._request("GET", f"/api/workspace/projects/{project_id}/review-trends/{aggregate_id}/evidence",
                             "WorkspaceTrendEvidenceResponse",
                             params={key: value for key, value in payload.items()
                                     if key not in {"project_id", "aggregate_id"}})
