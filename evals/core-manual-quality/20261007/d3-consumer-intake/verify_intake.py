"""Check new D3 consumer pins and literal context; no planning/model execution.

Run in a credential-free container with read-only pinned D3 and review inputs.
Author annotations describe limits; this checker does not infer review meaning.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--intake", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.pack / "manifest.json").read_bytes())
    intake = json.loads(args.intake.read_bytes())
    for entry in manifest["files"]:
        path = args.pack / entry["path"]
        assert path.parent == args.pack, "unexpected manifest path"
        raw = path.read_bytes()
        assert len(raw) == entry["bytes"] and digest(raw) == entry["sha256"], entry["path"]
    comparison_raw = (args.pack / "comparison.json").read_bytes()
    sources_raw = (args.pack / "official-sources.json").read_bytes()
    comparison = json.loads(comparison_raw)
    sources = json.loads(sources_raw)
    assert digest(comparison_raw) == intake["pins"]["comparison_sha256"]
    assert digest(sources_raw) == intake["pins"]["sources_sha256"]
    review_raw = args.reviews.read_bytes()
    assert digest(review_raw) == intake["pins"]["review_file_sha256"]
    original = next(r for r in json.loads(review_raw) if r["original_review_id"] == intake["review"]["id"])
    assert digest(original["text"].encode()) == original["text_sha256"] == comparison["problem"]["original_text_sha256"]
    assert original["purchase_date"] == comparison["problem"]["purchase_date"]
    assert original["published_at"] is comparison["problem"]["published_at"] is None
    assert original["actual_purchased_model_id"] is comparison["problem"]["actual_purchased_model_id"] is None
    assert original["eligible_for_model_input"] is False
    assert original["split"] == comparison["problem"]["existing_split"] == "development"
    for context in intake["review"]["literal_context"]:
        assert original["text"][context["start"]:context["end"]] == context["quote"], context["id"]
    ids = []
    for source in sources["sources"]:
        for excerpt in source["excerpts"]:
            assert digest(excerpt["text"].encode()) == excerpt["text_sha256"]
            assert excerpt["normalized_text_range"][1] - excerpt["normalized_text_range"][0] == len(excerpt["text"])
            ids.append(excerpt["id"])
    assert len(ids) == len(set(ids)) == 12
    assert len(sources["sources"]) == 3
    assert all(not comparison["comparability"][k] for k in (
        "same_capacity", "same_installation", "same_dimension_basis_verified",
        "same_test_conditions_verified", "reach_or_cleaning_test_performed"))
    assert all(m["pull_out_shelf"]["absence_confirmed"] is False for m in comparison["models"])
    assert comparison["problem"]["first_problem_id"] is None
    assert comparison["handoff"]["agent_input_approved"] is False
    assert intake["planning_run_executed"] is intake["canonical_evidence_imported"] is False
    print(json.dumps({
        "status": "PASS", "scope": "new D3 consumer byte pins and literal context only",
        "manifest_files": len(manifest["files"]), "official_sources": len(sources["sources"]),
        "excerpt_hashes": len(ids), "original_review_id": original["original_review_id"],
        "literal_contexts": len(intake["review"]["literal_context"]),
        "model_calls": 0, "network_calls": 0, "raw_html_reverification": False,
        "meaning_or_customer_effect_approved": False,
        "checker_sha256": digest(Path(__file__).read_bytes()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
