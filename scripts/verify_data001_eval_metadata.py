"""Check PM intake metadata; never read expected answers or run/tune a model."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prepare_evaluation import REQUIRED_CATEGORIES, _manifest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/research/P2-DATA-001-stage345-20261005"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identifiers_and_text_hashes(value):
    identifiers, texts = set(), set()

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, item in node.items():
                if key in {"id", "model_id", "source_id", "evidence_id"} and isinstance(item, str):
                    identifiers.add(item)
                if key == "text" and isinstance(item, str):
                    texts.add(sha(item.encode("utf-8")))
                walk(item)
    walk(value)
    return identifiers, texts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()
    cases_path = args.cases.resolve()
    if "private" not in cases_path.parts:
        raise ValueError("Evaluation input must remain private")
    cases = _manifest(cases_path)
    categories = Counter(c["category"] for c in cases.values())
    dev_ids, dev_texts = set(), set()
    for path in [ROOT / "data/demo/dataset.json", ROOT / "data/document_datasets/lg-three-models-20261005.json"]:
        ids, texts = identifiers_and_text_hashes(json.loads(path.read_text("utf-8")))
        dev_ids.update(ids)
        dev_texts.update(texts)
    results = []
    for case in cases.values():
        data_path = (cases_path.parent / case["data_path"]).resolve()
        schema_path = (cases_path.parent / case["output_contract_path"]).resolve()
        if not all(p.is_relative_to(cases_path.parent) for p in [data_path, schema_path]):
            raise ValueError("Evaluation paths escaped the private case directory")
        ids, texts = identifiers_and_text_hashes(json.loads(data_path.read_text("utf-8")))
        results.append({k: case[k] for k in ["case_id", "category", "data_path", "output_contract_path",
                                            "request_sha256", "data_sha256", "output_contract_sha256"]} |
                       {"development_id_overlap": sorted(ids & dev_ids),
                        "development_exact_text_overlap_count": len(texts & dev_texts)})
    # Hash opaque expected-answer bytes for PM transport only. Their content is not parsed or emitted.
    answers = [{"path": p.relative_to(cases_path.parent).as_posix(), "sha256": sha(p.read_bytes())}
               for p in sorted((cases_path.parent / "answer-key").glob("*")) if p.is_file()]
    report = {"checked_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "manifest_path": str(cases_path), "manifest_sha256": sha(cases_path.read_bytes()),
              "pm_manifest_parser_sha256": sha((ROOT / "scripts/prepare_evaluation.py").read_bytes()),
              "manifest_contract_passed": True, "required_categories": list(REQUIRED_CATEGORIES),
              "category_counts": dict(categories), "case_count": len(results), "cases": results,
              "answer_key_files": answers, "expected_answers_read_for_development": False,
              "expected_answer_validity": "pending_PM_review", "semantic_independence": "pending_PM_review",
              "actual_evaluation_execution": False, "baseline_comparison_execution": False,
              "evaluation_complete": False,
              "limitation": "Exact ID/text disjointness does not establish independent authorship or answer validity."}
    path = PUBLIC / "evaluation-intake-metadata.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"manifest_contract_passed": True, "case_count": len(results),
                      "types_present": len(categories), "expected_answer_validity": "pending_PM_review",
                      "evaluation_complete": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
