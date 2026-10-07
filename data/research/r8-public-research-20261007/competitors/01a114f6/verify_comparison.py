"""Verify the new comparison's values, evidence links and conservative claims."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    packet = json.loads((args.pack / "comparison.json").read_bytes())
    sources = json.loads((args.pack / "official-sources.json").read_bytes())
    evidence = {e["id"]: e for s in sources["sources"] for e in s["excerpts"]}
    for s in sources["sources"]:
        assert len(s["source_sha256"]) == 64
        assert s["http_status"] == 200
        assert sum(len(e["text"].split()) for e in s["excerpts"]) <= 25
        for e in s["excerpts"]:
            assert hashlib.sha256(e["text"].encode()).hexdigest() == e["text_sha256"]
            assert e["normalized_text_range"][1] - e["normalized_text_range"][0] == len(e["text"])
    lg, samsung = packet["models"]
    assert lg["model_id"] == "T876MEE1H1" and samsung["model_id"] == "RM70F63R231"
    assert lg["capacity_l"] == 870 and "870" in evidence[lg["capacity_evidence"]]["text"]
    assert samsung["capacity_l"] == 640 and "640" in evidence[samsung["capacity_evidence"]]["text"]
    for number in lg["dimensions_mm"].values():
        assert f"{number:,}" in evidence["LG-DIMS"]["text"]
    for number in samsung["dimensions_mm"].values():
        assert f"{number:,}" in evidence["SS-DIMS"]["text"]
    assert lg["release_month"] in evidence["LG-LAUNCH"]["text"]
    assert samsung["release_month"] is None
    assert samsung["side_clearance_mm_per_side"] == 4 and "4mm" in evidence["SS-GAP"]["text"]
    assert samsung["marketing_counter_depth_basis_mm"] == 700 and "700mm" in evidence["SS-COUNTER"]["text"]
    assert samsung["folding_shelf"]["count"] == 1 and "1개" in evidence["SS-FOLD"]["text"]
    assert packet["comparability"]["nominal_capacity_difference_l"] == lg["capacity_l"] - samsung["capacity_l"]
    assert not packet["comparability"]["same_dimension_basis_verified"]
    assert not packet["comparability"]["same_test_conditions_verified"]
    assert not packet["comparability"]["reach_or_cleaning_test_performed"]
    assert all(not m["pull_out_shelf"]["absence_confirmed"] for m in packet["models"])
    for m in packet["models"]:
        for key, value in m.items():
            if key.endswith("_evidence"):
                assert value in evidence, (m["model_id"], key, value)
    problem = packet["problem"]
    rows = json.loads((args.source_root / problem["review_path"]).read_bytes())
    original = next(r for r in rows if r["original_review_id"] == problem["original_review_id"])
    assert original["text_sha256"] == problem["original_text_sha256"]
    assert problem["excerpt"] in original["text"]
    assert original["split"] == problem["existing_split"] == "development"
    assert original["actual_purchased_model_id"] is problem["actual_purchased_model_id"] is None
    assert original["published_at"] is problem["published_at"] is None
    assert not problem["model_input_eligible"] and not problem["model_defect_confirmed"]
    assert problem["first_problem_id"] is None and not packet["handoff"]["first_problem_binding_ready"]
    assert not packet["handoff"]["agent_input_approved"] and not packet["handoff"]["parent_done"]
    result = {
        "scope": "new D3 source/value/uncertainty comparison only",
        "status": "PASS", "model_calls": 0, "network_requests": 0,
        "competitor_models": 1, "official_sources": len(sources["sources"]),
        "evidence_excerpts": len(evidence), "development_review_bound": problem["original_review_id"],
        "comparison_sha256": hashlib.sha256((args.pack / "comparison.json").read_bytes()).hexdigest(),
        "sources_sha256": hashlib.sha256((args.pack / "official-sources.json").read_bytes()).hexdigest(),
        "limitations": ["PM-selected first problem and P0 adapter not received", "not a physical/customer test", "buyer SKU remains unknown", "not full Issue235 or parent completion"]
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
