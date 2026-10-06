"""Trace candidate -> Gap -> Need -> review/manual without granting acceptance.

Numeric mentions are review targets, never measured effects or a keyword verdict.
The semantic reviewer must distinguish factual claims, design targets and hypotheses.
"""
import re
from copy import deepcopy

from lgax_contracts import validate

from .feature_support import build_feature_support
from .residual_matrix import build_residual_matrix

_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*(?:%|분|초|시간|배|개|kg|g|mm|cm|ml|mL|L|W|kWh)(?![A-Za-z])")


def trace_concept_lineage(payload: dict, output: dict, *, residual: dict | None = None) -> dict:
    """Return 0..3 candidate graphs, hold reasons and exact missing references."""
    residual = build_residual_matrix(payload, output) if residual is None else residual
    rows = {row["gap_id"]: row for row in residual["rows"]}
    sources = {row["id"]: row for row in payload["sources"]}
    features = {row["id"] for row in payload["features"]}
    assessments = {row["concept_id"]: row for row in output["concept_assessments"]}
    candidates, violations = [], []
    if len(output["concepts"]) > min(3, payload["max_concepts"]):
        violations.append({"code": "CONCEPT_LIMIT", "stage": "concepts"})
    for concept in output["concepts"]:
        validate("Concept", concept)
        errors, links = [], []
        if concept["status"] not in ("proposed", "needs_review"):
            errors.append("HUMAN_DECISION_REQUIRED")
        if any(eid not in sources for eid in concept["evidence_ids"]):
            errors.append("MISSING_EVIDENCE")
        product = payload["product"]
        if any(eid in sources and (
            any(sources[eid][key] != product[key] for key in ("model_id", "document_version"))
            or (sources[eid]["source_kind"] == "synthetic") != (product["source_kind"] == "synthetic")
        ) for eid in concept["evidence_ids"]):
            errors.append("SOURCE_SCOPE_MISMATCH")
        for gid in concept["gap_ids"]:
            row = rows.get(gid)
            if row is None:
                errors.append("CONCEPT_GAP_MISSING")
                continue
            links.append(row)
            if not row["candidate_eligible"]:
                errors.append("CONCEPT_WITHOUT_CONFIRMED_GAP")
            if not set(row["evidence_ids"]) <= set(concept["evidence_ids"]):
                errors.append("CONCEPT_GROUNDING_MISSING")
        assessment = assessments.get(concept["id"])
        if assessment is None:
            errors.append("ASSESSMENT_COVERAGE")
        elif set(assessment["compared_feature_ids"]) != features:
            errors.append("DUPLICATION_COMPARISON_INCOMPLETE")
        if assessment and assessment["duplication"] in ("duplicate", "uncertain"):
            errors.append("DUPLICATE_CONCEPT" if assessment["duplication"] == "duplicate" else "UNCERTAIN_DUPLICATION")
        texts = {"title": concept["title"], "differentiation": concept["differentiation"],
                 **{f"requirements.{i}": value for i, value in enumerate(concept["requirements"])},
                 **{f"assumptions.{i}": value for i, value in enumerate(concept["assumptions"])}}
        if assessment:
            texts["assessment.reason"] = assessment["reason"]
        mentions = [{"field": field, "quote": match.group(), "matching_evidence_ids": [
            eid for eid in concept["evidence_ids"] if eid in sources and match.group() in sources[eid]["text"]],
            "requires_semantic_review": True}
            for field, text in texts.items() for match in _NUMBER.finditer(text)]
        errors = list(dict.fromkeys(errors))
        violations.extend({"code": code, "stage": "concepts", "concept_id": concept["id"]} for code in errors)
        candidates.append({"concept_id": concept["id"], "links": links,
                           "evidence_ids": concept["evidence_ids"], "requirements": concept["requirements"],
                           "assumptions": concept["assumptions"], "numeric_mentions": mentions,
                           "valid": not errors})
    return deepcopy({"candidates": candidates, "violations": violations,
                     "hold_reasons": output["hold_reasons"], "no_candidate_reasons": output["no_candidate_reasons"],
                     "semantic_accuracy_verified": False})


def build_quality_context(payload: dict, output: dict) -> dict:
    """Use the same linked declarations in deterministic and semantic reviews."""
    support = build_feature_support(payload, output)
    residual = build_residual_matrix(payload, output, support=support)
    lineage = trace_concept_lineage(payload, output, residual=residual)
    return {"feature_support": support, "residual_matrix": residual, "concept_lineage": lineage}
