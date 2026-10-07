"""Read-only byte/JSON/CSV/link checks of this new audit and original Git files."""

import ast
import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
PREFIXES = ["evals/data-remaining-intake/20261008-01a1100e/",
            "data/reference/data-remaining-intake/20261008-01a1100e/",
            "docs/작업기록/신진하/2026-10-08/DATA-REMAINING-INTAKE-20261008-01a1100e.md",
            "docs/작업근거/신진하/2026-10-08/DATA-REMAINING-INTAKE-20261008-01a1100e.md"]


def git(*args):
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
    return subprocess.check_output(["git", "-c", "core.hooksPath=NUL", "-c", "core.fsmonitor=false",
                                    "-c", "core.quotepath=false", *args], cwd=ROOT, env=env)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    old_count, old_bytes, errors = 0, 0, []
    tree = git("ls-tree", "-rz", "--full-tree", BASE)
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        info, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = info.decode("ascii").split()
        if kind != "blob":
            continue
        file = raw_path.decode("utf-8")
        try:
            raw = (ROOT / file).read_bytes()
            actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            old_count += 1
            old_bytes += len(raw)
            if actual != oid:
                errors.append({"kind": "original_Git_bytes_changed", "path": file})
        except OSError as exc:
            errors.append({"kind": "original_unreadable", "path": file, "error_type": type(exc).__name__})
    all_files = set()
    for prefix in PREFIXES:
        path = ROOT / prefix
        all_files.update(path.rglob("*") if path.is_dir() else [path])
    files = sorted(p for p in all_files if p.is_file()
                   and p.name not in {"artifact-checks.json", "new-artifacts-manifest.json"})
    manifest, links, json_count, code_count = [], 0, 0, 0
    for file in files:
        raw = file.read_bytes()
        relative = file.relative_to(ROOT).as_posix()
        manifest.append({"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        if file.suffix in (".md", ".py", ".json", ".csv"):
            if b"\r" in raw:
                errors.append({"kind": "new_text_not_LF", "path": relative})
            text = raw.decode("utf-8-sig")
            if file.suffix == ".json":
                json.loads(text)
                json_count += 1
            if file.suffix == ".py":
                ast.parse(text)
                code_count += 1
            if file.suffix == ".md":
                for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                    parsed = urlsplit(target.strip("<>"))
                    if parsed.scheme or not parsed.path:
                        continue
                    links += 1
                    if not (file.parent / unquote(parsed.path)).resolve().exists():
                        errors.append({"kind": "broken_new_local_link", "path": relative, "target": target})
    ref = ROOT / PREFIXES[1]
    manuals = json.loads((ref / "manual-acquisition.json").read_text(encoding="utf-8"))
    pdf_captures, covers = {}, {}
    for row in manuals["models"]:
        for c in row["candidates"]:
            raw = (ROOT / c["local_private_path"]).read_bytes()
            pdf_captures[c["url"]] = c["pdf_sha256"]
            if hashlib.sha256(raw).hexdigest() != c["pdf_sha256"] or not raw.startswith(b"%PDF-"):
                errors.append({"kind": "new_manual_original_mismatch", "model": row["model_id"]})
            file = ref / c["reference_cover_path"]
            covers[str(file)] = c["reference_cover_sha256"]
            if hashlib.sha256(file.read_bytes()).hexdigest() != c["reference_cover_sha256"]:
                errors.append({"kind": "derived_cover_mismatch", "path": str(file.relative_to(ROOT))})
    qa = json.loads((ref / "qa-original-captures.json").read_text(encoding="utf-8"))
    for r in qa["receipts"]:
        if r["html_sha256"] and hashlib.sha256((ROOT / r["local_private_path"]).read_bytes()).hexdigest() != r["html_sha256"]:
            errors.append({"kind": "new_QA_original_mismatch", "candidate_id": r["candidate_id"]})
    with (OUT / "care-source-bridge.csv").open(encoding="utf-8-sig", newline="") as stream:
        care_rows = list(csv.DictReader(stream))
    with (ref / "manual-reference-table.csv").open(encoding="utf-8-sig", newline="") as stream:
        manual_rows = list(csv.DictReader(stream))
    result = {"record_id": "DATA-REMAINING-INTAKE-20261008-01a1100e", "baseline_commit": BASE,
              "status": "PASS" if not errors else "ERROR", "errors": errors,
              "original_tracked_files_checked": old_count, "original_tracked_bytes_checked": old_bytes,
              "new_manifest_files": len(manifest), "new_JSON_parsed": json_count,
              "new_Python_AST_parsed": code_count, "new_local_markdown_links_checked": links,
              "care_CSV_rows": len(care_rows), "manual_CSV_rows": len(manual_rows),
              "local_raw_PDF_captures_SHA_checked": len(pdf_captures),
              "distinct_PDF_SHA": len(set(pdf_captures.values())), "cover_SHA_checked": len(covers),
              "local_QA_HTML_SHA_checked": qa["raw_HTML_captures"],
              "new_model_calls": 0, "new_OCR_runs": 0, "producer_or_test_suite_execution": 0,
              "limitation": "File/metadata/link audit only; not runtime/meaning/automatic-table/PM approval"}
    write_json(OUT / "new-artifacts-manifest.json", manifest)
    write_json(OUT / "artifact-checks.json", result)
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
