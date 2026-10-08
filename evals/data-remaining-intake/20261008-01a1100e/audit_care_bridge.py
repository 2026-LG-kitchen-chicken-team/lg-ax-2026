"""Read pinned Git data only. No producer imports, PDF extraction, OCR or runtime."""

import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
AUDIT = "78a1906369479eb2336cecc3a134895a814f95b1"
PRODUCER = "94b560de72f91795cfd50aada9e17d6773383ae1"
AUDIT_DIR = "evals/data-dish-manual-audit/20261007-01a1100e"
PACK = "data/research/r8-public-research-20261007/d1-d2-01a10600"
PDF = "data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf"

# Visually inspected continuity of steps from the existing PDF audit.
# These are audit expectations, not automatic table graph predictions.
CONTINUATION = {
    "DW-CLEAN-SAFETY-P05": [],
    "DW-INTERNAL-CLEAN-P39": [],
    "DW-FOOD-FILTER-P39": [40],
    "DW-FOOD-FILTER-P40": [39],
    "DW-TUB-CITRIC-P41": [],
    "DW-TUB-VINEGAR-P41": [42],
    "DW-TUB-VINEGAR-P42": [41],
    "DW-NOZZLE-P42": [43],
    "DW-NOZZLE-P43": [42],
    "DW-STORAGE-P43": [],
    "DW-ODOR-DEVICE-P49": [],
    "DW-ODOR-FISHY-P49": [],
    "DW-POOR-CLEANING-P50": [],
    "DW-NOZZLE-DIAG-P48": [],
}


def git(*args):
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT, env=env,
    )


def blob(commit, path):
    return git("show", commit + ":" + path)


def load(commit, path):
    return json.loads(blob(commit, path))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")


def main():
    old = load(AUDIT, AUDIT_DIR + "/manual-native-excerpts.json")
    excerpts = {r["audit_evidence_id"]: r for r in old}
    bundle = load(PRODUCER, PACK + "/agent-input/dishwasher/research-bundle.json")
    index = load(PRODUCER, PACK + "/d2-care-evidence-index.json")
    references = {r["audit_evidence_id"]: r for r in index}
    care = [s for s in bundle["sources"] if s["source_id"].startswith("D2-DUE-CARE-")]
    sources = {s["metadata"]["audit_evidence_id"]: s for s in care}
    if set(excerpts) != set(CONTINUATION) or set(sources) != set(excerpts) or len(care) != 14:
        raise ValueError("The pinned 14-source bridge is incomplete or has duplicate IDs")
    rows, errors, warnings = [], [], []
    raw_pdf = blob(BASE, PDF)
    for aid, e in excerpts.items():
        s = sources[aid]
        r = references[aid]
        m = s["metadata"]
        locator = s["locator"]
        text_matches = (s["text"] == e["native_exact_excerpt"]
                        and sha(s["text"].encode()) == e["native_excerpt_sha256"])
        locator_matches = all(locator[k] == e[k] for k in ("page", "printed_page", "start_char", "end_char"))
        locator_matches = locator_matches and locator["section"] == e["section_start"]
        identity_matches = (
            s["source_id"] == "D2-DUE-CARE-" + aid == r["canonical_source_id"]
            and m["original_source_id"] == e["source_id"]
            and m["audit_source_commit"] == AUDIT
            and s["document_version"] == e["document_version"] == r["document_version"]
            and m["pdf_sha256"] == sha(raw_pdf) == r["pdf_sha256"]
            and m["text_sha256"] == e["native_excerpt_sha256"] == r["native_excerpt_sha256"]
            and s["product_group"] == "dishwasher" and s["source_type"] == "manual"
        )
        caveats_preserved = (
            s["page_model"] is None and s["purchased_model"] is None
            and s["published_at"] is None and s["date_kind"] == "unknown"
            and m["numeric_facts_extracted_automatically"] is False and m["ocr_used"] is False
            and "exact purchased SKU/purchase-time revision unverified" in m["applicability"]
        )
        expected = CONTINUATION[aid]
        actual = m["continuation_pages"]
        extra = sorted(set(actual) - set(expected))
        missing = sorted(set(expected) - set(actual))
        if not all((text_matches, locator_matches, identity_matches, caveats_preserved)):
            errors.append({"audit_evidence_id": aid, "kind": "source_bridge_mismatch"})
        if extra or missing:
            warnings.append({"audit_evidence_id": aid, "source_id": s["source_id"],
                             "expected_step_continuation_pages": expected,
                             "actual_metadata_pages": actual, "unrelated_extra_pages": extra,
                             "missing_step_pages": missing,
                             "kind": "page_based_continuation_crosses_section_boundary"})
        rows.append({"audit_evidence_id": aid, "canonical_source_id": s["source_id"],
                     "page": e["page"], "start_char": e["start_char"], "end_char": e["end_char"],
                     "document_version": s["document_version"], "text_sha256": m["text_sha256"],
                     "text_match": text_matches, "locator_match": locator_matches,
                     "identity_and_PDF_SHA_match": identity_matches, "caveats_preserved": caveats_preserved,
                     "expected_step_continuation_pages": json.dumps(expected),
                     "actual_continuation_pages": json.dumps(actual), "unrelated_extra_pages": json.dumps(extra),
                     "missing_step_pages": json.dumps(missing),
                     "verdict": "ERROR_SOURCE" if not all((text_matches, locator_matches, identity_matches, caveats_preserved))
                     else "MATCH_SOURCE_WARN_CONTINUATION" if extra or missing else "MATCH"})
    pins = []
    for commit, path in [(AUDIT, AUDIT_DIR + "/manual-native-excerpts.json"),
                         (AUDIT, AUDIT_DIR + "/audit-table.json"),
                         (PRODUCER, PACK + "/d2-care-evidence-index.json"),
                         (PRODUCER, PACK + "/agent-input/dishwasher/research-bundle.json"),
                         (PRODUCER, "evals/data-d1-d2/20261007-01a10600/current-delivery.json"),
                         (BASE, PDF)]:
        raw = blob(commit, path)
        pins.append({"commit": commit, "path": path, "bytes": len(raw), "sha256": sha(raw)})
    with (OUT / "care-source-bridge.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    result = {"record_id": "DATA-REMAINING-INTAKE-20261008-01a1100e",
              "observed_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "baseline_commit": BASE, "original_audit_commit": AUDIT, "producer_commit": PRODUCER,
              "bundle_id": bundle["bundle_id"], "bundle_sources": len(bundle["sources"]),
              "care_sources": len(care), "source_match_count": sum(r["verdict"] != "ERROR_SOURCE" for r in rows),
              "source_mismatches": errors, "continuation_warnings": warnings,
              "conclusion": "MATCH_SOURCE_WARN_CONTINUATION" if warnings and not errors else "ERROR" if errors else "MATCH",
              "scope": "14 care Sources from existing independent native excerpts to pinned producer JSON only",
              "continuation_expectation_basis": "existing visual PDF audit of steps within the same section",
              "producer_continuation_semantics_confirmed": False,
              "actual_model_misuse_verified": False,
              "automatic_graph_verified": False, "CORE_runtime_output_received": False,
              "operating_DB_API_restart_verified": False, "D4_sample_or_Excel_repeated": False,
              "new_model_calls": 0, "new_OCR_runs": 0, "new_PDF_extraction": 0,
              "producer_execution": 0, "production_file_changes": 0}
    write_json("care-bridge-result.json", result)
    write_json("care-source-pins.json", pins)
    print(json.dumps({"source_matches": result["source_match_count"], "care_sources": len(care),
                      "continuation_warnings": len(warnings), "source_errors": len(errors),
                      "conclusion": result["conclusion"]}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
