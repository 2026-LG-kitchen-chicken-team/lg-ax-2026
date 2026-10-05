"""Prepare development inputs for DATA002 step 1; this is not an ingestion API."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import pdfplumber

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DATASET = ROOT / "data/demo/dataset.json"
REFERENCE = ROOT / "data/research/P2-DATA-001-real-reference-20261004/reference-pack.json"
CASE_INPUT = ROOT / "data/research/R03-fridge-20261004/case-input.json"
PROJECT_PYTHON = ROOT / ".venv/Scripts/python.exe"
TASK = ROOT / "harness/phase2/tasks/P2-DATA-002.json"
FIELDS = ["id", "model_id", "document_version", "source_kind", "source_id", "row", "evidence_id", "text"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def command(argv):
    result = subprocess.run([str(a) for a in argv], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    return {"argv": [str(a) for a in argv], "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("run-id must contain letters, numbers, - or _")
    run = OUT / "runs" / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in (DATASET, REFERENCE, CASE_INPUT, TASK,
        ROOT / "packages/contracts/schemas/lgax.schema.json", ROOT / "packages/core/src/lgax_core/store.py")}
    dataset, reference, case = read(DATASET), read(REFERENCE), read(CASE_INPUT)
    pdf_path = Path(case["local_pdf"])
    if sha(pdf_path) != case["expected_sha256"]:
        raise ValueError("PDF bytes differ from the existing DATA001 input")
    source = next(s for s in reference["sources"] if s["id"] == case["source_id"])
    product = next(p for p in reference["products"] if p["model_id"] == case["model_id"])
    if source["model_id"] != product["model_id"] or source["document_version"] != product["document_version"]:
        raise ValueError("public product/source scope mismatch")
    reviews = dataset["reviews"]
    if len(reviews) != 36 or not all(r["locator"] == {"row": i + 2} for i, r in enumerate(reviews)):
        raise ValueError("existing review order changed; do not silently renumber locators")
    if any(r["source_kind"] != "synthetic" or r["source_id"] != "REVIEWS-CSV-v1.0" for r in reviews):
        raise ValueError("CSV export must preserve the existing synthetic source")
    if any("\n" in r["text"] or "\r" in r["text"] for r in reviews):
        raise ValueError("physical CSV line mapping needs explicit handling for multiline reviews")
    csv_path = OUT / "reviews-v1.0.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for review in reviews:
            writer.writerow({**{key: review[key] for key in FIELDS if key != "row"}, "row": review["locator"]["row"]})
    with csv_path.open(encoding="utf-8", newline="") as stream:
        reread = list(csv.DictReader(stream))
    reconstructed = [{"id": r["id"], "model_id": r["model_id"], "document_version": r["document_version"],
        "source_kind": r["source_kind"], "source_id": r["source_id"], "text": r["text"],
        "locator": {"row": int(r["row"])}, "evidence_id": r["evidence_id"]} for r in reread]
    if reconstructed != reviews:
        raise ValueError("CSV round-trip changed a review")
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
        page18 = pdf.pages[17].extract_text() or ""
        page19 = pdf.pages[18].extract_text() or ""
    snippet = "선반을 분리할 때, 선반 위에 있는 식품을 치운 후 분리하세요."
    normalize = lambda value: " ".join(value.split())
    if "냉장실 선반 사용하기" not in normalize(page18) or normalize(snippet) not in normalize(page19):
        raise ValueError("expected heading/snippet not present on the selected pages")
    pdf_candidate = {"id": "DATA002-FM-P19-SHELF-01", "model_id": product["model_id"],
        "document_version": product["document_version"], "source_kind": "public", "source_type": "manual",
        "source_id": source["id"], "locator": {"page": 19, "section": "냉장실 선반 사용하기 / 주의"},
        "text": snippet, "feature_ids": []}
    review_evidence_ids = {r["evidence_id"] for r in reviews}
    review_evidence = [e for e in dataset["evidence"] if e["id"] in review_evidence_ids]
    if len(review_evidence) != len(reviews):
        raise ValueError("review evidence is missing or duplicated")
    by_id = {e["id"]: e for e in review_evidence}
    for review in reviews:
        evidence = by_id[review["evidence_id"]]
        if any(review[key] != evidence[key] for key in ("model_id", "document_version", "source_kind", "source_id", "locator", "text")):
            raise ValueError("review and original evidence differ")
    expected = {"artifact_kind": "development_expected_records", "task_id": "P2-DATA-002", "stage": 1,
        "not_independent_evaluation": True, "not_service_output": True,
        "csv": {"products": dataset["products"], "reviews": reviews, "evidence": review_evidence,
            "id_policy": "Preserve existing review/evidence/source IDs and original rows exactly."},
        "pdf": {"product": product, "expected_excerpt": pdf_candidate,
            "evidence_id_status": "local candidate only; canonical registration has not occurred",
            "id_acceptance": "A future registered ID must round-trip to this source/model/version/page; candidate ID is not a PM contract change.",
            "feature_mapping": "No feature/support judgement is generated. Shared manual applicability remains conditional."}}
    write(OUT / "expected-records.json", expected)
    control_plan = {"task_id": "P2-DATA-002", "stage": 1, "status": "expected_only_not_executed_against_service",
        "cases": [
            {"id": "CSV-SAME-MODEL", "input": {"query": "식품을 모두 옮겨", "model_id": "FRIDGE-A", "document_version": "1.0"},
                "note": "Use the exact Korean review text in expected-records.json for the positive retrieval test.",
                "expected": "Return registered review evidence with the same original model/version/row/text."},
            {"id": "PDF-PAGE-TRACE", "model_id": product["model_id"], "page": 19,
                "expected": "Return the selected shelf warning and the original PDF source/version/page."},
            {"id": "CROSS-MODEL", "query_model": "FRIDGE-A", "source_model": product["model_id"],
                "expected": "Do not accept or return the real-model PDF as FRIDGE-A evidence."},
            {"id": "CROSS-VERSION", "query_model": "FRIDGE-A", "query_version": "2.0", "source_version": "1.0",
                "expected": "Do not substitute v1.0 records for the selected v2.0 scope."},
            {"id": "MISSING-SCOPE", "missing_fields": ["model_id", "document_version", "source_id", "source_kind"],
                "expected": "Request missing scope or reject validation; never infer it silently."},
            {"id": "NOT-MENTIONED", "feature": "자동 세척", "reviewed_pages": [18, 19],
                "expected": "Not mentioned in the selected pages; no unsupported-product judgement or whole-document absence claim."}
        ]}
    write(OUT / "control-plan.json", control_plan)
    selection = {"task_id": "P2-DATA-002", "stage": 1, "purpose": "development ingestion input preparation",
        "contract_version": read(ROOT / "packages/contracts/schemas/lgax.schema.json")["x-contract-version"],
        "inputs": [
            {"case_id": "CSV-SYNTHETIC", "format": "csv", "path": csv_path.relative_to(ROOT).as_posix(),
                "sha256": sha(csv_path), "origin": stamp(DATASET), "origin_kind": "lossless export from existing JSON, not a newly invented review set",
                "source_id": "REVIEWS-CSV-v1.0", "source_kind": "synthetic", "document_version": "1.0",
                "rows": len(reviews), "models": [p["model_id"] for p in dataset["products"]],
                "physical_record_rows": "2..37 including header at row 1; no review has an embedded newline"},
            {"case_id": "PDF-REAL-FRIDGE", "format": "pdf", "local_path": str(pdf_path), "sha256": sha(pdf_path),
                "source_id": source["id"], "source_kind": "public", "source_url": source["url"],
                "model_id": product["model_id"], "document_version": product["document_version"], "page_count": pages,
                "inspected_pages": [18, 19], "selected_evidence_page": 19,
                "copied_to_repository": False, "source_reference": stamp(REFERENCE),
                "applicability": source.get("applicability"), "license_reuse_confirmed": False}
        ], "scope_rules": ["The CSV synthetic models and real PDF model are separate cases.",
            "Public does not mean redistribution licensed.", "No independent evaluation answers are read or used.",
            "No feature support is inferred from non-mention.", "No common schema/API or task status is changed."]}
    write(OUT / "input-selection.json", selection)
    write(run / "pdf-inspection.json", {"input_sha256": sha(pdf_path), "page_count": pages,
        "heading_page18_present": True, "snippet_page19_present": True, "selected_excerpt": snippet,
        "text_extraction": "pdfplumber read-only source inspection", "pdfplumber_version": importlib.metadata.version("pdfplumber"),
        "render_command": "pdftoppm -f 18 -l 19 -scale-to 1400 -png <existing-pdf> tmp/pdfs/data002-step1/fridge",
        "visual_review": "Pages 18 and 19 visually reviewed in Codex; shelf heading/continuation and warning confirmed.",
        "not_production_parser": True})
    for name, argv in [("phase2-next", [PROJECT_PYTHON, "-B", "-X", "utf8", "scripts/phase2.py", "next", "--member", "신진하"]),
        ("phase2-packet", [PROJECT_PYTHON, "-B", "-X", "utf8", "scripts/phase2.py", "packet", "P2-DATA-002"])]:
        outcome = command(argv)
        write(run / (name + ".json"), outcome)
        if outcome["exit_code"]:
            raise ValueError(name + " failed")
    schema_code = '''import json,pathlib
from lgax_contracts import validate
p=pathlib.Path("data/research/P2-DATA-002-step1-20261005/expected-records.json")
d=json.loads(p.read_text(encoding="utf-8"))
counts={}
for kind,records in [("Product",d["csv"]["products"]+[d["pdf"]["product"]]),("Review",d["csv"]["reviews"]),("Evidence",d["csv"]["evidence"]+[d["pdf"]["expected_excerpt"]])]:
    for record in records: validate(kind,record)
    counts[kind]=len(records)
print(json.dumps({"passed":True,"validated_expected_records":counts,"service_executed":False}))
'''
    schema_outcome = command([PROJECT_PYTHON, "-B", "-X", "utf8", "-c", schema_code])
    write(run / "schema-check.json", schema_outcome)
    if schema_outcome["exit_code"]:
        raise ValueError("expected record Schema validation failed")
    after = {name: sha(ROOT / name) for name in before}
    if before != after:
        raise ValueError("an existing input/contract/task changed during preparation")
    commit = command(["git", "rev-parse", "HEAD"])["stdout"].strip()
    write(run / "verification.json", {"task_id": "P2-DATA-002", "stage": 1, "result": "pass",
        "execution_kind": "deterministic_preparation", "is_task_completion_evidence": False,
        "csv_rows": len(reviews), "csv_lossless_roundtrip": True, "original_review_evidence_matches": True,
        "source_hashes_preserved": after, "pdf_original_hash_matches": True,
        "model_scopes_separated": True, "private_evaluation_read": False, "harness_task_status": read(TASK)["status"],
        "schema_check": stamp(run / "schema-check.json"),
        "outputs": [stamp(OUT / name) for name in ("reviews-v1.0.csv", "expected-records.json", "control-plan.json", "input-selection.json")],
        "code_commit": commit, "builder": stamp(Path(__file__).resolve()),
        "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        "limitations": ["Preparation only: no ingestion service/parser/API/MCP run or model invocation.",
            "DATA001 remains an unfinished dependency; DATA002 official status is unchanged.",
            "Controls are future service expectations, not passed functional tests.",
            "Real PDF original is local-only; reuse permission and canonical ID assignment require later handling.",
            "Local pinned code is not claimed to be the current remote main."]})
    print(json.dumps({"prepared": True, "run": run.relative_to(ROOT).as_posix(), "reviews": len(reviews), "pdf_pages": pages,
        "schema": json.loads(schema_outcome["stdout"]), "task_status": read(TASK)["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
