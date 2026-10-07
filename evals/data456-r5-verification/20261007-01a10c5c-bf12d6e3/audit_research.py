"""Independent fixed-file R5 population audit; no sentiment inference or Gold access."""

import hashlib
import itertools
import json
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "data/research/r5-public-reviews-20261007"
BASE = "8ec1e8a51faabd6db032e52245680bef4229f93f"
HANDOFF = "0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def audit():
    checks = []
    sources = []

    def check(name, observed, expected):
        equal = (json.dumps(observed, sort_keys=True, ensure_ascii=False)
                 == json.dumps(expected, sort_keys=True, ensure_ascii=False))
        checks.append({"check": name, "passed": equal, "observed": observed, "expected": expected})

    for profile in ("fixed18", "balanced-pilot-v2"):
        directory = SOURCE / profile
        for name, expected in load(directory / "files.json").items():
            path = directory / name
            if name == "public-reviews.sqlite3":
                sources.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                                "status": "generated_research_DB_not_a_tracked_source",
                                "expected_artifact_sha256": expected})
                continue
            if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
                raise ValueError("Source manifest escapes fixed profile")
            actual = sha(path.read_bytes())
            check(profile + "/" + name + " exact source SHA", actual, expected)
            sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": actual})

    fixed = load(SOURCE / "fixed18/records.json")
    side = load(SOURCE / "balanced-pilot-v2/records.json")
    fixed_manifest = load(SOURCE / "fixed18/manifest.json")
    side_manifest = load(SOURCE / "balanced-pilot-v2/manifest.json")
    old = {row["original_review_id"]: row for row in fixed}
    new = [row for row in side if row["original_review_id"] not in old]
    combined = fixed + new
    check("179 fixed rows", len(fixed), 179)
    check("60 UI sidecar rows", len(side), 60)
    check("unique fixed IDs", len(old), len(fixed))
    check("unique sidecar IDs", len({row["original_review_id"] for row in side}), len(side))
    check("published new-unique projection", load(SOURCE / "balanced-pilot-v2/new_unique_records.json"), new)
    check("combined unique rows", len(combined), side_manifest["collection"]["combined_unique_IDs"])
    check("fixed handoff pin", sha((SOURCE / "fixed18/records.json").read_bytes()),
          "98830d3078d5c14443ee672a4fd6d5ae7fbafe6c77ea15ab6b14828ad2d5ad6f")
    check("sidecar handoff pin", sha((SOURCE / "balanced-pilot-v2/records.json").read_bytes()),
          "d8ac06a75f53eac2fc2db469d78fa967bbc20883048aa44190217fd19d26fb7d")
    check("sidecar old-input pins", side_manifest["v1_input_hashes"],
          {name: sha((SOURCE / "fixed18" / name).read_bytes())
           for name in ("records.json", "products.json", "manifest.json")})
    overlap = []
    for row in side:
        ident = row["original_review_id"]
        if ident in old:
            original = old[ident]
            check(ident + " overlap body equivalence", normalized(row["text"]), normalized(original["text"]))
            check(ident + " inherited split", row["split"], original["split"])
            overlap.append({"original_review_id": ident, "fixed_text_sha256": original["text_sha256"],
                            "sidecar_text_sha256": row["text_sha256"], "normalized_equal": True})
    check("duplicate raw-row count", len(overlap), side_manifest["collection"]["old_ID_overlap"])

    membership = []
    for index, row in enumerate(combined):
        ident = row["original_review_id"]
        check(ident + " raw UTF8 text SHA", sha(row["text"].encode("utf-8")), row["text_sha256"])
        check(ident + " public kind", row["source_kind"], "public")
        check(ident + " eligible flag remains false", row["eligible_for_model_input"], False)
        check(ident + " unknown purchased SKU", row["actual_purchased_model_id"], None)
        check(ident + " unknown posting date", row["published_at"], None)
        is_fixed = index < len(fixed)
        quarantined = row["split"] == "quarantine"
        if is_fixed:
            check(ident + " quarantine consistency", row["quarantined"], quarantined)
        source_path = "fixed18/records.json" if is_fixed else "balanced-pilot-v2/records.json"
        source_index = index if is_fixed else side.index(row)
        membership.append({"original_review_id": ident, "split": row["split"],
                           "quarantined": quarantined, "displayed_page_model": row["displayed_model_id"],
                           "actual_purchased_model_id": None, "published_at": None,
                           "purchase_date": row["purchase_date"], "text_sha256": row["text_sha256"],
                           "normalized_text_sha256": sha(normalized(row["text"]).encode("utf-8")),
                           "source_url": row["source_url"], "source_locator": row["source_locator"],
                           "source_file": (SOURCE / source_path).relative_to(ROOT).as_posix(),
                           "source_json_pointer": "/" + str(source_index),
                           "quality_flags": row.get("quality_flags", []),
                           "counted_in_research_population": not quarantined,
                           "counted_in_monthly_population": False})

    split_counts = dict(Counter(row["split"] for row in combined))
    check("combined split counts", split_counts, side_manifest["collection"]["combined_split_counts"])
    intersections = []
    for left, right in itertools.combinations(("development", "independent_evaluation", "demonstration"), 2):
        for field in ("original_review_id", "normalized_text_sha256"):
            a = {row[field] for row in membership if row["split"] == left}
            b = {row[field] for row in membership if row["split"] == right}
            shared = sorted(a & b)
            check(left + " / " + right + " " + field + " overlap", len(shared), 0)
            intersections.append({"left": left, "right": right, "field": field, "shared": shared})

    products = load(SOURCE / "fixed18/products.json")
    check("18 displayed page models", len(products), fixed_manifest["model_count"])
    models = []
    for product in products:
        model = product["model_id"]
        rows = [row for row in combined if row["displayed_model_id"] == model]
        included = [row for row in rows if row["split"] != "quarantine"]
        models.append({"displayed_page_model": model, "product_group": product["product_group"],
                       "raw_unique_rows_assigned_to_primary_page": len(rows),
                       "quarantined": len(rows) - len(included), "research_denominator": len(included),
                       "posting_date_unknown_excluded": len(included), "monthly_denominator": 0,
                       "topic_numerator": None, "topic_ratio": None,
                       "exact_SKU_denominator": 0,
                       "member_original_review_ids": [row["original_review_id"] for row in included]})
    population = [row for row in combined if row["split"] != "quarantine"]
    check("research denominator after quarantine", len(population), 226)
    check("per-primary-page research denominator sum", sum(m["research_denominator"] for m in models),
          len(population))
    check("unknown-date excluded population", sum(row["published_at"] is None for row in population), 226)
    execution = load(SOURCE / "fixed18/development.dataset.json")
    check("R5 execution SHA", sha((SOURCE / "fixed18/development.dataset.json").read_bytes()),
          "aee2b54b80b5d48559cab4d45eed1e3c3a3d2cb7d9f087542a820a22cf5e69a7")
    for collection, expected in (("products", 3), ("reviews", 0), ("features", 9), ("evidence", 21)):
        check("execution " + collection + " count", len(execution[collection]), expected)

    # Public prior development corpora only. Private candidate inputs/answers are never read.
    prior_paths = sorted((ROOT / "data/demo").glob("*.json")) + [
        ROOT / "data/research/PM-DATA-intake-20261006/generated/dataset.json",
        ROOT / "data/document_datasets/lg-three-models-20261005.json",
    ]
    previous = {}
    for path in prior_paths:
        value = load(path)
        if not isinstance(value, dict) or not isinstance(value.get("reviews"), list):
            continue
        for row in value["reviews"]:
            if isinstance(row, dict) and isinstance(row.get("text"), str):
                key = sha(normalized(row["text"]).encode("utf-8"))
                previous.setdefault(key, []).append({"file": path.relative_to(ROOT).as_posix(),
                                                      "review_id": row.get("id"),
                                                      "file_sha256": sha(path.read_bytes())})
    exposure = [{"original_review_id": row["original_review_id"], "split": row["split"],
                 "prior_sources": previous[row["normalized_text_sha256"]]}
                for row in membership if row["normalized_text_sha256"] in previous]
    return {
        "status": "PASS" if all(c["passed"] for c in checks) else "FAIL",
        "base_commit": BASE, "PM_handoff_head": HANDOFF, "source_files": sources,
        "checks": checks, "check_count": len(checks), "failed_checks": [c for c in checks if not c["passed"]],
        "raw_rows": len(fixed) + len(side), "overlap": overlap, "unique_rows": len(combined),
        "split_counts": split_counts, "split_intersections": intersections,
        "quarantine_excluded": split_counts["quarantine"], "research_denominator": len(population),
        "research_rating_counts": dict(Counter(str(row["rating"]) for row in population)),
        "unknown_posting_date_excluded": 226, "monthly_denominator": 0,
        "monthly_topic_numerators": None, "topic_ratios": None,
        "topic_status": "unconfirmed_no_approved_real_review_annotation",
        "exact_SKU_eligible_reviews": 0, "membership": membership, "page_models": models,
        "prior_public_development_exposure_matches": exposure,
        "exposure_scan_scope": [path.relative_to(ROOT).as_posix() for path in prior_paths],
        "exposure_scan_is_exhaustive": False,
        "evaluation_gate": {
            "old_public_eight_disposition": "development_diagnostics_and_regression_only",
            "disposition_authority": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6029601114",
            "R5_evaluation_research_candidates": split_counts["independent_evaluation"],
            "R5_candidates_already_in_Git_source": True,
            "candidate_research_split_is_independence_approval": False,
            "Gold_approved": False, "independence_approved": False,
            "final_independent_scorer_fixed": False, "private_delivery_receipt_received": False,
            "actual_paired_model_outputs_received": False, "actual_independent_scores": None,
            "private_inputs_or_answers_read": False,
        },
        "limitations": ["page model is not purchased SKU", "purchase date is not posting date",
                        "238 source records are a purposive sample, not a market population",
                        "ratings are not complaint/topic labels", "research DB artifact can be regenerated",
                        "source publication and internal split separation do not establish evaluator independence"],
        "new_model_calls": 0, "new_OCR_calls": 0, "network_requests": 0,
    }


if __name__ == "__main__":
    result = audit()
    Path("/artifacts/result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({key: result[key] for key in ("status", "check_count", "unique_rows", "split_counts",
                                                "research_denominator", "monthly_denominator")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
