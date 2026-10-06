"""Keep the existing Agent envelope authoritative without dropping Skill holds.

No source text is classified here. Duplicate declarations must agree exactly;
uncertainty fields are copied verbatim into existing shared hold fields.
"""
from copy import deepcopy

from .errors import DomainError


def prepare_stage_declaration(skill_id: str, declaration: dict) -> dict:
    stage = {"need_extract": "needs", "product_compare": "compare",
             "concept_draft": "concepts"}[skill_id]
    assessment = {"need_extract": "review_assessments", "product_compare": "gap_assessments",
                  "concept_draft": "concept_assessments"}[skill_id]
    result = declaration["result"]
    for field in (assessment, "questions", "hold_reasons", "no_candidate_reasons"):
        if field in result and result[field] != declaration[field]:
            raise DomainError(
                "VALIDATION_FAILED", "단계 판단 메타데이터의 두 표현이 다릅니다.",
                {"violations": [{"code": "VALIDATION_FAILED", "stage": stage}],
                 "conflicting_paths": [field, "result/" + field],
                 "instruction": "원 응답을 보존하고 두 선언을 같은 근거로 다시 작성하세요. "
                                "어느 쪽의 극성이나 사유도 코드가 대신 선택하지 않습니다."})

    prepared = deepcopy(declaration)
    if skill_id != "need_extract":
        return prepared
    polarities = {row["evidence_id"]: row["polarity"] for row in declaration[assessment]}
    seen = set()
    for row in result.get("uncertainty_assessments", []):
        eid = row["evidence_id"]
        if eid in seen or polarities.get(eid) not in ("uncertain", "conflicting"):
            raise DomainError(
                "VALIDATION_FAILED", "미확인 정보와 리뷰 판단의 근거 ID·극성이 다릅니다.",
                {"violations": [{"code": "VALIDATION_FAILED", "stage": stage}],
                 "evidence_id": eid, "declared_polarity": polarities.get(eid)})
        seen.add(eid)
        prepared["hold_reasons"] = list(dict.fromkeys(prepared["hold_reasons"] + [row["reason"]]))
        prepared["questions"] = list(dict.fromkeys(prepared["questions"] + row["questions"]))
        prepared["result"]["unresolved"] = list(dict.fromkeys(
            prepared["result"]["unresolved"] + row["missing_information"]))
    # This is a projection after consistency validation, not a rewrite of the
    # generated response (preserved separately in model_calls).
    if "questions" in result:
        prepared["result"]["questions"] = deepcopy(prepared["questions"])
    return prepared
