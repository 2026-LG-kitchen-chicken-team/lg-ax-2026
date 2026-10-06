"""A closed public projection of validation facts, never private diagnostics."""

import re

_CODES = frozenset({
    "REVIEW_SCOPE_MISMATCH", "REVIEW_REASON_MISSING", "REVIEW_ASSESSMENT_COVERAGE",
    "UNCERTAINTY_CONTEXT_MISSING", "UNCERTAINTY_SCOPE_MISMATCH",
    "UNCERTAINTY_FIELD_MISSING", "EMPTY_NEEDS_WITHOUT_JUDGEMENT", "NON_COMPLAINT_AS_NEED",
})
_FIELDS = frozenset({"review_assessments", "gap_assessments", "concept_assessments",
                     "questions", "hold_reasons", "no_candidate_reasons"})
_PATH = re.compile(r"(?:review_assessments/[0-9]{1,4}/(?:evidence_id|reason)|"
                   r"uncertainty_assessments/[0-9]{1,4}/(?:evidence_id|reason|missing_information|questions))")
_POLARITIES = frozenset({"complaint", "positive", "conflicting", "irrelevant", "uncertain"})


def public_validation_details(error: dict, evidence_ids: set[str]) -> dict:
    """Keep only known codes, public source IDs, schema paths and fixed reasons.

    The caller separately replaces the private message. Unknown error kinds and
    arbitrary strings/fields are excluded even when nested beside valid facts.
    """
    details = error.get("details")
    if error.get("code") != "VALIDATION_FAILED" or not isinstance(details, dict):
        return {}
    result = {}
    violations = []
    items = details.get("violations")
    for item in items[:100] if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or item["code"] not in _CODES:
            continue
        row = {"code": item["code"]}
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
    if details.get("reason") == "schema_mismatch":
        result["reason"] = "schema_mismatch"
    evidence_id = details.get("evidence_id")
    if isinstance(evidence_id, str) and evidence_id in evidence_ids:
        result["evidence_id"] = evidence_id
        polarity = details.get("declared_polarity")
        if isinstance(polarity, str) and polarity in _POLARITIES:
            result["declared_polarity"] = polarity
    return result
