"""Explicit local workspace credentials; secrets never become response/log fields."""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path

from lgax_core.errors import DomainError


@dataclass(frozen=True)
class Principal:
    id: str
    role: str

    @property
    def admin(self) -> bool:
        return self.role == "admin"

    def require_write(self) -> None:
        if self.role == "viewer":
            raise DomainError("FORBIDDEN", "읽기 권한으로는 기록을 변경할 수 없습니다.")


class TokenRegistry:
    def __init__(self, entries: list[dict]):
        if not entries:
            raise ValueError("At least one workspace credential is required")
        self._entries = []
        used = set()
        for entry in entries:
            if set(entry) != {"principal_id", "role", "token_sha256"}:
                raise ValueError("Invalid workspace credential configuration")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", entry["principal_id"]):
                raise ValueError("Invalid principal identifier")
            if entry["role"] not in {"admin", "editor", "viewer"}:
                raise ValueError("Invalid workspace role")
            digest = entry["token_sha256"]
            if not re.fullmatch(r"[a-f0-9]{64}", digest) or digest in used:
                raise ValueError("Invalid or duplicate credential digest")
            used.add(digest)
            self._entries.append((digest, Principal(entry["principal_id"], entry["role"])))

    @classmethod
    def from_file(cls, path: Path) -> "TokenRegistry":
        value = json.loads(path.read_text("utf-8"))
        if set(value) != {"credentials"} or not isinstance(value["credentials"], list):
            raise ValueError("Invalid workspace credential file")
        return cls(value["credentials"])

    def authenticate(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise DomainError("UNAUTHORIZED", "작업실 인증이 필요합니다.")
        token = authorization[7:]
        if not 32 <= len(token) <= 256 or any(char.isspace() for char in token):
            raise DomainError("UNAUTHORIZED", "작업실 인증을 확인해 주세요.")
        candidate = sha256(token.encode("utf-8")).hexdigest()
        matched = None
        for digest, principal in self._entries:
            if compare_digest(candidate, digest):
                matched = principal
        if matched is None:
            raise DomainError("UNAUTHORIZED", "작업실 인증을 확인해 주세요.")
        return matched
