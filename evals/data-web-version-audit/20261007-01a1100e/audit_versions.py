"""Independent, read-only metadata lineage audit; no producer imports or generation."""

import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
PRODUCER = "5fdb3ad55349726fbe03c9f69651f895d73e8f10"
PACK = "data/research/r8-public-research-20261007"
R5 = "data/research/r5-public-reviews-20261007"


def git(*args):
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false", *args], cwd=ROOT
    )


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(name):
    return json.loads((ROOT / name).read_bytes())


def inventory():
    return {
        name: sha((ROOT / name).read_bytes())
        for name in git("ls-files", "-z").decode("utf-8").split("\0") if name
    }


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_csv(name, values):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def main():
    if git("rev-parse", "HEAD").decode().strip() != SOURCE:
        raise ValueError("Run in the pinned audit worktree before committing new audit files")
    protected = inventory()
    records = load(PACK + "/records.json")
    products = {p["model_id"]: p for p in load(PACK + "/products.json")}
    original = {}
    for name in [R5 + "/fixed18/records.json", R5 + "/balanced-pilot-v2/new_unique_records.json"]:
        for row in load(name):
            rid = row["original_review_id"]
            if rid in original:
                raise ValueError("Duplicate origin review ID")
            original[rid] = (name, row)
    rows = {r["original_review_id"]: r for r in records}
    paths = sorted(
        [p.relative_to(ROOT).as_posix() for p in (ROOT / PACK / "bundles").glob("*.json")]
        + [p.relative_to(ROOT).as_posix() for p in (ROOT / "data/research/r8-public-official-expansion-20261007/bundles").glob("*.json")]
        + [p.relative_to(ROOT).as_posix() for p in (ROOT / "data/research/r8-public-competitor-adapter-20261007").glob("*.research-bundle.json")]
    )
    checked_paths = set(paths) | {
        PACK + "/products.json", PACK + "/records.json", PACK + "/manifest.json", PACK + "/files.json",
        R5 + "/fixed18/products.json", R5 + "/fixed18/records.json",
        R5 + "/balanced-pilot-v2/new_unique_records.json",
        "scripts/build_research_bundle.py", "packages/core/src/lgax_core/public_review_collection.py",
        "packages/contracts/schemas/research-planning.schema.json", "apps/web/src/ResearchSourcesPanel.tsx",
        "data/document_plans/lg-three-models-20261005.json",
    }
    bundle_rows, unique_rows, summaries, findings = [], {}, [], []
    for path in paths:
        bundle = load(path)
        reviewed = [s for s in bundle["sources"] if s["source_type"] == "review"]
        counts = Counter()
        for source in reviewed:
            rid = source["metadata"]["original_review_id"]
            record = rows[rid]
            origin_path, origin = original[rid]
            expected = origin.get("document_version", origin.get("manual_version"))
            product = products[origin["displayed_model_id"]]
            kind = ("related_page_model_manual_revision" if expected and expected.startswith("MFL")
                    else "related_page_model_PDP_snapshot" if expected and expected.startswith("LG-PDP-")
                    else "unknown")
            actual = source.get("document_version")
            matching = (
                actual == expected and source["page_model"] == origin["displayed_model_id"]
                and source["source_id"] == "LGE-R8-REVIEW-" + str(rid)
                and source["url"] == origin["source_url"]
                and source["locator"]["original_review_id"] == rid
                and kind != "unknown"
                and product["document_version_basis"] == (
                    "existing_manual_revision" if kind == "related_page_model_manual_revision"
                    else "official_pdp_snapshot_not_manual"
                )
                and source["text"] == origin["text"]
                and source["metadata"]["text_sha256"] == sha(origin["text"].encode("utf-8"))
                and source["purchased_model"] is None
                and source["metadata"]["manual_time_alignment"] == "current_reference_only_not_purchase_time_verified"
                and (expected == product["document_version"] or expected == product.get("manual_version"))
                and record["manual_version"] == origin["manual_version"]
            )
            counts[kind] += 1
            checked = {
                "source_id": source["source_id"], "original_review_id": rid,
                "product_group": source["product_group"], "page_model": source["page_model"],
                "document_version": actual, "meaning": kind,
                "catalog_document_version_basis": product["document_version_basis"],
                "origin_file": origin_path,
                "origin_field": "document_version" if "document_version" in origin else "manual_version_fallback",
                "purchased_model": "null", "purchase_time_manual_verified": False,
                "manual_time_alignment": source["metadata"]["manual_time_alignment"],
                "text_sha256": source["metadata"]["text_sha256"],
                "result": "MATCH" if matching else "ERROR",
            }
            if rid in unique_rows and unique_rows[rid] != checked:
                findings.append({"review_id": rid, "kind": "bundle_metadata_differs"})
            unique_rows[rid] = checked
            if not matching:
                findings.append({"review_id": rid, "bundle": path, "kind": "lineage_mismatch"})
            bundle_rows.append({"bundle_path": path, "bundle_id": bundle["bundle_id"], **checked})
        summaries.append({"path": path, "bundle_id": bundle["bundle_id"], "reviews": len(reviewed), "version_meaning_counts": dict(counts)})
    pins = []
    for path in sorted(checked_paths):
        raw = (ROOT / path).read_bytes()
        base = git("show", SOURCE + ":" + path)
        producer = git("show", PRODUCER + ":" + path)
        match = raw == base == producer
        pins.append({"path": path, "bytes": len(raw), "sha256": sha(raw),
                     "source_git_sha256": sha(base), "producer_git_sha256": sha(producer),
                     "producer_main_worktree_equal": match})
        if not match:
            findings.append({"path": path, "kind": "pinned_bytes_mismatch"})
    unique = sorted(unique_rows.values(), key=lambda v: v["original_review_id"])
    unique_counts = Counter(r["meaning"] for r in unique)
    changed = [name for name, digest in protected.items() if sha((ROOT / name).read_bytes()) != digest]
    write_csv("review-version-lineage.csv", unique)
    write_csv("bundle-version-lineage.csv", bundle_rows)
    write_csv("producer-main-source-byte-bridge.csv", pins)
    result = {
        "record_id": "DATA-WEB-VERSION-01a1100e", "observed_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "source_commit": SOURCE, "producer_commit": PRODUCER,
        "scope": "document_version meaning and immutable metadata lineage; not D4 sample independence or runtime verification",
        "unique_development_reviews_checked": len(unique), "bundle_occurrences_checked": len(bundle_rows),
        "version_meaning_counts": dict(unique_counts), "bundles": summaries,
        "missing_document_version_in_added_origin_records": sum("document_version" not in r for _, r in original.values()),
        "record_manual_version_inherited_not_review_revision": True,
        "purchased_models_independently_verified": 0, "purchase_time_manual_versions_verified": 0,
        "source_files_byte_compared": len(pins), "source_files_identical": sum(p["producer_main_worktree_equal"] for p in pins),
        "protected_tracked_files": len(protected), "protected_files_changed": changed,
        "findings": findings,
        "conclusion": "MATCH" if not findings and not changed else "ERROR",
        "WEB_display_issue": "A generic document revision label conflates manual revision and PDP snapshot and can suggest a review or purchased-product revision",
        "recommended_labels": {
            "review_with_manual_reference": "페이지 모델의 참고 설명서 판",
            "review_with_PDP_reference": "페이지 모델의 제품 페이지 스냅샷",
            "required_caveat": "후기 판본·구매 모델·구매 당시 설명서 판 확인 아님",
            "undifferentiated_review_fallback": "페이지 모델의 연결 참고자료 버전",
        },
        "contract_decision_owner": "jeongiryang; DATA recommends display meaning without changing the shared schema",
        "new_model_calls": 0, "new_OCR_calls": 0, "producer_execution": 0, "new_HTTP_or_DB_or_restart": 0,
    }
    write_json("audit-result.json", result)
    write_json("source-pins.json", pins)
    print(json.dumps({k: result[k] for k in ["conclusion", "unique_development_reviews_checked", "bundle_occurrences_checked", "version_meaning_counts", "source_files_byte_compared", "source_files_identical", "protected_tracked_files", "protected_files_changed", "findings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
