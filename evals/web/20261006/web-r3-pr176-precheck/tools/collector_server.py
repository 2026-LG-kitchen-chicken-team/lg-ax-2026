"""Test-only workspace server with DATA PR #176's collector injected (record 최길웅-20261006-036).

Pre-merge consumption check only. The collector module (`apps/api/src/lgax_api/review_trends.py`) and its candidate
sidecar (`data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json`) are read from a separate checkout of
PR #176's exact head; the server, contracts and MCP are this checkout's main. The sidecar is an unapproved candidate
(PM adoption pending) and the demo reviews carry no dates, so this is not a real-data trend result. The injection here
mirrors what PM would wire; it is not that wiring. Never point the user's 18869 workspace or DB at this server.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import uvicorn
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app

USER_PORTS = {5173, 18867, 18869}
MODULE = "apps/api/src/lgax_api/review_trends.py"
SIDECAR = "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json"


def load_collector_module(path: Path):
    # Loaded under the installed lgax_api package so its relative imports use this checkout's trend validation.
    spec = importlib.util.spec_from_file_location("lgax_api.review_trends", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-checkout", type=Path, required=True, help="checkout of PR #176's exact head")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18881)
    parser.add_argument("--provenance-out", type=Path, required=True)
    args = parser.parse_args()
    if args.port in USER_PORTS:
        raise SystemExit(f"{args.port} belongs to the user's servers; use a separate test port")
    module_path, sidecar_path = args.pr_checkout / MODULE, args.pr_checkout / SIDECAR
    module = load_collector_module(module_path)
    metadata = module.load_trend_metadata(sidecar_path)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.pr_checkout, check=True, capture_output=True,
                          text=True).stdout.strip()
    provenance = {
        "pr": 176, "pr_head": head, "collector_module": MODULE,
        "collector_module_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
        "sidecar": SIDECAR, "sidecar_file_sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
        "sidecar_annotation_version": metadata.get("annotation_version"),
        "sidecar_annotation_sha256": metadata.get("annotation_sha256"),
        "sidecar_status": "candidate (PM adoption pending)", "injection": "test-only, mirrors PM wiring",
    }
    args.provenance_out.parent.mkdir(parents=True, exist_ok=True)
    args.provenance_out.write_bytes(json.dumps(provenance, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    app = create_workspace_app(args.db, TokenRegistry.from_file(args.credentials), planning_runner=None,
                               trend_collector=module.create_review_trend_collector(metadata))
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
