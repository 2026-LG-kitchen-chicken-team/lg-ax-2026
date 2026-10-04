"""Execute change planning on three synthetic examples, without calling a model."""
import argparse
import json
from pathlib import Path

from lgax_core.reexecution import prepare_reexecution


def plan_examples(directory: Path) -> dict:
    results = []
    for group in ("fridge", "dishwasher", "microwave"):
        previous = json.loads((directory / f"{group}.before.input.json").read_text("utf-8"))
        current = json.loads((directory / f"{group}.after.input.json").read_text("utf-8"))
        results.append({"product_group": group, "plan": prepare_reexecution(previous, current)})
    return {"execution_kind": "fixture", "source_kind": "synthetic", "model_calls": 0,
            "cases": results, "notice": "Actual change planning only; no generation or semantic quality claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path(__file__).parent / "examples")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = plan_examples(args.examples)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, "utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
