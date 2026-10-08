"""Capture public official PDFs into a new ignored folder; read native cover text.

No producer imports, model/OCR calls, registration, or changes to existing files.
Run explicitly with the bundled PDF Python. Original bytes stay local/private.
"""

import concurrent.futures
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "data/reference/data-remaining-intake/20261008-01a1100e"
PRIVATE = ROOT / "private/data-remaining-intake/20261008-01a1100e/manuals"
MAX_BYTES = 25 * 1024 * 1024


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def acquire(url):
    if not url.startswith("https://gscs-b2c.lge.com/open/downloadFile?fileId="):
        raise ValueError("Only the discovered public LG manual URL is permitted")
    file_id = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["fileId"][0]
    if not re.fullmatch(r"[A-Za-z0-9]+", file_id):
        raise ValueError("Unexpected public file ID")
    receipt = {"url": url, "public_file_id": file_id,
               "observed_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat()}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/pdf"})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(MAX_BYTES + 1)
            receipt.update({"http_status": response.status,
                            "final_url": response.geturl(),
                            "content_type": response.headers.get("Content-Type")})
        if len(raw) > MAX_BYTES or not raw.startswith(b"%PDF-"):
            raise ValueError("Response is oversized or not original PDF bytes")
        digest = hashlib.sha256(raw).hexdigest()
        path = PRIVATE / (file_id + "-" + digest[:12] + ".pdf")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("An existing capture at this path has different bytes")
        if not path.exists():
            path.write_bytes(raw)
        doc = pdfium.PdfDocument(raw)
        page = doc[0]
        textpage = page.get_textpage()
        text = textpage.get_text_range()
        textpage.close()
        image = page.render(scale=1.2).to_pil()
        image.save(path.with_suffix(".cover.png"))
        page.close()
        receipt.update({"status": "CAPTURED_PDF_NATIVE_COVER", "bytes": len(raw),
                        "pdf_sha256": digest, "pdf_pages": len(doc),
                        "local_private_path": path.relative_to(ROOT).as_posix(),
                        "cover_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "cover_versions": re.findall(r"MFL\s*\d+\s+Rev\.\s*[\d]+_[\d]+", text),
                        "_native_cover_text": text})
        path.with_suffix(".cover.txt").write_text(text, encoding="utf-8", newline="")
        doc.close()
    except Exception as exc:
        receipt.update({"status": "UNCONFIRMED_CAPTURE", "error_type": type(exc).__name__,
                        "error": str(exc)[:300], "pdf_sha256": None})
    return receipt


def main():
    discovery = json.loads((REF / "manual-link-candidates.json").read_text(encoding="utf-8"))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    urls = sorted({c["url"] for row in discovery["rows"] for c in row["pdf_candidates"]})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(acquire, urls))
    by_url = {r["url"]: r for r in receipts}
    models = []
    for row in discovery["rows"]:
        copies = []
        for candidate in row["pdf_candidates"]:
            receipt = by_url[candidate["url"]]
            text = receipt.get("_native_cover_text", "")
            copies.append({**candidate,
                           **{k: v for k, v in receipt.items() if not k.startswith("_")},
                           "exact_SKU_in_native_cover": row["model_id"] in re.sub(r"\s+", "", text),
                           "purchased_SKU": None, "purchase_time_revision_verified": False,
                           "all_features_for_exact_SKU_verified": False,
                           "runtime_registered": False})
        models.append({"model_id": row["model_id"], "support_url": row["support_url"],
                       "support_link_basis": "independent read-only browser discovery; exact support title verified",
                       "candidates": copies, "ambiguity": row.get("ambiguity"),
                       "status": "CAPTURED_REFERENCE_NOT_REGISTERED" if any(c["pdf_sha256"] for c in copies)
                       else "LINK_ONLY_UNCONFIRMED_CAPTURE"})
    captured = [r for r in receipts if r["status"] == "CAPTURED_PDF_NATIVE_COVER"]
    result = {"record_id": "DATA-REMAINING-INTAKE-20261008-01a1100e",
              "model_count": len(models), "unique_candidate_URLs": len(urls),
              "public_URL_PDF_captures": len(captured),
              "unique_PDF_content_SHA_count": len({r["pdf_sha256"] for r in captured}),
              "models_with_original_PDF": sum(any(c["pdf_sha256"] for c in row["candidates"]) for row in models),
              "models_with_exact_SKU_on_native_cover": sum(any(c["exact_SKU_in_native_cover"] for c in row["candidates"]) for row in models),
              "capture_failures": [{k: v for k, v in r.items() if not k.startswith("_")}
                                   for r in receipts if r["status"] != "CAPTURED_PDF_NATIVE_COVER"],
              "models": models, "new_model_calls": 0, "new_OCR_runs": 0,
              "native_cover_extractions": len(captured), "existing_file_changes": 0,
              "original_PDF_location": "local/private only; fetch official URL and match complete SHA for independent reuse",
              "limitations": ["Listed registration dates are not customer review posting dates or confirmed first publication dates.",
                              "Support linkage/common cover/pattern does not prove every feature applies to the exact purchased SKU.",
                              "Multiple listed revisions remain separate; newer listing dates do not approve a replacement.",
                              "No ResearchBundle/Evidence/DB registration, collection pipeline, or production import was performed."]}
    write_json(REF / "manual-acquisition.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("models", "limitations", "capture_failures")}, ensure_ascii=False))
    print(json.dumps({"capture_failures": result["capture_failures"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
