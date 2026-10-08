"""Capture three public manufacturer Q&A HTML responses; no collector imports."""

import concurrent.futures
import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "data/reference/data-remaining-intake/20261008-01a1100e"
PRIVATE = ROOT / "private/data-remaining-intake/20261008-01a1100e/qa"


def acquire(candidate):
    url = candidate["source_url"]
    if not re.fullmatch(r"https://www\.lge\.co\.kr/support/solutions-\d+", url):
        raise ValueError("Only a discovered official public Q&A URL is allowed")
    receipt = {"candidate_id": candidate["candidate_id"], "source_url": url,
               "document_id": candidate["document_id"],
               "observed_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
               "customer_review_published_at": None, "exact_SKU_application_approved": False,
               "runtime_registered": False, "eligible_for_review_denominator": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(5 * 1024 * 1024 + 1)
            receipt.update({"http_status": response.status, "final_url": response.geturl(),
                            "content_type": response.headers.get("Content-Type")})
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError("Unexpectedly large response")
        text = raw.decode("utf-8")
        cleaned = re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", text)))
        excerpt = re.sub(r"\s+", "", candidate["excerpt"])
        digest = hashlib.sha256(raw).hexdigest()
        path = PRIVATE / (candidate["document_id"] + "-" + digest[:12] + ".html")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Existing new-folder capture changed")
        if not path.exists():
            path.write_bytes(raw)
        receipt.update({"status": "CAPTURED_PUBLIC_HTML_REFERENCE", "html_sha256": digest,
                        "bytes": len(raw), "local_private_path": path.relative_to(ROOT).as_posix(),
                        "short_excerpt_in_normalized_HTML": bool(excerpt and excerpt in cleaned),
                        "capture_does_not_resolve_date_or_SKU_semantics": True})
    except Exception as exc:
        receipt.update({"status": "UNCONFIRMED_CAPTURE", "html_sha256": None,
                        "error_type": type(exc).__name__, "error": str(exc)[:300]})
    return receipt


def main():
    discovery = json.loads((REF / "qa-review-candidates.json").read_text(encoding="utf-8"))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    selected = [c for c in discovery["candidates"] if c["candidate_id"].startswith("QA-C")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(acquire, selected))
    result = {"record_id": "DATA-REMAINING-INTAKE-20261008-01a1100e",
              "official_QA_candidates": len(selected), "raw_HTML_captures": sum(r["html_sha256"] is not None for r in receipts),
              "receipts": receipts, "new_confirmed_customer_reviews": 0,
              "new_model_calls": 0, "new_OCR_runs": 0, "producer_collector_runs": 0,
              "limitations": ["Full raw HTML is local/private; published receipt hashes apply to this particular HTTP response.",
                              "HTML hashing/short phrase presence is separate from visible article parsing and date/SKU approval.",
                              "Manufacturer article display dates are not customer review dates; Q&A is not customer experience."]}
    (REF / "qa-original-captures.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8", newline="\n")
    print(json.dumps({"official_QA_candidates": len(selected), "raw_HTML_captures": result["raw_HTML_captures"],
                      "confirmed_new_customer_reviews": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
