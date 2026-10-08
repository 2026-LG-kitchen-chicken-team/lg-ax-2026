"""Audit only six newly resolved IDs/date semantics against pinned prior evidence.

Run with stdlib Python in the recorded network-none, zero-auth container.
Inputs are explicitly copied public captures and immutable prior indexes.
No production code, Git checkout, network, model, OCR, or prior full audit runs.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


class Node:
    def __init__(self, tag="root", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def classes(self):
        return set(self.attrs.get("class", "").split())


class PublicHTML(HTMLParser):
    void = set("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag == "br":
            node.children.append("\n")
        if tag not in self.void:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    inp, out = args.input, args.output
    checks = []

    def check(name, condition, detail=None):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    def load(name):
        return json.loads((inp / name).read_text(encoding="utf-8"))

    def save(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pins = load("evidence-pins.json")
    for p in pins["files"]:
        data = (inp / p["file"]).read_bytes()
        check("pin:" + p["file"], len(data) == p["bytes"] and sha(data) == p["sha256"])

    prior = load("prior-sources.sidecar.json")
    dates = load("prior-date-candidates.json")
    membership = load("d1-membership.json")
    old_ids = {str(r["original_review_id"]) for r in membership}
    old_hashes = {r["normalized_body_sha256"] for r in membership}
    r9 = load("r9-original-sources.json")["sources"]
    r9_by_id = {r.get("source_id", r.get("id")): r for r in r9}
    check("prior_238_index_count_only_no_reaudit", len(membership) == 238)
    expected = {
        "ML32WW1": ("oven-list.html", "MD08044721", ["184196", "50141", "840090"]),
        "Z330MEEF11": ("kimchi-list.html", "MD10545829", ["844576", "808362", "808186"]),
    }
    rows = []
    for model, (file, md, native_ids) in expected.items():
        tree = PublicHTML((inp / file).read_text(encoding="utf-8")).root
        containers = [n for n in tree.walk() if n.attrs.get("id") == "divReviewList"]
        check(model + ":one_review_list", len(containers) == 1)
        if len(containers) != 1:
            continue
        for index, rid in enumerate(native_ids, 1):
            hits = [n for n in containers[0].walk() if n.tag == "li" and n.attrs.get("data-review-id") == rid]
            check(rid + ":one_original_id", len(hits) == 1)
            if len(hits) != 1:
                continue
            row = hits[0]
            message = [n for n in row.walk() if "message" in n.classes()]
            purchase = [n for n in row.walk() if "purchase-date" in n.classes()]
            check(rid + ":message_and_date_fields", len(message) == len(purchase) == 1)
            if len(message) != 1 or len(purchase) != 1:
                continue
            body = message[0].text().strip()
            date_text = normalized(purchase[0].text())
            found = re.findall(r"\d{4}\.\d{2}\.\d{2}", date_text)
            check(rid + ":purchase_label_and_one_date", "구매 일자" in date_text and len(found) == 1)
            if len(found) != 1:
                continue
            date = found[0].replace(".", "-")
            sid = f"LGE-EXPANSION-{model}-PREVIEW-{index:02d}"
            previous = next(r for r in prior["reviews"] if r["source_id"] == sid)
            prev_date = next(r for r in dates["rows"] if r["source_id"] == sid)
            nsha = sha(normalized(body).encode("utf-8"))
            check(rid + ":listing_model_association", row.attrs.get("data-model-id") == md)
            check(rid + ":body_matches_pinned_preview", nsha == previous["normalized_body_sha256"])
            check(rid + ":metadata_equals_purchase_not_posting", date == previous["declared_datePublished"] == prev_date["site_declared_datePublished"])
            check(rid + ":prior_unknowns_not_silently_promoted", previous["published_at"] is None and previous["purchased_model_id"] is None and previous["split"] == "unassigned")
            check(rid + ":not_existing_238_by_id_or_normalized_body", rid not in old_ids and nsha not in old_hashes)
            existing = previous.get("existing_r9_source_id")
            if existing:
                old = r9_by_id.get(existing)
                # R9 uses canonical Source.content; no patching its source ID or bytes.
                check(rid + ":existing_R9_alias_preserved", old is not None)
                if old:
                    old_body = old.get("content", old.get("text", ""))
                    check(rid + ":same_R9_body", sha(normalized(old_body).encode("utf-8")) == nsha)
            options = [normalized(n.text()) for n in row.walk() if "option-list" in n.classes()]
            rows.append({
                "source_id_alias": sid,
                "existing_r9_source_id_alias": existing,
                "original_review_id": rid,
                "listing_model_id": md,
                "page_model": model,
                "listing_url": next(p["url"] for p in pins["files"] if p["file"] == file),
                "body_sha256_with_lf_breaks": sha(body.encode("utf-8")),
                "body_length_with_lf_breaks": len(body),
                "normalized_body_sha256": nsha,
                "normalization": "NFKC + whitespace collapse; HTMLParser entity decoding once; br to LF",
                "prior_preview_body_sha256": previous["body_sha256"],
                "purchase_date_display_label": "구매 일자",
                "displayed_purchase_date": date,
                "prior_site_declared_datePublished": prev_date["site_declared_datePublished"],
                "posting_date_evidence_status": "rejected_purchase_date_label",
                "published_at": None,
                "first_published_at": None,
                "actual_purchased_model_id": None,
                "model_binding": "public listing row data-model-id; no independent buyer SKU proof",
                "purchase_option_display": options,
                "split": previous["split"],
                "model_input_approved": False,
                "topic_approved": False,
                "trend_approved": False,
                "approved_time_denominator_contribution": 0,
                "coverage": "rendered list .message matches prior preview; attached media not inspected; publication time not shown in captured row",
                "capture_sha256": next(p["sha256"] for p in pins["files"] if p["file"] == file),
            })

    check("six_unique_original_ids", len(rows) == len({r["original_review_id"] for r in rows}) == 6)
    check("six_rejected_publication_candidates", all(r["posting_date_evidence_status"] == "rejected_purchase_date_label" for r in rows) and len(rows) == 6)
    check("original_and_new_time_denominators_unchanged", dates["original238_approved_time_denominator"] == dates["existing141_approved_time_denominator"] == dates["approved_new_time_denominator"] == sum(r["approved_time_denominator_contribution"] for r in rows) == 0)
    model_scope = load("model-scope-observation.json")
    manual = load("kimchi-manual-text.json")
    check("kimchi_pdf_is_prior_fixed_revision", sha((inp / "kimchi-manual.pdf").read_bytes()) == "594b38d6cedfeb2607651c078f031157e5f3d6d5a0fc72d40b4ed0da941ea14a")
    check("common_manual_scope_caveat", "공용" in manual[1] and "모델" in manual[10])
    check("manual_conditional_basket", "일부 모델에는 내부 바스켓이 없습니다" in normalized(manual[19]))
    check("manual_conditional_cover", "모델에 따라 상칸 냉기 단속 커버가 없는" in normalized(manual[18]))
    check("manual_upper_shelf_cleaning_limit", "청소 이외의 용도로는 상칸 아래 선반을 분리하여" in normalized(manual[18]))
    check("manual_sensor_condition_preserved", "조도 센서" in manual[25] and "적용" in manual[25])
    check("manual_dimensions_agree_with_observed_dom", model_scope["facts"]["size_w_h_d_mm"] == [666, 1787, 737] and all(str(n) in manual[25] for n in [666, 1787, 737]))
    check("sku_purchase_not_promoted_by_spec_read", not model_scope["purchased_review_sku_proven"] and all(r["actual_purchased_model_id"] is None for r in rows))
    save("identity-date-delta.json", {
        "version": "review-identity-date-delta.20261008.01a11628-c73f9a.v1",
        "corrects": {"pr": 276, "head": "913036481a01028959220f267b841a8338fbc895", "scope": "six metadata-only posting date candidates; prior canonical dates were null"},
        "canonical_source_files_modified": False,
        "new_reviews_added": 0,
        "existing_review_identities_resolved": len(rows),
        "rows": rows,
        "counts": {"resolved_original_ids": len(rows), "rejected_posting_date_candidates": 6, "new_confirmed_posting_dates": 0, "previous_blog_display_date_candidates_reused": 1, "original238_time_denominator": 0, "development141_time_denominator": 0, "new_approved_time_denominator": 0},
        "acceptance": "DATA delta self-audit; PM policy/cohort approval and receiver acknowledgement still pending",
    })
    passed = sum(c["passed"] for c in checks)
    result = {
        "audit": "six ID/date delta plus limited manual applicability checks",
        "checks_passed": passed, "checks_failed": len(checks) - passed, "checks": checks,
        "old_audits_rerun": False, "model_calls": 0, "ocr_calls": 0,
        "limitations": ["Capture/normalization checks do not authenticate purchase SKU or publication date.", "DOM facts and PDF visual meaning were reviewed separately; static assertions do not prove UI or operating success.", "No CORE/WEB receipt, real fridge planning output, topic/date/cohort approval, or PM acceptance is inferred.", "No media analysis, production metadata updates, or new independent evaluation cohort."],
    }
    save("audit-result.json", result)
    print(json.dumps({"passed": passed, "failed": len(checks) - passed, "failed_checks": [c["check"] for c in checks if not c["passed"]], "rows": len(rows)}))
    raise SystemExit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
