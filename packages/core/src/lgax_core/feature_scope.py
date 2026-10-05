"""Select canonical originals before judgement, without inferring feature support.

Call ``select_feature_scope(request, document_versions, store.bootstrap()['data'])``.
Each returned input uses the existing judgement input contract. No model is called.
The caller must supply its authorized dataset; a version string is not authorization.
Supported/unsupported statements, conditions and unmentioned features are never
collapsed into a boolean. Empty features do not establish absence or novelty.
"""
from copy import deepcopy
from typing import Any

from jsonschema import ValidationError
from lgax_contracts import validate

from .errors import DomainError


def _fail(code: str, reason: str, question: str, **details: Any) -> None:
    raise DomainError(code, question, {"reason": reason, "question": question, **details})


def _validate(definition: str, value: Any) -> None:
    try:
        validate(definition, value)
    except ValidationError as exc:
        _fail("INVALID_ARGUMENT", "invalid_contract", "공통 계약에 맞는 입력을 제공해 주세요.",
              definition=definition, path=list(exc.absolute_path))


def select_feature_scope(request: dict, document_versions: dict[str, str], dataset: dict) -> dict:
    """Return isolated judgement inputs, atomically rejecting unsafe references.

    Versions must be explicit for every requested model (no latest-version fallback).
    Unrequested model/version records are excluded. Links from selected records to
    excluded or missing records fail closed instead of silently trimming originals.
    Accepts DemoStore and DocumentStore data containers and canonical entity types.
    Returned objects are independent copies; inputs and original text stay unchanged.
    """
    _validate("PlanningRequest", request)
    if not isinstance(dataset, dict):
        _fail("INVALID_ARGUMENT", "invalid_dataset", "자료집 객체를 제공해 주세요.")
    if not isinstance(document_versions, dict):
        _fail("INVALID_DOCUMENT_VERSION", "missing_document_version", "모델별 문서 버전을 지정해 주세요.")
    for model in request["model_ids"]:
        version = document_versions.get(model)
        if not isinstance(version, str) or not version.strip():
            _fail("INVALID_DOCUMENT_VERSION", "missing_document_version", "요청 모델의 문서 버전을 지정해 주세요.",
                  model_id=model)
    if set(document_versions) != set(request["model_ids"]):
        _fail("INVALID_ARGUMENT", "version_scope_mismatch", "요청 모델에 해당하는 버전만 지정해 주세요.")

    manifest = dataset.get("manifest")
    if manifest is not None:
        _validate("Manifest", manifest)
        version = manifest["version"]
        if "dataset_version" in dataset and dataset["dataset_version"] != version:
            _fail("DATASET_MISMATCH", "ambiguous_dataset_version", "자료집 버전 표기를 일치시켜 주세요.")
    elif dataset.get("artifact_kind") == "document_dataset":
        version = dataset.get("dataset_version")
    else:
        _fail("INVALID_ARGUMENT", "missing_dataset_metadata", "자료집 종류와 버전을 제공해 주세요.")
    if not isinstance(version, str) or not version.strip() or request["dataset_version"] != version:
        _fail("DATASET_MISMATCH", "dataset_version_mismatch", "요청한 버전의 자료집을 제공해 주세요.")

    indexed = {}
    for collection, definition in (("products", "Product"), ("evidence", "Evidence"), ("features", "Feature")):
        records = dataset.get(collection)
        if not isinstance(records, list):
            _fail("INVALID_ARGUMENT", "missing_collection", "원본 자료 목록을 제공해 주세요.", collection=collection)
        index = {}
        for item in records:
            # Give missing versions a distinct repair question before schema validation.
            if isinstance(item, dict) and (not isinstance(item.get("document_version"), str)
                                          or not item["document_version"].strip()):
                _fail("INVALID_DOCUMENT_VERSION", "missing_source_version", "원본 문서 버전을 확인해 주세요.",
                      collection=collection)
            _validate(definition, item)
            key = ((item["model_id"], item["document_version"]) if collection == "products" else item["id"])
            if key in index:
                _fail("VALIDATION_FAILED", "duplicate_identity", "중복 원본 식별자를 해소해 주세요.",
                      collection=collection)
            index[key] = item
        indexed[collection] = index

    def scope(item: dict) -> tuple[str, str]:
        return item["model_id"], item["document_version"]

    inputs = []
    for model in request["model_ids"]:
        target = (model, document_versions[model])
        if not any(key[0] == model for key in indexed["products"]):
            _fail("INVALID_MODEL_ID", "model_not_found", "자료집에 있는 모델을 지정해 주세요.", model_id=model)
        product = indexed["products"].get(target)
        if product is None:
            _fail("INVALID_DOCUMENT_VERSION", "document_version_not_found", "해당 모델·버전의 제품 자료를 제공해 주세요.",
                  model_id=model, document_version=target[1])
        if product["product_group"] != request["product_group"]:
            _fail("INVALID_ARGUMENT", "product_group_mismatch", "요청 제품군과 모델을 일치시켜 주세요.", model_id=model)
        sources = {key: item for key, item in indexed["evidence"].items() if scope(item) == target}
        features = {key: item for key, item in indexed["features"].items() if scope(item) == target}
        if not sources:
            _fail("INSUFFICIENT_EVIDENCE", "no_scoped_evidence", "해당 모델·버전의 원문을 제공해 주세요.",
                  model_id=model, document_version=target[1])
        for source in sources.values():
            if source["source_kind"] != product["source_kind"]:
                _fail("VALIDATION_FAILED", "source_kind_mismatch", "실자료·합성 자료의 출처 구분을 확인해 주세요.",
                      evidence_id=source["id"])
            for fid in source["feature_ids"]:
                if fid not in features:
                    _fail("VALIDATION_FAILED", "source_feature_scope_mismatch", "원문의 기능 연결 모델·버전을 확인해 주세요.",
                          evidence_id=source["id"], feature_id=fid)
                if source["source_type"] == "manual" and source["id"] not in features[fid]["evidence_ids"]:
                    _fail("VALIDATION_FAILED", "nonreciprocal_link", "기능과 설명서의 양방향 연결을 확인해 주세요.",
                          evidence_id=source["id"], feature_id=fid)
        for feature in features.values():
            for eid in feature["evidence_ids"]:
                if eid not in sources:
                    reason = "feature_evidence_scope_mismatch" if eid in indexed["evidence"] else "missing_evidence"
                    _fail("VALIDATION_FAILED", reason, "기능 근거의 원문·모델·버전을 확인해 주세요.",
                          feature_id=feature["id"], evidence_id=eid)
                source = sources[eid]
                if source["source_type"] != "manual" or feature["id"] not in source["feature_ids"]:
                    _fail("VALIDATION_FAILED", "invalid_manual_link", "기능과 설명서 원문의 연결을 확인해 주세요.",
                          feature_id=feature["id"], evidence_id=eid)
        inputs.append(deepcopy({"request": request, "product": product, "sources": list(sources.values()),
                       "features": list(features.values()), "revision_count": 0, "max_concepts": 3,
                       "changed_evidence_ids": []}))
    return deepcopy({"dataset_version": version, "manifest": manifest, "inputs": inputs})
