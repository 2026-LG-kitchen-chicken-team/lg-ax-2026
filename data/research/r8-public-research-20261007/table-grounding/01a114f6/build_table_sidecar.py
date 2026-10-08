"""Bind visually reviewed table topology to fixed native spans; no OCR/model."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(root, relative):
    raw = (root / relative).read_bytes()
    return {"path": relative, "bytes": len(raw), "sha256": sha(raw)}


def span(text, start, end, anchor):
    assert anchor in text[start:end]
    a = text.index(anchor, start, end)
    return {"native_range": [start, end], "span_sha256": sha(text[start:end].encode()),
            "short_anchor": anchor, "anchor_range": [a, a + len(anchor)],
            "range_basis": "0-based end-exclusive characters in the pinned native page text"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root, out = args.source_root, args.output
    out.mkdir(parents=True, exist_ok=True)
    native = "evals/data14-auto-table-link-audit/20261007-01a1100e/native-source-text/"
    renders = "evals/data14-auto-table-link-audit/20261007-01a1100e/pdf-renders/"
    due_path = "data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf"
    mw_path = "data/sources/lg-manuals-20261005/MW23FDI-3ceec78295d0.pdf"
    due = (root / (native + "DUE6BGL2E-p57.txt")).read_text(encoding="utf-8")
    mw = (root / (native + "MW23FDI-p37.txt")).read_text(encoding="utf-8")
    assert pin(root, due_path)["sha256"] == "ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5"
    assert pin(root, mw_path)["sha256"] == "3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc"
    fixed = json.loads((root / "data/research/PM-DATA-intake-20261006/generated/dataset.json").read_bytes())
    evidence = {e["id"]: e for e in fixed["evidence"]}
    rows = list(re.finditer(r"598\s*mm\s*X\s*(845|815)\s*mm\s*X\s*(600|567)\s*mm(?:\s*\(([^)]+)\))?", due))
    assert len(rows) == 3 and [int(m[1]) for m in rows] == [845, 815, 815]
    cells = []
    specs = [
        ("DUE-FREE-STANDARD", "DFE", "freestanding", None),
        ("DUE-FREE-TOP-REMOVED", "DFE", "freestanding", "top_removed"),
        ("DUE-BUILTIN", "DUE", "built_in", None),
    ]
    for match, (cid, family, install, condition) in zip(rows, specs):
        assert bool(match[3]) == (condition == "top_removed")
        cells.append({"id": cid, "document": "DUE", "page": 57, "row": "dimensions_w_h_d",
                      "column_family": family, "installation_type": install, "condition": condition,
                      "values": {"width_mm": 598, "height_mm": int(match[1]), "depth_mm": int(match[2])},
                      "unit": "mm", "source": span(due, match.start(), match.end(), match[1] + " mm"),
                      "canonical_evidence_ids": ["DATA003-DUE6BGL2E-D03"],
                      "binding_meaning": "broad evidence contains all columns; this sidecar identifies which cell is applicable"})
    power = re.search(r"정격 소비전력\s+(1570\s*W)", mw)
    output = re.search(r"정격 고주파 출력\s+(Max\.\s*1000\s*W\*1)", mw)
    footnote = re.search(r"\*1\s+고주파 출력[^\n]+", mw)
    assert power and output and footnote
    cells += [
        {"id": "MW-CONSUMPTION", "document": "MW", "page": 37, "row": "rated_consumption",
         "column_family": "shared_23_25", "value": 1570, "unit": "W", "quantity": "electric_input",
         "source": span(mw, power.start(), power.end(), power[1]),
         "canonical_evidence_ids": ["DATA003-MW23FDI-M06", "DATA003-MW23FDI-M07"]},
        {"id": "MW-RF-OUTPUT", "document": "MW", "page": 37, "row": "rated_rf_output",
         "column_family": "shared_23_25", "value": 1000, "unit": "W", "maximum": True,
         "quantity": "rf_output", "footnote_ids": ["MW-FN1"],
         "source": span(mw, output.start(), output.end(), output[1]),
         "canonical_evidence_ids": ["DATA003-MW23FDI-M06"]},
    ]
    fn = {"id": "MW-FN1", "document": "MW", "page": 37,
          "meaning": "short-duration output; can change as cooking time elapses",
          "source": span(mw, footnote.start(), footnote.end(), "짧은 시간"),
          "canonical_evidence_ids": ["DATA003-MW23FDI-M06"]}
    mappings = []
    for eid in ("DATA003-DUE6BGL2E-D03", "DATA003-MW23FDI-M06", "DATA003-MW23FDI-M07"):
        e = evidence[eid]
        text = due if "DUE" in eid else mw
        start = text.find(e["text"])
        assert start >= 0, (eid, "canonical quote does not match frozen page")
        mappings.append({"evidence_id": eid, "model_id": e["model_id"],
                         "document_version": e["document_version"], "locator": e["locator"],
                         "native_quote_range": [start, start + len(e["text"])],
                         "canonical_text_sha256": sha(e["text"].encode()),
                         "feature_ids": e["feature_ids"],
                         "has_output_and_short_duration_note": eid.endswith("M06"),
                         "canonical_fields_modified": False})
    graph = {
        "version": "table-grounding.20261008.01a114f6.v1",
        "source_commit": "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f",
        "relation_method": "Codex visual review of fixed full-page renders plus existing native parser spans",
        "automatic_producer_graph_received": False, "automatic_accuracy": None,
        "automatic_error_count": None, "new_ocr_model_calls": 0,
        "documents": [
            {"id": "DUE", "model_id": "DUE6BGL2E", "page": 57, "version": "MFL71959117 Rev.07_030626",
             "pdf": pin(root, due_path), "native": pin(root, native + "DUE6BGL2E-p57.txt"),
             "render": pin(root, renders + "DUE6BGL2E-p57-180dpi.png"),
             "column_headers": {"DFE": {"family": ["DFE6**E", "DFE6***E"], "type": "freestanding"},
                                "DUE": {"family": ["DUE6**E", "DUE6***E", "DUE6****E", "DEE6**E"], "type": "built_in"}},
             "exact_document_model_pattern": "DUE6****E", "buyer_sku_verified": False},
            {"id": "MW", "model_id": "MW23FDI", "page": 37, "version": "MFL68822538 Rev.00_120925",
             "pdf": pin(root, mw_path), "native": pin(root, native + "MW23FDI-p37.txt"),
             "render": pin(root, renders + "MW23FDI-p37-180dpi.png"),
             "column_headers": {"23": ["MWJ23PI", "MWJ23EI", "MW23FDI"], "25": ["MWJ25PI", "MWJ25EI"]},
             "power_rows_merge_columns": ["23", "25"], "buyer_sku_verified": False},
        ],
        "cells": cells, "footnotes": [fn], "canonical_mapping": mappings,
        "dataset_pin": pin(root, "data/research/PM-DATA-intake-20261006/generated/dataset.json"),
        "consumer_rules": {
            "DUE6BGL2E_applicable_cell": "DUE-BUILTIN",
            "DFE_top_removed_is_not_DUE_condition": True,
            "M07_cannot_support_max_rf_output_or_note": True,
            "empty_feature_ids_are_not_automatic_feature_approval": True,
            "disconnected_cells_must_not_be_forged_into_a_contiguous_quote": True,
            "sidecar_is_not_canonical_schema_extension": True,
        },
        "limitations": ["manual source-derived topology, not automatic table/OCR accuracy",
                        "no approved production adapter imported", "CORE actual consumption acknowledgement pending"],
    }
    (out / "table-evidence-sidecar.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cells": len(cells), "footnotes": 1, "canonical_bindings": len(mappings),
                      "automatic_accuracy": None, "model_ocr_calls": 0}))


if __name__ == "__main__":
    main()
