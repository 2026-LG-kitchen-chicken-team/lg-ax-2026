"""Deterministic canonical evidence reads; the default demo pack remains synthetic."""

import json
import re
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from lgax_contracts import CONTRACT_VERSION, validate

from .errors import DomainError


def _load_default() -> dict[str, Any]:
    for parent in Path(__file__).resolve().parents:
        path = parent / "data/demo/dataset.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(files("lgax_bootstrap_data").joinpath("dataset.json").read_text("utf-8"))


class EvidenceReader:
    """Shared canonical read operations; concrete stores control their data policy."""

    def list_products(self, product_group: str | None = None) -> dict[str, Any]:
        if product_group is not None and product_group not in {"fridge", "dishwasher", "microwave"}:
            raise DomainError("INVALID_ARGUMENT", "지원하지 않는 제품군입니다.", {"product_group": product_group})
        products = [p for p in self._products.values() if product_group is None or p["product_group"] == product_group]
        result = {"ok": True, "data": {"products": deepcopy(products), "contract_version": CONTRACT_VERSION}}
        validate("ProductsResponse", result)
        return result

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        if evidence_id not in self._evidence:
            raise DomainError("INVALID_EVIDENCE_ID", "해당 근거 ID가 없습니다.", {"evidence_id": evidence_id})
        result = {"ok": True, "data": {"evidence": deepcopy(self._evidence[evidence_id]), "contract_version": CONTRACT_VERSION}}
        validate("EvidenceResponse", result)
        return result

    def search_evidence(
        self,
        q: str,
        model_id: str | None = None,
        document_version: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        if not isinstance(q, str) or not q.strip() or len(q) > 500:
            raise DomainError("INVALID_ARGUMENT", "검색어는 1~500자여야 합니다.", {"field": "q"})
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise DomainError("INVALID_ARGUMENT", "limit은 1~50의 정수여야 합니다.", {"field": "limit"})
        if model_id is not None and model_id not in self._products:
            raise DomainError("INVALID_MODEL_ID", "해당 모델 ID가 없습니다.", {"model_id": model_id})
        if document_version is not None:
            if model_id is None:
                raise DomainError("INVALID_ARGUMENT", "버전 검색에는 model_id가 필요합니다.", {"field": "model_id"})
            versions = {e["document_version"] for e in self._evidence.values() if e["model_id"] == model_id}
            if document_version not in versions:
                raise DomainError("INVALID_DOCUMENT_VERSION", "해당 모델의 문서 버전이 없습니다.", {"document_version": document_version})
        tokens = re.findall(r"[\w]+", q.casefold())
        if not tokens:
            raise DomainError("INVALID_ARGUMENT", "검색어에 문자 또는 숫자가 필요합니다.", {"field": "q"})
        matches = []
        for evidence in self._evidence.values():
            if model_id is not None and evidence["model_id"] != model_id:
                continue
            if document_version is not None and evidence["document_version"] != document_version:
                continue
            haystack = evidence["text"].casefold()
            score = sum(haystack.count(token) for token in tokens)
            if score:
                matches.append((score, evidence["id"], evidence))
        matches.sort(key=lambda match: (-match[0], match[1]))
        result = {"ok": True, "data": {
            "query": q, "model_id": model_id, "document_version": document_version,
            "items": [deepcopy(item[2]) for item in matches[:limit]], "total": len(matches),
            "contract_version": CONTRACT_VERSION, "search_method": "literal_token_count",
        }}
        validate("EvidenceSearchResponse", result)
        return result


class DemoStore(EvidenceReader):
    """In-memory read-only store. No file upload, private data, API calls or GPU work."""

    def __init__(self, dataset: dict[str, Any] | None = None):
        self._dataset = deepcopy(dataset if dataset is not None else _load_default())
        validate("DemoDataset", self._dataset)
        for collection in ("products", "reviews", "evidence"):
            if any(item["source_kind"] != "synthetic" for item in self._dataset[collection]):
                raise ValueError("Bootstrap store only accepts synthetic data")
        self._products = {product["model_id"]: product for product in self._dataset["products"]}
        self._evidence = {evidence["id"]: evidence for evidence in self._dataset["evidence"]}
        self._features = {feature["id"]: feature for feature in self._dataset["features"]}
        if self._dataset["manifest"]["model_count"] != len(self._dataset["products"]):
            raise ValueError("Manifest model count mismatch")
        if self._dataset["manifest"]["review_count"] != len(self._dataset["reviews"]):
            raise ValueError("Manifest review count mismatch")
        if len(self._products) != len(self._dataset["products"]):
            raise ValueError("Duplicate model_id")
        if len(self._evidence) != len(self._dataset["evidence"]):
            raise ValueError("Duplicate evidence ID")
        if len(self._features) != len(self._dataset["features"]):
            raise ValueError("Duplicate feature ID")
        for evidence in self._evidence.values():
            if evidence["model_id"] not in self._products:
                raise ValueError(f"Unknown evidence model: {evidence['id']}")
            for feature_id in evidence["feature_ids"]:
                feature = self._features.get(feature_id)
                if not feature or feature["model_id"] != evidence["model_id"]:
                    raise ValueError(f"Cross-model or missing feature: {evidence['id']}")
                if feature["document_version"] != evidence["document_version"]:
                    raise ValueError(f"Cross-version feature: {evidence['id']}")
        for feature in self._features.values():
            for evidence_id in feature["evidence_ids"]:
                evidence = self._evidence.get(evidence_id)
                if (not evidence or evidence["model_id"] != feature["model_id"]
                        or evidence["document_version"] != feature["document_version"]):
                    raise ValueError(f"Cross-model or missing feature evidence: {feature['id']}")
        review_ids = set()
        for review in self._dataset["reviews"]:
            if review["id"] in review_ids:
                raise ValueError("Duplicate review ID")
            review_ids.add(review["id"])
            evidence = self._evidence.get(review["evidence_id"])
            if not evidence or evidence["source_type"] != "review":
                raise ValueError(f"Missing review evidence: {review['id']}")
            for field in ("model_id", "document_version", "text", "source_id", "locator", "source_kind"):
                if evidence[field] != review[field]:
                    raise ValueError(f"Review evidence {field} mismatch: {review['id']}")

    def bootstrap(self) -> dict[str, Any]:
        result = {"ok": True, "data": {**deepcopy(self._dataset), "contract_version": CONTRACT_VERSION}}
        validate("BootstrapResponse", result)
        return result


@lru_cache(maxsize=1)
def default_store() -> DemoStore:
    return DemoStore()
