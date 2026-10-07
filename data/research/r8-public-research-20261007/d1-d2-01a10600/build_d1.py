"""Reuse fixed R5 records and landing writer; build a separate research delivery.

No acquisition, resplitting, model invocation or runtime contract modification.
Run in the existing zero-auth validator; output remains outside tracked sources.
"""
import argparse
from collections import Counter
from hashlib import sha256
import itertools
import json
from pathlib import Path
import sqlite3
import unicodedata

from lgax_core.public_review_collection import save_landing_db

SOURCE_COMMIT = "58feb9c30fc5faae1cc8acfb0ff409106a6d7174"
R5 = "data/research/r5-public-reviews-20261007"
PINS = {
    "fixed18/records.json": "98830d3078d5c14443ee672a4fd6d5ae7fbafe6c77ea15ab6b14828ad2d5ad6f",
    "fixed18/products.json": "5575df7a988d919eedc16a050914d192e30fc8eff1e0ad7b5a97c6328adb9d8b",
    "fixed18/manifest.json": "3a35518787c1959d29dd11f6a651194f7b7a6be971e392a470cff3da240c895d",
    "balanced-pilot-v2/records.json": "d8ac06a75f53eac2fc2db469d78fa967bbc20883048aa44190217fd19d26fb7d",
    "balanced-pilot-v2/new_unique_records.json": "2929d20a4cb12c9ff20faa9d4fc1db8b5a14ae947c374f0b5166290178a2f3b2",
    "balanced-pilot-v2/manifest.json": "9ceb23e5b02e9541091a15673d6d1f161462bfd79c421eed5ddc652093aff37d",
    "fixed18/development.dataset.json": "aee2b54b80b5d48559cab4d45eed1e3c3a3d2cb7d9f087542a820a22cf5e69a7",
    "independence-holds.20261007.v1.json": "df4d83bc74a68897f17d0709a2ff5b4ab5edcc00eec0c6709491588a48d5fbbf",
}
VERSION = "lg-public-research.20261007.d1-01a10600.v1"
PRIMARY = {"fridge": "T876MEE1H1", "dishwasher": "DUE6BGL2E", "microwave": "MW23FDI"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalized_digest(text):
    return sha256(" ".join(unicodedata.normalize("NFKC", text).split()).encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def build(root, output):
    if output.exists():
        raise ValueError("Preserve prior delivery: choose a new output folder")
    output.mkdir(parents=True)
    values, source_hashes = {}, {}
    for name, expected in PINS.items():
        raw = (root / R5 / name).read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError("Fixed input hash changed: " + name)
        values[name] = json.loads(raw)
        source_hashes[f"{R5}/{name}"] = digest
    first = values["fixed18/records.json"]
    newer = values["balanced-pilot-v2/new_unique_records.json"]
    observations = [("fixed18", i, r) for i, r in enumerate(first)] + [
        ("balanced-pilot-v2", i, r) for i, r in enumerate(values["balanced-pilot-v2/records.json"])
    ]
    products = values["fixed18/products.json"]
    product_map = {p["model_id"]: p for p in products}
    all_records = first + newer
    assert len(first) == 179 and len(newer) == 59 and len(all_records) == 238
    assert len({r["original_review_id"] for r in all_records}) == 238
    counts = Counter(r["split"] for r in all_records)
    assert dict(counts) == {"development": 141, "independent_evaluation": 36, "demonstration": 49, "quarantine": 12}
    old_ids = {r["original_review_id"] for r in first}
    repeated = [r for r in values["balanced-pilot-v2/records.json"] if r["original_review_id"] in old_ids]
    assert len(repeated) == 1 and repeated[0]["original_review_id"] == "860977"
    assert all(r["actual_purchased_model_id"] is None and r["published_at"] is None for r in all_records)
    assert not any(r["eligible_for_model_input"] for r in all_records)
    overlay = values["independence-holds.20261007.v1.json"]
    exposure = {r["original_review_id"]: r for r in overlay["known_development_exposure"]}
    original_map = {r["original_review_id"]: r for r in all_records}
    normalized = []
    membership = []
    for r in all_records:
        rid = r["original_review_id"]
        assert sha256(r["text"].encode()).hexdigest() == r["text_sha256"]
        source_profile = "fixed18" if rid in old_ids else "balanced-pilot-v2"
        row = dict(r)
        group = r.get("dedup_group_id", r.get("body_group_id"))
        assert group
        # Adapter-only column for the existing landing writer; original rows retained below.
        row["dedup_group_id"] = group
        normalized.append(row)
        membership.append({
            "original_review_id": rid, "product_group": product_map[r["displayed_model_id"]]["product_group"],
            "displayed_model_id": r["displayed_model_id"], "actual_purchased_model_id": None,
            "published_at": None, "purchase_date": r["purchase_date"], "split": r["split"],
            "source_profile": source_profile, "original_group_field": "dedup_group_id" if "dedup_group_id" in r else "body_group_id",
            "original_group_id": group, "normalized_body_sha256": normalized_digest(r["text"]),
            "text_sha256": r["text_sha256"], "original_record_sha256": sha256(canonical(r)).hexdigest(),
            "source_url": r["source_url"], "source_locator": r["source_locator"],
            "manual_version": r["manual_version"], "document_version": r.get("document_version", r.get("manual_version")),
            "observed_at": r.get("collected_at", r.get("observed_at")), "rating": r["rating"],
            "quarantined": r["split"] == "quarantine", "eligible_for_exact_sku_judgement": False,
            "known_development_exposure": rid in exposure, "independent_use_approved": False,
            "quality_flags": r["quality_flags"], "input_hold_reasons": r["input_hold_reasons"],
        })
    intersections = {}
    usable_splits = ["development", "independent_evaluation", "demonstration"]
    for a, b in itertools.combinations(usable_splits, 2):
        for field in ["original_review_id", "normalized_body_sha256"]:
            left = {r[field] for r in membership if r["split"] == a}
            right = {r[field] for r in membership if r["split"] == b}
            overlap = sorted(left & right)
            intersections[f"{a}__{b}__{field}"] = overlap
            assert not overlap
    summary = {
        "artifact_kind": "research_delivery_manifest", "version": VERSION, "source_commit": SOURCE_COMMIT,
        "task_ids": ["D1", "P2-DATA-001", "P2-DATA-002", "P2-DATA-005"],
        "source_hashes": source_hashes, "observations": 239, "unique_reviews": 238,
        "v1_rows": 179, "new_v2_rows": 59, "duplicate_observations": 1,
        "split_counts": dict(counts), "split_intersections": intersections,
        "research_denominator_excluding_quarantine": 226,
        "verified_purchased_model_count": 0, "known_publication_date_count": 0,
        "exact_sku_judgement_eligible_count": 0, "monthly_publication_denominator": 0,
        "rating_counts": dict(sorted(Counter(str(r["rating"]) for r in all_records).items())),
        "product_group_counts": dict(Counter(r["product_group"] for r in membership)),
        "source_sampling": {"fixed18": "first recommendation-sorted page; all 179 five-star",
                            "balanced_v2": "three primary pages, latest 10 plus low-rating 10 each; 60 observations with one overlap"},
        "biases": ["purposive, not random", "recommendation and rating sort bias", "rating is not sentiment",
                   "page model is not purchased SKU", "purchase date is not publication date",
                   "current manual is not verified purchase-time revision"],
        "exposure_overlay": {"source_path": f"{R5}/independence-holds.20261007.v1.json",
                             "known_groups": 3, "demonstration_hold_groups": 2,
                             "all_independent_use_approved": False, "remaining_historical_exposure": "unverified"},
        "research_bundle_schema_status": "producer-sidecar pending PM P0 canonical schema and consumer acceptance",
        "runtime_integration_verified": False, "model_calls": 0, "network_calls": 0,
        "original_179_database_received": False, "database_kind": "new 238-row research landing, not app/operating DB",
    }
    db_path = output / "research-238.sqlite3"
    save_landing_db(db_path, records=normalized, products=products, manifest=summary)
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE original_observations (profile TEXT NOT NULL, row_index INTEGER NOT NULL, original_review_id TEXT NOT NULL, original_json TEXT NOT NULL, PRIMARY KEY(profile,row_index))")
        db.executemany("INSERT INTO original_observations VALUES (?,?,?,?)", [(p, i, r["original_review_id"], canonical(r).decode()) for p, i, r in observations])
        db.execute("CREATE TABLE approval_holds (original_review_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL)")
        db.executemany("INSERT INTO approval_holds VALUES (?,?)", [(rid, canonical(r).decode()) for rid, r in exposure.items()])
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM reviews").fetchone()[0] == 238
        assert db.execute("SELECT count(*) FROM original_observations").fetchone()[0] == 239
        assert db.execute("SELECT count(*) FROM reviews WHERE actual_purchased_model_id IS NOT NULL OR published_at IS NOT NULL").fetchone()[0] == 0
        stored = {r[0]: json.loads(r[1]) for r in db.execute("SELECT original_review_id,metadata_json FROM reviews")}
        for rid, r in original_map.items():
            assert {k: stored[rid][k] for k in r} == r
        for p, i, r in observations:
            got = json.loads(db.execute("SELECT original_json FROM original_observations WHERE profile=? AND row_index=?", (p, i)).fetchone()[0])
            assert got == r
    write_json(output / "membership.json", membership)
    write_json(output / "original-records.json", all_records)
    for group, primary in PRIMARY.items():
        selected = [r for r, m in zip(all_records, membership) if m["product_group"] == group and r["split"] == "development"]
        bundle = {
            "artifact_kind": "ResearchBundleProducerSidecar", "bundle_version": VERSION + "." + group,
            "source_commit": SOURCE_COMMIT, "product_group": group, "primary_model_id": primary,
            "scope": "product-group research; displayed page models do not prove purchased model",
            "canonical_contract_status": "PM P0 schema/adapter pending", "model_execution_performed": False,
            "reviews": [{"source_type": "review", "source_kind": "public", "source_id": r.get("review_id", "LGE-R5-V2-REVIEW-" + r["original_review_id"]),
                         "original_review_id": r["original_review_id"], "original_record": r,
                         "source_profile": "fixed18" if r["original_review_id"] in old_ids else "balanced-pilot-v2",
                         "text_extent": "collected visible review body; no new truncation",
                         "fact_role": "customer observation/expectation, not verified product specification",
                         "exact_sku_judgement_eligible": False, "independent_use_approved": False} for r in selected],
            "excluded_split_counts": dict(Counter(r["split"] for r, m in zip(all_records, membership) if m["product_group"] == group and r["split"] != "development")),
            "published_month_trends_allowed": False, "sentiment_labels": None,
        }
        write_json(output / "agent-input" / group / "research-bundle.producer.json", bundle)
    raw = (root / R5 / "fixed18/development.dataset.json").read_bytes()
    (output / "agent-input/canonical-models.dataset.json").write_bytes(raw)
    canonical_dataset = json.loads(raw)
    assert len(canonical_dataset["reviews"]) == 0
    assert {p["model_id"] for p in canonical_dataset["products"]} == set(PRIMARY.values())
    summary["agent_development_reviews"] = 141
    summary["canonical_manual_dataset"] = {"products": 3, "features": 9, "evidence": 21, "reviews": 0, "sha256": sha256(raw).hexdigest()}
    summary["delivery_checks"] = {"sqlite_integrity": True, "unique_rows_preserved": 238,
                                  "all_original_observations_preserved": 239, "source_text_hashes_verified": 238,
                                  "existing_splits_preserved": 238, "unknown_fields_preserved": 238,
                                  "exact_canonical_dataset_bytes_preserved": True, "development_only_bundles": True}
    summary["output_files"] = {str(p.relative_to(output)): {"sha256": sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "manifest.json", summary)
    print(json.dumps({"unique_reviews": 238, "observations": 239, "split_counts": dict(counts),
                      "db_integrity": "ok", "dev_bundle_reviews": 141, "exact_sku_eligible": 0, "model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None, help="Validator source root; builder stays inside this fixed copy")
    parser.add_argument("--output", type=Path, default=Path("/output/d1"))
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[4], args.output)
