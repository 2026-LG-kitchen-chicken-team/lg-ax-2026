"""Plan an owner-authorized re-execution without overwriting an earlier run.

Pure change detection only: no model calls, database writes or tool selection
from document text. PM owns workspace integration and actual model execution.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from .errors import DomainError
from .judgement_contract import STAGES, input_digest, review_judgement, schema_for


def _validate(value: Any, label: str) -> None:
    if list(Draft202012Validator(schema_for("input")).iter_errors(value)):
        raise DomainError("INVALID_ARGUMENT", "이전·현재 입력 계약을 확인해야 합니다.", {"input": label})
    preflight = review_judgement(value, {})
    if any(item["code"] != "OUTPUT_SCHEMA" for item in preflight["violations"]):
        raise DomainError("VALIDATION_FAILED", "변경 입력의 근거·제품 범위가 맞지 않습니다.",
                          {"input": label, "violations": preflight["violations"]})


def _diff(previous: list[dict], current: list[dict]) -> dict[str, list[str]]:
    before, after = {p["id"]: p for p in previous}, {p["id"]: p for p in current}
    return {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
            "updated": sorted(key for key in before.keys() & after.keys() if before[key] != after[key])}


def prepare_reexecution(previous: dict, current: dict, *, explicit_new_run: bool = False) -> dict:
    """Compare frozen CORE001 inputs and return a fresh-input plan, never a result.

    explicit_new_run is an owner/code decision for an intentional repeat. It is
    not read from sources, model output or changed_evidence_ids. Identical input
    alone cannot reset an existing revision count. IDs flag actual content diffs.
    """
    if type(explicit_new_run) is not bool:
        raise DomainError("INVALID_ARGUMENT", "새 실행 요청은 호출자가 명시해야 합니다.", {})
    _validate(previous, "previous")
    _validate(current, "current")
    request_fields = sorted(key for key in previous["request"] if previous["request"][key] != current["request"][key])
    evidence = _diff(previous["sources"], current["sources"])
    features = _diff(previous["features"], current["features"])
    evidence_changed = any(evidence.values())
    features_changed = any(features.values())
    product_changed = previous["product"] != current["product"]
    source_order_changed = [e["id"] for e in previous["sources"]] != [e["id"] for e in current["sources"]]
    feature_order_changed = [f["id"] for f in previous["features"]] != [f["id"] for f in current["features"]]
    cap_changed = previous["max_concepts"] != current["max_concepts"]
    meaningful_change = bool(request_fields or evidence_changed or features_changed or product_changed
                             or source_order_changed or feature_order_changed or cap_changed)
    new_run = meaningful_change or explicit_new_run
    stages: list[str] = []
    reasons: list[str] = []
    if request_fields or product_changed or explicit_new_run:
        stages.append("plan")
        reasons.append("원 요청·제품 조건 또는 호출자의 명시적 새 실행 요청을 반영한다.")
    if evidence_changed or features_changed or source_order_changed or feature_order_changed:
        stages.append("retrieve")
        reasons.append("현재 원문/기능을 재조회하고 새 근거의 버전·내용·순서를 검증한다.")
    if cap_changed:
        stages.append("concepts")
        reasons.append("새 후보 상한에 맞춰 생성·중복 검사를 다시 수행한다.")
    first = min(stages, key=STAGES.index) if stages else None
    scope_changed = (previous["request"]["product_group"] != current["request"]["product_group"]
                     or set(previous["request"]["model_ids"]) != set(current["request"]["model_ids"])
                     or previous["product"]["document_version"] != current["product"]["document_version"])
    data_changed = evidence_changed or features_changed or product_changed
    version_changed = previous["request"]["dataset_version"] != current["request"]["dataset_version"]
    needs_project = bool(scope_changed or data_changed or version_changed)
    if new_run:
        prepared = deepcopy(current)
        prepared["revision_count"] = 0
        prepared["changed_evidence_ids"] = sorted(evidence["added"] + evidence["updated"])
    else:
        # Counter/changed-ID declarations alone cannot create a new execution.
        prepared = deepcopy(previous)
        reasons.append("원 입력의 실질 변경이 없어 이전 실행·내부 회차를 유지한다.")
    return {"new_run_required": new_run, "new_project_required": needs_project,
            "first_stage": first, "stages": list(STAGES[STAGES.index(first):]) if first else [],
            "project_action": "new_project_required" if needs_project else "new_run" if new_run else "keep_previous",
            "previous_input_sha256": input_digest(previous), "supplied_input_sha256": input_digest(current),
            "prepared_input_sha256": input_digest(prepared), "prepared_input": prepared,
            "changes": {"request_fields": request_fields, "evidence": evidence, "features": features,
                        "product": product_changed, "source_order": source_order_changed,
                        "feature_order": feature_order_changed, "max_concepts": cap_changed},
            "reasons": reasons, "model_calls": 0,
            "notice": "재실행 계획이다. 실제 생성·변경 효과·Workspace 저장 성공이 아니다."}
