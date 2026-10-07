"""Run the public ResearchBundle planner using explicit existing LG model settings."""
import argparse
import json
from pathlib import Path

from lgax_core.model_client import StructuredModelClient
from lgax_core.public_planning import PublicPlanner


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-model-calls", type=int, default=12)
    args = parser.parse_args(argv)
    inputs = [args.bundle] + ([args.previous] if args.previous else [])
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("output must differ from all input files")
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    # from_env requires an explicit loopback endpoint, model tag and digest.
    # It does not install a model, launch a service or change foreign settings.
    with StructuredModelClient.from_env() as client:
        planner = PublicPlanner.from_model_client(client, max_model_calls=args.max_model_calls)
        result = planner.run(bundle, args.goal, args.constraint, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"brief_id": result["brief_id"], "run_id": result["run_id"],
                      "status": result["status"], "concepts": len(result["concepts"]),
                      "model_calls": len(result["runtime"]["model_calls"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
