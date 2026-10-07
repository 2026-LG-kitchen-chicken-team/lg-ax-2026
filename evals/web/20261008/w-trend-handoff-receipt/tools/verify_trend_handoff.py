"""WEB read-receipt check of the DATA #16/#148 trend handoff (record 최길웅-20261008-064). Read-only, no model.

Reads the handoff files at PR #258 head and the source commit they name, and checks, independently of web code:
file SHA-256 and annotation_version, draft/not-approved status, 141 development IDs and their product-group split,
that every source object equals the original object at the source commit (bundles/*.development.research-bundle.json),
that every quote equals the source text at its text_range and its quote_sha256, that topic IDs exist in the taxonomy,
counter-example pairs point at rows, no excluded (evaluation/demonstration/quarantine) ID is present, and dates/SKUs stay null.
Usage: python verify_trend_handoff.py <repo> <handoff_commit> <source_commit> > receipt.json"""
import hashlib
import json
import subprocess
import sys
from collections import Counter

repo, handoff, source_commit = sys.argv[1:4]
BASE = "data/research/r8-public-research-20261007"
D = f"{BASE}/trend-annotations/01a114f6"


def show(commit, path):
    return subprocess.run(["git", "-C", repo, "show", f"{commit}:{path}"], capture_output=True, check=True).stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


ann_raw, src_raw = show(handoff, f"{D}/annotation.draft.json"), show(handoff, f"{D}/development-sources.json")
ann, src = json.loads(ann_raw), json.loads(src_raw)
checks, problems = {}, []
checks["annotation_sha256"] = sha(ann_raw)
checks["sources_sha256"] = sha(src_raw)
checks["annotation_version_same"] = ann["annotation_version"] == src["annotation_version"]
checks["annotation_version"] = ann["annotation_version"]
checks["draft_not_approved_not_gold"] = ann["status"] == "draft" and ann["pm_approved"] is False and ann["gold"] is False \
    and all(row["status"] == "draft" and row["approved"] is False for row in ann["rows"])
checks["source_commit_declared"] = src["source_commit"]

sources = {s["source_id"]: s for s in src["sources"]}
rows = {row["source_id"]: row for row in ann["rows"]}
checks["rows"], checks["sources"] = len(ann["rows"]), len(src["sources"])
checks["ids_unique_and_equal"] = len(rows) == len(ann["rows"]) and len(sources) == len(src["sources"]) and set(rows) == set(sources)
checks["product_groups"] = dict(Counter(row["product_group"] for row in ann["rows"]))
checks["overall_opinion"] = dict(Counter(row["overall_opinion"] for row in ann["rows"]))

# Original objects at the declared source commit.
original = {}
for group in ("fridge", "dishwasher", "microwave"):
    bundle = json.loads(show(source_commit, f"{BASE}/bundles/{group}.development.research-bundle.json"))
    for item in bundle["sources"]:
        if item["source_type"] == "review":
            original[item["source_id"]] = item
checks["original_development_reviews_at_source_commit"] = len(original)
mismatched = [sid for sid, item in sources.items() if original.get(sid) != item]
checks["sources_equal_original_objects"] = not mismatched
problems += [f"source differs from original: {sid}" for sid in mismatched[:10]]
checks["set_equals_original_development_reviews"] = set(sources) == set(original)

# Quotes against source text.
quotes = bad_quotes = 0
taxonomy = {topic["topic_id"] for topic in ann["taxonomy"]}
unknown_topics = set()
for sid, row in rows.items():
    text = sources[sid]["text"]
    unknown_topics |= set(row["topic_ids"]) - taxonomy
    for aspect in row["aspects"]:
        unknown_topics |= {aspect["topic_id"]} - taxonomy
        quotes += 1
        r = aspect["text_range"]
        span = text[r["start"]:r["end"]]
        if span != aspect["quote"] or sha(aspect["quote"].encode("utf-8")) != aspect["quote_sha256"]:
            bad_quotes += 1
            if bad_quotes <= 10:
                problems.append(f"quote mismatch {sid} {r} {aspect['quote'][:20]!r}")
checks["quotes"], checks["quotes_mismatched"] = quotes, bad_quotes
checks["unknown_topic_ids"] = sorted(unknown_topics)
checks["taxonomy_topics"] = len(taxonomy)

pairs = ann["counterexample_pairs"]
by_original = {row["original_review_id"] for row in ann["rows"]}
checks["counterexample_pairs"] = len(pairs)
checks["counterexample_ids_in_rows"] = all(rid in by_original for pair in pairs for rid in pair["original_review_ids"])
checks["counterexample_no_causal_claim"] = all(pair["causal_or_same_sku_conclusion"] is False for pair in pairs)

# Excluded splits must not be present (split recorded in the original object's metadata).
splits = Counter(item.get("metadata", {}).get("split") for item in sources.values())
checks["splits_in_handoff"] = dict(splits)
checks["dates_and_skus_null"] = all(row["published_at"] is None and row["actual_purchased_model_id"] is None for row in ann["rows"]) \
    and all(item["published_at"] is None and item["purchased_model"] is None for item in sources.values())
checks["problems"] = problems
json.dump({"kind": "web_read_receipt_trend_handoff", "handoff_commit": handoff, "source_commit": source_commit, "model_calls": 0, "checks": checks},
          sys.stdout, ensure_ascii=False, indent=1)
print()
