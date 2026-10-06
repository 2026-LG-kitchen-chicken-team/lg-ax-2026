"""Check declared IDs/polarities before sending a bad stage downstream.

This repeats only existing judgement consistency rules at the stage boundary.
It never classifies source text or rewrites a model's semantic declarations.
"""
from collections import Counter


def stage_alignment_feedback(payload: dict, skill_id: str, declaration: dict) -> dict | None:
    fields = {
        "need_extract": ("needs", "review_assessments", "evidence_id"),
        "product_compare": ("compare", "gap_assessments", "gap_id"),
        "concept_draft": ("concepts", "concept_assessments", "concept_id"),
    }
    stage, assessment_field, assessment_key = fields[skill_id]
    entity_field = {"need_extract": "needs", "product_compare": "gaps", "concept_draft": "concepts"}[skill_id]
    entities = declaration["result"][entity_field]
    entity_ids = [row["id"] for row in entities]
    assessments = declaration[assessment_field]
    actual_ids = [row[assessment_key] for row in assessments]
    expected_ids = ([e["id"] for e in payload["sources"] if e["source_type"] == "review"]
                    if skill_id == "need_extract" else entity_ids)
    expected, actual = set(expected_ids), set(actual_ids)
    duplicate_entities = sorted(key for key, count in Counter(entity_ids).items() if count > 1)
    duplicate_assessments = sorted(key for key, count in Counter(actual_ids).items() if count > 1)
    violations = []
    if expected != actual:
        violations.append({"code": "ASSESSMENT_COVERAGE", "stage": stage})
    if duplicate_entities or duplicate_assessments:
        violations.append({"code": "DUPLICATE_ID", "stage": stage})
    non_complaint_links = []
    if skill_id == "need_extract":
        polarities = {row["evidence_id"]: row["polarity"] for row in assessments}
        for need in entities:
            for eid in need["evidence_ids"]:
                # Uncertainty/conflict grounding still goes to the ordinary
                # hold/semantic review; do not turn it into an early retry.
                if eid in expected and polarities.get(eid) in ("positive", "irrelevant", None):
                    non_complaint_links.append({"need_id": need["id"], "evidence_id": eid,
                                               "declared_polarity": polarities.get(eid)})
        if non_complaint_links:
            violations.append({"code": "NON_COMPLAINT_AS_NEED", "stage": stage})
    if not violations:
        return None
    return {"violations": violations, "entity_field": entity_field,
            "duplicate_entity_ids": duplicate_entities, "non_complaint_links": non_complaint_links,
            "assessment_coverage": {"field": assessment_field, "expected_ids": sorted(expected),
                                    "actual_ids": actual_ids, "missing_ids": sorted(expected - actual),
                                    "unexpected_ids": sorted(actual - expected),
                                    "duplicate_ids": duplicate_assessments},
            "instruction": "원문과 해당 ID를 다시 대조해 극성 선언과 니즈 근거를 일치시키고, 실제 결과 ID마다 "
                           "평가를 정확히 한 번 작성하세요. 코드가 극성·니즈·후보를 대신 고치지 않습니다."}
