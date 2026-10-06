"""Source-bound support declarations, independent of whether discomfort remains.

This checks model declarations against canonical references, not the truth of a
model's reading. Silence and conflicting sources remain separate uncertain states.
No request exclusions are inferred from the existing product's usage conditions.
"""
from copy import deepcopy

from lgax_contracts import validate

from .errors import DomainError

SUPPORT = {"explicit_supported": "supported", "explicit_unsupported": "unsupported",
           "unmentioned": "insufficient_evidence", "conflicting": "insufficient_evidence"}


def build_feature_support(payload: dict, output: dict) -> dict:
    """Project canonical Gap declarations with their own review/manual/conditions.

    Call after input/output contract validation. Returned values are detached;
    missing references are reported, never repaired or interpreted as non-support.
    """
    product = payload["product"]
    validate("Product", product)
    sources = {row["id"]: row for row in payload["sources"]}
    features = {row["id"]: row for row in payload["features"]}
    needs = {row["id"]: row for row in output["needs"]}
    assessments = {row["gap_id"]: row for row in output["gap_assessments"]}
    for definition, items in (("Evidence", sources.values()), ("Feature", features.values()),
                              ("Need", needs.values()), ("Gap", output["gaps"])):
        for item in items:
            validate(definition, item)
    rows, violations = [], []

    def scoped(item):
        return all(item[key] == product[key] for key in ("model_id", "document_version")) and (
            "source_kind" not in item or (item["source_kind"] == "synthetic") == (product["source_kind"] == "synthetic"))

    for gap in output["gaps"]:
        errors = []
        need = needs.get(gap["need_id"])
        cited = set(gap["evidence_ids"])
        if any(eid not in sources for eid in cited):
            errors.append("MISSING_EVIDENCE")
        if any(eid in sources and not scoped(sources[eid]) for eid in cited):
            errors.append("SOURCE_SCOPE_MISMATCH")
        if not need or gap["model_id"] != product["model_id"] or need["model_id"] != product["model_id"]:
            errors.append("GAP_NEED_MISMATCH")
        elif not set(need["evidence_ids"]) <= cited:
            errors.append("GAP_REVIEW_MISSING")
        reviews = [] if not need else [eid for eid in need["evidence_ids"] if eid in cited
            and eid in sources and scoped(sources[eid]) and sources[eid]["source_type"] == "review"]
        manuals = [eid for eid in gap["evidence_ids"] if eid in sources and scoped(sources[eid])
                   and sources[eid]["source_type"] == "manual"]
        linked_features = []
        for fid in gap["feature_ids"]:
            feature = features.get(fid)
            if feature is None:
                errors.append("GAP_FEATURE_MISSING")
                linked_features.append({"feature_id": fid, "conditions": [], "manual_evidence_ids": []})
                continue
            if not scoped(feature):
                errors.append("FEATURE_SCOPE_MISMATCH")
            if not set(feature["evidence_ids"]) <= cited:
                errors.append("GAP_MANUAL_MISSING")
            if any(eid not in sources or sources[eid]["source_type"] != "manual"
                   or fid not in sources[eid]["feature_ids"] for eid in feature["evidence_ids"]):
                errors.append("FEATURE_MANUAL_MISSING")
            linked_features.append({"feature_id": fid, "conditions": feature["conditions"],
                                    "manual_evidence_ids": [eid for eid in feature["evidence_ids"]
                                                            if eid in manuals]})
        assessment = assessments.get(gap["id"])
        basis = None if assessment is None else assessment.get("support_basis")
        if assessment is not None and basis not in SUPPORT:
            raise DomainError("INVALID_ARGUMENT", "기능 지원 선언을 확인해야 합니다.", {"gap_id": gap["id"]})
        if assessment is None:
            errors.append("ASSESSMENT_COVERAGE")
        elif gap["support_status"] != SUPPORT[basis]:
            errors.append("SUPPORT_BASIS_MISMATCH")
        if basis == "explicit_supported" and not gap["feature_ids"]:
            errors.append("SUPPORTED_WITHOUT_FEATURE")
        if basis == "explicit_unsupported" and not manuals:
            errors.append("UNSUPPORTED_WITHOUT_MANUAL")
        errors = list(dict.fromkeys(errors))
        violations.extend({"code": code, "stage": "compare", "gap_id": gap["id"]} for code in errors)
        rows.append({"gap_id": gap["id"], "need_id": gap["need_id"],
                     "model_id": product["model_id"], "document_version": product["document_version"],
                     "source_kind": product["source_kind"], "support_basis": basis,
                     "support_status": gap["support_status"], "review_evidence_ids": reviews,
                     "manual_evidence_ids": manuals, "features": linked_features,
                     "evidence_ids": gap["evidence_ids"], "questions": gap["questions"],
                     "reason": None if assessment is None else assessment["reason"], "valid": not errors})
    return deepcopy({"rows": rows, "violations": violations, "semantic_accuracy_verified": False})
