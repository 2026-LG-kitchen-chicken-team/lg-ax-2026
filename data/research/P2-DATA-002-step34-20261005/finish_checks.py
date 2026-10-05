"""Record independent source checks and actual execution results for DATA002 steps 3/4."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("Use the executed alphanumeric run-id")
    source = ROOT / "tmp" / ("data002-step34-source-" + args.run_id)
    destination = OUT / "runs" / args.run_id / "final-checks.json"
    if destination.exists():
        raise ValueError("Preserve existing verification evidence")
    python = [sys.executable, "-B", "-X", "utf8"]

    def run(tail, *, cwd=ROOT, pinned=False):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if pinned:
            env["PYTHONPATH"] = os.pathsep.join(str(source / path) for path in
                                              ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src"))
        result = subprocess.run(python + tail, cwd=cwd, env=env, capture_output=True,
                                encoding="utf-8", errors="replace", timeout=180, check=False)
        return {"argv": python + tail, "cwd": str(cwd), "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "pinned_source": pinned}

    checks = {}
    # The pinned main's regression suite is separate from real-input HTTP evidence.
    checks["pinned_main_regression"] = run(["-m", "unittest", "discover", "-s", "tests", "-v"],
                                          cwd=source, pinned=True)
    for name, tail in [("pinned_main_contracts", ["scripts/check_contracts.py"]),
                       ("pinned_main_agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
                       ("pinned_main_phase2", ["scripts/phase2.py", "validate"])]:
        checks[name] = run(tail, cwd=source, pinned=True)
    for name, tail in [("own_runner_lint", ["-m", "ruff", "check", str(OUT / "run_steps.py"), str(Path(__file__))]),
                       ("current_clone_contracts", ["scripts/check_contracts.py"]),
                       ("current_clone_agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
                       ("current_clone_phase2", ["scripts/phase2.py", "validate"])]:
        checks[name] = run(tail)
    whitespace = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True,
                                encoding="utf-8", errors="replace", check=False)
    checks["diff_whitespace"] = {"exit_code": whitespace.returncode, "stdout": whitespace.stdout,
                                 "stderr": whitespace.stderr}
    status_read = run(["scripts/project_report.py", "status", "--member", "신진하"], cwd=source, pinned=True)
    result_path = OUT / "runs" / args.run_id / "step34-checks.json"
    evidence = json.loads(result_path.read_text("utf-8"))
    passed = (evidence["result"] == "pass" and evidence["servers_stopped"]
              and all(c["passed"] for c in evidence["checks"])
              and all(c["exit_code"] == 0 for c in checks.values())
              and evidence["runner"]["sha256"] == hashlib.sha256((OUT / "run_steps.py").read_bytes()).hexdigest())
    report = {"task_id": "P2-DATA-002", "stages": [3, 4], "result": "pass" if passed else "fail",
              "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
              "code_commit": evidence["code_commit"], "checks": checks, "project_status_cli_read": status_read,
              "browser_fallback": {"url": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13",
                                   "observed": "Open; owner ginaginaring; Project Todo; dependency P2-DATA-001; no completion checks marked",
                                   "mutated": False},
              "execution_report_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
              "actual_check_count": len(evidence["checks"]), "actual_HTTP_requests": evidence["http_requests"],
              "formal_task_completion": False, "private_evaluation_read": False, "model_calls": 0,
              "source_and_previous_inputs_preserved": all(evidence["preserved_previous_sources"].values()),
              "runner_sha256": hashlib.sha256((OUT / "run_steps.py").read_bytes()).hexdigest(),
              "finisher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"result": report["result"], "checks": {n: c["exit_code"] for n, c in checks.items()},
                      "actual_check_count": report["actual_check_count"], "actual_HTTP_requests": report["actual_HTTP_requests"],
                      "project_status_cli_exit": status_read["exit_code"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
