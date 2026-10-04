"""Run a fixed, private autonomous PM deployment; never turns automation ON."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.automation.github_bridge import exclusive_bridge_lock
from services.automation.isolation import regular_file
from services.automation.pm import AutonomousPM, PMError, protected_path
from services.automation.pm_broker import TrustedPMBroker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--once", action="store_true", help="one tick; no implicit ON or retries")
    parser.add_argument("--observe", action="store_true", help="metadata only; no model or side effects")
    parser.add_argument("--preflight", action="store_true", help="identity, private policy and Docker metadata only")
    args = parser.parse_args(argv)
    try:
        config = json.loads(regular_file(protected_path(args.config)))
        interval = config.get("poll_seconds", 30)
        if type(interval) is not int or not 10 <= interval <= 300:
            raise PMError("bounded PM polling interval required")
        broker = TrustedPMBroker(config)
        pm = AutonomousPM(policy_path=config["policy_file"], policy_sha256=config["policy_sha256"],
                          journal_path=config["journal_file"], broker=broker, decide=broker.driver)
        with exclusive_bridge_lock(Path(config["state_dir"]) / "pm-loop.lock"):
            if args.preflight:
                identity = broker.authenticate()
                boundary = broker.executor.preflight()
                print(json.dumps({"preflight": "passed", "identity": identity, "boundary": boundary,
                                  "model_called": False, "mutated": False}, ensure_ascii=False))
                return 0
            if args.observe:
                print(json.dumps(broker.observe(collect=False), ensure_ascii=False, indent=2))
                return 0
            while True:
                result = pm.tick()
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if args.once:
                    return 0
                # Inert OFF/unchanged events incur no new model call; a missing
                # receipt remains halted for explicit operator reconciliation.
                time.sleep(interval)
    except (PMError, ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"ok": False, "error": "PM operation refused; inspect private deployment and readiness, no credentials printed"}),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
