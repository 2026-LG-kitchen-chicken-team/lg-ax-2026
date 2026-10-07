"""One field patch per reviewed public-planning item, never full regeneration.

Accepted means contract/guard acceptance only, not independent semantic approval.
Failures preserve the original item and produce private, structured diagnostics.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError
from lgax_contracts.research import load_research_schema, validate_planning_brief, validate_research_bundle

from .errors import DomainError
from .model_client import StructuredModelResult
from .public_planning import (
    _MODEL_ERROR_CODES,
    _MODEL_ERROR_REASONS,
    INSTRUCTIONS,
    PublicPlanner,
    _definition_schema,
    _digest,
    _output_schema,
    _strings,
    apply_field_patch,
    claim_issues,
    is_customer_source,
    source_facts,
)

ITEM_COLLECTIONS = {"Problem": "problems", "Comparison": "comparisons", "Concept": "concepts"}
IMMUTABLE_FIELDS = {"id", "problem_id", "problem_ids"}


def validate_feedback(bundle: dict, previous: dict, feedback: list[dict]) -> None:
    """Validate the complete request before a caller opens any model connection."""
    try:
        validate_research_bundle(bundle)
        validate_planning_brief(previous)
    except (ValidationError, ValueError, TypeError, KeyError) as error:
        raise ValueError("Repair requires valid research and previous-brief contracts") from error
    if any(previous[key] != bundle[key] for key in ("bundle_id", "product_group", "analysis_scope")):
        raise ValueError("Repair bundle, product group and scope must match the previous brief")
    if previous["source_facts"] != source_facts(bundle):
        raise ValueError("Repair requires the exact original source-facts snapshot")
    if (previous["revision"] == 0 and previous["previous_brief_id"] is not None
            or previous["revision"] > 0 and (not previous["previous_brief_id"]
                                             or previous["previous_brief_id"] == previous["brief_id"])):
        raise ValueError("Previous revision and parent identity are inconsistent")
    catalog = {source["source_id"] for source in bundle["sources"]}
    problem_ids = {item["id"] for item in previous["problems"]}
    item_ids = [item["id"] for collection in ITEM_COLLECTIONS.values() for item in previous[collection]]
    if len(set(item_ids)) != len(item_ids) or set(item_ids) & catalog:
        raise ValueError("Item identities must be unique and distinct from sources")
    for kind, collection in ITEM_COLLECTIONS.items():
        items = previous[collection]
        if len({item["id"] for item in items}) != len(items):
            raise ValueError("Previous item IDs must be unique within each kind")
        for item in items:
            if not set(item["source_ids"] + item.get("counter_source_ids", [])) <= catalog:
                raise ValueError("Previous items must cite sources in the pinned bundle")
            if kind == "Comparison" and item["problem_id"] not in problem_ids:
                raise ValueError("A previous comparison has an unknown problem")
            if kind == "Concept" and not set(item["problem_ids"]) <= problem_ids:
                raise ValueError("A previous concept has an unknown problem")
    for relation in previous["relations"]:
        if (not set(relation["source_ids"]) <= catalog
                or relation["from_id"] not in catalog | set(item_ids)
                or relation["to_id"] not in catalog | set(item_ids)):
            raise ValueError("Previous relations must refer to pinned sources and existing items")
    if not isinstance(feedback, list) or not 1 <= len(feedback) <= 4:
        raise ValueError("Feedback must contain one to four item requests")
    seen = set()
    definitions = load_research_schema()["$defs"]
    for request in feedback:
        if not isinstance(request, dict) or set(request) != {"item_kind", "item_id", "fields", "message"}:
            raise ValueError("Each feedback item requires exactly kind, ID, fields and message")
        kind, item_id, fields, message = (request[key] for key in ("item_kind", "item_id", "fields", "message"))
        if not isinstance(kind, str) or kind not in ITEM_COLLECTIONS or not isinstance(item_id, str):
            raise ValueError("Feedback item kind and ID must identify an existing item")
        identity = (kind, item_id)
        if identity in seen:
            raise ValueError("An item may receive only one repair request")
        seen.add(identity)
        if not any(item["id"] == item_id for item in previous[ITEM_COLLECTIONS[kind]]):
            raise ValueError("Feedback item ID does not exist")
        allowed = definitions[kind]["properties"].keys() - IMMUTABLE_FIELDS
        if (not isinstance(fields, list) or not fields or any(not isinstance(field, str) for field in fields)
                or len(fields) != len(set(fields)) or not set(fields) <= allowed):
            raise ValueError("Repair fields must be distinct mutable fields of the requested kind")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise ValueError("A review message must contain one to 500 characters")


def _patch_issues(kind: str, candidate: dict, fields: set[str], catalog: dict, constraints: list[str]) -> list[dict]:
    issues = []
    references = candidate["source_ids"] + candidate.get("counter_source_ids", [])
    if not set(references) <= catalog.keys():
        return [{"code": "unknown_source_id", "field": "source_ids"}]
    cited = [catalog[eid] for eid in candidate["source_ids"]]
    if kind == "Problem" and not any(is_customer_source(source) for source in cited):
        issues.append({"code": "problem_requires_customer_source", "field": "source_ids"})
    if kind == "Concept" and candidate["status"] == "supported":
        issues.append({"code": "draft_has_no_independent_quality_approval", "field": "status"})
    no_hardware = kind == "Concept" and any(re.search(
        r"하드웨어.{0,8}(?:불가|없이)|센서.{0,8}불가|기기.{0,8}제어.{0,8}불가", constraint)
        for constraint in constraints)
    for field in fields - {"source_ids", "counter_source_ids", "status"}:
        for _, text in _strings(candidate[field]):
            issues.extend(claim_issues(field, text, cited))
            if (no_hardware and field in {"mechanism", "proposed_changes", "after_steps"}
                    and re.search(r"센서.{0,8}(?:추가|탑재)|(?:새|신규)\s*부품|(?:기기|원격).{0,8}제어|(?:가열)?출력.{0,8}변경", text)
                    and not re.search(r"없이|하지\s*않|변경\s*불가|추가\s*불가|제어\s*불가", text)):
                issues.append({"code": "explicit_no_hardware_constraint", "field": field})
    return issues


def repair_public_brief(model_caller, bundle: dict, previous: dict, feedback: list[dict], *,
                        runtime_metadata: dict | None = None, max_prompt_characters: int = 26000,
                        max_source_characters: int = 1800, max_model_calls: int = 4) -> dict:
    """Patch only requested fields once each; retain failed items byte-for-byte."""
    validate_feedback(bundle, previous, feedback)
    if not callable(model_caller):
        raise ValueError("A repair caller must accept a prompt and schema")  # noqa: TRY004 -- one input-error type
    if (type(max_prompt_characters) is not int or not 4000 <= max_prompt_characters <= 40000
            or type(max_source_characters) is not int or not 300 <= max_source_characters <= 2000
            or type(max_model_calls) is not int or not 1 <= max_model_calls <= 4):
        raise ValueError("Repair budgets are outside supported bounds")
    if runtime_metadata is not None and not isinstance(runtime_metadata, dict):
        raise ValueError("Runtime metadata must be an object")
    bundle, previous, feedback = deepcopy(bundle), deepcopy(previous), deepcopy(feedback)
    catalog = {source["source_id"]: source for source in bundle["sources"]}
    result = deepcopy(previous)
    result.update(brief_id=f"brief-{uuid4().hex}", run_id=f"run-{uuid4().hex}",
                  revision=previous["revision"] + 1, previous_brief_id=previous["brief_id"])
    trace, issues, outcomes, selected_ids = [], [], [], set()
    context_builder = PublicPlanner(model_caller, max_source_characters=max_source_characters)._source_context
    definitions = load_research_schema()["$defs"]
    removed_by_item = {}
    for request in feedback:
        kind, item_id = request["item_kind"], request["item_id"]
        collection = ITEM_COLLECTIONS[kind]
        position = next(index for index, item in enumerate(result[collection]) if item["id"] == item_id)
        original = previous[collection][position]
        fields = set(request["fields"])
        source_ids = list(dict.fromkeys(original["source_ids"] + original.get("counter_source_ids", [])
                                        + [eid for eid in catalog if eid in request["message"]]))
        sources = [context_builder(catalog[eid]) for eid in source_ids]
        properties = {field: deepcopy(definitions[kind]["properties"][field]) for field in sorted(fields)}
        for field in fields & {"source_ids", "counter_source_ids"}:
            properties[field]["items"] = {"type": "string", "enum": source_ids}
        if "status" in fields and kind == "Concept":
            properties["status"]["enum"] = ["draft", "needs_sources"]
        schema = _output_schema({"patch": {"type": "object", "properties": properties,
                                          "required": sorted(fields), "additionalProperties": False}}, ())
        context = {"task": "독립 검수에서 지적한 필드만 한 번 수정하세요. 정상 필드·항목과 정체성을 보존하세요.",
                   "review": request, "original_item": original, "analysis_scope": bundle["analysis_scope"],
                   "goal": previous["goal"], "constraints": previous["constraints"], "sources": sources}
        prompt = INSTRUCTIONS + "\n분석할 데이터(JSON):\n" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        failure = None
        if len(prompt) > max_prompt_characters:
            failure = "prompt_too_large"
        elif len(trace) >= max_model_calls:
            failure = "repair_call_budget_exhausted"
        if failure is not None:
            issues.append({"kind": kind, "item_id": item_id, "code": failure})
            outcomes.append({"item_kind": kind, "item_id": item_id, "status": "failed"})
            continue
        record = {"stage": "repair_fields", "item_kind": kind, "item_id": item_id,
                  "prompt_sha256": _digest(prompt), "prompt_characters": len(prompt), "status": "attempted"}
        trace.append(record)
        selected_ids.update(source_ids)
        try:
            returned = model_caller(prompt, deepcopy(schema))
            data, metadata = ((returned.data, returned.metadata) if isinstance(returned, StructuredModelResult)
                              else (returned, {}))
            record["response"], record["metadata"] = deepcopy(data), deepcopy(metadata)
            Draft202012Validator(schema).validate(data)
            candidate = apply_field_patch(original, data["patch"], fields)
            Draft202012Validator(_definition_schema(kind)).validate(candidate)
            candidate_issues = _patch_issues(kind, candidate, fields, catalog, previous["constraints"])
            if candidate_issues:
                issues.append({"kind": kind, "item_id": item_id, "issues": candidate_issues})
                record["status"] = "rejected"
                outcomes.append({"item_kind": kind, "item_id": item_id, "status": "failed"})
                continue
            result[collection][position] = candidate
            old_sources = set(original["source_ids"] + original.get("counter_source_ids", []))
            new_sources = set(candidate["source_ids"] + candidate.get("counter_source_ids", []))
            removed_by_item[item_id] = old_sources - new_sources
            record["status"] = "returned"
            outcomes.append({"item_kind": kind, "item_id": item_id, "status": "accepted"})
        except (ValidationError, ValueError, TypeError, KeyError, RuntimeError, DomainError, OSError) as error:
            record["status"], record["error_type"] = "rejected", type(error).__name__
            if isinstance(error, DomainError):
                if isinstance(error.code, str) and error.code in _MODEL_ERROR_CODES:
                    record["error_code"] = error.code
                reason = error.details.get("reason") if isinstance(error.details, dict) else None
                if isinstance(reason, str) and reason in _MODEL_ERROR_REASONS:
                    record["error_reason"] = reason
            issues.append({"kind": kind, "item_id": item_id, "code": "repair_response_rejected",
                           "error_type": type(error).__name__})
            outcomes.append({"item_kind": kind, "item_id": item_id, "status": "failed"})
    for relation in result["relations"]:
        removed = (removed_by_item.get(relation["from_id"], set())
                   | removed_by_item.get(relation["to_id"], set()))
        relation["source_ids"] = [eid for eid in relation["source_ids"] if eid not in removed]
    if (any(outcome["status"] == "failed" for outcome in outcomes)
            or any(concept["status"] == "needs_sources" for concept in result["concepts"])):
        result["status"] = "needs_sources"
    result["runtime"] = {**deepcopy(runtime_metadata or {}), "execution_kind": "public_research_field_repair",
                         "independent_semantic_quality_verified": False, "market_frequency_estimated": False,
                         "model_calls": trace, "feedback": feedback, "repair_outcomes": outcomes, "item_issues": issues,
                         "parent_run_id": previous["run_id"], "source_bundle_sha256": _digest(bundle),
                         "source_facts_sha256": _digest(result["source_facts"]), "input_source_count": len(catalog),
                         "selected_source_ids": sorted(selected_ids), "omitted_source_count": len(catalog) - len(selected_ids),
                         "max_model_calls": max_model_calls, "max_repairs_per_item": 1}
    validate_planning_brief(result)
    return result
