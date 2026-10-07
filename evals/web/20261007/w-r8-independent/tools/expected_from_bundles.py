"""Independent expectations for the R8 research web flow (record 최길웅-20261007-057), computed from the bundle JSON
files only (no web code). Counts the screen should show per bundle: sources, reviews by type, confirmed posting days,
unknown purchase model / page model, official-document coverage, and the plain keyword filter result.
Usage: python expected_from_bundles.py <bundle.json>... > expected.json"""
import datetime
import hashlib
import json
import sys
from collections import Counter

KEYWORDS = ["냄새", "소음", "설치", "문"]


def posting_day(source):
    if source.get("date_kind") != "posting" or not source.get("published_at"):
        return None
    head = source["published_at"][:10]
    try:
        datetime.date.fromisoformat(head)
    except ValueError:
        return None
    return head


out = {"kind": "r8_research_web_expectations", "bundles": {}}
for path in sys.argv[1:]:
    raw = open(path, "rb").read()
    bundle = json.loads(raw)
    sources = bundle["sources"]
    reviews = [s for s in sources if s["source_type"] == "review"]
    docs = [s for s in sources if s["source_type"] in ("manual", "faq", "spec", "installation")]
    keyword_hits = {}
    for word in KEYWORDS:
        keyword_hits[word] = sum(1 for s in sources if word in f"{s.get('title') or ''} {s['text']}".lower())
    out["bundles"][bundle["bundle_id"]] = {
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "product_group": bundle["product_group"],
        "analysis_scope": bundle["analysis_scope"],
        "sources": len(sources),
        "by_type": dict(Counter(s["source_type"] for s in sources)),
        "reviews": len(reviews),
        "confirmed_posting_days": sum(1 for s in sources if posting_day(s)),
        "reviews_unknown_posting": sum(1 for s in reviews if not posting_day(s)),
        "reviews_unknown_purchase_model": sum(1 for s in reviews if s.get("purchased_model") is None),
        "sources_unknown_page_model": sum(1 for s in sources if s.get("page_model") is None),
        "page_models": sorted({s["page_model"] for s in sources if s.get("page_model")}),
        "docs_excerpt": sum(1 for s in docs if s.get("coverage") == "excerpt"),
        "docs_unknown_coverage": sum(1 for s in docs if s.get("coverage") == "unknown"),
        "keyword_hits_title_or_text": keyword_hits,
        "independent_evaluation_approved": bundle["collection_manifest"].get("independent_evaluation_approved"),
    }
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print()
