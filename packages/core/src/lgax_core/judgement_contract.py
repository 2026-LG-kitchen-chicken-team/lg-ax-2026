"""CORE001 contracts and deterministic review policy, without a model backend.

The declarations about sentiment, support and duplication come from a future
reasoning handler. Checking their consistency does not prove semantic accuracy.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from lgax_contracts import load_schema

from .concept_lineage import build_quality_context

STAGES = ("plan", "retrieve", "needs", "compare", "concepts", "review")
MAX_REVISIONS = 2


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _array(items: dict, **limits: Any) -> dict:
    return {"type": "array", "items": items, **limits}


def _ref(name: str) -> dict:
    return {"$ref": f"#/$defs/{name}"}


def schema_for(direction: str) -> dict:
    """Reuse canonical types without changing the shared 0.1.0 contract."""
    text = {"type": "string", "minLength": 1, "pattern": r"\S"}
    texts = _array(text, uniqueItems=True)
    ids = _array(_ref("ID"), uniqueItems=True)
    if direction == "input":
        body = _object({
            "request": _ref("PlanningRequest"), "product": _ref("Product"),
            "sources": _array(_ref("Evidence")), "features": _array(_ref("Feature")),
            "revision_count": {"type": "integer", "minimum": 0, "maximum": MAX_REVISIONS},
            "max_concepts": {"type": "integer", "minimum": 1, "maximum": 3},
            "changed_evidence_ids": ids,
        })
    elif direction == "output":
        body = _object({
            "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "model_id": _ref("ID"), "document_version": text,
            "revision_count": {"type": "integer", "minimum": 0, "maximum": MAX_REVISIONS},
            "status": {"enum": ["completed", "held", "failed"]},
            "needs": _array(_ref("Need")), "gaps": _array(_ref("Gap")),
            "desired_outcomes": _array(_object({"need_id": _ref("ID"), "desired_outcome": text})),
            "concepts": _array(_ref("Concept"), maxItems=3),
            "review_assessments": _array(_object({
                "evidence_id": _ref("ID"),
                "polarity": {"enum": ["complaint", "positive", "conflicting", "irrelevant", "uncertain"]},
                "reason": text,
            })),
            "gap_assessments": _array(_object({
                "gap_id": _ref("ID"),
                "support_basis": {"enum": ["explicit_supported", "explicit_unsupported", "unmentioned", "conflicting"]},
                "resolution": {"enum": ["resolved", "remaining", "unknown"]}, "reason": text,
            })),
            "concept_assessments": _array(_object({
                "concept_id": _ref("ID"),
                "duplication": {"enum": ["distinct", "duplicate", "uncertain"]},
                "compared_feature_ids": ids, "reason": text,
            })),
            "questions": texts, "hold_reasons": texts, "unresolved": texts,
            "no_candidate_reasons": texts,
        })
    else:
        raise ValueError("direction must be input or output")
    canonical = deepcopy(load_schema()["$defs"])
    canonical["ID"] = deepcopy(canonical["Need"]["properties"]["id"])
    included: dict[str, dict] = {}

    def include(value: Any) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/$defs/"):
                name = reference.removeprefix("#/$defs/")
                if name not in included:
                    included[name] = canonical[name]
                    include(canonical[name])
            for child in value.values():
                include(child)
        elif isinstance(value, list):
            for child in value:
                include(child)

    include(body)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"urn:lgax:core:judgement:{direction}:1", **body, "$defs": included}


def input_digest(payload: dict) -> str:
    """Bind a result to the original request, source text, versions and revision."""
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def review_judgement(payload: Any, output: Any) -> dict:
    """Return a review decision; never execute tools, revise data or call models."""
    violations: list[dict[str, Any]] = []

    def flag(code: str, stage: str, **details: Any) -> None:
        item = {"code": code, "stage": stage, **details}
        if item not in violations:
            violations.append(item)

    def shape(direction: str, value: Any) -> bool:
        if any(Draft202012Validator(schema_for(direction)).iter_errors(value)):
            flag(f"{direction.upper()}_SCHEMA", "plan" if direction == "input" else "review")
            return False
        return True

    def index(items: list[dict], key: str, stage: str) -> dict:
        result = {item[key]: item for item in items}
        if len(result) != len(items):
            flag("DUPLICATE_ID", stage)
        return result

    def finish(input_valid: bool) -> dict:
        count = payload.get("revision_count", 0) if isinstance(payload, dict) else 0
        if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= MAX_REVISIONS:
            count = 0
        grounding = {"REVIEW_CONFLICT", "REVIEW_UNCERTAIN", "NO_REVIEW_EVIDENCE",
                     "SUPPORT_UNKNOWN", "SOURCE_KIND_MISMATCH",
                     "UNSUPPORTED_WITHOUT_MANUAL", "UNCERTAIN_DUPLICATION"}
        status = output.get("status") if isinstance(output, dict) else None
        if not input_valid or any(item["code"] in grounding for item in violations):
            action = "hold"
        elif violations:
            action = "revise" if count < MAX_REVISIONS else "unresolved"
        else:
            action = {"completed": "accept", "held": "hold", "failed": "unresolved"}[status]
        ordered = sorted(violations, key=lambda item: (STAGES.index(item["stage"]), item["code"]))
        return {"valid": not violations, "action": action, "revision_count": count,
                "next_revision_count": count + int(action == "revise"),
                "rerun_from": ordered[0]["stage"] if action == "revise" else None,
                "violations": ordered}

    if not shape("input", payload):
        return finish(False)
    product, request = payload["product"], payload["request"]
    scope = (product["model_id"], product["document_version"])
    if product["model_id"] not in request["model_ids"] or product["product_group"] != request["product_group"]:
        flag("REQUEST_PRODUCT_MISMATCH", "plan")
    sources = index(payload["sources"], "id", "retrieve")
    features = index(payload["features"], "id", "retrieve")
    for source in sources.values():
        if (source["model_id"], source["document_version"]) != scope:
            flag("SOURCE_SCOPE_MISMATCH", "retrieve")
        if (source["source_kind"] == "synthetic") != (product["source_kind"] == "synthetic"):
            flag("SOURCE_KIND_MISMATCH", "retrieve")
        for fid in source["feature_ids"]:
            if fid not in features:
                flag("SOURCE_FEATURE_MISSING", "retrieve")
            elif source["source_type"] == "manual" and source["id"] not in features[fid]["evidence_ids"]:
                flag("SOURCE_FEATURE_LINK_MISMATCH", "retrieve")
    for feature in features.values():
        if (feature["model_id"], feature["document_version"]) != scope:
            flag("FEATURE_SCOPE_MISMATCH", "retrieve")
        for eid in feature["evidence_ids"]:
            if eid not in sources or sources[eid]["source_type"] != "manual":
                flag("FEATURE_MANUAL_MISSING", "retrieve")
            elif feature["id"] not in sources[eid]["feature_ids"]:
                flag("FEATURE_SOURCE_LINK_MISMATCH", "retrieve")
    if any(eid not in sources for eid in payload["changed_evidence_ids"]):
        flag("CHANGED_EVIDENCE_MISSING", "retrieve")
    if violations:
        return finish(False)
    if not shape("output", output):
        return finish(True)
    if output["input_sha256"] != input_digest(payload):
        flag("STALE_INPUT", "plan")
    if (output["model_id"], output["document_version"]) != scope:
        flag("OUTPUT_SCOPE_MISMATCH", "plan")
    if output["revision_count"] != payload["revision_count"]:
        flag("REVISION_COUNT_MISMATCH", "review")
    needs = index(output["needs"], "id", "needs")
    gaps = index(output["gaps"], "id", "compare")
    concepts = index(output["concepts"], "id", "concepts")
    reviews = index(output["review_assessments"], "evidence_id", "needs")
    comparisons = index(output["gap_assessments"], "gap_id", "compare")
    duplicates = index(output["concept_assessments"], "concept_id", "concepts")
    outcomes = index(output["desired_outcomes"], "need_id", "needs")
    if set(outcomes) != set(needs):
        flag("DESIRED_OUTCOME_COVERAGE", "needs")
    expected_reviews = {eid for eid, source in sources.items() if source["source_type"] == "review"}
    if not expected_reviews and (
        output["status"] != "held" or not output["questions"] or not output["hold_reasons"]
    ):
        flag("NO_REVIEW_EVIDENCE", "needs")
    for actual, expected, stage in [
        (set(reviews), expected_reviews, "needs"), (set(comparisons), set(gaps), "compare"),
        (set(duplicates), set(concepts), "concepts"),
    ]:
        if actual != expected:
            flag("ASSESSMENT_COVERAGE", stage)

    def citations(item: dict, stage: str) -> None:
        if any(eid not in sources for eid in item["evidence_ids"]):
            flag("MISSING_EVIDENCE", stage)

    for need in needs.values():
        citations(need, "needs")
        if need["model_id"] != scope[0]:
            flag("NEED_MODEL_MISMATCH", "needs")
        for eid in need["evidence_ids"]:
            source, assessment = sources.get(eid), reviews.get(eid)
            if not source or source["source_type"] != "review":
                flag("NEED_REVIEW_REQUIRED", "needs")
            elif not assessment or assessment["polarity"] not in ("complaint", "conflicting"):
                flag("NON_COMPLAINT_AS_NEED", "needs")
    for assessment in reviews.values():
        if assessment["polarity"] == "conflicting" and (
            output["status"] != "held" or not output["questions"] or not output["hold_reasons"]
        ):
            flag("REVIEW_CONFLICT", "needs")
        if assessment["polarity"] == "uncertain" and (
            output["status"] != "held" or not output["questions"] or not output["hold_reasons"]
        ):
            flag("REVIEW_UNCERTAIN", "needs")
    if output["status"] == "completed":
        cited_reviews = {eid for need in needs.values() for eid in need["evidence_ids"]}
        complaints = {eid for eid, item in reviews.items() if item["polarity"] == "complaint"}
        if not complaints <= cited_reviews:
            flag("COMPLAINT_NOT_EXTRACTED", "needs")
        if {gap["need_id"] for gap in gaps.values()} != set(needs):
            flag("NEED_COMPARISON_MISSING", "compare")
    for module in build_quality_context(payload, output).values():
        for violation in module["violations"]:
            # Preserve the exact omitted edges for correction, never repair them.
            details = ({key: deepcopy(value) for key, value in violation.items()
                        if key not in ("code", "stage")}
                       if violation["code"] == "CONCEPT_GROUNDING_MISSING" else {})
            flag(violation["code"], violation["stage"], **details)
    if not concepts and not output["no_candidate_reasons"]:
        flag("ZERO_CANDIDATES_WITHOUT_REASON", "concepts")
    if output["status"] == "completed" and (output["hold_reasons"] or output["unresolved"]):
        flag("COMPLETED_WITH_UNRESOLVED", "review")
    if output["status"] == "held" and (concepts or not output["hold_reasons"] or not output["questions"]):
        flag("HOLD_WITHOUT_QUESTIONS", "review")
    if output["status"] == "failed" and (
        concepts or payload["revision_count"] != MAX_REVISIONS or not output["unresolved"]
    ):
        flag("INVALID_REVISION_TERMINATION", "review")
    return finish(True)
