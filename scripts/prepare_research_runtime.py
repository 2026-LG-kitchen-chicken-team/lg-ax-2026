"""Prepare three frozen public research inputs; correct only five care-page relations."""

import argparse
import json
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
INPUT_BASE = Path("data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input")
OUTPUT = Path("data/research/r9-public-runtime-20261008")
GROUPS = ("fridge", "microwave", "dishwasher")
SOURCE_COMMIT = "94b560de72f91795cfd50aada9e17d6773383ae1"
INPUT_SHA256 = {
    "fridge": "75423a9844a468ad5e64e9086e43b68649335faf0c7c68b82f3a949ebf6bf4dc",
    "microwave": "457461ebd8cf13a1be6b171ed1a80802d33ed3b5714118179afef11ce1b87a5d",
    "dishwasher": "e922c51dd7f1f805953fd8e4df4ea1a75479ad8da0e2ba500b541acd720e84d0",
}
CORRECTIONS = {
    "D2-DUE-CARE-DW-INTERNAL-CLEAN-P39": ([40], [], "Page 40 continues food-filter cleaning, not internal cleaning."),
    "D2-DUE-CARE-DW-TUB-CITRIC-P41": ([42], [], "Citric-acid steps finish on page 41; page 42 continues vinegar."),
    "D2-DUE-CARE-DW-TUB-VINEGAR-P42": ([41, 43], [41], "Page 41 contains vinegar step 1; page 43 is nozzle/storage."),
    "D2-DUE-CARE-DW-NOZZLE-P42": ([41, 43], [43], "Page 43 continues nozzle cleaning; page 41 is tub cleaning."),
    "D2-DUE-CARE-DW-STORAGE-P43": ([42], [], "Storage is complete on page 43; page 42 is a different section."),
}
AUDIT_REFERENCES = [
    {
        "path": "evals/data-remaining-intake/20261008-01a1100e/care-source-bridge.csv",
        "sha256": "22e11a49d74e46a550c392fe5ceaf71702a9c0a2f20dd870d4e221a57faca661",
        "commit": "9516caa27f05330830aa91d725d4bd8902bf4d9e",
        "pull_request": 259,
    },
    {
        "path": "evals/data-dish-manual-audit/20261007-01a1100e/manual-native-excerpts.json",
        "sha256": "975b562d2c3c1f86fcc66efad0915c3ed8b4defd4e872c1dea32c41dd6c032c0",
        "commit": "78a1906369479eb2336cecc3a134895a814f95b1",
        "pull_request": 252,
    },
]


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def prepare_runtime_inputs(source_paths: Mapping[str, Path], output_dir: Path):
    """Return the handoff manifest after writing a separate, reproducible three-bundle edition."""
    if set(source_paths) != set(GROUPS):
        raise ValueError("Exactly fridge, microwave and dishwasher inputs are required")
    payloads = {}
    entries = {}
    corrections = []
    for group in GROUPS:
        source_path = Path(source_paths[group])
        raw = source_path.read_bytes()
        if sha256(raw).hexdigest() != INPUT_SHA256[group]:
            raise ValueError(f"Frozen {group} input hash changed")
        original = json.loads(raw)
        validate_research_bundle(original)
        if original["product_group"] != group or original["analysis_scope"] != "product_group":
            raise ValueError(f"Unexpected {group} analysis scope")
        prepared = deepcopy(original)
        prepared["bundle_id"] = f"LGE-R9-{group}-development-20261008-v1"
        if group == "dishwasher":
            sources = {source["source_id"]: source for source in prepared["sources"]}
            for source_id, (before, after, reason) in CORRECTIONS.items():
                source = sources[source_id]
                if source["metadata"]["continuation_pages"] != before:
                    raise ValueError(f"Frozen relation changed: {source_id}")
                source["metadata"]["continuation_pages"] = list(after)
                corrections.append({
                    "source_id": source_id,
                    "field": "metadata.continuation_pages",
                    "old_value": before,
                    "new_value": after,
                    "reason": reason,
                    "original_locator": deepcopy(source["locator"]),
                    "original_text_sha256": source["metadata"]["text_sha256"],
                    "original_pdf_sha256": source["metadata"]["pdf_sha256"],
                })
        validate_research_bundle(prepared)
        restored = deepcopy(prepared)
        restored["bundle_id"] = original["bundle_id"]
        if group == "dishwasher":
            for source in restored["sources"]:
                if source["source_id"] in CORRECTIONS:
                    source["metadata"]["continuation_pages"] = list(CORRECTIONS[source["source_id"]][0])
        if restored != original:
            raise ValueError(f"Unexpected change outside permitted {group} metadata")
        filename = f"{group}.research-bundle.json"
        output_raw = json_bytes(prepared)
        payloads[filename] = output_raw
        review_sources = [source for source in prepared["sources"] if source["source_type"] == "review"]
        entries[group] = {
            "input_path": str(INPUT_BASE / group / "research-bundle.json").replace("\\", "/"),
            "input_sha256": sha256(raw).hexdigest(),
            "input_bundle_id": original["bundle_id"],
            "output_path": filename,
            "output_sha256": sha256(output_raw).hexdigest(),
            "output_bundle_id": prepared["bundle_id"],
            "source_count": len(prepared["sources"]),
            "development_review_count": len(review_sources),
            "schema_valid": True,
            "permitted_diff_only": True,
        }
    manifest = {
        "version": "r9-public-runtime.20261008.v1",
        "producer": "scripts/prepare_research_runtime.py",
        "source_commit": SOURCE_COMMIT,
        "source_pull_request": 254,
        "groups": entries,
        "metadata_corrections": corrections,
        "continuation_pages_semantics": "Other pages continuing the same procedure/section, not nearby care sections",
        "audit_references": deepcopy(AUDIT_REFERENCES),
        "source_text_facts_locators_ids_and_other_metadata_preserved": True,
        "original_input_bytes_preserved": True,
        "development_reviews_preserved": 141,
        "review_publication_dates_and_purchased_skus_unchanged": True,
        "independent_evaluation_and_demonstration_not_added": True,
        "runtime_registered": False,
        "model_calls": 0,
        "network_calls": 0,
        "semantic_quality_verified": False,
        "implementation_provenance": "Current chat manual support implementation; not an owner's direct execution record",
    }
    payloads["manifest.json"] = json_bytes(manifest)
    output_dir = Path(output_dir)
    # Check all destinations before writing: preserve any existing edition with different contents.
    for name, raw in payloads.items():
        destination = output_dir / name
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError(f"Preserve prior output: {name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in payloads.items():
        destination = output_dir / name
        if not destination.exists():
            destination.write_bytes(raw)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for group in GROUPS:
        parser.add_argument(f"--{group}", type=Path, default=ROOT / INPUT_BASE / group / "research-bundle.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / OUTPUT)
    args = parser.parse_args()
    manifest = prepare_runtime_inputs({group: getattr(args, group) for group in GROUPS}, args.output_dir)
    print(json.dumps({"groups": manifest["groups"], "metadata_corrections": len(manifest["metadata_corrections"])}))


if __name__ == "__main__":
    main()
