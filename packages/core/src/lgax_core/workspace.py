"""Append-only workspace snapshots; planning runs only through server opt-in."""

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import ValidationError
from lgax_contracts import CONTRACT_VERSION, validate

from .errors import DomainError
from .store import DemoStore
from .workspace_planning import PlanningRunner, build_planning_input, failed_execution, planning_run_fields

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")
_CLIENTS = {"web", "mcp", "skill", "api"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _created_at() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _invalid(field: str, message: str = "입력 값을 확인해 주세요.") -> DomainError:
    return DomainError("INVALID_ARGUMENT", message, {"field": field})


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise _invalid(field)
    return value


def _contract(definition: str, value: Any, field: str) -> None:
    try:
        validate(definition, value)
    except ValidationError as error:
        # ValidationError's default message can contain submitted input; do not expose it.
        raise _invalid(field, "공통 입력 규격에 맞지 않습니다.") from error


class WorkspaceStore:
    """SQLite project/run snapshots with per-operation connections and ownership checks.

    ``admin`` is a trusted service-layer privilege, never a claim to take from a request body.
    ``dataset_sha256`` hashes canonical UTF-8 JSON of DemoDataset (not file whitespace and
    not the transport-only ``contract_version`` field). Stored snapshots remain readable
    after the dataset changes; a new run against their old source scope is rejected.
    """

    def __init__(self, path: Path, evidence_store: DemoStore | None = None,
                 *, planning_runner: PlanningRunner | None = None):
        self.path = Path(path).resolve()
        if Path(path).name == ":memory:":
            raise _invalid("path", "영구 기록을 저장할 데이터베이스 파일이 필요합니다.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_store = evidence_store if evidence_store is not None else DemoStore()
        if planning_runner is not None and not callable(planning_runner):
            raise _invalid("planning_runner")
        self.planning_runner = planning_runner
        connection = self._open_connection()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS workspace_projects (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS workspace_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES workspace_projects(id),
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS workspace_projects_owner_created
                ON workspace_projects(owner_id, created_at, id)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS workspace_runs_project_created
                ON workspace_runs(project_id, created_at, id)
            """)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _dataset(self) -> tuple[dict[str, Any], str]:
        dataset = self.evidence_store.bootstrap()["data"]
        dataset.pop("contract_version")
        digest = hashlib.sha256(_json(dataset).encode("utf-8")).hexdigest()
        return dataset, digest

    @property
    def dataset_sha256(self) -> str:
        return self._dataset()[1]

    @staticmethod
    def _access(owner: str, actor: str, admin: bool) -> None:
        if not isinstance(admin, bool):
            raise _invalid("admin")
        if owner != actor and not admin:
            raise DomainError("FORBIDDEN", "이 작업 기록에 접근할 권한이 없습니다.")

    @staticmethod
    def _validate_snapshot(definition: str, snapshot: dict[str, Any]) -> None:
        validate(definition, snapshot)

    @staticmethod
    def _request(request: Any) -> dict[str, Any]:
        copied = deepcopy(request)
        _contract("PlanningRequest", copied, "request")
        for field in ("target_customer", "use_situation", "improvement_task", "dataset_version"):
            if not copied[field].strip():
                raise _invalid(field)
        return copied

    @staticmethod
    def _source_scope(
        request: dict[str, Any], document_versions: Any, dataset: dict[str, Any],
    ) -> dict[str, str]:
        if request["dataset_version"] != dataset["manifest"]["version"]:
            raise DomainError("DATASET_MISMATCH", "현재 자료 버전과 기획 요청의 자료 버전이 다릅니다.")
        products = {product["model_id"]: product for product in dataset["products"]}
        models = set(request["model_ids"])
        if any(model not in products or products[model]["product_group"] != request["product_group"]
               for model in models):
            raise _invalid("model_ids", "선택한 모델과 제품군이 현재 자료에 맞지 않습니다.")
        if not isinstance(document_versions, dict) or set(document_versions) != models:
            raise _invalid("document_versions", "선택한 모델 각각의 문서 버전이 필요합니다.")
        for model, version in document_versions.items():
            if not isinstance(version, str) or not version.strip():
                raise _invalid("document_versions")
            if not any(evidence["model_id"] == model and evidence["document_version"] == version
                       for evidence in dataset["evidence"]):
                raise _invalid("document_versions", "선택한 모델의 문서 버전이 현재 자료에 없습니다.")
        return deepcopy(document_versions)

    @staticmethod
    def _project_row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT owner_id, snapshot_json FROM workspace_projects WHERE id = ?", (project_id,),
        ).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "작업 기록을 찾을 수 없습니다.")
        return row

    @staticmethod
    def _run_row(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row:
        row = connection.execute("""
            SELECT runs.project_id, projects.owner_id, runs.snapshot_json
            FROM workspace_runs AS runs
            JOIN workspace_projects AS projects ON projects.id = runs.project_id
            WHERE runs.id = ?
        """, (run_id,)).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "작업 기록을 찾을 수 없습니다.")
        return row

    def create_project(
        self, name: str, request: dict[str, Any], owner_id: str, document_versions: dict[str, str],
    ) -> dict[str, Any]:
        actor = _identifier(owner_id, "owner_id")
        if not isinstance(name, str) or not name.strip() or len(name) > 500:
            raise _invalid("name")
        copied_request = self._request(request)
        dataset, digest = self._dataset()
        versions = self._source_scope(copied_request, document_versions, dataset)
        project = {"id": f"project-{uuid4().hex}", "name": name, "request": copied_request,
                   "status": "draft", "dataset_version": copied_request["dataset_version"]}
        _contract("Project", project, "project")
        snapshot = {"project": project, "owner_id": actor, "document_versions": versions,
                    "created_at": _created_at(), "dataset_sha256": digest}
        self._validate_snapshot("WorkspaceProjectSnapshot", snapshot)
        with self._connection(write=True) as connection:
            connection.execute(
                "INSERT INTO workspace_projects (id, owner_id, created_at, snapshot_json) VALUES (?, ?, ?, ?)",
                (project["id"], actor, snapshot["created_at"], _json(snapshot)),
            )
        return deepcopy(snapshot)

    def list_projects(self, owner_id: str, admin: bool = False) -> list[dict[str, Any]]:
        actor = _identifier(owner_id, "owner_id")
        self._access(actor, actor, admin)
        with self._connection() as connection:
            if admin:
                rows = connection.execute(
                    "SELECT snapshot_json FROM workspace_projects ORDER BY created_at, id",
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT snapshot_json FROM workspace_projects WHERE owner_id = ? ORDER BY created_at, id",
                    (actor,),
                ).fetchall()
        return [json.loads(row["snapshot_json"]) for row in rows]

    def get_project(self, project_id: str, owner_id: str, admin: bool = False) -> dict[str, Any]:
        project_id = _identifier(project_id, "project_id")
        actor = _identifier(owner_id, "owner_id")
        with self._connection() as connection:
            row = self._project_row(connection, project_id)
            self._access(row["owner_id"], actor, admin)
            return json.loads(row["snapshot_json"])

    def create_run(
        self, project_id: str, request: dict[str, Any], owner_id: str, client: str,
        previous_run_id: str | None = None, unconfirmed: list[str] | None = None, admin: bool = False,
    ) -> dict[str, Any]:
        project_id = _identifier(project_id, "project_id")
        actor = _identifier(owner_id, "owner_id")
        if not isinstance(client, str) or client not in _CLIENTS:
            raise _invalid("client")
        if previous_run_id is not None:
            previous_run_id = _identifier(previous_run_id, "previous_run_id")
        uncertainties = deepcopy(unconfirmed) if unconfirmed is not None else []
        if (not isinstance(uncertainties, list)
                or any(not isinstance(item, str) or not item.strip() for item in uncertainties)
                or len(set(uncertainties)) != len(uncertainties)):
            raise _invalid("unconfirmed")
        def checked_context(connection):
            project_row = self._project_row(connection, project_id)
            self._access(project_row["owner_id"], actor, admin)
            project_snapshot = json.loads(project_row["snapshot_json"])
            copied_request = self._request(request)
            dataset, digest = self._dataset()
            if project_snapshot["dataset_sha256"] != digest:
                raise DomainError("DATASET_MISMATCH", "자료가 변경되어 기존 프로젝트에 실행을 추가할 수 없습니다.")
            source_request = project_snapshot["project"]["request"]
            if (copied_request["product_group"] != source_request["product_group"]
                    or set(copied_request["model_ids"]) != set(source_request["model_ids"])):
                raise _invalid("request", "프로젝트의 제품군과 검토 모델 범위를 유지해 주세요.")
            versions = self._source_scope(copied_request, project_snapshot["document_versions"], dataset)
            revision = int(copied_request != source_request)
            if previous_run_id is not None:
                previous_row = self._run_row(connection, previous_run_id)
                self._access(previous_row["owner_id"], actor, admin)
                if previous_row["project_id"] != project_id:
                    raise _invalid("previous_run_id", "이전 실행은 같은 프로젝트의 기록이어야 합니다.")
                previous = json.loads(previous_row["snapshot_json"])
                if previous["dataset_sha256"] != digest or previous["document_versions"] != versions:
                    raise DomainError("DATASET_MISMATCH", "이전 실행과 현재 자료 범위가 다릅니다.")
                revision = previous["request_revision"] + int(copied_request != previous["request"])
            return copied_request, digest, versions, revision

        # Authenticate and pin parent/source before any potentially costly model call.
        with self._connection() as connection:
            copied_request, digest, versions, revision = checked_context(connection)
        missing_agent = "상품기획 Agent 분석·콘셉트 생성·검사·수정은 아직 구현되지 않았습니다."
        fields = {
            "status": "not_implemented", "stage": "plan", "revision_count": 0, "max_revisions": 2,
            "concepts": [], "unresolved": list(dict.fromkeys([*uncertainties, missing_agent])), "evidence_ids": [],
            "events": [{"stage": "plan", "summary": "기획 요청과 자료 범위를 저장했습니다. 분석은 실행하지 않았습니다.",
                        "tool": None, "evidence_ids": []}],
        }
        output = None
        if self.planning_runner is not None:
            payload = build_planning_input(copied_request, versions, self.evidence_store)
            execution = None
            try:
                execution = self.planning_runner(deepcopy(copied_request), deepcopy(versions), self.evidence_store)
                fields, output = planning_run_fields(execution, payload)
                _json(output)
            except Exception:  # noqa: BLE001 -- Untrusted adapter details must not escape the stored failure boundary.
                kind = execution.get("execution_kind") if isinstance(execution, dict) else None
                fallback = failed_execution(payload, "CONTRACT_MISMATCH" if execution is not None
                                            else "MODEL_UNAVAILABLE",
                                            execution_kind=kind if kind in {"fixture", "live_model"}
                                            else "live_model")
                if execution is not None:
                    try:
                        _json(execution)
                        fallback["rejected_execution"] = deepcopy(execution)
                    except (TypeError, ValueError, RecursionError):
                        fallback["rejected_execution_omitted"] = "non_json_execution"
                fields, output = planning_run_fields(fallback, payload)
            fields["unresolved"] = list(dict.fromkeys([*uncertainties, *fields["unresolved"]]))
        run = {
            "id": f"run-{uuid4().hex}", "project_id": project_id,
            "dataset_version": copied_request["dataset_version"], "contract_version": CONTRACT_VERSION,
            **fields,
        }
        _contract("Run", run, "run")
        snapshot = {
            "run": run, "request": copied_request, "previous_run_id": previous_run_id,
            "request_revision": revision, "actor_id": actor, "client": client,
            "created_at": _created_at(), "document_versions": versions, "dataset_sha256": digest,
            "unconfirmed": uncertainties, "output": output,
        }
        self._validate_snapshot("WorkspaceRunSnapshot", snapshot)
        # No model call occurs within this short SQLite write transaction.
        with self._connection(write=True) as connection:
            if checked_context(connection) != (copied_request, digest, versions, revision):
                raise DomainError("DATASET_MISMATCH", "판단 중 요청 또는 자료 범위가 변경됐습니다.", {})
            connection.execute(
                "INSERT INTO workspace_runs (id, project_id, created_at, snapshot_json) VALUES (?, ?, ?, ?)",
                (run["id"], project_id, snapshot["created_at"], _json(snapshot)),
            )
        return deepcopy(snapshot)

    def get_run(self, run_id: str, owner_id: str, admin: bool = False) -> dict[str, Any]:
        run_id = _identifier(run_id, "run_id")
        actor = _identifier(owner_id, "owner_id")
        with self._connection() as connection:
            row = self._run_row(connection, run_id)
            self._access(row["owner_id"], actor, admin)
            return json.loads(row["snapshot_json"])

    def list_runs(self, project_id: str, owner_id: str, admin: bool = False) -> list[dict[str, Any]]:
        project_id = _identifier(project_id, "project_id")
        actor = _identifier(owner_id, "owner_id")
        with self._connection() as connection:
            row = self._project_row(connection, project_id)
            self._access(row["owner_id"], actor, admin)
            rows = connection.execute(
                "SELECT snapshot_json FROM workspace_runs WHERE project_id = ? ORDER BY created_at, id",
                (project_id,),
            ).fetchall()
        return [json.loads(row["snapshot_json"]) for row in rows]
