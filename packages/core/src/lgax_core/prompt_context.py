"""Bound model context by avoiding duplicate derived evidence graphs.

Canonical request, sources, features and prior model declarations stay complete.
Full deterministic quality graphs remain in the run's request_context and trace;
the model receives their eligibility/validation annotations once by stable ID.
Column tables losslessly encode the existing annotation projection, not sources.
This does not alter any acceptance rule or infer support from customer pain.
"""
from copy import deepcopy


PUBLIC_PROVENANCE_GUIDE = (
    "모든 제목·요약·비교·콘셉트·장면에서 관찰로 쓰는 증상·신체 부위·대상·원인·행동·기간은 "
    "인용 원문이 직접 입증한 범위까지만 적습니다. 연관되거나 그럴듯하다는 이유로 다른 증상·부위·"
    "원인으로 확대하지 않습니다. 고객의 추측은 고객의 추측으로 남기고 확정 사실로 바꾸지 않습니다. "
    "새 대상·상황 확장은 해당 필드에서 기획 가정이라고 명시하고 assumptions에 기록합니다. "
    "반복 관리 언급을 단일 치료 시점으로 바꾸거나 총 사용 기간을 추가 사용 기간으로 합산하지 "
    "않습니다. before_steps와 visual_scenes.before도 원문에서 확인된 행동만 관찰로 씁니다. "
    "원문에 없는 설명서 열람·안내 실행·조치 실패를 추가한 가상 before는 그 자리에서 가정이라고 "
    "명시하고 assumptions에 기록합니다. 구매 희망·기대는 실제 만족이나 효과를 입증하지 않습니다. "
    "긍정·부정·혼합은 별점이 아니라 본문에 명시된 실제 경험으로 분류하고, 혼합은 명시적 칭찬과 "
    "불편이 함께 있을 때만 사용합니다. 칭찬과 초기 불편이 공존하면 둘을 보존합니다. "
    "공용 문서의 조건별 참고 안내는 고객의 원인·해결 증거가 아닙니다. 정확한 모델·문서 버전과 "
    "적용 조건이 미확인이면 그 한계를 표시하고, 발췌에 없는 실행 절차는 만들지 말고 공식 원문 "
    "연결 또는 추가 확인으로 남깁니다."
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
