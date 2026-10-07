"""Authenticated source metadata; the public bootstrap remains synthetic only."""
import hashlib
import json
from copy import deepcopy

from lgax_contracts import CONTRACT_VERSION, validate
from lgax_core.errors import DomainError


def workspace_bootstrap(store) -> dict:
    original = store.bootstrap()
    data = original["data"]
    if data.get("manifest", {}).get("source_kind") == "synthetic":
        validate("BootstrapResponse", original)
        return original
    if (data.get("artifact_kind") != "document_dataset"
            or not isinstance(data.get("dataset_version"), str)
            or not data["dataset_version"].strip()
            or not data.get("products")
            or any(item.get("source_kind") != "public"
                   for collection in ("products", "reviews", "evidence")
                   for item in data.get(collection, []))):
        raise DomainError("NOT_IMPLEMENTED", "이 자료 범위의 웹 조회 규격은 아직 지원하지 않습니다.", {})
    dataset = deepcopy(data)
    dataset.pop("contract_version", None)
    digest = hashlib.sha256(json.dumps(dataset, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    result = {"ok": True, "data": {
        **{collection: deepcopy(data[collection]) for collection in ("products", "reviews", "features", "evidence")},
        "manifest": {"dataset_id": "lgax-public-workspace", "version": data["dataset_version"],
                     "description": "등록된 공개 제품 원문과 후기 자료. 현재 서버가 읽은 동일 버전입니다.",
                     "source_kind": "public", "model_count": len(data["products"]),
                     "review_count": len(data["reviews"]), "analysis_implemented": False,
                     "dataset_sha256": digest,
                     "warnings": ["공개 후기 수집과 정확한 구매 SKU·게시일 확인은 별도입니다.",
                                  "자료 조회 성공은 실모델 판단·고객 수요 검증을 뜻하지 않습니다."]},
        "contract_version": CONTRACT_VERSION}}
    validate("PublicBootstrapResponse", result)
    return result
