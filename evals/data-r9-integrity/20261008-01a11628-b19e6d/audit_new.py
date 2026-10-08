"""Audit only this intake's new public captures; no model, OCR or network."""
import hashlib
import json
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
checks = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def norm(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def check(name, condition, detail=None):
    checks.append({"check": name, "pass": bool(condition), "detail": detail})


class PublicMarkup(HTMLParser):
    """Read only actual public JSON-LD nodes and visible paragraph text."""
    def __init__(self):
        super().__init__()
        self.ld = False
        self.buf = []
        self.docs = []
        self.paragraph_depth = 0
        self.paragraphs = []
        self.pbuf = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.ld, self.buf = True, []
        if tag == "p":
            self.paragraph_depth += 1
            self.pbuf = []

    def handle_data(self, text):
        if self.ld:
            self.buf.append(text)
        if self.paragraph_depth:
            self.pbuf.append(text)

    def handle_endtag(self, tag):
        if tag == "script" and self.ld:
            self.docs.append(json.loads("".join(self.buf)))
            self.ld = False
        if tag == "p" and self.paragraph_depth:
            self.paragraphs.append("".join(self.pbuf))
            self.paragraph_depth -= 1


data = load("sources.sidecar.json")
dates = load("date-candidates.json")
raw = {r["source_id"]: r["text"] for r in load("new-review-bodies.json")}
membership = load("baseline/d1-membership.json")
old_hashes = {r["normalized_body_sha256"] for r in membership}
old_ids = {r["original_review_id"] for r in membership}
check("baseline_membership_count_reused_not_reaudited", len(membership) == 238)
check("new_and_reused_review_rows", len(data["reviews"]) == 7)
check("new_review_count", data["review_originals_new_count"] == 4)
check("new_QA_count", len(data["qa"]) == 2)
check("new_manual_count", len(data["manuals"]) == 2)

parsers = {}
for model, name in [("ML32WW1", "oven-pdp.html"), ("Z330MEEF11", "kimchi-pdp.html")]:
    parser = PublicMarkup()
    parser.feed((ROOT / "captures" / name).read_text(encoding="utf-8"))
    parsers[model] = parser

overlap = []
for r in data["reviews"]:
    rid = r["source_id"]
    text = raw[rid]
    nsha = sha(norm(text).encode())
    check(rid + ":body_sha", sha(text.encode()) == r["body_sha256"])
    check(rid + ":normalized_sha", nsha == r["normalized_body_sha256"])
    check(rid + ":split_unapproved", r["split"] == "unassigned" and not r["trend_approved"])
    check(rid + ":canonical_date_null", r["published_at"] is None)
    overlap.append({"source_id": rid, "exact_normalized_overlap_238": nsha in old_hashes})
    if "short_quote" in r:
        a, b = r["quote_codepoint_range"]
        check(rid + ":codepoint_quote", text[a:b] == r["short_quote"])
    if "native_jsonld_pointer" in r:
        product = next(x for x in parsers[r["page_model"]].docs
                       if isinstance(x, dict) and x.get("@type") == "Product"
                       and x.get("model", "").upper() == r["page_model"])
        entry = product["review"][int(r["native_jsonld_pointer"].split("/")[-1])]
        check(rid + ":native_public_metadata", entry["reviewBody"] == text
              and entry["datePublished"] == r["declared_datePublished"])
        check(rid + ":no_original_id_inference", r["original_review_id"] is None)
    else:
        html = (ROOT / "captures/kimchi-original-blog.html").read_text(encoding="utf-8")
        check(rid + ":visible_date_and_native_post_id",
              'post-view224375944885' in html and "2026. 8. 12. 9:39" in html)
        check(rid + ":native_id_not_238", r["original_post_id"] not in old_ids)

check("new_candidate_normalized_bodies_not_238", not any(x["exact_normalized_overlap_238"] for x in overlap))
old_preview = load("baseline/r9-original-sources.json")["sources"]
for r in data["reviews"]:
    if r.get("existing_r9_source_id"):
        prior = next(x for x in old_preview if x["source_id"] == r["existing_r9_source_id"])
        check(r["source_id"] + ":prior_preview_lineage", norm(prior["text"]) == norm(raw[r["source_id"]]))

for r in data["qa"]:
    parser = PublicMarkup()
    parser.feed((ROOT / "captures" / ("oven-qa-" + r["original_question_id"] + ".html")).read_text(encoding="utf-8"))
    check(r["source_id"] + ":question_excerpt_in_native_paragraph",
          any(r["short_quote"] in p for p in parser.paragraphs))
    check(r["source_id"] + ":not_review_denominator", r["review_population_eligible"] is False)

for r in load("evidence-receipts.json")["raw_assets"]:
    b = (ROOT / "captures" / Path(r["local_file"]).name).read_bytes()
    check("capture:" + r["local_file"], len(b) == r["bytes"] and sha(b) == r["sha256"])

for r in load("reuse-pins.json")["files"]:
    b = (ROOT / "reuse" / r["path"]).read_bytes()
    check("reused_pin:" + r["path"], len(b) == r["bytes"] and sha(b) == r["sha256"])

for r in data["manuals"]:
    check(r["source_id"] + ":shared_scope_retained", r["exact_model_name_in_native_text"] is False)
check("date_candidate_count", len(dates["rows"]) == 7)
check("date_stages", dates["visible_original_blog_post_dates"] == 1
      and dates["native_product_metadata_date_candidates"] == 6)
check("time_denominators_remain_zero", dates["original238_approved_time_denominator"] == 0
      and dates["existing141_approved_time_denominator"] == 0
      and dates["approved_new_time_denominator"] == 0)
comp = load("competitor-output-intake.json")
check("no_competitor_output_inferred", not comp["actual_planning_output_received"]
      and comp["actual_output_sha256"] is None and not comp["new_model_run_requested"]
      and all(x["actual_output_value"] is None for x in comp["matrix"]))
result = {"audit_scope": "new intake and hashes only; old238/141 audits and model/OCR not rerun",
          "checks": checks, "passed": sum(x["pass"] for x in checks),
          "failed": sum(not x["pass"] for x in checks), "overlap": overlap,
          "limits": ["Exact normalized non-overlap is not semantic independence.",
                     "Visible blog date and native datePublished metadata are separate approval stages.",
                     "Manual visual/table review is separate from byte checks.",
                     "No runtime import, receiver ACK, PM approval or actual comparison output verified."]}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "failed": result["failed"]}))
raise SystemExit(bool(result["failed"]))
