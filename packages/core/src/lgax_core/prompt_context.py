"""Bound model context by avoiding duplicate derived evidence graphs.

Canonical request, sources, features and prior model declarations stay complete.
Full deterministic quality graphs remain in the run's request_context and trace;
the model receives their eligibility/validation annotations once by stable ID.
Column tables losslessly encode the existing annotation projection, not sources.
This does not alter any acceptance rule or infer support from customer pain.
"""
from copy import deepcopy

PUBLIC_PROVENANCE_GUIDE = (
    "지침·예시는 고객 자료가 아니며 출력에 복사하지 않습니다. 원문 주체·증상·신체 부위·행동·"
    "총 사용 기간·추측 범위를 보존하고 추측을 확정하거나 기간을 합산하지 않습니다. "
    "원문 밖 가상 before는 해당 자리와 assumptions에 가정으로 표시합니다. "
    "scope_caveat는 이번 문제 원문의 미확인 사항만 1~2문장입니다. "
    "공용 자료는 원인·해결 증거가 아니며 적용 모델·조건 미확인을 표시하고 "
    "발췌 밖 절차를 만들지 않습니다."
)


def public_generation_stage(schema: dict) -> str | None:
    """Recognize only the planner's complete, trusted generation schemas.

    Patch, legacy and extended schemas remain strict. This recognizes an
    envelope for item validation; it does not validate or approve any item.
    """
    from lgax_contracts.research import load_research_schema

    root = load_research_schema()
    definitions = root["$defs"]
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    problem_array = properties.get("problems", {})
    limit = problem_array.get("maxItems") if isinstance(problem_array, dict) else None
    if type(limit) is int and 1 <= limit <= 5:
        discover = {
            "type": "object", "properties": {
                "problems": {"type": "array", "maxItems": limit, "items": {"$ref": "#/$defs/Problem"}},
                "summaries": definitions["PlanningBrief"]["properties"]["summaries"],
            }, "required": ["problems", "summaries"], "additionalProperties": False,
            "$defs": {name: definitions[name] for name in ("Problem", "SummaryItem")},
        }
        if schema == discover:
            return "discover"
    plan = {
        "type": "object", "properties": {
            "comparisons": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/Comparison"}},
            "concepts": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"$ref": "#/$defs/Concept"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
        }, "required": ["comparisons", "concepts", "uncertainties"], "additionalProperties": False,
        "$defs": {name: definitions[name] for name in ("Comparison", "Concept")},
    }
    return "plan" if schema == plan else None


def candidate_item_path(stage: str, path: list) -> bool:
    """Array shape, cardinality and envelope errors never count as item errors."""
    if stage == "discover":
        return (len(path) >= 2 and path[0] == "problems" and type(path[1]) is int
                or len(path) >= 3 and path[0] == "summaries"
                and path[1] in {"positive", "negative", "mixed"} and type(path[2]) is int)
    return (stage == "plan" and len(path) >= 2 and path[0] in {"comparisons", "concepts"}
            and type(path[1]) is int)


def _column_table(rows: list[dict], columns: tuple[str, ...]) -> dict:
    return {"columns": list(columns), "values": [[row[key] for key in columns] for row in rows]}


def model_context(context: dict) -> dict:
    result = deepcopy(context)
    quality = result.get("quality_context")
    if not isinstance(quality, dict):
        return result
    support = quality["feature_support"]
    residual = quality["residual_matrix"]
    lineage = quality["concept_lineage"]
    quality["representation"] = "derived_annotations_column_table_v2"
    quality["reference"] = (
        "Canonical facts and wording are in sources, features, skill_input, upstream_assessments or judgement. "
        "Annotations are not sources or semantic acceptance. Each values row follows its table's columns order; "
        "zip(columns, row) restores every annotation field exactly."
    )
    # Keep all module-level violations, flags and future metadata. Only repeated
    # keys in the same v1 annotation projection change their representation.
    quality["feature_support"] = {
        **{key: value for key, value in support.items() if key != "rows"},
        **_column_table(support["rows"], ("gap_id", "support_basis", "support_status", "valid")),
    }
    quality["residual_matrix"] = {
        **{key: value for key, value in residual.items() if key != "rows"},
        **_column_table(residual["rows"], ("gap_id", "resolution", "candidate_eligible",
                                          "requires_confirmation", "valid")),
    }
    # The lineage projection, links and numeric mentions stay as in v1. Full
    # deterministic graphs are retained separately in the immutable request_context.
    quality["concept_lineage"] = {
        **lineage,
        "candidates": [{"concept_id": row["concept_id"],
                        "gap_ids": [link["gap_id"] for link in row["links"]],
                        "links": row["links"],
                        "numeric_mentions": row["numeric_mentions"], "valid": row["valid"]}
                       for row in lineage["candidates"]],
    }
    return result
