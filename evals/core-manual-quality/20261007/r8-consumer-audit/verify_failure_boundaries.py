"""Fixed-source failure probes only: no model, synthetic review, or concept.

The retained official review/manual and actual faulty Qwen wording come from
the producer's test_public_planning.py. Test-only wire item IDs exercise call
isolation; they are not customer problems or semantic quality results.
Run only inside the credential-free, network-disabled source container.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from lgax_core.public_planning import PublicPlanner, source_facts
from test_public_planning import real_bundle


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def wire_problem(bundle, item_id, description):
    return {"id": item_id, "title": "TEST ONLY: 응답 경계 검사",
            "description": description, "source_ids": [bundle["sources"][0]["source_id"]],
            "counter_source_ids": [], "scope_caveat": "TEST ONLY: 고객 문제/품질/기획 승인 아님"}


def invoke(bundle, rows):
    stages = []
    discovery = {"problems": deepcopy(rows), "summaries": {"positive": [], "negative": [], "mixed": []}}

    def wire_caller(prompt, schema):
        context = json.loads(prompt.split("\n분석할 데이터(JSON):\n", 1)[1])
        if "batch" in context:
            stages.append("discover")
            return deepcopy(discovery)
        if "rejected_fields" in context:
            stages.append("repair_fields")
            # Rejected response, never forced acceptance or invented repair.
            return None
        stages.append("plan")
        return None

    before = deepcopy(bundle)
    brief = PublicPlanner(wire_caller, max_model_calls=12).run(
        bundle, "TEST ONLY: 원문 기반 실패 경계 검사", [])
    assert bundle == before
    assert brief["source_facts"] == source_facts(bundle)
    assert brief["concepts"] == []
    assert brief["status"] == "needs_sources"
    assert brief["runtime"]["independent_semantic_quality_verified"] is False
    return stages, brief, discovery


def main():
    bundle = real_bundle()
    # This faulty sentence is retained actual Qwen27B diagnostic output, not
    # a synthetic review. Three test-only wire IDs exercise a shared budget.
    faulty = "고객은 냉동 핫도그를 데웠으나, 1분 후에도 완전 차가운 냉동 상태였다고 보고했습니다."
    rows = [wire_problem(bundle, f"test-only-rejected-{index}", faulty) for index in range(3)]
    stages, budget_brief, original = invoke(bundle, rows)
    repair_calls = stages.count("repair_fields")
    assert repair_calls == 3, stages
    assert budget_brief["problems"] == []
    assert budget_brief["runtime"]["model_calls"][0]["response"] == original
    assert all(any(error["code"] == "expected_time_as_actual_action" for error in item["issues"])
               for item in budget_brief["runtime"]["item_issues"])

    # The healthy wire item copies exact source text. It is not an inferred
    # problem or a generated concept; a malformed neighbor tests container loss.
    healthy = wire_problem(bundle, "test-only-source-copy", bundle["sources"][0]["text"])
    malformed = deepcopy(healthy)
    malformed["id"] = "test-only-missing-title"
    del malformed["title"]
    stages2, container_brief, response2 = invoke(bundle, [healthy, malformed])
    assert stages2 == ["discover"], stages2
    assert container_brief["problems"] == []
    assert container_brief["runtime"]["model_calls"][0]["error_type"] == "ValidationError"
    assert container_brief["runtime"]["model_calls"][0]["response"] == response2
    assert container_brief["runtime"]["item_issues"] == []

    code = Path("packages/core/src/lgax_core/public_planning.py").read_bytes()
    schema = Path("packages/contracts/schemas/research-planning.schema.json").read_bytes()
    print(json.dumps({
        "fixed_head": "e04f42b5de37b2d1cad606f2f06a3f7fe6a91f30",
        "probe_kind": "test_only_wire_failure_boundaries",
        "public_planning_sha256": hashlib.sha256(code).hexdigest(),
        "research_schema_sha256": hashlib.sha256(schema).hexdigest(),
        "bundle_sha256": digest(bundle), "source_ids": [s["source_id"] for s in bundle["sources"]],
        "shared_repair_budget": {"required_max": 2, "observed_repair_calls": repair_calls,
                                  "wire_stages": stages, "requirement_satisfied": False},
        "container_isolation": {"wire_stages": stages2, "healthy_wire_item_retained": False,
                                "raw_response_retained": True, "per_item_checks_reached": False,
                                "requirement_satisfied": False},
        "actual_model_calls": 0, "new_review_texts": 0, "generated_concepts": 0,
        "independent_ai_grading": 0, "source_facts_unchanged": True,
        "status": "two_failure_boundaries_reproduced",
        "limits": "Contract wire probes; no live quality, meaning acceptance, PM approval or Done."
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
