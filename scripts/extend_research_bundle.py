"""Append frozen public official/Q&A excerpts to R8 bundles without recollection."""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("data/research/r8-public-research-20261007")
PACK = Path("data/research/r8-public-official-expansion-20261007")
VERSION = "r8-public-official-expansion.20261007.v1"
BASE_INDEX_SHA256 = "345e8bfcd186ac556369b393fefad53eb0494b0373712894bf0dd67205b7c249"
CAPTURE_SHA256 = "b8bc2f3e2bcac4d41d1fc7119ae91f9c3383ee10b0274f3fd1c2deed6977622c"
PUBLIC_OFFICIAL_HOSTS = {"www.lge.co.kr", "www.samsungsvc.co.kr"}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def pinned_bytes(path, expected):
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise ValueError(f"Pinned source changed: {path.name}")
    return raw


def load_sources(root=ROOT):
    raw = pinned_bytes(root / PACK / "captured-sources.json", CAPTURE_SHA256)
    sources = json.loads(raw)
    ids = set()
    for source in sources:
        if source["source_id"] in ids:
            raise ValueError("Duplicate expansion source ID")
        ids.add(source["source_id"])
        parsed = urlsplit(source["url"])
        if parsed.scheme != "https" or parsed.hostname not in PUBLIC_OFFICIAL_HOSTS:
            raise ValueError("Expansion capture must use a public official HTTPS page")
        if source["source_kind"] != "public" or source["purchased_model"] is not None:
            raise ValueError("Expansion capture has invalid public/model provenance")
        metadata = source["metadata"]
        metadata["excerpt_sha256"] = sha256(source["text"].encode("utf-8"))
        metadata["hash_scope"] = "exact_UTF8_text_field_only_not_full_HTML_or_entire_document"
        metadata["collector"] = "current_chat_manual_support"
        if source["source_type"] == "qa":
            if metadata["usage_problem_sample_eligible"] is not False:
                raise ValueError("Purchase Q&A is not a usage-problem sample")
            if source["source_role"] not in {"customer_question", "official_answer"}:
                raise ValueError("Public Q&A question/answer roles must remain separate")
        elif source["published_at"] is not None or source["date_kind"] != "unknown":
            raise ValueError("Unlabelled official article date is not a confirmed posting date")
    by_id = {source["source_id"]: source for source in sources}
    for source in sources:
        if source["source_type"] != "qa":
            continue
        other = by_id[source["metadata"]["paired_source_id"]]
        if (other["metadata"]["qa_pair_id"] != source["metadata"]["qa_pair_id"]
                or other["url"] != source["url"] or other["source_role"] == source["source_role"]):
            raise ValueError("Public Q&A pair provenance mismatch")
    return raw, sources


def build_expansion(root=ROOT, output=None):
    output = output or root / PACK
    base_path = (root / BASE).resolve()
    capture_path = (root / PACK / "captured-sources.json").resolve()
    if output.resolve() == base_path or base_path in output.resolve().parents:
        raise ValueError("Frozen R8 baseline cannot be used as output")
    if output.resolve() == capture_path:
        raise ValueError("Frozen capture file cannot be used as output")
    index_raw = pinned_bytes(root / BASE / "files.json", BASE_INDEX_SHA256)
    base_pins = json.loads(index_raw)
    baseline = {name: json.loads(pinned_bytes(root / BASE / name, digest))
                for name, digest in base_pins.items()}
    capture_raw, sources = load_sources(root)
    base_source_ids = {source["source_id"] for name, bundle in baseline.items()
                       if name.startswith("bundles/") for source in bundle["sources"]}
    if base_source_ids & {source["source_id"] for source in sources}:
        raise ValueError("Expansion must not replace a baseline source")
    artifacts = {"captured-sources.json": json.loads(capture_raw), "sources.json": sources}
    bundle_counts = {}
    for name, original in baseline.items():
        if not name.startswith("bundles/"):
            continue
        bundle = deepcopy(original)
        group = bundle["product_group"]
        additions = [source for source in sources if source["product_group"] == group]
        bundle["bundle_id"] = f"LGE-R8-{group}-development-20261007-official-v1"
        bundle["sources"].extend(additions)
        manifest = bundle["collection_manifest"]
        manifest["dataset_version"] = VERSION
        manifest["baseline_bundle_id"] = original["bundle_id"]
        manifest["baseline_bundle_sha256"] = base_pins[name]
        manifest["baseline_review_and_source_fields_preserved"] = True
        manifest["source_type_counts"] = dict(Counter(s["source_type"] for s in bundle["sources"]))
        manifest["additional_context_page_models"] = sorted({s["page_model"] for s in additions
                                                            if s["page_model"]})
        manifest["new_source_ids"] = [source["source_id"] for source in additions]
        manifest["confirmed_customer_qa_question_count"] = sum(
            s["source_type"] == "qa" and s["source_role"] == "customer_question" for s in additions)
        manifest["confirmed_customer_qa_usage_problem_count"] = 0
        manifest["limitations"] += [
            "New official article dates are visible document dates, not confirmed first-posting dates.",
            "Shared official guidance is comparison context, not an exact-SKU performance test or proof of resolved burden.",
            "MW25S Q&A is a purchase/stock inquiry, not a product-usage customer experience sample.",
        ]
        if any(s["source_type"] == "qa" for s in additions):
            manifest["missing_source_types"] = [{"source_type": "qa_usage_problem",
                "status": "not_captured", "verified_text_count": 0,
                "reason": "Only one public purchase inquiry and its official answer were verified."}]
        validate_research_bundle(bundle)
        artifacts[name] = bundle
        bundle_counts[group] = manifest["source_type_counts"]
    manifest = {
        "artifact_kind": "public_official_context_expansion", "dataset_version": VERSION,
        "manual_support_author": "current_chat_manual_support", "collection_mode": "manual_public_read_only",
        "capture_finished_at": "2026-10-07T12:42:02Z",
        "new_page_count": len({s["url"] for s in sources}), "new_source_count": len(sources),
        "new_source_type_counts": dict(Counter(s["source_type"] for s in sources)),
        "confirmed_customer_qa_question_count": 1, "confirmed_official_qa_answer_count": 1,
        "confirmed_customer_qa_usage_problem_count": 0,
        "corpus_review_count": 238, "development_review_count": 141,
        "original_split_counts": baseline["manifest.json"]["split_counts"],
        "registered_product_page_models": 18, "additional_context_page_models": ["MW25S"],
        "baseline_index_sha256": BASE_INDEX_SHA256, "baseline_file_pins": base_pins,
        "capture_input_sha256": CAPTURE_SHA256, "bundle_source_type_counts": bundle_counts,
        "comparison_context_groups": [
            {"topic": "drying_material_conditions", "source_ids": [
                "LGE-FAQ-20151571626779-drying-conditions", "SAMSUNG-FAQ-1085788-plastic-drying"],
             "scope": "Both are product-group guidance; not a same-condition comparative experiment."},
            {"topic": "dish_loading", "source_ids": [
                "LGE-FAQ-20151678633118-loading", "SAMSUNG-FAQ-4227974-cup-placement"],
             "scope": "Official placement guidance may inform a hypothesis; customer usability is unmeasured."},
        ],
        "limitations": [
            "No new reviews, synthetic reviews or market prevalence estimates were added.",
            "Customer Q&A contains one purchase inquiry. No product-usage Q&A was captured.",
            "All new excerpts are partial references with excerpt-only hashes; they are not complete manuals.",
            "No SKU, review posting date, customer defect cause or comparative performance was inferred.",
            "Availability answer is historical to its posting date, not a live inventory or future-sale commitment.",
            "Existing review splits, holds, original source fields and the 18-model registry remain frozen.",
        ],
        "synthetic_review_count": 0, "build_network_requests": 0, "model_calls": 0,
        "operating_db_changed": False, "automation_changed": False,
    }
    artifacts["manifest.json"] = manifest
    # Validate and verify every immutable input before writing new derived files.
    hashes = {}
    for name, value in artifacts.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the frozen capture byte-for-byte, including its original formatting.
        raw = capture_raw if name == "captured-sources.json" else json_bytes(value)
        if destination.resolve() == capture_path and destination.read_bytes() == raw:
            pass
        else:
            destination.write_bytes(raw)
        hashes[name] = sha256(raw)
    (output / "files.json").write_bytes(json_bytes(hashes))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / PACK)
    args = parser.parse_args()
    result = build_expansion(output=args.output)
    print(json.dumps({"output": str(args.output), "new_sources": result["new_source_count"],
                      "new_pages": result["new_page_count"], "customer_qa_questions": 1,
                      "usage_problem_qa": 0, "reviews": 238, "network_requests": 0, "model_calls": 0}))


if __name__ == "__main__":
    main()
