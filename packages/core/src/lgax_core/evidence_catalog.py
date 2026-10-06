"""Detached, version-scoped canonical evidence catalog; no model or file guessing."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy

from jsonschema import ValidationError
from lgax_contracts import validate

from .document_store import DocumentStore
from .errors import DomainError
from .store import DemoStore


class EvidenceCatalog:
    """Index one or more validated snapshots with globally unique evidence IDs.

    Sources, when supplied, must cover every referenced source/model/version/kind.
    A shared CSV source ID may belong to several model scopes. A source_reader
    checks current original bytes on every read, rather than trusting cached data.
    Without a reader this is explicitly a canonical snapshot catalog, not proof
    of live original-file availability or OCR fidelity.
    """

    def __init__(self, datasets: Sequence[Mapping], *, sources: Sequence[Mapping] | None = None,
                 source_reader: Callable[[str], bytes | None] | None = None):
        self._items, self._reviews, self._features, self._scopes = {}, [], [], set()
        self._versions = set()
        collection_ids = {"reviews": set(), "features": set()}
        self._source_reader = source_reader
        self._sources = {}
        for source in sources or ():
            source = deepcopy(dict(source))
            key = self._source_key(source)
            if key in self._sources:
                raise DomainError("DUPLICATE_ID", "승인 출처 범위가 중복됩니다.", {})
            if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
                raise DomainError("INVALID_ORIGIN", "승인 출처 SHA256이 필요합니다.", {})
            try:
                validate("Evidence", {"id": "source-scope", "source_id": key[0], "model_id": key[1],
                    "document_version": key[2], "source_kind": key[3], "source_type": "manual",
                    "locator": {"page": 1}, "text": "scope validation", "feature_ids": []})
            except ValidationError as error:
                raise DomainError("INVALID_ORIGIN", "승인 출처 ID·모델·버전·자료 성격이 다릅니다.", {}) from error
            if source.get("status", "active") not in {"active", "retired"}:
                raise DomainError("INVALID_ARGUMENT", "자료 상태를 확인해 주세요.", {})
            self._sources[key] = source
        hashes_by_id = {}
        for key, source in self._sources.items():
            if hashes_by_id.setdefault(key[0], source["sha256"]) != source["sha256"]:
                raise DomainError("SOURCE_MISMATCH", "같은 출처 ID가 서로 다른 원문 해시를 가리킵니다.", {})
        if source_reader is not None and sources is None:
            raise DomainError("INVALID_ARGUMENT", "원문 조회에는 승인 출처·해시가 필요합니다.", {})
        for supplied in datasets:
            dataset = deepcopy(dict(supplied))
            version = dataset.get("dataset_version", dataset.get("manifest", {}).get("version"))
            if not isinstance(version, str) or not version.strip():
                raise DomainError("INVALID_ARGUMENT", "자료집 버전이 필요합니다.", {})
            canonical = {"artifact_kind": "document_dataset", "dataset_version": version,
                         **{key: dataset[key] for key in ("products", "reviews", "features", "evidence")}}
            for collection in ("reviews", "features", "evidence"):
                ids = [item["id"] for item in canonical[collection]]
                if len(ids) != len(set(ids)):
                    raise DomainError("DUPLICATE_ID", "자료집 ID가 중복됩니다.", {"collection": collection})
                if collection in collection_ids:
                    if set(ids) & collection_ids[collection]:
                        raise DomainError("DUPLICATE_ID", "자료집 사이의 리뷰·기능 ID가 중복됩니다.", {"collection": collection})
                    collection_ids[collection].update(ids)
            try:
                if dataset.get("artifact_kind") == "document_dataset":
                    DocumentStore(canonical)
                else:
                    # The frozen demo intentionally includes FRIDGE-A manual 2.0
                    # beside reviews 1.0. Keep its approved multi-edition policy.
                    DemoStore(dataset)
            except (ValueError, ValidationError) as error:
                raise DomainError("SOURCE_MISMATCH", "자료집의 ID·모델·버전 연결이 다릅니다.", {}) from error
            self._versions.add(version)
            for product in canonical["products"]:
                scope = (version, product["model_id"], product["document_version"], product["source_kind"])
                if scope in self._scopes:
                    raise DomainError("DUPLICATE_ID", "자료집의 제품 범위가 중복됩니다.", {})
                self._scopes.add(scope)
            self._scopes.update((version, item["model_id"], item["document_version"], item["source_kind"])
                                for item in canonical["evidence"])
            for item in canonical["evidence"]:
                if item["id"] in self._items:
                    raise DomainError("DUPLICATE_ID", "근거 ID는 자료집 간에도 고유해야 합니다.", {"evidence_id": item["id"]})
                key = self._source_key(item)
                if sources is not None:
                    source = self._sources.get(key)
                    if source is None:
                        raise DomainError("UNKNOWN_SOURCE", "등록된 승인 출처가 없습니다.", {"source_id": item["source_id"]})
                    if source.get("status", "active") == "retired":
                        raise DomainError("SOURCE_RETIRED", "폐기한 출처의 근거입니다.", {"source_id": item["source_id"]})
                self._items[item["id"]] = (version, item)
            self._reviews.extend((version, item) for item in canonical["reviews"])
            self._features.extend((version, item) for item in canonical["features"])

    @staticmethod
    def _source_key(item):
        product = item.get("product", {})
        return (item.get("source_id", item.get("document_id")), item.get("model_id", product.get("model_id")),
                item.get("document_version"), item.get("source_kind"))

    def _check_originals(self, items):
        if self._source_reader is None:
            return
        for key in sorted({self._source_key(item) for item in items}):
            raw = self._source_reader(key[0])
            if raw is None:
                raise DomainError("SOURCE_MISSING", "보존 원문이 없습니다.", {"source_id": key[0]})
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != self._sources[key]["sha256"]:
                raise DomainError("SOURCE_CHANGED", "현재 원문 SHA256이 다릅니다.", {"source_id": key[0]})

    def select(self, *, model_id=None, document_version=None, dataset_version=None, source_kind=None):
        if model_id is not None and model_id not in {s[1] for s in self._scopes}:
            raise DomainError("INVALID_MODEL_ID", "해당 모델 ID가 없습니다.", {"model_id": model_id})
        if dataset_version is not None and dataset_version not in self._versions:
            raise DomainError("INVALID_DATASET_VERSION", "해당 자료집 버전이 없습니다.", {})
        if document_version is not None:
            if model_id is None:
                raise DomainError("INVALID_ARGUMENT", "문서 버전에는 모델 ID가 필요합니다.", {})
            if not any(s[1] == model_id and s[2] == document_version
                       and (dataset_version is None or s[0] == dataset_version) for s in self._scopes):
                raise DomainError("INVALID_DOCUMENT_VERSION", "모델의 문서 버전이 다릅니다.", {})
        if source_kind is not None and source_kind not in {"public", "synthetic", "private", "licensed"}:
            raise DomainError("INVALID_ARGUMENT", "자료 성격을 확인해 주세요.", {})
        selected = [item for version, item in self._items.values()
                    if (dataset_version is None or version == dataset_version)
                    and (model_id is None or item["model_id"] == model_id)
                    and (document_version is None or item["document_version"] == document_version)
                    and (source_kind is None or item["source_kind"] == source_kind)]
        self._check_originals(selected)
        return deepcopy(sorted(selected, key=lambda item: item["id"]))

    def get_evidence(self, evidence_id, **scope):
        if evidence_id not in self._items:
            raise DomainError("INVALID_EVIDENCE_ID", "해당 근거 ID가 없습니다.", {"evidence_id": evidence_id})
        selected = self.select(**scope)
        item = next((item for item in selected if item["id"] == evidence_id), None)
        if item is None:
            raise DomainError("SOURCE_MISMATCH", "근거 ID와 선택한 자료 범위가 다릅니다.", {"evidence_id": evidence_id})
        return item

    def related(self, *, collection, **scope):
        if collection not in {"reviews", "features"}:
            raise DomainError("INVALID_ARGUMENT", "리뷰 또는 기능 조회만 지원합니다.", {})
        evidence_ids = {item["id"] for item in self.select(**scope)}
        items = self._reviews if collection == "reviews" else self._features
        return deepcopy([item for _, item in items if (
            item["evidence_id"] in evidence_ids if collection == "reviews"
            else bool(set(item["evidence_ids"]) & evidence_ids))])
