"""Trace supplied fixed outputs to exact original sources. This tool never generates model output."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

REQUIREMENTS = ["R06", "R04", "R13", "R05"]


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def trace_output(payload, output, *, expected_model=None, expected_kind=None, dataset=None):
    sources = payload.get("sources", [])
    by_id = {}
    errors = []
    rows = []
    for s in sources:
        if s["id"] in by_id:
            raise ValueError("Duplicate original evidence ID")
        by_id[s["id"]] = s
    originals = {}
    reviews = {}
    if dataset is not None:
        for source in dataset["evidence"]:
            if source["id"] in originals:
                raise ValueError("Duplicate dataset evidence ID")
            originals[source["id"]] = source
        for review in dataset["reviews"]:
            if review["evidence_id"] in reviews:
                raise ValueError("Duplicate review evidence mapping")
            reviews[review["evidence_id"]] = review
    product = payload["product"]
    model = expected_model or product["model_id"]
    version = product["document_version"]
    expected_kind = expected_kind or product["source_kind"]
    if product["model_id"] != model:
        errors.append("INPUT_SCOPE_MISMATCH")
    if output is None:
        return {
            "requirements": REQUIREMENTS,
            "status": "fixed_output_pending",
            "output_present": False,
            "model_id": model,
            "document_version": version,
            "rows": [],
            "errors": ["NO_FIXED_OUTPUT"],
            "input_sha256": sha256(canonical(payload)).hexdigest(),
            "model_generations": 0,
            "semantic_support_verified": False,
            "http_sqlite_resume_verified": False,
        }
    if not isinstance(output, dict):
        raise TypeError("Fixed output must be a JSON object")

    def walk(node, pointer=""):
        if isinstance(node, dict):
            for key, value in node.items():
                here = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
                if key == "evidence_id":
                    yield here, value
                elif key.endswith("evidence_ids"):
                    if isinstance(value, list):
                        for n, eid in enumerate(value):
                            yield here + "/" + str(n), eid
                    else:
                        yield here, None
                else:
                    yield from walk(value, here)
        elif isinstance(node, list):
            for n, value in enumerate(node):
                yield from walk(value, pointer + "/" + str(n))

    for pointer, eid in walk(output):
        if not isinstance(eid, str) or not eid.strip():
            rows.append(
                {
                    "output_pointer": pointer,
                    "output_evidence_id": eid,
                    "valid": False,
                    "errors": ["INVALID_EVIDENCE_ID"],
                }
            )
            errors.append(pointer + ": INVALID_EVIDENCE_ID")
            continue
        s = by_id.get(eid)
        issues = []
        if s is None:
            rows.append(
                {
                    "output_pointer": pointer,
                    "output_evidence_id": eid,
                    "valid": False,
                    "errors": ["UNKNOWN_EVIDENCE_ID"],
                }
            )
            errors.append(pointer + ": UNKNOWN_EVIDENCE_ID")
            continue
        for name, wanted in [("model_id", model), ("document_version", version)]:
            if s.get(name) != wanted:
                issues.append(name.upper() + "_MISMATCH")
        if expected_kind is not None and s.get("source_kind") != expected_kind:
            issues.append("SOURCE_KIND_MISMATCH")
        if s.get("source_kind") not in ("public", "synthetic"):
            issues.append("UNDECLARED_SOURCE_KIND")
        if (
            not s.get("source_id")
            or not s.get("locator")
            or not isinstance(s.get("text"), str)
            or not s["text"].strip()
        ):
            issues.append("ORIGINAL_LOCATION_OR_TEXT_MISSING")
        if dataset is not None and originals.get(eid) != s:
            issues.append("ORIGINAL_SOURCE_MISMATCH")
        review = reviews.get(eid)
        if dataset is not None and s.get("source_type") == "review":
            if review is None:
                issues.append("REVIEW_RECORD_MISSING")
            elif any(
                review.get(k) != s.get(k)
                for k in ["model_id", "document_version", "source_kind", "source_id", "locator", "text"]
            ):
                issues.append("REVIEW_ORIGINAL_MISMATCH")
        requirements = ["R06", "R04", "R13"] if s.get("source_type") == "review" else ["R06", "R05"]
        rows.append(
            {
                "requirements": requirements,
                "output_pointer": pointer,
                "output_evidence_id": eid,
                "model_id": s.get("model_id"),
                "document_version": s.get("document_version"),
                "source_kind": s.get("source_kind"),
                "source_type": s.get("source_type"),
                "original_source_id": s.get("source_id"),
                "locator": s.get("locator"),
                "original_text": s.get("text"),
                "feature_ids": s.get("feature_ids", []),
                "original_review_id": review["id"] if review is not None else None,
                "review_origin_verified": review is not None and not issues,
                "original_source_sha256": sha256(canonical(s)).hexdigest(),
                "valid": not issues,
                "errors": issues,
            }
        )
        errors.extend(pointer + ": " + issue for issue in issues)
    if output.get("model_id") != model or output.get("document_version") != version:
        errors.append("OUTPUT_SCOPE_MISMATCH")
    return {
        "requirements": REQUIREMENTS,
        "status": "references_traced" if not errors else "failed",
        "output_present": True,
        "model_id": model,
        "document_version": version,
        "source_kind": product.get("source_kind"),
        "rows": rows,
        "errors": errors,
        "input_sha256": sha256(canonical(payload)).hexdigest(),
        "output_sha256": sha256(canonical(output)).hexdigest(),
        "model_generations": 0,
        "dataset_version": (
            dataset.get("dataset_version") or dataset.get("manifest", {}).get("version")
            if dataset is not None
            else None
        ),
        "dataset_sha256": sha256(canonical(dataset)).hexdigest() if dataset is not None else None,
        "dataset_originals_compared": dataset is not None,
        "output_contract_verified": False,
        "semantic_support_verified": False,
        "http_sqlite_resume_verified": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error("Preserve prior checks; choose a new output file")
    packet = json.loads(args.packet.read_bytes())
    result = trace_output(
        packet["input"],
        packet.get("output"),
        expected_model=packet.get("expected_model"),
        expected_kind=packet.get("expected_kind"),
        dataset=packet.get("dataset"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return 0 if result["status"] == "references_traced" else 2


if __name__ == "__main__":
    raise SystemExit(main())
