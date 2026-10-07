"""Model-free wire checks on retained official sources; run in source-only Docker."""
import json
from hashlib import sha256
from pathlib import Path

from lgax_core.public_planning import _digest, _planning_customer_context, source_facts
from test_public_planning import real_bundle
from test_public_planning_isolation import FAULTY, invoke, wire_problem
from test_public_planning_sampling import PACK


def main():
    bundle = real_bundle()
    rows = [wire_problem(bundle, f"test-only-rejected-{index}", FAULTY) for index in range(3)]
    limited, stages, _, raw = invoke(bundle, rows)
    assert stages == ["discover", "repair_fields", "repair_fields"]
    assert limited["runtime"]["model_calls"][0]["response"] == raw
    assert limited["runtime"]["correction_budget"]["revision_count"] == 2
    healthy = wire_problem(bundle, "test-only-source-copy", bundle["sources"][0]["text"])
    malformed = {key: value for key, value in healthy.items() if key != "title"}
    malformed["id"] = "test-only-missing-title"
    isolated, stages2, schemas, original = invoke(bundle, [healthy, malformed])
    assert isolated["problems"] == [{**healthy, "id": "problem-1"}]
    assert isolated["runtime"]["model_calls"][0]["response"] == original
    assert "title" in schemas[0]["$defs"]["Problem"]["required"]
    assert limited["source_facts"] == isolated["source_facts"] == source_facts(bundle)
    corpus = json.loads(PACK.read_text("utf-8"))
    catalog = {row["source_id"]: row for row in corpus["sources"]}
    wiring = {"source_ids": ["LGE-R8-REVIEW-752651", "LGE-R8-REVIEW-800073"],
              "counter_source_ids": ["LGE-R8-REVIEW-853593"]}
    selected = _planning_customer_context(wiring, catalog)
    assert [row["source_id"] for row in selected] == [wiring["source_ids"][0], wiring["counter_source_ids"][0]]
    files = ["packages/core/src/lgax_core/public_planning.py", "packages/core/src/lgax_core/public_repair.py",
             "packages/contracts/schemas/research-planning.schema.json"]
    print(json.dumps({
        "kind": "retained_real_source_wire_boundaries_not_live_quality",
        "base": "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f",
        "source_sha256": {name: sha256(Path(name).read_bytes()).hexdigest() for name in files},
        "bundle_sha256": _digest(bundle), "source_ids": [row["source_id"] for row in bundle["sources"]],
        "shared_corrections": {"max": 2, "observed": stages.count("repair_fields"), "stages": stages,
                               "failed_attempts_spent": True, "original_response_preserved": True},
        "returned_response_item_isolation": {"healthy_retained": True, "stages": stages2,
                                             "full_caller_schema_preserved": True, "original_response_preserved": True},
        "native_client_item_recovery": {"implemented": False, "reason": "schema_mismatch_before_data_return",
                                        "owner": "PM model_client boundary", "verified_by": "test_public_planning_isolation"},
        "counter_context": {"existing_customer_slots": 2, "selected_ids": [row["source_id"] for row in selected],
                            "source_records_unchanged": True, "roles": "test_only_wiring_not_sentiment_judgement"},
        "actual_model_calls": 0, "new_reviews": 0, "generated_concepts": 0,
        "independent_ai_grading": 0, "facts_preserved": True, "pm_intake_or_Done": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
