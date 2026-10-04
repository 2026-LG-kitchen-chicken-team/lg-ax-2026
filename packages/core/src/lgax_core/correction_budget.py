"""Owner-held correction budget shared by stage retries and review_revision.

This primitive does not install a Skill or invoke a model. A run owner must pass
the same instance to both schedulers; creating it again would create a new budget.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock

from .errors import DomainError
from .judgement_contract import MAX_REVISIONS


class CorrectionBudget:
    """Atomically spend a correction before attempting it, with no refund/reset."""

    OPERATIONS = ("stage_retry", "review_revision")
    CLOSE_REASONS = ("hold", "backend_failure", "policy_changed", "unresolved")

    def __init__(self, *, initial_count: int = 0):
        # Nonzero input is only for an owner-verified existing run, never model text.
        if type(initial_count) is not int or not 0 <= initial_count <= MAX_REVISIONS:
            raise DomainError("INVALID_ARGUMENT", "수정 예산의 초기 회차가 유효하지 않습니다.", {})
        self._count = initial_count
        self._closed = initial_count == MAX_REVISIONS
        self._reason = "revision_limit" if self._closed else None
        self._attempts: list[dict] = []
        self._lock = RLock()

    @property
    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy({"revision_count": self._count, "max_revisions": MAX_REVISIONS,
                             "closed": self._closed, "terminal_reason": self._reason,
                             "attempts": self._attempts})

    def claim(self, *, expected_revision_count: int, operation: str) -> int:
        """Return the next count once; stale/terminal callers cannot run a correction."""
        if type(expected_revision_count) is not int or not 0 <= expected_revision_count <= MAX_REVISIONS:
            raise DomainError("INVALID_ARGUMENT", "수정 요청 회차가 유효하지 않습니다.", {})
        if operation not in self.OPERATIONS:
            raise DomainError("INVALID_ARGUMENT", "코드가 허용한 수정 경로만 사용할 수 있습니다.", {})
        with self._lock:
            if self._closed:
                raise DomainError("INSUFFICIENT_EVIDENCE", "수정 실행이 이미 종료됐습니다.",
                                  {"reason": self._reason, "revision_count": self._count})
            if expected_revision_count != self._count:
                raise DomainError("VALIDATION_FAILED", "이전 수정 회차를 다시 사용할 수 없습니다.",
                                  {"reason": "revision_counter_replay", "expected": self._count})
            self._count += 1
            self._attempts.append({"operation": operation, "revision_count": self._count})
            if self._count == MAX_REVISIONS:
                self._closed, self._reason = True, "revision_limit"
            return self._count

    def close(self, *, reason: str) -> None:
        """A hold or execution-policy failure ends the shared budget without a retry."""
        if reason not in self.CLOSE_REASONS:
            raise DomainError("INVALID_ARGUMENT", "종료 이유는 코드가 정한 값이어야 합니다.", {})
        with self._lock:
            if not self._closed:
                self._closed, self._reason = True, reason
