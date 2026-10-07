"""Read pinned original PDF/native text and producer records; never run OCR/model."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
PDF_REL = "data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf"
PDF_SHA = "ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5"
VERSION = "MFL71959117 Rev.07_030626"
OFFICIAL = "data/research/r8-public-research-20261007/official-sources.json"
BUNDLE = "data/research/r8-public-research-20261007/bundles/dishwasher.development.research-bundle.json"
DATASET = "data/document_datasets/lg-three-models-20261005.json"
PLAN = "data/document_plans/lg-three-models-20261005.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def norm(text):
    return re.sub(r"\s+", "", text)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    captured_at = datetime.now(timezone(timedelta(hours=9))).isoformat()
    pdf = pdfium.PdfDocument(str(ROOT / PDF_REL))
    # Native text inspection is read-only; no raster-to-text/OCR or model generation.
    page_numbers = [1, 2, 5, 20, 23, 24, 39, 40, 41, 42, 43, 47, 48, 49, 50, 52]
    pages = {}
    for number in page_numbers:
        page = pdf[number - 1]
        textpage = page.get_textpage()
        pages[number] = textpage.get_text_range()
        textpage.close()
        page.close()
    pdf.close()

    files = []
    for relative in [PDF_REL, OFFICIAL, BUNDLE, DATASET, PLAN,
                     "data/research/r8-public-official-expansion-20261007/sources.json"]:
        raw = (ROOT / relative).read_bytes()
        pinned = subprocess.run(["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false",
                                 "show", SOURCE + ":" + relative], cwd=ROOT, capture_output=True, check=True).stdout
        files.append({"path": relative, "bytes": len(raw), "sha256": digest(raw),
                      "matches_fixed_source_bytes": raw == pinned})
    if not all(row["matches_fixed_source_bytes"] for row in files):
        raise ValueError("Pinned input bytes changed")
    if digest((ROOT / PDF_REL).read_bytes()) != PDF_SHA:
        raise ValueError("PDF SHA mismatch")

    official = json.loads((ROOT / OFFICIAL).read_bytes())
    bundle = json.loads((ROOT / BUNDLE).read_bytes())
    dataset = json.loads((ROOT / DATASET).read_bytes())
    plan = json.loads((ROOT / PLAN).read_bytes())
    manual_rows = [x for x in official if x.get("source_type") == "manual" and x.get("page_model") == "DUE6BGL2E"]
    by_id = {x["source_id"]: x for x in bundle["sources"]}
    dataset_by_id = {x["id"]: x for x in dataset["evidence"]}
    docplan = next(x for x in plan["documents"] if x["product"]["model_id"] == "DUE6BGL2E")
    selections = {x["evidence_id"]: x for x in docplan["selections"]}
    existing = []
    for row in manual_rows:
        identifier = row["source_id"]
        number = row["locator"]["page"]
        text = row["text"]
        facts = row["facts"]
        check = {
            "source_id": identifier, "page": number, "section": row["locator"]["section"],
            "document_id": row["metadata"]["document_id"], "document_version": row["document_version"],
            "document_sha256": row["metadata"]["document_sha256"], "text_sha256": digest(text.encode("utf-8")),
            "original_text": text,
            "native_pdf_text_matches_after_whitespace_only_normalization": norm(text) in norm(pages[number]),
            "bundle_preserves_entire_source_record": by_id[identifier] == row,
            "dataset_text_and_page_preserved": dataset_by_id[identifier]["text"] == text
                and dataset_by_id[identifier]["locator"]["page"] == number,
            "plan_selection_text_and_page_preserved": selections[identifier]["excerpt"] == text
                and selections[identifier]["page"] == number,
            "fact_text_and_locator_match_source": all(f["text"] == text and f["locator"] == row["locator"] for f in facts),
            "model_version_sha_preserved": row["page_model"] == "DUE6BGL2E"
                and row["document_version"] == VERSION and row["metadata"]["document_sha256"] == PDF_SHA,
            "source_topic": "loading_height_or_nozzle_clearance",
            "supports_existing_loading_claim": "supported",
            "supports_cleaning_or_odor_solution_claim": "unsupported",
            "supports_customer_actual_odor_cause_or_recovery_claim": "unconfirmed",
        }
        existing.append(check)

    # Each native segment is independently checkable using a page and exact extraction offsets.
    # Display paraphrases and applicability belong in the separate human audit, not in source text.
    specs = [
        ("DW-CLEAN-SAFETY-P05", 5, "• 청소할 때는", "준수 사항"),
        ("DW-INTERNAL-CLEAN-P39", 39, "내부 청소하기", "음식물 거름 필터 청소하기"),
        ("DW-FOOD-FILTER-P39", 39, "음식물 거름 필터 청소하기", None),
        ("DW-FOOD-FILTER-P40", 40, "4 부드러운 솔로", "에어필터 교체하기"),
        ("DW-TUB-CITRIC-P41", 41, "세척조 청소하기", "식초를 사용하여 청소하기"),
        ("DW-TUB-VINEGAR-P41", 41, "식초를 사용하여 청소하기", None),
        ("DW-TUB-VINEGAR-P42", 42, "2 상단 식기 바구니 중앙", "노즐 청소하기"),
        ("DW-NOZZLE-P42", 42, "노즐 청소하기", None),
        ("DW-NOZZLE-P43", 43, "6 상단 노즐을", "제품 보관하기"),
        ("DW-STORAGE-P43", 43, "제품 보관하기", None),
        ("DW-ODOR-DEVICE-P49", 49, "제품에서 냄새가 나요.", "세척 후 비린내가 나요."),
        ("DW-ODOR-FISHY-P49", 49, "세척 후 비린내가 나요.", None),
        ("DW-POOR-CLEANING-P50", 50, "세척이 잘 되지 않아요.", "제품 내부에 거품이 남아"),
        ("DW-NOZZLE-DIAG-P48", 48, "노즐이 부드럽게 돌아가지", "제품 문이 완전히 닫히지"),
    ]
    snippets = []
    for identifier, number, begin, end in specs:
        raw = pages[number]
        if begin not in raw:
            raise ValueError(f"Missing native anchor {identifier}: {begin}")
        start = raw.index(begin)
        stop = raw.index(end, start) if end else len(raw)
        text = raw[start:stop]
        snippets.append({"audit_evidence_id": identifier, "source_id": "DUE6BGL2E-manual-ff60f78ab832",
                         "pdf_path": PDF_REL, "pdf_sha256": PDF_SHA,
                         "document_version": VERSION, "page": number, "printed_page": number,
                         "section_start": begin, "start_char": start, "end_char": stop,
                         "native_page_text_sha256": digest(raw.encode("utf-8")),
                         "native_excerpt_sha256": digest(text.encode("utf-8")),
                         "native_exact_excerpt": text, "extractor": "PDFium native text, no OCR",
                         "source_role": "audit_only_not_registered_ResearchBundle_source",
                         "exact_SKU_applicability": "unconfirmed_by_pdf_cover",
                         "customer_purchased_model": None,
                         "supports_actual_customer_recovery": False})

    manual_pages = sorted({row["locator"]["page"] for row in manual_rows})
    cover = pages[1]
    validation_fields = ["native_pdf_text_matches_after_whitespace_only_normalization",
                         "bundle_preserves_entire_source_record", "dataset_text_and_page_preserved",
                         "plan_selection_text_and_page_preserved", "fact_text_and_locator_match_source",
                         "model_version_sha_preserved"]
    result = {
        "record_id": "DATA-DISH-MANUAL-01a1100e", "captured_at_kst": captured_at,
        "source_commit": SOURCE, "scope": "manual_original_semantic_audit_not_producer_edit_or_live_model_evaluation",
        "pm_request": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/5#issuecomment-6039619781",
        "pdf": {"path": PDF_REL, "sha256": PDF_SHA, "bytes": (ROOT / PDF_REL).stat().st_size,
                "page_count": 60, "document_version": VERSION,
                "document_id": "DUE6BGL2E-manual-ff60f78ab832", "official_url": docplan["url"],
                "cover_model_patterns": ["DFE6**E", "DFE6***E", "DUE6**E", "DUE6***E", "DUE6****E", "DEE6**E"],
                "cover_document_version_present": all(x in cover for x in VERSION.split()),
                "exact_model_DUE6BGL2E_listed_on_cover": "DUE6BGL2E" in cover,
                "common_manual_caution_present_on_page2": "공용으로 제작" in pages[2],
                "association_basis": docplan["applicability"]},
        "input_byte_checks": files,
        "existing_manual_records": existing,
        "existing_record_validation": {"record_count": len(existing), "comparison_count": len(existing) * len(validation_fields),
                                        "all_pass": all(x[field] for x in existing for field in validation_fields),
                                        "comparison_fields": validation_fields},
        "existing_r8_manual_pages": manual_pages,
        "management_and_odor_pages_missing_from_existing_R8_manual_records": [39, 40, 41, 42, 43, 49, 50],
        "new_audit_native_excerpt_count": len(snippets),
        "source_native_extraction_is_not_OCR": True,
        "model_calls": 0, "ocr_runs": 0, "runtime_HTTP_calls": 0,
        "producer_files_modified": 0, "common_code_modified": 0, "personal_README_modified": 0,
        "independent_actual_case_resolution": "unconfirmed",
        "automatic_table_structure_validation": "not_in_scope_no_structure_output_received",
        "limitations": [
            "Common manual and inherited SKU association do not establish every optional feature for exact purchased SKU.",
            "Purchased model and purchase-time manual version of the odor review remain unknown.",
            "Native manual symptom/cause/solution tables are visually reviewed manually, not automatic cell graph output.",
            "Existing sources preserve loading facts but do not contain cleaning/odor sections; omission does not prove LG lacks an answer.",
            "Official cleaning guidance is documented, not an independent measurement that a customer's odor was caused or resolved.",
            "The public source registry uses full DUE6BGL2E-MANUAL-D* identifiers; unreceived runtime shorthand M11 must not be inferred as a dishwasher source.",
        ],
    }
    write("source-inspection.json", result)
    write("manual-native-excerpts.json", snippets)
    print(json.dumps({"record": result["record_id"], "input_files": len(files), "preserved": all(x["matches_fixed_source_bytes"] for x in files),
                      "existing_manual_records": len(existing), "native_excerpts": len(snippets), "pages": manual_pages}, ensure_ascii=False))


if __name__ == "__main__":
    main()
