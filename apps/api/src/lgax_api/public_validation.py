"""A closed public projection of validation facts, never private diagnostics."""

import re

_CODES = frozenset({
    "REVIEW_SCOPE_MISMATCH", "REVIEW_REASON_MISSING", "REVIEW_ASSESSMENT_COVERAGE",
    "UNCERTAINTY_CONTEXT_MISSING", "UNCERTAINTY_SCOPE_MISMATCH",
    "UNCERTAINTY_FIELD_MISSING", "EMPTY_NEEDS_WITHOUT_JUDGEMENT", "NON_COMPLAINT_AS_NEED",
    "CONCEPT_GROUNDING_MISSING",
})
_FIELDS = frozenset({"review_assessments", "gap_assessments", "concept_assessments",
                     "questions", "hold_reasons", "no_candidate_reasons"})
_PATH = re.compile(r"(?:review_assessments/[0-9]{1,4}/(?:evidence_id|reason)|"
                   r"uncertainty_assessments/[0-9]{1,4}/(?:evidence_id|reason|missing_information|questions))")
_POLARITIES = frozenset({"complaint", "positive", "conflicting", "irrelevant", "uncertain"})
_REASONS = frozenset({"schema_mismatch", "difference_requires_review_and_manual",
                      "difference_requires_feature_manual", "reviewer_reports_existing_need",
                      "question_basis_coverage", "output_omission_is_not_missing_source",
                      "missing_need_requires_violation"})


def _ids(value, allowed: set[str]) -> list[str] | None:
    if (not isinstance(value, list) or not 1 <= len(value) <= 64
            or any(not isinstance(item, str) or item not in allowed for item in value)):
        return None
    return list(dict.fromkeys(value))


def _grounding(item: dict, evidence_ids: set[str], entities: dict[str, set[str]]) -> dict:
    row = {"code": "CONCEPT_GROUNDING_MISSING"}
    if isinstance(item.get("concept_id"), str) and item["concept_id"] in entities.get("concepts", set()):
        row["concept_id"] = item["concept_id"]
    links = []
    values = item.get("missing_links")
    for link in values[:32] if isinstance(values, list) else []:
        if (not isinstance(link, dict) or not isinstance(link.get("gap_id"), str)
                or link["gap_id"] not in entities.get("gaps", set())
                or not isinstance(link.get("need_id"), str)
                or link["need_id"] not in entities.get("needs", set())):
            continue
        required = _ids(link.get("required_evidence_ids"), evidence_ids)
        missing = _ids(link.get("missing_evidence_ids"), evidence_ids)
        if required and missing and set(missing) <= set(required):
            links.append({"gap_id": link["gap_id"], "need_id": link["need_id"],
                          "required_evidence_ids": required, "missing_evidence_ids": missing})
    if links:
        row["missing_links"] = links
    return row


def public_validation_details(error: dict, evidence_ids: set[str],
                              entities: dict[str, set[str]] | None = None) -> dict:
    """Keep only known codes, public source IDs, schema paths and fixed reasons.

    The caller separately replaces the private message. Unknown error kinds and
    arbitrary strings/fields are excluded even when nested beside valid facts.
    """
    details = error.get("details")
    if error.get("code") != "VALIDATION_FAILED" or not isinstance(details, dict):
        return {}
    result = {}
    entities = entities or {}
    violations = []
    items = details.get("violations")
    for item in items[:100] if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or item["code"] not in _CODES:
            continue
        row = (_grounding(item, evidence_ids, entities) if item["code"] == "CONCEPT_GROUNDING_MISSING"
               else {"code": item["code"]})
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id in evidence_ids:
            row["evidence_id"] = evidence_id
        path = item.get("path")
        if isinstance(path, str) and _PATH.fullmatch(path):
            row["path"] = path
        violations.append(row)
    if violations:
        result["violations"] = violations
    code = details.get("code")
    if isinstance(code, str) and code in _CODES:
        result["code"] = code
    paths = details.get("conflicting_paths")
    if (isinstance(paths, list) and len(paths) == 2 and isinstance(paths[0], str)
            and paths[0] in _FIELDS and paths[1] == "result/" + paths[0]):
        result["conflicting_paths"] = list(paths)
    if isinstance(details.get("reason"), str) and details["reason"] in _REASONS:
        result["reason"] = details["reason"]
    evidence_id = details.get("evidence_id")
    if isinstance(evidence_id, str) and evidence_id in evidence_ids:
        result["evidence_id"] = evidence_id
        polarity = details.get("declared_polarity")
        if isinstance(polarity, str) and polarity in _POLARITIES:
            result["declared_polarity"] = polarity
    items = details.get("grounding_violations")
    grounding = [_grounding(item, evidence_ids, entities)
                 for item in (items[:100] if isinstance(items, list) else [])
                 if isinstance(item, dict) and item.get("code") == "CONCEPT_GROUNDING_MISSING"]
    if grounding:
        result["grounding_violations"] = grounding
    for key in ("gap_id", "need_id", "concept_id"):
        collection = {"gap_id": "gaps", "need_id": "needs", "concept_id": "concepts"}[key]
        value = details.get(key)
        if isinstance(value, str) and value in entities.get(collection, set()):
            result[key] = value
    for key in ("required_review_evidence_ids", "linked_manual_evidence_ids", "required_manual_evidence_ids"):
        values = _ids(details.get(key), evidence_ids)
        if values:
            result[key] = values
    contradictions = []
    items = details.get("contradictions")
    for item in items[:64] if isinstance(items, list) else []:
        if (not isinstance(item, dict) or not isinstance(item.get("review_evidence_id"), str)
                or item["review_evidence_id"] not in evidence_ids):
            continue
        needs = _ids(item.get("existing_need_ids"), entities.get("needs", set()))
        if needs:
            contradictions.append({"review_evidence_id": item["review_evidence_id"], "existing_need_ids": needs})
    if contradictions:
        result["contradictions"] = contradictions
    return result
