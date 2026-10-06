"""Keep supported functionality and review-grounded remaining discomfort apart."""
from copy import deepcopy

from .feature_support import build_feature_support


def build_residual_matrix(payload: dict, output: dict, *, support: dict | None = None) -> dict:
    """Return resolved/remaining/unknown rows without inferring them from support.

    Resolution is a model declaration requiring semantic review. A supported
    feature can have remaining pain; unmentioned/conflicting claims need a hold.
    """
    support = build_feature_support(payload, output) if support is None else support
    supports = {row["gap_id"]: row for row in support["rows"]}
    assessments = {row["gap_id"]: row for row in output["gap_assessments"]}
    rows, violations = [], []
    for gap in output["gaps"]:
        declared = assessments.get(gap["id"])
        state = supports[gap["id"]]
        resolution = "unknown" if declared is None else declared["resolution"]
        errors = []
        if (resolution == "remaining" and not gap["remaining_pain"].strip()) or (
            resolution == "resolved" and gap["remaining_pain"].strip()
        ):
            errors.append("RESOLUTION_PAIN_MISMATCH")
        uncertain = state["support_basis"] in (None, "unmentioned", "conflicting") or resolution == "unknown"
        if uncertain and (output["status"] != "held" or not gap["questions"] or not output["hold_reasons"]):
            errors.append("SUPPORT_UNKNOWN")
        violations.extend({"code": code, "stage": "compare", "gap_id": gap["id"]} for code in errors)
        rows.append({**state, "resolution": resolution, "remaining_pain": gap["remaining_pain"],
                     "candidate_eligible": state["valid"] and not errors and not uncertain
                        and resolution == "remaining" and state["support_status"] != "insufficient_evidence",
                     "requires_confirmation": uncertain, "hold_reasons": output["hold_reasons"],
                     "valid": state["valid"] and not errors})
    return deepcopy({"rows": rows, "violations": violations, "semantic_accuracy_verified": False})
