"""Independent, read-only D4 audit of a fixed D1 delivery; no producer imports."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from datetime import datetime, timedelta
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sqlite3
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


class Audit:
    def __init__(self):
        self.findings = []
        self.warnings = []

    def check(self, condition, code, detail=None):
        if not condition:
            self.findings.append({"code": code, "detail": detail})


def inspect_xlsx(path, expected, audit):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    by_sheet = {}
    with ZipFile(path) as z:
        audit.check(sum(i.file_size for i in z.infolist()) < 64_000_000, "xlsx_size_limit")
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(si.itertext()) for si in root.findall("m:si", ns)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        wb_properties = wb.find("m:workbookPr", ns)
        date_origin = datetime(1904, 1, 1) if wb_properties is not None and wb_properties.attrib.get("date1904") in {"1", "true"} else datetime(1899, 12, 30)
        relationships = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships.findall(rel_ns + "Relationship")}
        errors, uncached = [], []
        for sheet in wb.findall("m:sheets/m:sheet", ns):
            target = targets[sheet.attrib[rel_attr]]
            name = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            audit.check(name.startswith("xl/") and ".." not in PurePosixPath(name).parts, "xlsx_sheet_path", name)
            root = ET.fromstring(z.read(name))
            rows = []
            for row in root.findall("m:sheetData/m:row", ns):
                cells = {}
                for cell in row.findall("m:c", ns):
                    ref = cell.attrib["r"]
                    kind = cell.attrib.get("t")
                    value = cell.find("m:v", ns)
                    formula = cell.find("m:f", ns)
                    if kind == "s":
                        parsed = strings[int(value.text)]
                    elif kind == "inlineStr":
                        node = cell.find("m:is", ns)
                        parsed = "".join(node.itertext()) if node is not None else ""
                    else:
                        parsed = value.text if value is not None and value.text is not None else ""
                    cells[re.sub(r"\d+", "", ref)] = parsed
                    if kind == "e":
                        errors.append({"sheet": sheet.attrib["name"], "cell": ref, "error": parsed})
                    if formula is not None and not parsed:
                        uncached.append({"sheet": sheet.attrib["name"], "cell": ref})
                rows.append({"row": int(row.attrib["r"]), "cells": cells})
            by_sheet[sheet.attrib["name"]] = rows
    audit.check(not errors, "xlsx_error_cells", errors)
    review_rows = by_sheet.get("리뷰", [])
    header = next((r for r in review_rows if any(normalized(v).replace(" ", "") in {"후기ID", "원후기ID"} for v in r["cells"].values())), None)
    audit.check(header is not None, "xlsx_review_header")
    verified = 0
    if header:
        labels = {c: normalized(v).replace(" ", "") for c, v in header["cells"].items()}
        id_col = next(c for c, v in labels.items() if v in {"후기ID", "원후기ID"})
        body_cols = [c for c, v in labels.items() if "원문" in v and not any(k in v.upper() for k in ("SHA", "해시", "위치", "출처"))]
        audit.check(bool(body_cols), "xlsx_review_body_columns", labels)
        found = {}
        for r in review_rows:
            if r["row"] <= header["row"]:
                continue
            rid = r["cells"].get(id_col, "")
            if rid not in expected:
                continue
            audit.check(rid not in found, "xlsx_duplicate_review_id", rid)
            text = "".join(r["cells"].get(c, "") for c in body_cols)
            audit.check(text == expected[rid]["text"], "xlsx_original_text_changed", rid)
            for label, field in (("기존분할", "split"), ("원문SHA256", "text_sha256"),
                                 ("공식출처URL", "source_url"), ("원문위치", "source_locator")):
                col = next((c for c, v in labels.items() if v.upper() == label.upper()), None)
                audit.check(col is not None and r["cells"].get(col, "") == str(expected[rid][field]),
                            "xlsx_original_field_changed", {"id": rid, "field": field})
            for label in ("구매모델", "게시일"):
                col = next((c for c, v in labels.items() if v == label), None)
                audit.check(col is not None and r["cells"].get(col, "") == "", "xlsx_unknown_field_filled", {"id": rid, "label": label})
            date_col = next((c for c, v in labels.items() if v == "구매일"), None)
            value = r["cells"].get(date_col, "") if date_col else ""
            if value and re.fullmatch(r"\d+(?:\.\d+)?", value):
                value = (date_origin + timedelta(days=float(value))).date().isoformat()
            audit.check(value == (expected[rid]["purchase_date"] or ""), "xlsx_purchase_date_changed", rid)
            found[rid] = text
            verified += 1
        audit.check(set(found) == set(expected), "xlsx_id_coverage", {"seen": len(found), "expected": len(expected)})
    if uncached:
        audit.warnings.append({"code": "xlsx_formula_cache_not_measured", "count": len(uncached)})
    return {"sha256": digest(path.read_bytes()), "sheets": list(by_sheet), "original_review_texts_compared": verified,
            "formula_error_cells": errors, "uncached_formula_count": len(uncached),
            "layout_recreated": False, "excel_native_open_performed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--producer", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--xlsx", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    audit = Audit()
    receipt = load(args.receipt)
    if not re.fullmatch(r"[0-9a-f]{40}", receipt.get("producer_head", "")):
        raise SystemExit("Fixed producer commit/head has not been received.")
    for rel, info in receipt["input_files"].items():
        if PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
            raise SystemExit("Receipt path is outside producer scope.")
        raw = (args.producer / rel).read_bytes()
        audit.check(digest(raw) == info["sha256"] and len(raw) == info["bytes"], "receipt_file_changed", rel)
    manifest = load(args.producer / "manifest.json")
    audit.check(manifest["version"] == receipt["producer_version"], "producer_version_mismatch")
    for rel, info in manifest["source_hashes"].items():
        path = PurePosixPath(rel)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit("Source path is outside fixed scope.")
        raw = (args.source_root / path).read_bytes()
        declared = info["sha256"] if isinstance(info, dict) else info
        audit.check(digest(raw) == declared, "source_sha_changed", rel)
    verified_outputs = []
    for rel, info in manifest["output_files"].items():
        path = PurePosixPath(rel)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit("Output path is outside fixed scope.")
        raw = (args.producer / path).read_bytes()
        audit.check(digest(raw) == info["sha256"] and len(raw) == info["bytes"], "manifest_output_changed", rel)
        verified_outputs.append(rel)

    old_root = args.source_root / "data/research/r5-public-reviews-20261007"
    v1 = load(old_root / "fixed18/records.json")
    v2_new = load(old_root / "balanced-pilot-v2/new_unique_records.json")
    v2_all = load(old_root / "balanced-pilot-v2/records.json")
    expected = {r["original_review_id"]: r for r in v1 + v2_new}
    records = load(args.producer / "original-records.json")
    actual = {r["original_review_id"]: r for r in records}
    audit.check(len(records) == len(actual) == len(expected), "id_count_or_duplicate")
    audit.check(set(actual) == set(expected), "original_id_set_changed")
    for rid, original in expected.items():
        audit.check(actual.get(rid) == original, "original_record_changed", rid)
    membership = load(args.producer / "membership.json")
    member_map = {r["original_review_id"]: r for r in membership}
    audit.check(len(membership) == len(member_map) == len(expected), "membership_duplicates")
    split_ids, split_groups, split_body = defaultdict(set), defaultdict(set), defaultdict(set)
    for rid, original in expected.items():
        member = member_map.get(rid)
        if not member:
            audit.check(False, "membership_missing", rid)
            continue
        for field in ("split", "text_sha256", "source_url", "source_locator", "rating", "purchase_date", "published_at", "actual_purchased_model_id", "quarantined"):
            audit.check(member.get(field) == original.get(field), "membership_field_changed", {"id": rid, "field": field})
        group_field = "dedup_group_id" if "dedup_group_id" in original else "body_group_id"
        audit.check(member.get("original_group_field") == group_field and member.get("original_group_id") == original[group_field], "original_group_changed", rid)
        audit.check(member.get("independent_use_approved") is False, "independent_approval_fabricated", rid)
        audit.check(member.get("eligible_for_exact_sku_judgement") is False, "sku_eligibility_fabricated", rid)
        split = member["split"]
        split_ids[split].add(rid)
        split_groups[split].add(member["original_group_id"])
        split_body[split].add(normalized(original["text"]))
    intersections = {}
    for a, b in (("development", "independent_evaluation"), ("development", "demonstration"), ("independent_evaluation", "demonstration")):
        overlaps = {"ids": sorted(split_ids[a] & split_ids[b]), "groups": sorted(split_groups[a] & split_groups[b]),
                    "normalized_body_count": len(split_body[a] & split_body[b])}
        intersections[a + "__" + b] = overlaps
        audit.check(not overlaps["ids"] and not overlaps["groups"] and not overlaps["normalized_body_count"], "split_overlap", a + "__" + b)
    counts = dict(Counter(r["split"] for r in records))
    audit.check(counts == manifest["split_counts"], "split_count_claim_mismatch")
    audit.check(manifest["observations"] == len(v1) + len(v2_all), "observation_count")
    audit.check(manifest["unique_reviews"] == len(expected), "unique_review_count")
    duplicates = [r["original_review_id"] for r in v2_all if r["original_review_id"] in {r["original_review_id"] for r in v1}]
    for rid in duplicates:
        audit.check(actual[rid] == next(r for r in v1 if r["original_review_id"] == rid), "additional_observation_overwrote_original", rid)
    audit.check(manifest["duplicate_observations"] == len(duplicates), "duplicate_observation_count")
    audit.check(all(r["published_at"] is None and r["actual_purchased_model_id"] is None for r in records), "unknown_fields_filled")
    audit.check(manifest["known_publication_date_count"] == 0 and manifest["monthly_publication_denominator"] == 0, "purchase_dates_promoted_to_posting_dates")
    audit.check(bool(manifest["biases"]) and bool(manifest["source_sampling"]), "sampling_bias_missing")
    audit.check(bool(manifest["exposure_overlay"]), "prior_exposure_overlay_missing")
    audit.check(manifest["runtime_integration_verified"] is False and manifest["original_179_database_received"] is False, "runtime_or_old_db_receipt_fabricated")
    bundle_counts = {}
    for group in ("fridge", "dishwasher", "microwave"):
        bundle = load(args.producer / f"agent-input/{group}/research-bundle.producer.json")
        target = {rid for rid, m in member_map.items() if m["product_group"] == group and m["split"] == "development" and not m["quarantined"]}
        seen = set()
        for row in bundle["reviews"]:
            rid = row["original_review_id"]
            audit.check(rid in target and rid not in seen, "bundle_split_leak_or_duplicate", {"group": group, "id": rid})
            seen.add(rid)
            audit.check(row["original_record"] == expected.get(rid), "bundle_original_record_changed", rid)
            audit.check(row["source_type"] == "review" and row["source_kind"] == "public", "bundle_source_kind", rid)
        audit.check(seen == target, "bundle_development_coverage", group)
        audit.check(bundle["model_execution_performed"] is False and bundle["published_month_trends_allowed"] is False, "bundle_unearned_execution_or_trends", group)
        bundle_counts[group] = len(seen)
    db_path = args.producer / "research-238.sqlite3"
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        columns = {r[1] for r in db.execute("PRAGMA table_info(reviews)")}
        record_col = next((c for c in ("original_record_json", "record_json", "metadata_json", "original_json") if c in columns), None)
        audit.check(record_col is not None, "research_db_record_column", sorted(columns))
        db_rows = [json.loads(r[0]) for r in db.execute("SELECT " + record_col + " FROM reviews")] if record_col else []
        audit.check({r["original_review_id"]: r for r in db_rows} == expected and len(db_rows) == len(expected), "research_db_original_rows_changed")
    workbook = inspect_xlsx(args.xlsx, expected, audit) if args.xlsx else {"status": "not received"}
    result = {
        "scope": "D4 independent source/membership/split/bundle/research-file/Excel content audit",
        "status": "PASS" if not audit.findings and args.xlsx else "FAIL" if audit.findings else "PARTIAL",
        "producer_head": receipt["producer_head"], "producer_version": receipt["producer_version"],
        "producer_manifest_sha256": digest((args.producer / "manifest.json").read_bytes()),
        "source_commit": manifest["source_commit"], "unique_reviews": len(expected),
        "original_observations": len(v1) + len(v2_all), "reobserved_ids": duplicates,
        "split_counts": counts, "split_intersections": intersections,
        "known_publication_dates": sum(r["published_at"] is not None for r in records),
        "verified_buyer_sku": sum(r["actual_purchased_model_id"] is not None for r in records),
        "research_rows_excluding_quarantine": sum(not r["quarantined"] for r in records),
        "development_only_bundle_counts": bundle_counts, "verified_output_files": verified_outputs,
        "workbook": workbook, "findings": audit.findings, "warnings": audit.warnings,
        "network_requests": 0, "model_calls": 0,
        "limitations": ["structural/source verification; no semantic Gold or LLM comparison approval",
                        "independent-use approval remains false", "P0/API/MCP/operating DB acceptance belongs to PM/coordination",
                        "no monthly/seasonal posting trend evidence", "not parent Done"],
        "audit_code_sha256": digest(Path(__file__).read_bytes()),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "producer_head", "unique_reviews", "split_counts", "development_only_bundle_counts", "findings", "warnings")}, ensure_ascii=False))
    raise SystemExit(1 if audit.findings else 0)


if __name__ == "__main__":
    main()
