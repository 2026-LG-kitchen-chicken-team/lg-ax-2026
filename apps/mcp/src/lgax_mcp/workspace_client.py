"""Private workspace proxy: web/MCP share one owner-checked server and database."""

import json
import re
from urllib.parse import urlparse

import httpx
from jsonschema import ValidationError
from lgax_contracts import validate
from lgax_contracts.research import validate_research
from lgax_core.errors import DomainError
from lgax_core.guides import build_official_reference_guide, render_guide_html, render_guide_markdown


def _validate_research_guide(result):
    fields = {"bundle_id", "bundle_sha256", "source_ids", "guide", "markdown", "html"}
    if (not isinstance(result, dict) or set(result) != fields
            or not isinstance(result["bundle_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", result["bundle_id"])
            or not isinstance(result["bundle_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", result["bundle_sha256"])
            or not isinstance(result["source_ids"], list) or not result["source_ids"]
            or any(not isinstance(value, str) for value in result["source_ids"])
            or len(result["source_ids"]) != len(set(result["source_ids"]))
            or not isinstance(result["guide"], dict)
            or not isinstance(result["markdown"], str) or not isinstance(result["html"], str)):
        raise ValidationError("Invalid official reference export")
    guide = result["guide"]
    sources = guide.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValidationError("Official reference sources are required")
    for source in sources:
        validate_research("ResearchSource", source)
    if [source["source_id"] for source in sources] != result["source_ids"]:
        raise ValidationError("Official reference selection differs from exported sources")
    bundle = {
        "schema_version": "1.0", "bundle_id": result["bundle_id"],
        "product_group": sources[0]["product_group"], "analysis_scope": "product_group",
        "sources": sources, "collection_manifest": {},
    }
    try:
        expected = build_official_reference_guide(bundle, result["source_ids"])
    except (ValueError, TypeError) as error:
        raise ValidationError("Invalid official reference role or scope") from error
    if (guide != expected or result["markdown"] != render_guide_markdown(expected)
            or result["html"] != render_guide_html(expected)):
        raise ValidationError("Official reference render differs from preserved source objects")


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
            if definition in {"ResearchBundle", "PlanningBrief"}:
                validate_research(definition, result)
            elif definition == "ResearchGuide":
                _validate_research_guide(result)
            elif definition == "ResearchBundleList":
                if not isinstance(result, dict) or not isinstance(result.get("bundles"), list):
                    raise ValidationError("Invalid research bundle list")
                for item in result["bundles"]:
                    if (not isinstance(item, dict) or not isinstance(item.get("bundle_id"), str)
                            or not isinstance(item.get("source_count"), int)
                            or not isinstance(item.get("review_count"), int)
                            or not 0 <= item["review_count"] <= item["source_count"]):
                        raise ValidationError("Invalid research bundle summary")
            else:
                validate(definition, result)
        except ValidationError:
            raise DomainError("CONTRACT_MISMATCH", "작업실 응답이 공통 규격과 다릅니다.") from None
        return result

    def list_projects(self):
        return self._request("GET", "/api/workspace/projects", "WorkspaceProjectsResponse")

    def list_research_bundles(self):
        return self._request("GET", "/api/research/bundles", "ResearchBundleList")

    def get_research_bundle(self, bundle_id):
        self._identifier(bundle_id)
        return self._request("GET", f"/api/research/bundles/{bundle_id}", "ResearchBundle")

    def create_research_run(self, bundle_id, goal, constraints=None, previous_run_id=None,
                            review_feedback: list[dict] | None = None,
                            selected_source_ids: list[str] | None = None, bundle_sha256: str | None = None):
        self._identifier(bundle_id)
        if previous_run_id is not None:
            self._identifier(previous_run_id)
        payload = {"bundle_id": bundle_id, "goal": goal, "constraints": constraints or [],
                   "previous_run_id": previous_run_id}
        if review_feedback is not None:
            payload["review_feedback"] = review_feedback
        if selected_source_ids is not None:
            payload["selected_source_ids"] = selected_source_ids
        if bundle_sha256 is not None:
            payload["bundle_sha256"] = bundle_sha256
        return self._request("POST", "/api/research/planning-runs", "PlanningBrief", payload, timeout=600)

    def get_research_run(self, run_id):
        self._identifier(run_id)
        return self._request("GET", f"/api/research/planning-runs/{run_id}", "PlanningBrief")

    def create_research_guide(self, bundle_id, source_ids, bundle_sha256: str | None = None):
        self._identifier(bundle_id)
        payload = {"bundle_id": bundle_id, "source_ids": source_ids}
        if bundle_sha256 is not None:
            payload["bundle_sha256"] = bundle_sha256
        result = self._request("POST", "/api/research/guides", "ResearchGuide", payload)
        if (result["bundle_id"] != bundle_id or set(result["source_ids"]) != set(source_ids)
                or bundle_sha256 is not None and result["bundle_sha256"] != bundle_sha256):
            raise DomainError("CONTRACT_MISMATCH", "공식 참고자료의 선택·자료 버전이 다릅니다.")
        return result

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
