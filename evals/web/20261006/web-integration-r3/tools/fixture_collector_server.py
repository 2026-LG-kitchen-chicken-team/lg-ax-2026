"""Test-only workspace server with PM's unit FixtureCollector injected (record 최길웅-20261006-031).

Purpose: exercise the real HTTP/storage/validation path that a DATA #148 collector will use, before that collector
exists. The collector is `tests/test_workspace_trends.py::FixtureCollector`: the 36 canonical demo reviews are
unchanged and exactly one (REVIEW-001) carries a unit-fixture date/topic. It is not an approved sidecar, not a real
collector and not demand evidence. Never point the user's 18869 workspace or DB at this server.
"""
import argparse
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tests"))

from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from test_workspace_trends import FixtureCollector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18879)
    args = parser.parse_args()
    if args.port == 18869:
        raise SystemExit("18869 is the user's workspace; use a separate test port")
    app = create_workspace_app(args.db, TokenRegistry.from_file(args.credentials),
                               planning_runner=None, trend_collector=FixtureCollector())
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
