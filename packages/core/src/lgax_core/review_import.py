"""Import new, bounded CSV reviews against a caller-approved product/source scope.

No I/O, formula evaluation, demo equality check, or registration side effects.
FIELDS is the existing review_csv wire format. ``row`` is the physical starting
line (header is line 1); embedded newlines count, including CRLF as one line.
Source approvals are document metadata with document_id, document_version,
source_kind and either model_id or product.model_id. An optional sha256 pins the
uploaded CSV bytes. Approval is supplied by the caller, never inferred from CSV.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from jsonschema import ValidationError
from lgax_contracts import validate

from .document_store import DocumentStore
from .errors import DomainError
from .review_csv import FIELDS, MAX_CSV_BYTES

MAX_REVIEW_ROWS = 10_000


@dataclass(frozen=True)
class ReviewImportResult:
    """Detached snapshot: each dataset/origins access returns a fresh JSON tree."""

    original: bytes
    _dataset_json: str
    _origins_json: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.original).hexdigest()

    @property
    def dataset(self) -> dict:
        return json.loads(self._dataset_json)

    @property
    def origins(self) -> list[dict]:
        return json.loads(self._origins_json)

    def store(self) -> DocumentStore:
        """A new canonical reader, isolated from inputs and other returned readers."""
        return DocumentStore(self.dataset)


def import_review_csv(
    data: bytes | bytearray,
    *,
    products: Sequence[Mapping],
    sources: Sequence[Mapping],
    dataset_version: str,
    max_bytes: int = MAX_CSV_BYTES,
    max_rows: int = MAX_REVIEW_ROWS,
    existing_review_ids: Iterable[str] = (),
    existing_evidence_ids: Iterable[str] = (),
) -> ReviewImportResult:
    """Parse new reviews atomically; raise DomainError without returning partial data.

    Limits may be lowered, not raised above the module caps. Identity fields are
    exact (padding is rejected); review text, quotes, formulas and newlines are
    preserved. The required wire row is checked, never trusted as a locator.
    Origins carry inclusive physical row/end_row and the original byte SHA256;
    canonical Review/Evidence carry only the unchanged ``locator.row`` field.
    """
    if (type(max_bytes) is not int or not 1 <= max_bytes <= MAX_CSV_BYTES
            or type(max_rows) is not int or not 1 <= max_rows <= MAX_REVIEW_ROWS):
        raise DomainError("INVALID_ARGUMENT", "CSV 한도 설정이 잘못됐습니다.", {})
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise DomainError("INVALID_DOCUMENT", "비어 있지 않은 CSV 바이트가 필요합니다.", {})
    if len(data) > max_bytes:
        raise DomainError("SIZE_LIMIT_EXCEEDED", "CSV 바이트 한도를 초과했습니다.", {})
    original = bytes(data)
    sha = hashlib.sha256(original).hexdigest()
    try:
        text = original.decode("utf-8-sig", errors="strict")
    except UnicodeError as error:
        raise DomainError("INVALID_ENCODING", "CSV는 UTF-8 또는 UTF-8 BOM이어야 합니다.", {}) from error
    if "\x00" in text:
        raise DomainError("INVALID_FIELD", "CSV에 NUL 문자가 있습니다.", {})
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise DomainError("INVALID_ARGUMENT", "자료 묶음 버전이 필요합니다.", {})
    # Detach before validation/indexing; DocumentStore's internal indexes must
    # never retain references to a caller's mutable approval dictionaries.
    approved_products = deepcopy(list(products))
    approved_sources = deepcopy(list(sources))
    product_map, source_map = {}, {}
    try:
        for product in approved_products:
            validate("Product", product)
            if product["model_id"] in product_map:
                raise ValueError("duplicate approved model")
            product_map[product["model_id"]] = product
        for source in approved_sources:
            did = source["document_id"]
            model = source.get("model_id", source.get("product", {}).get("model_id"))
            if did in source_map or model not in product_map:
                raise ValueError("duplicate source or unknown source model")
            product = product_map[model]
            if any(source[k] != product[k] for k in ("document_version", "source_kind")):
                raise ValueError("source/product scope mismatch")
            if "product" in source and source["product"] != product:
                raise ValueError("source product mismatch")
            if "sha256" in source and source["sha256"] != sha:
                raise DomainError("SOURCE_MISMATCH", "승인된 CSV 원문 해시와 다릅니다.", {})
            source_map[did] = {"model_id": model, **{k: source[k] for k in
                                                   ("document_version", "source_kind")}}
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError) as error:
        raise DomainError("INVALID_APPROVAL", "승인된 제품·출처 메타데이터를 확인해 주세요.", {}) from error

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    reviews, evidence, origins = [], [], []
    review_ids, evidence_ids = set(existing_review_ids), set(existing_evidence_ids)
    start = 1
    try:
        if next(reader, None) != list(FIELDS) or reader.line_num != 1:
            raise DomainError("INVALID_HEADER", "기존 리뷰 CSV의 정확한 열 이름·순서가 필요합니다.", {})
        while True:
            start = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if len(reviews) >= max_rows:
                raise DomainError("ROW_LIMIT_EXCEEDED", "리뷰 행 수 한도를 초과했습니다.", {"row": start})
            if len(values) != len(FIELDS) or any(not value.strip() for value in values):
                raise DomainError("INVALID_FIELD", "누락되거나 빈 CSV 필드입니다.", {"row": start})
            row = dict(zip(FIELDS, values))
            if any(v != v.strip() for k, v in row.items() if k != "text"):
                raise DomainError("INVALID_FIELD", "식별 필드에 공백이 있습니다.", {"row": start})
            wire_row = row.pop("row")
            if not re.fullmatch(r"[1-9][0-9]*", wire_row) or wire_row != str(start):
                raise DomainError("INVALID_LOCATOR", "CSV 행 위치가 실제 물리 행과 다릅니다.", {"row": start})
            review = {**row, "locator": {"row": start}}
            try:
                validate("Review", review)
            except ValidationError as error:
                raise DomainError("INVALID_FIELD", "리뷰 필드가 계약과 다릅니다.", {"row": start}) from error
            product = product_map.get(review["model_id"])
            if product is None:
                raise DomainError("UNAPPROVED_MODEL", "승인하지 않은 제품 모델입니다.", {"row": start})
            source = source_map.get(review["source_id"])
            if source is None:
                raise DomainError("UNKNOWN_SOURCE", "등록된 승인 출처가 없습니다.", {"row": start})
            if any(review[k] != source[k] for k in ("model_id", "document_version", "source_kind")):
                raise DomainError("SOURCE_MISMATCH", "리뷰의 모델·버전·자료 성격이 출처와 다릅니다.", {"row": start})
            if review["id"] in review_ids or review["evidence_id"] in evidence_ids:
                raise DomainError("DUPLICATE_ID", "리뷰 또는 근거 ID가 중복됩니다.", {"row": start})
            review_ids.add(review["id"])
            evidence_ids.add(review["evidence_id"])
            item = {k: deepcopy(review[k]) for k in
                    ("model_id", "document_version", "source_kind", "source_id", "locator", "text")}
            item.update(id=review["evidence_id"], source_type="review", feature_ids=[])
            validate("Evidence", item)
            reviews.append(review)
            evidence.append(item)
            origins.append({"evidence_id": item["id"], "source_id": item["source_id"],
                            "document_version": item["document_version"], "source_kind": item["source_kind"],
                            "sha256": sha, "row": start, "end_row": reader.line_num,
                            "text_sha256": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                            "original_role": "uploaded_review_csv", "parser": "stdlib.csv"})
    except csv.Error as error:
        raise DomainError("PARSING_FAILED", "CSV 인용부호 또는 필드 파싱에 실패했습니다.",
                          {"row": start, "end_row": reader.line_num}) from error
    if not reviews:
        raise DomainError("EMPTY_REVIEWS", "리뷰가 한 행 이상 필요합니다.", {})
    dataset = {"artifact_kind": "document_dataset", "dataset_version": dataset_version,
               "products": approved_products, "reviews": reviews, "features": [], "evidence": evidence}
    DocumentStore(dataset)
    return ReviewImportResult(original, json.dumps(dataset, ensure_ascii=False),
                              json.dumps(origins, ensure_ascii=False))
