"""In-memory metadata tamper probes; never write a workbook or customer data."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import posixpath
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--xlsx", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location("d4", Path(__file__).with_name("audit_delivery.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = args.source_root / "data/research/r5-public-reviews-20261007"
    expected = {r["original_review_id"]: r for f in ("fixed18/records.json", "balanced-pilot-v2/new_unique_records.json") for r in module.load(root / f)}
    groups = {r["model_id"]: r["product_group"] for r in module.load(root / "fixed18/products.json")}
    before = module.digest(args.xlsx.read_bytes())
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with ZipFile(args.xlsx) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        sheet = next(s for s in wb.findall("m:sheets/m:sheet", ns) if s.attrib["name"] == "리뷰")
        target = targets[sheet.attrib[rel_attr]]
        target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
    original_zip = module.ZipFile
    results = []
    for mode, wanted in (("unknown_id", "xlsx_unregistered_review_row"), ("wrong_group", "xlsx_product_group_changed")):
        class MemoryZip(original_zip):
            def read(self, name, *args, **kwargs):
                raw = super().read(name, *args, **kwargs)
                if name != target:
                    return raw
                sheet_root = ET.fromstring(raw)
                data = sheet_root.find("m:sheetData", ns)
                source = next(r for r in data if int(r.attrib["r"]) == 5)
                row = copy.deepcopy(source)
                if mode == "unknown_id":
                    index = max(int(r.attrib["r"]) for r in data) + 1
                    row.attrib["r"] = str(index)
                    for cell in row:
                        cell.attrib["r"] = "".join(c for c in cell.attrib["r"] if not c.isdigit()) + str(index)
                    selected = next(c for c in row if c.attrib["r"].startswith("A"))
                    value = "AUDIT_ONLY_UNREGISTERED_ID"
                    data.append(row)
                else:
                    row = source
                    selected = next(c for c in row if c.attrib["r"] == "B5")
                    value = "microwave"
                selected.clear()
                selected.attrib.update({"r": "A" + str(index) if mode == "unknown_id" else "B5", "t": "inlineStr"})
                inline = ET.SubElement(selected, "{" + ns["m"] + "}is")
                ET.SubElement(inline, "{" + ns["m"] + "}t").text = value
                return ET.tostring(sheet_root, encoding="utf-8")
        module.ZipFile = MemoryZip
        audit = module.Audit()
        module.inspect_xlsx(args.xlsx, expected, groups, audit)
        codes = {f["code"] for f in audit.findings}
        assert wanted in codes, (mode, codes)
        results.append({"probe": mode, "required_finding": wanted, "detected": True})
    module.ZipFile = original_zip
    after = module.digest(args.xlsx.read_bytes())
    assert before == after
    result = {"status": "PASS", "scope": "two in-memory metadata tamper probes, not new customer reviews or workbook authoring",
              "probes": results, "source_workbook_sha256": before, "source_workbook_unchanged": True,
              "workbook_files_written": 0, "model_calls": 0, "network_requests": 0,
              "audit_code_sha256": module.digest(Path(__file__).with_name("audit_delivery.py").read_bytes())}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
