"""Build a fresh public-manual pack; no network, credentials, OCR or models.

The pypdf wheel is an optional, separately pinned DATA tool. It is loaded only
for this preparation and its child parser, without installing into any runtime.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

from lgax_core.document_store import DocumentStore
from lgax_core.documents import DocumentRepository
from lgax_core.review_csv import FIELDS
from lgax_core.review_import import import_review_csv
from lgax_core.source_ranges import capture_source, verify_source_range
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[3]
VERSION = "lg-manual-scope-20261006.3-pm-intake"
FOLDER = Path("data/research/PM-DATA-intake-20261006")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_bytes())


def write(directory, name, value):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def prepare(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Preserve the previous pack; choose a fresh output directory")
    output.mkdir(parents=True)
    wheel = read("evals/pm-data-intake/20261006/parser-wheel.json")
    wheel_path = ROOT / wheel["path"]
    if sha(wheel_path.read_bytes()) != wheel["sha256"]:
        raise ValueError("Pinned optional parser wheel changed")
    previous_sys_path = sys.path[:]
    sys.path.insert(0, str(wheel_path))
    previous_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(wheel_path) + os.pathsep + (previous_pythonpath or "")
    try:
        import pypdf
        from pypdf import PdfReader

        if pypdf.__version__ != wheel["version"]:
            raise ValueError("Active optional parser version does not match the pin")
        plan = read("data/document_plans/lg-three-models-20261005.json")
        plan["dataset_version"] = VERSION
        proposal = read("evals/data003-independent/20261005-01a10834/missing-evidence-proposal.json")
        for item in proposal["selections"]:
            doc = next(d for d in plan["documents"] if d["document_id"] == item["document_id"])
            if (doc["sha256"] != item["pdf_sha256"] or doc["document_version"] != item["document_version"]
                    or doc["product"]["model_id"] != item["model_id"]):
                raise ValueError("Additional selection changed its approved source scope")
            doc["selections"].append({"evidence_id": item["evidence_id"], "page": item["page"],
                "section": item["section"], "excerpt": item["excerpt"], "feature_ids": []})
        write(output, "plan.json", plan)
        proofs, origins = [], []
        with tempfile.TemporaryDirectory(prefix="lgax-data-pack-") as temporary:
            repository = DocumentRepository(Path(temporary), plan, sys.executable)
            for doc in plan["documents"]:
                path = ROOT / "data/sources/lg-manuals-20261005" / (
                    doc["product"]["model_id"] + "-" + doc["sha256"][:12] + ".pdf")
                raw = path.read_bytes()
                if sha(raw) != doc["sha256"]:
                    raise ValueError("Preserved approved manual bytes changed")
                record = repository.upload(doc["document_id"], raw)
                origins.extend(record["origins"])
                pages = tuple(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
                sections = {o["evidence_id"]: (o["page"], o["start_char"], o["end_char"])
                            for o in record["origins"]}
                snapshot = capture_source(raw, document_id=doc["document_id"],
                    model_id=doc["product"]["model_id"], document_version=doc["document_version"],
                    source_kind="public", pages=pages)
                for evidence, origin in zip(record["dataset"]["evidence"], record["origins"]):
                    # Section labels in the canonical plan are human labels. Bind
                    # this exact evidence to its own span, even if labels repeat.
                    label = evidence["locator"]["section"]
                    captured = capture_source(raw, document_id=snapshot.document_id,
                        model_id=snapshot.model_id, document_version=snapshot.document_version,
                        source_kind="public", pages=pages, sections={label: sections[evidence["id"]]})
                    proofs.append(verify_source_range(captured, evidence, origin, current_original=raw))
                for item in proposal["selections"]:
                    if item["document_id"] != doc["document_id"]:
                        continue
                    text = pages[item["page"] - 1]
                    if (text[item["start_char"]:item["end_char"]] != item["excerpt"]
                            or sha(item["excerpt"].encode()) != item["text_sha256"]):
                        raise ValueError("Owner proposal range does not match fresh exact PDF text")
            dataset = repository.store().bootstrap()["data"]
            dataset.pop("contract_version", None)
        write(output, "dataset.json", dataset)
        write(output, "origins.json", origins)
        write(output, "source-range-verification.json", {"parser": "pypdf", "parser_version": pypdf.__version__,
            "pdf_count": 3, "verified_exact_text_ranges": len(proofs), "proofs": proofs,
            "extra_selections_verified_against_actual_pdf": len(proposal["selections"]),
            "ocr_used": False, "visual_layout_or_optional_sku_applicability_newly_verified": False})
        situations = {
            "fridge": ("가상의 높이 큰 용기 보관과 선반 분리 상황", "기존 선반 구조의 제약과 추가로 확인할 고객 요구를 대조", "접이식 선반을 새로운 기능으로 제안"),
            "dishwasher": ("가상의 큰 식기 적재와 노즐 간섭 확인 상황", "기존 적재 안내와 바구니 조절의 제약을 대조하고 추가 확인 질문을 도출", "기존 바구니 높이 조절을 새로운 기능으로 제안"),
            "microwave": ("가상의 반복 가열과 개인 설정 요청 상황", "출력·기억된 메뉴·설정의 조건을 보존하고 기능 중복 여부를 대조", "새 고주파 출력 모드를 제안"),
        }
        for product in dataset["products"]:
            model, group = product["model_id"], product["product_group"]
            scoped = deepcopy(dataset)
            scoped["products"] = [deepcopy(product)]
            for key in ("evidence", "features", "reviews"):
                scoped[key] = [deepcopy(e) for e in dataset[key] if e["model_id"] == model]
            write(output, model + "/dataset.json", scoped)
            store = DocumentStore(scoped)
            request = {"product_group": group, "target_customer": "가상 기획 시나리오의 가정 사용자",
                "use_situation": situations[group][0], "improvement_task": situations[group][1],
                "exclusions": ["근거 없이 고객 불편이나 효과를 단정"], "model_ids": [model], "dataset_version": VERSION}
            versions = {model: product["document_version"]}
            write(output, model + "/normal.input.json", build_planning_input(request, versions, store))
            changed = deepcopy(request)
            changed["exclusions"].append(situations[group][2])
            write(output, model + "/changed.input.json", build_planning_input(changed, versions, store))
        raw_path = Path("data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv")
        raw = (ROOT / raw_path).read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = list(reader)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        derived = stream.getvalue().encode()
        with (output / "synthetic-reviews-derived-wire.csv").open("xb") as target:
            target.write(derived)
        products = deepcopy(read("data/demo/dataset.json")["products"])
        for product in products:
            product["document_version"] = "1.0"  # Existing CSV edition, separate from the demo manuals.
        sources = [{"document_id": "REVIEWS-CSV-v1.0", "model_id": product["model_id"],
                    "document_version": "1.0", "source_kind": "synthetic"} for product in products]
        # One source ID spans several approved models, so import each scope into
        # a separate reader instead of weakening the source-ID uniqueness guard.
        imported = 0
        for product in products:
            selected = [row for row in rows if row["model_id"] == product["model_id"]]
            part = io.StringIO(newline="")
            csv_writer = csv.DictWriter(part, fieldnames=FIELDS, lineterminator="\n")
            csv_writer.writeheader()
            for line, row in enumerate(selected, 2):
                csv_writer.writerow({**row, "row": str(line)})
            source = next(s for s in sources if s["model_id"] == product["model_id"])
            imported += len(import_review_csv(part.getvalue().encode(), products=[product], sources=[source],
                dataset_version="synthetic-review-import-pm-20261006").dataset["reviews"])
        write(output, "review-field-coverage.json", {"original_path": raw_path.as_posix(), "original_sha256": sha(raw),
            "original_rows": len(rows), "original_columns": reader.fieldnames,
            "model_counts": dict(Counter(row["model_id"] for row in rows)),
            "source_kind_counts": dict(Counter(row["source_kind"] for row in rows)),
            "imported_scoped_synthetic_rows": imported, "derived_wire_sha256": sha(derived),
            "wire_conversion_is_not_the_historical_original": True,
            "duplicate_ids": len(rows) - len({row["id"] for row in rows}),
            "duplicate_scoped_exact_text_rows": len(rows) - len({(row["model_id"], row["document_version"], row["source_id"], row["text"]) for row in rows}),
            "review_timestamp_present": 0, "category_column_present": False,
            "product_category_available_via_canonical_model_lookup": True,
            "monthly_or_seasonal_eligible_rows": 0, "real_customer_reviews": 0,
            "dates_fabricated": False})
        write(output, "pack-summary.json", {"dataset_version": VERSION, "models": [p["model_id"] for p in dataset["products"]],
            "manual_evidence": len(dataset["evidence"]), "features": len(dataset["features"]), "public_review_count": 0,
            "standalone_new_evidence": [i["evidence_id"] for i in proposal["selections"]],
            "unresolved_conditions": [{k: i[k] for k in ("evidence_id", "conditions", "unresolved_conflict", "layout_note") if k in i}
                                      for i in proposal["selections"]],
            "expected_behavior": "Preserve manual conditions; hold customer-need conclusions without supporting customer evidence.",
            "model_calls": 0, "active_runtime_or_harness_changed": False,
            "inheritance_limit": "Same-model manual association inherited from approved source mapping; optional SKU features not independently proved."})
        return dataset
    finally:
        sys.path[:] = previous_sys_path
        if previous_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous_pythonpath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / FOLDER / "generated")
    args = parser.parse_args()
    dataset = prepare(args.output)
    print(json.dumps({"dataset_version": dataset["dataset_version"], "evidence": len(dataset["evidence"]),
                      "model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
