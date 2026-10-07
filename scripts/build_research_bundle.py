"""Build R8 public research inputs offline, preserving R5 bodies and splits."""

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
PACK = Path("data/research/r8-public-research-20261007")
R5 = Path("data/research/r5-public-reviews-20261007")
VERSION = "r8-public-research.20261007.v1"
SOURCE_PINS = {
    str(R5 / "fixed18/records.json"): "98830d3078d5c14443ee672a4fd6d5ae7fbafe6c77ea15ab6b14828ad2d5ad6f",
    str(R5 / "fixed18/products.json"): "5575df7a988d919eedc16a050914d192e30fc8eff1e0ad7b5a97c6328adb9d8b",
    str(R5 / "balanced-pilot-v2/new_unique_records.json"): "2929d20a4cb12c9ff20faa9d4fc1db8b5a14ae947c374f0b5166290178a2f3b2",
    "data/document_plans/lg-three-models-20261005.json": "6ec5d5ffa457ba87b9d982e9b22920f2e2b2466ec41afba3273c9584f7d491be",
    "data/document_datasets/lg-three-models-20261005.json": "6699cfe98196800e6a809a80b90b86ae6d5d4e799ac431165fad752a78381ac5",
    str(R5 / "independence-holds.20261007.v1.json"): "df4d83bc74a68897f17d0709a2ff5b4ab5edcc00eec0c6709491588a48d5fbbf",
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_inputs(root=ROOT):
    """Verify every immutable input before generating any output."""
    inputs = {}
    for name, expected in SOURCE_PINS.items():
        raw = (root / name).read_bytes()
        if sha256(raw) != expected:
            raise ValueError(f"Pinned source changed: {name}")
        inputs[name] = json.loads(raw)
    return inputs


def normalized_body(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def merge_records(base, added):
    """Add landing aliases only; keep original fields, body hashes and splits."""
    merged = []
    ids = set()
    body_groups = defaultdict(list)
    for rows, name in ((base, "fixed18/records.json"), (added, "balanced-pilot-v2/new_unique_records.json")):
        for original in rows:
            review_id = original["original_review_id"]
            if review_id in ids:
                raise ValueError(f"Duplicate original review ID: {review_id}")
            if sha256(original["text"].encode("utf-8")) != original["text_sha256"]:
                raise ValueError(f"Public body hash mismatch: {review_id}")
            if original["source_kind"] != "public":
                raise ValueError(f"Non-public review: {review_id}")
            if original["published_at"] is not None or original["actual_purchased_model_id"] is not None:
                raise ValueError(f"R5 posting/SKU assumptions changed: {review_id}")
            row = deepcopy(original)
            if "dedup_group_id" not in row:
                row["dedup_group_id"] = row["body_group_id"]
            row["r8_origin"] = {
                "file": (R5 / name).as_posix(),
                "record_sha256": sha256(json_bytes(original)),
                "original_fields_preserved": True,
            }
            merged.append(row)
            ids.add(review_id)
            body_groups[normalized_body(row["text"])].append(row)
    duplicates = [rows for rows in body_groups.values() if len(rows) > 1]
    if duplicates:
        # Do not resplit records or expose an evaluation-equivalent body to development.
        raise ValueError("Unexpected body-equivalent reviews; reconcile without changing R5 splits")
    return merged


def review_source(row, group, known_exposure):
    metadata = {
        "original_review_id": row["original_review_id"],
        "text_sha256": row["text_sha256"],
        "original_text_sha256": row.get("original_text_sha256", row.get("original_visible_text_sha256")),
        "split": row["split"],
        "split_version": row["split_version"],
        "purchase_date": row["purchase_date"],
        "sku_binding": row["sku_binding"],
        "strict_exact_model_eligible_for_model_input": row["eligible_for_model_input"],
        "original_input_hold_reasons": row["input_hold_reasons"],
        "quality_flags": row["quality_flags"],
        "redactions": row["redactions"],
        "r8_origin": row["r8_origin"],
        "known_historical_development_exposure": row["original_review_id"] in known_exposure,
        "scope_caveats": [
            "The displayed product page does not independently establish the purchased SKU.",
            "The visible purchase date is not a confirmed posting date.",
            "Customer experience is a report, not a verified defect or causal explanation.",
        ],
        "manual_time_alignment": row.get("manual_time_alignment"),
    }
    return {
        "source_id": f"LGE-R8-REVIEW-{row['original_review_id']}",
        "source_type": "review", "source_kind": "public", "product_group": group,
        "url": row["source_url"], "title": f"LG 공개 후기 {row['original_review_id']}",
        "text": row["text"], "page_model": row["displayed_model_id"],
        "purchased_model": row["actual_purchased_model_id"], "published_at": row["published_at"],
        "date_kind": "purchase" if row["purchase_date"] else "unknown", "coverage": "full",
        "source_role": "customer_experience", "brand": "LG", "rating": row["rating"],
        "document_version": row.get("document_version", row.get("manual_version")),
        "collected_at": row.get("collected_at", row.get("observed_at")),
        "sort_order": row.get("sort", "recommendation"), "duplicate_group": row["dedup_group_id"],
        "locator": {"selector": row["source_locator"], "original_review_id": row["original_review_id"]},
        "facts": [], "metadata": metadata,
    }


def manual_sources(plans, dataset):
    docs = {doc["document_id"]: doc for doc in plans["documents"]}
    products = {p["model_id"]: p for p in dataset["products"]}
    features = {f["id"]: f for f in dataset["features"]}
    result = []
    for evidence in dataset["evidence"]:
        doc = docs[evidence["source_id"]]
        product = products[evidence["model_id"]]
        result.append({
            "source_id": evidence["id"], "source_type": "manual", "source_kind": "public",
            "product_group": product["product_group"], "url": doc["url"],
            "title": f"{product['model_id']} 설명서: {evidence['locator']['section']}",
            "text": evidence["text"], "page_model": product["model_id"], "purchased_model": None,
            "published_at": None, "date_kind": "unknown", "coverage": "excerpt",
            "source_role": "official_document", "document_version": evidence["document_version"],
            "brand": "LG", "collected_at": doc["checked_at"], "locator": evidence["locator"],
            "facts": [{"fact_id": f"{evidence['id']}-fact", "kind": "document_fact", "text": evidence["text"], "locator": evidence["locator"]}],
            "metadata": {
                "document_id": doc["document_id"], "document_sha256": doc["sha256"],
                "feature_ids": evidence["feature_ids"],
                "feature_conditions": {f: features[f]["conditions"] for f in evidence["feature_ids"]},
                "full_document_captured_in_payload": False,
                "manual_time_alignment": "current_reference_only_not_purchase_time_verified",
                "scope_caveat": "설명서 기능 존재만으로 고객의 발견·이해·실행 불편이 해소되었다고 판단하지 않음. 공용 설명서의 적용 조건을 유지함.",
                "origin_file": "data/document_datasets/lg-three-models-20261005.json",
            },
        })
    return result


def build_pack(root=ROOT, output=None):
    output = output or root / PACK
    original_pack = (root / R5).resolve()
    if output.resolve() == original_pack or original_pack in output.resolve().parents:
        raise ValueError("Original R5 source packs cannot be used as output")
    inputs = load_inputs(root)
    records = merge_records(inputs[str(R5 / "fixed18/records.json")], inputs[str(R5 / "balanced-pilot-v2/new_unique_records.json")])
    products = inputs[str(R5 / "fixed18/products.json")]
    overlay = inputs[str(R5 / "independence-holds.20261007.v1.json")]
    official = json.loads((root / PACK / "selected-official-sources.json").read_bytes())
    official += manual_sources(inputs["data/document_plans/lg-three-models-20261005.json"], inputs["data/document_datasets/lg-three-models-20261005.json"])
    product_groups = {p["model_id"]: p["product_group"] for p in products}
    exposure = {r["original_review_id"] for r in overlay["known_development_exposure"]}
    counts = dict(Counter(r["split"] for r in records))
    manifest = {
        "artifact_kind": "public_research_landing", "dataset_version": VERSION,
        "manual_support_author": "current_chat_manual_support",
        "source_review_counts": {"fixed18": 179, "new_unique_v2": 59, "combined": len(records)},
        "registered_page_models": len(products), "split_counts": counts,
        "rating_counts": dict(sorted(Counter(str(r["rating"]) for r in records).items())),
        "product_group_counts": dict(Counter(product_groups[r["displayed_model_id"]] for r in records)),
        "body_equivalent_duplicate_count": 0,
        "selected_official_sources_sha256": sha256((root / PACK / "selected-official-sources.json").read_bytes()),
        "source_pins": {Path(k).as_posix(): v for k, v in SOURCE_PINS.items()},
        "original_splits_unchanged": True,
        "confirmed_purchased_sku_count": 0, "confirmed_review_posting_date_count": 0,
        "verified_manual_documents": len({s["metadata"]["document_id"] for s in official if s["source_type"] == "manual"}),
        "manual_excerpt_count": sum(s["source_type"] == "manual" for s in official),
        "official_source_counts": dict(Counter(s["source_type"] for s in official)),
        "bundle_split": "development", "analysis_scope": "product_group",
        "independence_overlay": overlay,
        "limitations": [
            "Purposive UI sample; counts are not market prevalence or a representative customer rate.",
            "Original 179 reviews all have rating 5; 59 additions include recent/low-rating UI selections.",
            "Ratings are not text sentiment labels. Positive, negative and mixed claims require text analysis.",
            "Posting dates and independently confirmed purchased SKUs remain unknown.",
            "Only three of 18 page-model manuals are verified; current references do not verify purchase-time manuals.",
            "Independent evaluation and demonstration remain candidates with original holds; neither is approved by this build.",
        ],
        "missing_source_types": [{"source_type": "qa", "status": "needs_normal_UI_capture", "verified_text_count": 0, "reason": "No frozen, independently verified public Q&A body was available for this pack; no text was invented."}],
        "operating_db_changed": False, "synthetic_review_count": 0, "build_network_requests": 0, "model_calls": 0,
        "source_collection_mode": "existing_review_captures_and_manual_public_official_page_excerpts",
    }
    artifacts = {"records.json": records, "products.json": products, "manifest.json": manifest, "official-sources.json": official}
    for group in sorted(set(product_groups.values())):
        selected = [r for r in records if product_groups[r["displayed_model_id"]] == group and r["split"] == "development"]
        sources = [review_source(r, group, exposure) for r in selected]
        sources.extend(s for s in official if s["product_group"] == group)
        bundle = {
            "schema_version": "1.0", "bundle_id": f"LGE-R8-{group}-development-20261007-v1",
            "product_group": group, "analysis_scope": "product_group", "sources": sources,
            "collection_manifest": {
                "dataset_version": VERSION, "split": "development", "review_count": len(selected),
                "stored_corpus_review_count": len(records), "stored_group_review_count": manifest["product_group_counts"][group],
                "review_rating_counts": dict(Counter(str(r["rating"]) for r in selected)),
                "page_models": [p["model_id"] for p in products if p["product_group"] == group],
                "source_type_counts": dict(Counter(s["source_type"] for s in sources)),
                "excluded_splits": ["independent_evaluation", "demonstration", "quarantine"],
                "limitations": manifest["limitations"], "missing_source_types": manifest["missing_source_types"],
                "synthetic_review_count": 0, "independent_evaluation_approved": False,
                "original_exact_model_holds_preserved": True,
            },
        }
        validate_research_bundle(bundle)
        artifacts[f"bundles/{group}.development.research-bundle.json"] = bundle
    # Validate all data before creating outputs. Original packs are never written.
    hashes = {}
    for name, value in artifacts.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = json_bytes(value)
        destination.write_bytes(raw)
        hashes[name] = sha256(raw)
    (output / "files.json").write_bytes(json_bytes(hashes))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / PACK)
    args = parser.parse_args()
    manifest = build_pack(output=args.output)
    print(json.dumps({"output": str(args.output), "reviews": manifest["source_review_counts"]["combined"], "split_counts": manifest["split_counts"], "official_source_counts": manifest["official_source_counts"], "model_calls": 0, "network_requests": 0}))


if __name__ == "__main__":
    main()
