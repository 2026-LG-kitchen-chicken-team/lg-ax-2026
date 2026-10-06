"""Bound model context by avoiding duplicate derived evidence graphs.

Canonical request, sources, features and prior model declarations stay complete.
Full deterministic quality graphs remain in the run's request_context and trace;
the model receives their eligibility/validation annotations once by stable ID.
This does not alter any acceptance rule or infer support from customer pain.
"""
from copy import deepcopy


def model_context(context: dict) -> dict:
    result = deepcopy(context)
    quality = result.get("quality_context")
    if not isinstance(quality, dict):
        return result
    support = quality["feature_support"]
    residual = quality["residual_matrix"]
    lineage = quality["concept_lineage"]
    result["quality_context"] = {
        "representation": "derived_annotations_by_id_v1",
        "reference": "Canonical facts and wording are in sources, features, skill_input, "
                     "upstream_assessments or judgement. Rows below are validation annotations, "
                     "not independent sources or semantic acceptance.",
        "feature_support": {
            "rows": [{key: row[key] for key in ("gap_id", "support_basis", "support_status", "valid")}
                     for row in support["rows"]],
            "violations": support["violations"],
            "semantic_accuracy_verified": support["semantic_accuracy_verified"],
        },
        "residual_matrix": {
            "rows": [{key: row[key] for key in ("gap_id", "resolution", "candidate_eligible",
                                               "requires_confirmation", "valid")}
                     for row in residual["rows"]],
            "violations": residual["violations"],
            "semantic_accuracy_verified": residual["semantic_accuracy_verified"],
        },
        "concept_lineage": {
            "candidates": [{"concept_id": row["concept_id"],
                            "gap_ids": [link["gap_id"] for link in row["links"]],
                            "links": row["links"],
                            "numeric_mentions": row["numeric_mentions"], "valid": row["valid"]}
                           for row in lineage["candidates"]],
            "violations": lineage["violations"],
            "hold_reasons": lineage["hold_reasons"],
            "no_candidate_reasons": lineage["no_candidate_reasons"],
            "semantic_accuracy_verified": lineage["semantic_accuracy_verified"],
        },
    }
    return result
