"""Private trend gateway: trusted collector injection and immutable source snapshots.

There is deliberately no default collector. Data #148 owns approved date/topic
annotations and aggregation; a disconnected backend returns NOT_IMPLEMENTED.
This gateway never accepts annotations, raw text or model instructions from HTTP.
"""

import hashlib
import json
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from jsonschema import ValidationError
from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.workspace import WorkspaceStore

from .trend_validation import canonical_annotation, validate_trend_collection, validate_trend_request


def canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class TrendCollection:
    """Server-trusted provider result; membership lists contain canonical Evidence IDs.

Every bucket uses ``__all__`` for its denominator, including unclassified reviews.
Other keys are topic IDs. These complete lists are independent of representative
IDs truncated to fifty in the aggregate and are saved for honest pagination.
"""

    aggregate: dict
    metadata: dict
    memberships: dict[str, dict[str, list[str]]]


TrendCollector = Callable[[dict, dict, dict], TrendCollection]


class WorkspaceTrends:
    def __init__(self, workspace: WorkspaceStore, collector: TrendCollector | None = None):
        if collector is not None and not callable(collector):
            raise ValueError("A server-side trend collector must be callable")
        self.workspace = workspace
        self.collector = collector
        with workspace._connection(write=True) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS workspace_review_trends (
                    aggregate_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES workspace_projects(id),
                    snapshot_json TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL
                )
            """)

    def collect(self, project_id: str, filters: dict, actor: str, *, admin: bool = False) -> dict:
        # Ownership is checked before source access, validation or provider execution.
        project = self.workspace.get_project(project_id, actor, admin=admin)
        dataset, digest = self.workspace._dataset()
        query = validate_trend_request(filters, project, dataset, digest)
        if query["project_id"] != project_id:
            raise DomainError("INVALID_INPUT", "작업실과 조회 조건이 다릅니다.")
        if self.collector is None:
            raise DomainError("NOT_IMPLEMENTED", "승인된 리뷰 동향 집계기가 아직 연결되지 않았습니다.")
        try:
            result = self.collector(deepcopy(project), deepcopy(dataset), deepcopy(query))
            if not isinstance(result, TrendCollection):
                raise DomainError("CONTRACT_MISMATCH", "동향 집계기의 반환 규격이 다릅니다.")
            aggregate = deepcopy(result.aggregate)
            metadata = deepcopy(result.metadata)
            memberships = deepcopy(result.memberships)
            if aggregate.get("filters") != query:
                raise DomainError("CONTRACT_MISMATCH", "동향 집계 조건이 요청과 다릅니다.")
            validate_trend_collection(aggregate, metadata, memberships, project, dataset, digest)
            metadata = canonical_annotation(metadata)
        except DomainError:
            raise
        except Exception as error:  # provider diagnostics must not cross the API boundary
            raise DomainError("CONTRACT_MISMATCH", "동향 집계 결과를 검증하지 못했습니다.") from error
        evidence_ids = {
            identifier
            for topics in memberships.values()
            for identifiers in topics.values()
            for identifier in identifiers
        }
        # Materialize source originals at acceptance, rather than reading a changed
        # live dataset when an older snapshot is requested after restart.
        evidence = {item["id"]: deepcopy(item) for item in dataset["evidence"] if item["id"] in evidence_ids}
        snapshot = {"aggregate": aggregate, "metadata": metadata,
                    "memberships": memberships, "evidence": evidence}
        raw = canonical(snapshot)
        checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self.workspace._connection(write=True) as connection:
            # A concurrent identical GET is idempotent; a different result with
            # the same source/version/filters identity is never overwritten.
            connection.execute(
                "INSERT OR IGNORE INTO workspace_review_trends VALUES (?, ?, ?, ?)",
                (aggregate["aggregate_id"], project_id, raw, checksum),
            )
            saved = connection.execute(
                "SELECT project_id, snapshot_json, snapshot_sha256 FROM workspace_review_trends "
                "WHERE aggregate_id = ?", (aggregate["aggregate_id"],),
            ).fetchone()
            if saved["project_id"] != project_id or saved["snapshot_json"] != raw or saved["snapshot_sha256"] != checksum:
                raise DomainError("CONTRACT_MISMATCH", "같은 동향 ID의 기존 결과를 변경할 수 없습니다.")
        return aggregate

    def _load(self, project_id: str, aggregate_id: str, actor: str, *, admin: bool = False) -> dict:
        self.workspace.get_project(project_id, actor, admin=admin)
        if not isinstance(aggregate_id, str) or not re.fullmatch(r"TREND-[0-9a-f]{64}", aggregate_id):
            raise DomainError("INVALID_INPUT", "동향 ID 형식을 확인해 주세요.")
        with self.workspace._connection() as connection:
            row = connection.execute(
                "SELECT snapshot_json, snapshot_sha256 FROM workspace_review_trends "
                "WHERE aggregate_id = ? AND project_id = ?", (aggregate_id, project_id),
            ).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "해당 작업실에 저장된 동향이 없습니다.")
        raw = row["snapshot_json"]
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row["snapshot_sha256"]:
            raise DomainError("CONTRACT_MISMATCH", "저장된 동향 무결성을 확인하지 못했습니다.")
        try:
            snapshot = json.loads(raw)
            validate("ReviewTrendAggregate", snapshot["aggregate"])
        except (ValidationError, ValueError, KeyError, TypeError) as error:
            raise DomainError("CONTRACT_MISMATCH", "저장된 동향 규격이 다릅니다.") from error
        if (snapshot["aggregate"]["project_id"] != project_id
                or snapshot["aggregate"]["aggregate_id"] != aggregate_id):
            raise DomainError("CONTRACT_MISMATCH", "저장된 동향의 작업실 범위가 다릅니다.")
        return snapshot

    def get(self, project_id: str, aggregate_id: str, actor: str, *, admin: bool = False) -> dict:
        return deepcopy(self._load(project_id, aggregate_id, actor, admin=admin)["aggregate"])

    def evidence(self, project_id: str, aggregate_id: str, bucket_id: str, topic_id: str,
                 actor: str, *, offset: int = 0, limit: int = 50, admin: bool = False) -> dict:
        snapshot = self._load(project_id, aggregate_id, actor, admin=admin)
        payload = {"project_id": project_id, "aggregate_id": aggregate_id,
                   "bucket_id": bucket_id, "topic_id": topic_id, "offset": offset, "limit": limit}
        try:
            validate("ReviewTrendEvidenceRequest", payload)
        except ValidationError as error:
            raise DomainError("INVALID_INPUT", "동향 원문 조회 조건을 확인해 주세요.") from error
        topics = snapshot["memberships"].get(bucket_id)
        if topics is None or topic_id == "__all__" or topic_id not in topics:
            raise DomainError("NOT_FOUND", "집계에 포함된 기간·주제만 조회할 수 있습니다.")
        identifiers = topics[topic_id]
        selected = identifiers[offset:offset + limit]
        return {**payload, "total": len(identifiers),
                "next_offset": offset + limit if offset + limit < len(identifiers) else None,
                "evidence": [deepcopy(snapshot["evidence"][identifier]) for identifier in selected]}
