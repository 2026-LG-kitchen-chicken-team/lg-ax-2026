"""Exact citations in preserved text pages; no PDF parsing or OCR is performed.

Canonical Locator has page/row/section, not end positions. The separate origin
record uses documents.py's page, start_char/end_char (zero-based, half-open),
sha256, text_sha256 and document_version. Optional end_row/paragraph_start/
paragraph_end constrain inclusive one-based physical lines or blank-line-delimited
paragraphs. ``section`` is a trusted label mapped to a page/character span at
capture time, never guessed from a heading. All supplied constraints must agree.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from jsonschema import ValidationError
from lgax_contracts import validate

from .errors import DomainError


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(code: str, message: str) -> None:
    raise DomainError(code, message, {})


def _integer(value, minimum=1) -> bool:
    return type(value) is int and value >= minimum


def _lines(text: str) -> list[tuple[int, int]]:
    """CRLF, CR and LF only; retain offsets and avoid Unicode splitlines surprises."""
    spans, start = [], 0
    for match in re.finditer(r"\r\n|\r|\n", text):
        spans.append((start, match.end()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _paragraphs(text: str) -> list[tuple[int, int]]:
    spans, start, end = [], None, 0
    for left, right in _lines(text):
        if text[left:right].strip():
            if start is None:
                start = left
            end = right
        elif start is not None:
            spans.append((start, end))
            start = None
    if start is not None:
        spans.append((start, end))
    return spans


@dataclass(frozen=True)
class SourceSnapshot:
    """Use capture_source to construct a detached, validated snapshot."""

    document_id: str
    model_id: str
    document_version: str
    source_kind: str
    sha256: str
    pages: tuple[str, ...]
    sections: tuple[tuple[str, int, int, int], ...]
    text_basis: str


def capture_source(
    original: bytes | bytearray,
    *,
    document_id: str,
    model_id: str,
    document_version: str,
    source_kind: str,
    pages: Sequence[str] | None = None,
    sections: Mapping[str, tuple[int, int, int]] | None = None,
) -> SourceSnapshot:
    """Capture scope and exact text. UTF-8/BOM text splits pages on form feed.

    With pages supplied, the caller MUST supply the trusted extraction of these
    same original bytes (e.g. documents.py's parsed pages). This API cannot prove
    PDF-to-text/OCR fidelity. It reports caller_supplied_extraction explicitly.
    Section values are (one-based page, zero-based start, exclusive end).
    Future verification requires current_original, so deletion/change is not
    hidden by a cached copy. No file paths or URLs are read.
    """
    if not isinstance(original, (bytes, bytearray)) or not original:
        _fail("INVALID_DOCUMENT", "원문 바이트가 필요합니다.")
    raw = bytes(original)
    try:
        validate("Evidence", {"id": "scope", "model_id": model_id,
                 "document_version": document_version, "source_kind": source_kind,
                 "source_type": "manual", "source_id": document_id,
                 "locator": {"page": 1}, "text": "scope", "feature_ids": []})
        if not document_version.strip():
            raise ValueError("empty version")
    except (ValidationError, ValueError) as error:
        raise DomainError("INVALID_ARGUMENT", "원문 식별·버전·자료 성격을 확인해 주세요.", {}) from error
    if pages is None:
        try:
            captured_pages = tuple(raw.decode("utf-8-sig", errors="strict").split("\f"))
        except UnicodeError as error:
            raise DomainError("INVALID_ENCODING", "UTF-8 원문 또는 신뢰된 추출 페이지가 필요합니다.", {}) from error
        basis = "utf8_original"
    else:
        if isinstance(pages, (str, bytes)):
            _fail("INVALID_ARGUMENT", "페이지 문자열의 목록이 필요합니다.")
        captured_pages = tuple(pages)
        basis = "caller_supplied_extraction"
    if not captured_pages or any(not isinstance(p, str) for p in captured_pages):
        _fail("INVALID_ARGUMENT", "페이지 문자열의 목록이 필요합니다.")
    captured_sections = []
    for label, span in (sections or {}).items():
        if not isinstance(label, str) or not label.strip() or not isinstance(span, (tuple, list)) or len(span) != 3:
            _fail("INVALID_LOCATOR", "절 위치 형식이 잘못됐습니다.")
        page, start, end = span
        if (not _integer(page) or page > len(captured_pages) or not _integer(start, 0)
                or not _integer(end) or not start < end <= len(captured_pages[page - 1])):
            _fail("INVALID_LOCATOR", "절 위치가 원문 범위를 벗어납니다.")
        captured_sections.append((label, page, start, end))
    return SourceSnapshot(document_id, model_id, document_version, source_kind,
                          _sha(raw), captured_pages, tuple(captured_sections), basis)


def verify_source_range(
    source: SourceSnapshot,
    evidence: Mapping,
    origin: Mapping,
    *,
    current_original: bytes | bytearray | None,
) -> dict:
    """Return a detached verification receipt or raise a specific DomainError.

    ``None`` means the preserved original is missing. The caller reads its own
    repository/file and passes current bytes; this function never trusts cached
    existence. Hash identifies original bytes, version identifies the document
    edition even when bytes happen to be identical. Text/offsets are exact: no
    whitespace folding, Unicode normalization, fuzzy matching or global fallback.
    Origin requires evidence_id, sha256, text_sha256, document_version and
    start_char/end_char. Page may come from either origin or canonical locator.
    """
    if current_original is None:
        _fail("SOURCE_MISSING", "보존 원문이 없습니다.")
    if not isinstance(current_original, (bytes, bytearray)):
        _fail("INVALID_ARGUMENT", "현재 원문 바이트가 필요합니다.")
    if _sha(bytes(current_original)) != source.sha256:
        _fail("SOURCE_CHANGED", "보존 원문 SHA256이 변경됐습니다.")
    try:
        validate("Evidence", evidence)
    except ValidationError as error:
        raise DomainError("INVALID_EVIDENCE", "근거가 현재 계약과 다릅니다.", {}) from error
    if not isinstance(origin, Mapping):
        _fail("INVALID_ORIGIN", "원문 위치 근거 객체가 필요합니다.")
    required = {"evidence_id", "sha256", "text_sha256", "document_version", "start_char", "end_char"}
    if not required <= origin.keys():
        _fail("INVALID_ORIGIN", "해시·버전·문자 범위 근거가 누락됐습니다.")
    if evidence["document_version"] != source.document_version or origin["document_version"] != source.document_version:
        _fail("VERSION_MISMATCH", "같은 내용이어도 다른 문서 버전입니다.")
    if (evidence["source_id"] != source.document_id or evidence["model_id"] != source.model_id
            or evidence["source_kind"] != source.source_kind or origin["evidence_id"] != evidence["id"]
            or origin.get("source_id", source.document_id) != source.document_id
            or origin.get("source_kind", source.source_kind) != source.source_kind):
        _fail("SOURCE_MISMATCH", "근거의 모델·출처·자료 성격이 다릅니다.")
    if origin["sha256"] != source.sha256:
        _fail("SOURCE_MISMATCH", "인용이 참조하는 원문 SHA256이 다릅니다.")
    text = evidence["text"]
    if origin["text_sha256"] != _sha(text.encode("utf-8")):
        _fail("TEXT_HASH_MISMATCH", "인용문 SHA256이 다릅니다.")
    locator = evidence["locator"]
    section = None
    if "section" in locator:
        section = next((s for s in source.sections if s[0] == locator["section"]), None)
        if section is None:
            _fail("INVALID_LOCATOR", "원문에 등록된 절 위치가 없습니다.")
    page = locator.get("page", origin.get("page", section[1] if section else 1))
    if (not _integer(page) or page > len(source.pages)
            or ("page" in origin and (not _integer(origin["page"]) or origin["page"] != page))
            or (section is not None and section[1] != page)):
        _fail("INVALID_LOCATOR", "페이지 위치가 원문 또는 다른 위치 조건과 다릅니다.")
    if len(source.pages) > 1 and "page" not in locator and "page" not in origin and section is None:
        _fail("INVALID_LOCATOR", "여러 페이지 원문에는 페이지 식별이 필요합니다.")
    page_text = source.pages[page - 1]
    start, end = origin["start_char"], origin["end_char"]
    if not _integer(start, 0) or not _integer(end) or not start < end <= len(page_text):
        _fail("INVALID_LOCATOR", "문자 범위가 원문 범위를 벗어납니다.")
    if section is not None and not section[2] <= start < end <= section[3]:
        _fail("INVALID_LOCATOR", "인용 문자 범위가 지정한 절 밖입니다.")
    if "end_row" in origin and "row" not in locator:
        _fail("INVALID_LOCATOR", "끝 행에는 시작 행이 필요합니다.")
    if "row" in locator:
        first, last = locator["row"], origin.get("end_row", locator["row"])
        lines = _lines(page_text)
        if (not _integer(first) or not _integer(last) or not first <= last <= len(lines)
                or not lines[first - 1][0] <= start < lines[first - 1][1]
                or not lines[last - 1][0] < end <= lines[last - 1][1]):
            _fail("INVALID_LOCATOR", "문자 범위와 실제 시작·끝 행이 다릅니다.")
    if "paragraph_start" in origin or "paragraph_end" in origin:
        first, last = origin.get("paragraph_start"), origin.get("paragraph_end")
        paragraphs = _paragraphs(page_text)
        if (not _integer(first) or not _integer(last) or not first <= last <= len(paragraphs)
                or not paragraphs[first - 1][0] <= start < paragraphs[first - 1][1]
                or not paragraphs[last - 1][0] < end <= paragraphs[last - 1][1]):
            _fail("INVALID_LOCATOR", "문자 범위와 실제 시작·끝 문단이 다릅니다.")
    if page_text[start:end] != text:
        _fail("QUOTE_MISMATCH", "인용문이 지정한 원문 범위와 정확히 일치하지 않습니다.")
    return {"verified": True, "evidence_id": evidence["id"], "source_id": source.document_id,
            "document_version": source.document_version, "source_kind": source.source_kind,
            "sha256": source.sha256, "text_sha256": origin["text_sha256"], "page": page,
            "start_char": start, "end_char": end, "text_basis": source.text_basis,
            "pdf_or_ocr_verified": False}
