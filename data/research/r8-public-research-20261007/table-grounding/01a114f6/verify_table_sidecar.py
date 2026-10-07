"""Read-only original-span checks and targeted metadata counterexamples."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


def check(graph, root):
    documents = {d["id"]: d for d in graph["documents"]}
    texts = {}
    for d in documents.values():
        for key in ("pdf", "native", "render"):
            entry = d[key]
            raw = (root / entry["path"]).read_bytes()
            assert len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"]
        texts[d["id"]] = (root / d["native"]["path"]).read_text(encoding="utf-8")
    for item in graph["cells"] + graph["footnotes"]:
        text = texts[item["document"]]
        start, end = item["source"]["native_range"]
        assert hashlib.sha256(text[start:end].encode()).hexdigest() == item["source"]["span_sha256"]
        a, b = item["source"]["anchor_range"]
        assert text[a:b] == item["source"]["short_anchor"] and start <= a < b <= end
    cells = {c["id"]: c for c in graph["cells"]}
    assert cells["DUE-FREE-STANDARD"]["values"] == {"width_mm": 598, "height_mm": 845, "depth_mm": 600}
    assert cells["DUE-FREE-STANDARD"]["column_family"] == "DFE"
    assert cells["DUE-FREE-TOP-REMOVED"]["condition"] == "top_removed"
    assert cells["DUE-FREE-TOP-REMOVED"]["column_family"] == "DFE"
    assert cells["DUE-BUILTIN"]["values"] == {"width_mm": 598, "height_mm": 815, "depth_mm": 567}
    assert cells["DUE-BUILTIN"]["installation_type"] == "built_in" and cells["DUE-BUILTIN"]["condition"] is None
    assert cells["DUE-BUILTIN"]["column_family"] == "DUE"
    mask = documents["DUE"]["exact_document_model_pattern"]
    assert re.fullmatch(re.escape(mask).replace(r"\*", "."), documents["DUE"]["model_id"])
    assert cells["MW-CONSUMPTION"]["value"] == 1570 and cells["MW-CONSUMPTION"]["quantity"] == "electric_input"
    rf = cells["MW-RF-OUTPUT"]
    assert rf["value"] == 1000 and rf["quantity"] == "rf_output" and rf["maximum"]
    assert rf["footnote_ids"] == ["MW-FN1"] and rf["canonical_evidence_ids"] == ["DATA003-MW23FDI-M06"]
    fn = graph["footnotes"][0]
    assert fn["id"] == "MW-FN1" and fn["canonical_evidence_ids"] == ["DATA003-MW23FDI-M06"]
    fixed = json.loads((root / graph["dataset_pin"]["path"]).read_bytes())
    evidence = {e["id"]: e for e in fixed["evidence"]}
    for binding in graph["canonical_mapping"]:
        original = evidence[binding["evidence_id"]]
        text = texts["DUE" if "DUE" in binding["evidence_id"] else "MW"]
        start, end = binding["native_quote_range"]
        assert text[start:end] == original["text"]
        assert hashlib.sha256(original["text"].encode()).hexdigest() == binding["canonical_text_sha256"]
        assert original["model_id"] == binding["model_id"] and original["document_version"] == binding["document_version"]
        assert original["locator"] == binding["locator"] and original["feature_ids"] == binding["feature_ids"] == []
        assert binding["canonical_fields_modified"] is False
    assert "1000" not in evidence["DATA003-MW23FDI-M07"]["text"]
    assert graph["automatic_producer_graph_received"] is False
    assert graph["automatic_accuracy"] is graph["automatic_error_count"] is None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--sidecar", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    raw = args.sidecar.read_bytes()
    graph = json.loads(raw)
    check(graph, args.source_root)
    modifications = [
        ("wrong_DUE_height", lambda g: g["cells"][2]["values"].update(height_mm=845)),
        ("DFE_condition_on_DUE", lambda g: g["cells"][2].update(condition="top_removed")),
        ("M07_used_for_output", lambda g: g["cells"][4].update(canonical_evidence_ids=["DATA003-MW23FDI-M07"])),
        ("input_power_used_as_output", lambda g: g["cells"][4].update(value=1570)),
        ("missing_time_note", lambda g: g["cells"][4].update(footnote_ids=[])),
    ]
    probes = []
    for name, edit in modifications:
        changed = deepcopy(graph)
        edit(changed)
        rejected = False
        try:
            check(changed, args.source_root)
        except AssertionError:
            rejected = True
        assert rejected, name
        probes.append({"metadata_probe": name, "rejected": True})
    result = {"status": "PASS", "sidecar_sha256": hashlib.sha256(raw).hexdigest(),
              "bound_cells": len(graph["cells"]), "bound_footnotes": len(graph["footnotes"]),
              "canonical_bindings": len(graph["canonical_mapping"]), "probes": probes,
              "original_files_modified": 0, "new_model_ocr_calls": 0, "network_requests": 0,
              "automatic_accuracy": None, "automatic_error_count": None,
              "scope": "original bytes/spans and manually reviewed table relationships; not automatic graph performance"}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
