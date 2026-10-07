"""Offline landing for bounded official product-page review HTML.

The page model is an association, never proof of the purchased SKU. Purchase
dates are separate from publication dates. This module makes no network or
model calls and never evaluates source HTML, JavaScript or spreadsheet cells.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_REVIEWS_PER_MODEL = 100
SPLIT_VERSION = "r5-public-group-split.20261007.v1"


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)

    def find(self, *, ident=None, css=None):
        if (ident is not None and self.attrs.get("id") == ident
                or css is not None and css in self.attrs.get("class", "").split()):
            return self
        for child in self.children:
            if isinstance(child, _Node):
                found = child.find(ident=ident, css=css)
                if found:
                    return found
        return None

    def text(self):
        if self.tag in {"script", "style"}:
            return ""
        if self.tag == "br":
            return "\n"
        return "".join(child.text() if isinstance(child, _Node) else child
                       for child in self.children)


class _PublicHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _date(node):
    if node is None:
        return None
    match = re.search(r"(?<!\d)(20\d\d)[.-](\d{2})[.-](\d{2})(?!\d)", node.text())
    if not match:
        return None
    from datetime import date
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def _redact(text):
    # Author names, household demographics and media are never extracted.
    # Explicit contact details appearing inside a review are removed as well.
    patterns = (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
                r"(?<!\d)(?:0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)")
    reasons = []
    for pattern in patterns:
        text, count = re.subn(pattern, "[개인정보 제외]", text)
        if count:
            reasons.append("contact_detail")
    return text, reasons


def parse_public_review_html(raw: bytes, *, product: dict, source: dict,
                             limit: int = MAX_REVIEWS_PER_MODEL) -> list[dict]:
    """Only list rows, with explicit unknown purchased SKU and posting date."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_HTML_BYTES:
        raise ValueError("Invalid public HTML byte limit")
    if type(limit) is not int or not 1 <= limit <= MAX_REVIEWS_PER_MODEL:
        raise ValueError("Review limit must be 1..100")
    if sha256(raw) != source["sha256"]:
        raise ValueError("Public capture hash mismatch")
    if product["source_kind"] != "public":
        raise ValueError("Public product scope required")
    parser = _PublicHTML()
    parser.feed(raw.decode("utf-8", errors="strict"))
    listing = parser.root.find(ident="divReviewList")
    if listing is None:
        raise ValueError("Normal public review list absent; no fallback or bypass")
    rows = []
    for node in listing.children:
        if not isinstance(node, _Node) or node.tag != "li":
            continue
        rid, md = node.attrs.get("data-review-id"), node.attrs.get("data-model-id")
        message = node.find(css="message")
        if not rid or not re.fullmatch(r"[0-9]{1,20}", rid) or not md or message is None:
            raise ValueError("Public row is missing its original ID/model/message")
        body = message.text().strip()
        if not body:
            raise ValueError("Empty review body")
        cleaned, redactions = _redact(body)
        flags = []
        if md != product["lge_model_id"]:
            flags.append("review_list_model_differs")
        if (product["product_group"] == "dishwasher"
                and re.search(r"(?:화력|하이라이트|불조절|가스레인지)", body)
                and not re.search(r"(?:식세기|식기세척|설거지|세척)", body)):
            flags.append("other_product_category_text")
        purchase_date = _date(node.find(css="purchase-date"))
        rating_node = node.find(css="star-wrap")
        rating_match = re.search(r"5점 중\s*([1-5])점", rating_node.text()) if rating_node else None
        rows.append({
            "original_review_id": rid,
            "review_id": "LGE-R5-REVIEW-" + rid,
            "displayed_model_id": product["model_id"],
            "review_list_model_id": md,
            "actual_purchased_model_id": None,
            "sku_binding": "official_product_review_page_only",
            "text": cleaned,
            "original_text_sha256": sha256(body.encode("utf-8")),
            "text_sha256": sha256(cleaned.encode("utf-8")),
            "redactions": redactions,
            "rating": int(rating_match.group(1)) if rating_match else None,
            "purchase_date": purchase_date,
            "purchase_date_precision": "day" if purchase_date else "unknown",
            "published_at": None,
            "published_date_precision": "unknown",
            "date_basis": "visible_purchase_date_is_not_publication_date",
            "source_kind": "public",
            "source_url": source["source_url"],
            "source_sha256": source["sha256"],
            "source_locator": '#divReviewList > li[data-review-id="' + rid + '"] .message',
            "collected_at": source["captured_at"],
            "manual_version": product.get("manual_version"),
            "document_version": product["document_version"],
            "manual_time_alignment": "current_reference_only_not_purchase_time_verified",
            "quality_flags": flags,
            "eligible_for_model_input": False,
            "input_hold_reasons": ["purchased_sku_not_independently_verified"],
            "quarantined": bool(flags or redactions),
        })
        if len(rows) >= limit:
            break
    if not rows:
        raise ValueError("No normal public review rows; stop without fabricated data")
    return rows


def group_and_split(records: list[dict]) -> tuple[list[dict], dict]:
    """Global original-ID dedup before fixed, indivisible group assignment.

    Different IDs with the same long normalized text and purchase date keep
    their original records but share a split, preventing repost leakage.
    Generic short positive texts are not collapsed into a single customer.
    """
    by_id = {}
    duplicates = []
    for record in records:
        rid = record["original_review_id"]
        prior = by_id.get(rid)
        if prior:
            if prior["text_sha256"] != record["text_sha256"]:
                raise ValueError("Same original review ID has conflicting text; manual review required")
            prior["page_associations"].append({"model_id": record["displayed_model_id"],
                                                "source_url": record["source_url"],
                                                "source_sha256": record["source_sha256"]})
            duplicates.append({"original_review_id": rid,
                               "additional_display_model": record["displayed_model_id"]})
        else:
            detached = json.loads(json.dumps(record))
            detached["page_associations"] = [{"model_id": record["displayed_model_id"],
                                               "source_url": record["source_url"],
                                               "source_sha256": record["source_sha256"]}]
            by_id[rid] = detached
    rows = list(by_id.values())
    text_groups = {}
    for record in rows:
        normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", record["text"])).strip()
        if len(normalized) >= 40:
            key = sha256((normalized + "\n" + str(record["purchase_date"])).encode())
            text_groups.setdefault(key, []).append(record["original_review_id"])
    group_of = {rid: rid for rid in by_id}
    for ids in text_groups.values():
        group = min(ids)
        for rid in ids:
            group_of[rid] = group
    counts = {name: 0 for name in ("development", "independent_evaluation", "demonstration", "quarantine")}
    for record in rows:
        group = "LGE-R5-GROUP-" + group_of[record["original_review_id"]]
        slot = int(sha256((SPLIT_VERSION + "\n" + group).encode()), 16) % 100
        split = "development" if slot < 60 else "independent_evaluation" if slot < 80 else "demonstration"
        if record["quarantined"]:
            split = "quarantine"
        record.update(dedup_group_id=group, split=split, split_version=SPLIT_VERSION)
        counts[split] += 1
    # Any quarantined duplicate group stays wholly quarantined.
    blocked = {record["dedup_group_id"] for record in rows if record["split"] == "quarantine"}
    for record in rows:
        if record["dedup_group_id"] in blocked and record["split"] != "quarantine":
            counts[record["split"]] -= 1
            counts["quarantine"] += 1
            record["split"] = "quarantine"
            record["eligible_for_model_input"] = False
            record["quality_flags"].append("quarantined_related_review")
    return rows, {"captured_page_rows": len(records), "unique_original_ids": len(rows),
                  "duplicate_page_rows": duplicates, "split_counts": counts,
                  "assignment": "sha256(group+fixed_version)%100; 60/20/20 targets, not forced counts",
                  "group_intersection_count": 0,
                  "split_version": SPLIT_VERSION}


def save_landing_db(path: Path, *, records: list[dict], products: list[dict], manifest: dict):
    """A fresh SQLite landing with all record metadata, separate from app DB."""
    if path.exists():
        raise ValueError("Immutable landing DB already exists")
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE products (model_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL);
            CREATE TABLE reviews (original_review_id TEXT PRIMARY KEY, dedup_group_id TEXT NOT NULL,
                split TEXT NOT NULL, displayed_model_id TEXT NOT NULL, actual_purchased_model_id TEXT,
                published_at TEXT, purchase_date TEXT, text TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE manifest (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE INDEX review_split ON reviews(split, displayed_model_id);
        """)
        db.executemany("INSERT INTO products VALUES (?, ?)",
                       [(p["model_id"], json.dumps(p, ensure_ascii=False, sort_keys=True)) for p in products])
        db.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       [(r["original_review_id"], r["dedup_group_id"], r["split"], r["displayed_model_id"],
                         r["actual_purchased_model_id"], r["published_at"], r["purchase_date"], r["text"],
                         json.dumps(r, ensure_ascii=False, sort_keys=True)) for r in records])
        db.execute("INSERT INTO manifest VALUES (?, ?)", ("collection", json.dumps(manifest, ensure_ascii=False, sort_keys=True)))
