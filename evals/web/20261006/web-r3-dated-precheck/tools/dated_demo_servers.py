"""Test-only servers for DATA PR #183's constructed dated demo (record 최길웅-20261006-040).

Pre-merge web check only; PM approval and production injection are pending. Run with PYTHONPATH pointing at a checkout
of PR #183's exact head (its core adds GroundedDemoStore). Two roles, each its own process:
  --role workspace : private workspace API with the dated dataset as evidence store and the #183/#176 collector fed the
                     dated demo sidecar (mirrors DATA's run_dated_trend_path.py wiring; not PM's production wiring).
  --role public    : the public bootstrap API with its default store swapped for the same dated dataset, so the web reads
                     the dated demo's review sources (the user's 18867 keeps the original dataset and is not touched).
The constructed dates are demo data: not real publication dates, demand or complaint ratios.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import uvicorn

USER_PORTS = {5173, 18867, 18869}
FOLDER = "data/research/DATA-owner-followup-20261006-01a1100e"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["workspace", "public"], required=True)
    parser.add_argument("--pr-checkout", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--provenance-out", type=Path)
    args = parser.parse_args()
    if args.port in USER_PORTS:
        raise SystemExit(f"{args.port} belongs to the user's servers; use a separate test port")
    folder = args.pr_checkout / FOLDER
    dataset_path, annotation_path = folder / "dataset.synthetic-dated-demo.v1.json", folder / "annotation.synthetic-dated-demo.v1.json"
    dataset = json.loads(dataset_path.read_bytes())
    from lgax_core.retrieval import GroundedDemoStore  # from the PR #183 checkout via PYTHONPATH
    store = GroundedDemoStore(dataset)
    if args.role == "public":
        import lgax_api.server as public
        public.default_store = lambda: store  # test-only swap; the module's routes call default_store() per request
        uvicorn.run(public.app, host="127.0.0.1", port=args.port)
        return
    from lgax_api.review_trends import create_review_trend_collector, load_trend_metadata
    from lgax_api.workspace_auth import TokenRegistry
    from lgax_api.workspace_server import create_workspace_app
    metadata = load_trend_metadata(annotation_path)
    if args.provenance_out:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.pr_checkout, check=True, capture_output=True, text=True).stdout.strip()
        provenance = {
            "pr": 183, "pr_head": head, "dataset": f"{FOLDER}/dataset.synthetic-dated-demo.v1.json",
            "dataset_file_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(), "dataset_version": dataset["manifest"]["version"],
            "annotation": f"{FOLDER}/annotation.synthetic-dated-demo.v1.json",
            "annotation_file_sha256": hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
            "annotation_sha256": metadata.get("annotation_sha256"), "topic_taxonomy_version": metadata.get("topic_taxonomy_version"),
            "status": "constructed dated demo, PM approval and production injection pending", "injection": "test-only",
        }
        args.provenance_out.parent.mkdir(parents=True, exist_ok=True)
        args.provenance_out.write_bytes(json.dumps(provenance, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    app = create_workspace_app(args.db, TokenRegistry.from_file(args.credentials), planning_runner=None,
                               evidence_store=store, trend_collector=create_review_trend_collector(metadata))
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
