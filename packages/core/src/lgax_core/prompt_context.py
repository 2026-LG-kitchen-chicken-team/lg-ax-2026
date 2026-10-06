"""Bound model context by avoiding duplicate derived evidence graphs.

Canonical request, sources, features and prior model declarations stay complete.
Full deterministic quality graphs remain in the run's request_context and trace;
the model receives their eligibility/validation annotations once by stable ID.
Column tables losslessly encode the existing annotation projection, not sources.
This does not alter any acceptance rule or infer support from customer pain.
"""
from copy import deepcopy


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
