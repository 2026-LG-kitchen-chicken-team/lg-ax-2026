"""Replay declared contract fixtures; no generation or semantic scoring."""
import argparse
import json
from pathlib import Path

from lgax_core.judgement_contract import review_judgement


def check_suite(directory: Path) -> dict:
    manifest = json.loads((directory / "cases.json").read_text("utf-8"))
    expected = json.loads((directory / "expected.json").read_text("utf-8"))
    results = []
    for case in manifest["cases"]:
        payload = json.loads((directory / case["input"]).read_text("utf-8"))
        output = json.loads((directory / case["fixture_output"]).read_text("utf-8"))
        # Only input and declared fixture response reach the reviewer.
        decision = review_judgement(payload, output)
        observed = {key: decision[key] for key in ("action", "rerun_from")}
        observed["codes"] = sorted(item["code"] for item in decision["violations"])
        results.append({"case_id": case["case_id"], "type": case["type"],
                        "passed": observed == expected[case["case_id"]], "decision": decision,
                        "expected": expected[case["case_id"]]})
    return {"suite": manifest["suite"], "execution_kind": "fixture", "source_kind": "synthetic",
            "passed": all(case["passed"] for case in results), "cases": results,
            "limitations": ["Deterministic consistency of declared judgements only.",
                            "No model, semantic accuracy, user value or PM approval claim."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check_suite(args.suite)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
