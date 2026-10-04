"""Stored-run records for the web from the real core pipeline with a mocked model (never a live LLM).

Runs lgax_core.planning_agent.PlanningAgent of the checkout given by --root, answering every model request from the
core's own test fixtures (tests/test_planning_agent.py: MockTransport, authored stage outputs), then projects each
result through workspace_planning.planning_run_fields exactly as the workspace server stores it. The scenarios are
failure/hold/revise paths the PM live record (two accepted runs) does not contain. Model answers are authored
fixtures, so the records show what the core does with them, not what a model would say.

  uv run python evals/web/20261005/p2-web-003-core-records/generate.py --root . --set main --out .../main-core.json
  PYTHONPATH=<pr60>/packages/core/src:<pr60>/packages/contracts/src \
    uv run python .../generate.py --root <pr60> --set semantic --out .../pr60-semantic-preview.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--set", choices=("main", "semantic"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "tests"))
    import test_planning_agent as fixtures  # the checkout's own pinned mocks
    import httpx
    import lgax_core
    from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
    from lgax_core.planning_agent import PlanningAgent
    from lgax_core.store import DemoStore
    from lgax_core.workspace_planning import planning_run_fields

    if not Path(lgax_core.__file__).resolve().is_relative_to(root):
        raise SystemExit(f"lgax_core is imported from {lgax_core.__file__}, not from --root {root}")
    payload = fixtures.read("normal.input.json")
    output = fixtures.read("normal.fixture-output.json")
    dataset = fixtures.dataset_for(payload)

    def run(alter):
        transport = fixtures.Transport(fixtures.stages_for(output), alter)
        adapter = OllamaAdapter(ModelConfig("http://127.0.0.1:18864", fixtures.MODEL, fixtures.DIGEST,
                                            max_output_tokens=2048, context_tokens=8192),
                                transport=httpx.MockTransport(transport))
        with StructuredModelClient(adapter) as client:
            return PlanningAgent(client, DemoStore(dataset), execution_kind="fixture").run(deepcopy(payload))

    def positive(skill, context, value, count):
        value["result"].update(needs=[], desired_outcomes=[], unresolved=["긍정 리뷰에서 확정된 불편이 없다"])
        value["review_assessments"][0]["polarity"] = "positive"
        value.update(questions=["불편을 경험한 리뷰가 있나요?"], hold_reasons=["불편 근거 없음"],
                     no_candidate_reasons=["확인된 불편 없음"])
        return value

    def duplicate(skill, context, value, count):
        if skill == "concept_draft":
            value["concept_assessments"][0]["duplication"] = "duplicate"
        return value

    def wrong_need_once(skill, context, value, count):
        if skill == "need_extract" and context["revision_count"] == 0:
            value["result"]["needs"][0]["evidence_ids"] = ["MISSING"]
        return value

    def exclusion(verdict, question=None):
        def alter(skill, context, value, count):
            if skill == "semantic_review":
                value["exclusion_assessments"][0].update(verdict=verdict, reason="테스트가 작성한 검토 선언: " + verdict)
                if question:
                    value["questions"] = [question]
            return value
        return alter

    def wrong_review_hash(skill, context, value, count):
        if skill == "semantic_review":
            value["input_sha256"] = "b" * 64
        return value

    scenarios = {
        "main": {
            "generation_failed": lambda *a: "{broken",
            "duplicate_unresolved": duplicate,
            "positive_held": positive,
            "need_reference_revised": wrong_need_once,
        },
        "semantic": {
            "semantic_accept": None,
            "exclusion_violation_unresolved": exclusion("violation"),
            "exclusion_uncertain_held": exclusion("uncertain", "후보가 기존 부품만으로 동작하는지 확인할 수 있나요?"),
            "semantic_review_invalid": wrong_review_hash,
        },
    }[args.set]

    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    model = payload["product"]["model_id"]
    records = {}
    for index, (name, alter) in enumerate(scenarios.items()):
        execution = run(alter)
        fields, browser = planning_run_fields(execution, payload)
        records[name] = {
            "run": {"id": f"run-core-{args.set}-{index}", "project_id": "prj-core-records",
                    "dataset_version": payload["request"]["dataset_version"], "contract_version": "0.1.0", **fields},
            "request": deepcopy(payload["request"]), "previous_run_id": None, "request_revision": 0,
            "actor_id": "planner-demo", "client": "web", "created_at": "2026-10-05T00:00:00Z",
            "document_versions": {model: payload["product"]["document_version"]},
            "dataset_sha256": hashlib.sha256(json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "unconfirmed": [], "output": browser,
        }
    document = {"execution_kind": "core_pipeline_with_mocked_model", "core_commit": head.stdout.strip(),
                "scenario_set": args.set, "input": "evals/core-contract/development/normal.input.json",
                "model_answers": "tests/test_planning_agent.py fixtures of that commit (authored, not model output)",
                "runs": records}
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(json.dumps({name: [r["run"]["status"], (r["output"]["planning_execution"]["decision"] or {}).get("action")]
                      for name, r in records.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
