"""Need judgement metadata; never invent pain, polarity, reasons or questions."""

from .errors import DomainError

POLARITIES = ("complaint", "positive", "conflicting", "irrelevant", "uncertain")


def metadata_properties():
    text = {"type": "string", "minLength": 1, "pattern": r"\S"}
    texts = {"type": "array", "items": text, "uniqueItems": True}
    identity = {"type": "string", "minLength": 1}

    def obj(properties):
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    return {
        "review_assessments": {
            "type": "array",
            "items": obj({"evidence_id": identity, "polarity": {"enum": list(POLARITIES)}, "reason": text}),
        },
        "uncertainty_assessments": {
            "type": "array",
            "items": obj(
                {
                    "evidence_id": identity,
                    "reason": text,
                    "missing_information": {**texts, "minItems": 1},
                    "questions": {**texts, "minItems": 1},
                }
            ),
        },
        "questions": texts,
    }


def validate_judgement(result, review_ids):
    """Validate optional declarations; legacy shapes are accepted without invented metadata."""
    if not isinstance(result, dict):
        return set()
    assessments = result.get("review_assessments")
    unknowns = result.get("uncertainty_assessments", [])
    if assessments is None:
        if unknowns:
            raise DomainError(
                "VALIDATION_FAILED",
                "미확인 항목에는 원 리뷰 판단이 필요합니다.",
                {
                    "stage": "need_extract",
                    "missing_fields": ["review_assessments"],
                    "expected_review_evidence_ids": list(review_ids),
                },
            )
        return set()
    if not isinstance(assessments, list) or not all(isinstance(a, dict) for a in assessments):
        return set()
    if any(not isinstance(a.get("evidence_id"), str) for a in assessments):
        return set()  # Keep malformed identity handling in the structural validator.
    issues = []
    seen = [a.get("evidence_id") for a in assessments]
    for index, assessment in enumerate(assessments):
        eid = assessment.get("evidence_id")
        if eid not in review_ids:
            issues.append(
                {
                    "code": "REVIEW_SCOPE_MISMATCH",
                    "evidence_id": eid,
                    "path": f"review_assessments/{index}/evidence_id",
                }
            )
        if not isinstance(assessment.get("reason"), str) or not assessment["reason"].strip():
            issues.append(
                {
                    "code": "REVIEW_REASON_MISSING",
                    "evidence_id": eid,
                    "path": f"review_assessments/{index}/reason",
                }
            )
    if set(seen) != set(review_ids) or len(seen) != len(set(seen)):
        issues.append(
            {
                "code": "REVIEW_ASSESSMENT_COVERAGE",
                "expected_review_evidence_ids": list(review_ids),
                "actual_review_evidence_ids": seen,
            }
        )
    if not isinstance(unknowns, list) or not all(isinstance(u, dict) for u in unknowns):
        return set()
    if any(not isinstance(u.get("evidence_id"), str) for u in unknowns):
        return set()
    declared = {a.get("evidence_id"): a.get("polarity") for a in assessments}
    expected = {eid for eid, p in declared.items() if p in ("uncertain", "conflicting")}
    actual = [u.get("evidence_id") for u in unknowns]
    for eid in sorted(expected - set(actual)):
        issues.append(
            {
                "code": "UNCERTAINTY_CONTEXT_MISSING",
                "evidence_id": eid,
                "required_fields": ["reason", "missing_information", "questions"],
            }
        )
    for index, entry in enumerate(unknowns):
        eid = entry.get("evidence_id")
        if eid not in expected or actual.count(eid) != 1:
            issues.append(
                {
                    "code": "UNCERTAINTY_SCOPE_MISMATCH",
                    "evidence_id": eid,
                    "path": f"uncertainty_assessments/{index}/evidence_id",
                }
            )
        for field in ("reason", "missing_information", "questions"):
            v = entry.get(field)
            valid = (
                isinstance(v, str) and bool(v.strip())
                if field == "reason"
                else (isinstance(v, list) and bool(v) and all(isinstance(i, str) and i.strip() for i in v))
            )
            if not valid:
                issues.append(
                    {
                        "code": "UNCERTAINTY_FIELD_MISSING",
                        "evidence_id": eid,
                        "path": f"uncertainty_assessments/{index}/{field}",
                        "field": field,
                    }
                )
    for need in result.get("needs", []) if isinstance(result.get("needs"), list) else []:
        if isinstance(need, dict):
            evidence_ids = need.get("evidence_ids", [])
            if not isinstance(evidence_ids, list) or not all(isinstance(eid, str) for eid in evidence_ids):
                continue  # Structural validation owns malformed Need fields.
            for eid in evidence_ids:
                if eid in declared and declared[eid] != "complaint":
                    issues.append(
                        {
                            "code": "NON_COMPLAINT_AS_NEED",
                            "evidence_id": eid,
                            "need_id": need.get("id"),
                            "declared_polarity": declared[eid],
                        }
                    )
    if issues:
        raise DomainError(
            "VALIDATION_FAILED",
            "리뷰 판단 사유·미확인 정보·확인 질문을 보완해야 합니다.",
            {
                "stage": "need_extract",
                "violations": issues,
                "expected_review_evidence_ids": list(review_ids),
                "feedback_policy": "Preserve the raw reply. Ask the model to fill the identified fields; never fabricate reasons, pain or questions.",
            },
        )
    return set(seen)


def hold_reasons(result):
    return [u["reason"] for u in result.get("uncertainty_assessments", [])]


def has_explained_no_need(result):
    a = result.get("review_assessments", [])
    return (
        bool(a)
        and not result.get("needs")
        and all(
            v.get("polarity") in ("positive", "irrelevant", "uncertain", "conflicting")
            and isinstance(v.get("reason"), str)
            and v["reason"].strip()
            for v in a
        )
    )
