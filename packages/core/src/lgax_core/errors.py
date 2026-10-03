"""Stable application failures: invalid identifiers differ from valid empty searches."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def response(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": self.message, "details": self.details}}


def not_implemented() -> dict[str, Any]:
    return DomainError(
        "NOT_IMPLEMENTED",
        "상품기획 분석·콘셉트 생성·검사·수정 Agent는 아직 구현되지 않았습니다.",
        {"implemented": ["list_products", "search_evidence", "get_evidence"], "phase": "bootstrap"},
    ).response()
