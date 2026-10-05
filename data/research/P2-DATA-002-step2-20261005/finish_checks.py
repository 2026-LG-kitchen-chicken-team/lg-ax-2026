"""Record scoped checks for the registration run; never update PM or task state."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / "tmp/data002-step2-source-verified"


def run(argv, *, cwd=ROOT, pinned=False):
    env = os.environ.copy()
    if pinned:
        env["PYTHONPATH"] = os.pathsep.join(str(BASE / path) for path in
                                          ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src"))
    result = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True,
                            encoding="utf-8", errors="replace", check=False)
    return {"argv": [str(a) for a in argv], "cwd": str(cwd), "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr, "pinned_code": pinned}


def main():
    results = {}
    python = [sys.executable, "-B", "-X", "utf8"]
    for name, tail in [
        ("registration_fixture_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_document_registration.py", "-v"]),
        ("CSV_boundary_fixture_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_data001_connections.py", "-v"]),
    ]:
        results[name] = run(python + tail, cwd=BASE, pinned=True)
    for name, tail in [
        ("runner_lint", ["-m", "ruff", "check", str(OUT / "run_registration.py"), str(Path(__file__))]),
        ("agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
        ("contracts", ["scripts/check_contracts.py"]),
        ("phase2", ["scripts/phase2.py", "validate"]),
    ]:
        results[name] = run(python + tail)
    results["diff_whitespace"] = run(["git", "diff", "--check"])
    # CLI availability is a read failure, not a fictional board snapshot.
    status_read = run(python + [str(BASE / "scripts/project_report.py"), "status", "--member", "신진하"])
    registration = json.loads((OUT / "runs/verified/registration-checks.json").read_text("utf-8"))
    phase2 = json.loads(results["phase2"]["stdout"]) if results["phase2"]["exit_code"] == 0 else {}
    passed = (registration["result"] == "pass" and registration["servers_stopped"]
              and all(r["exit_code"] == 0 for r in results.values()) and phase2.get("valid") is True)
    report = {"task_id": "P2-DATA-002", "stage": 2, "result": "pass" if passed else "fail",
              "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
              "checks": results, "project_status_cli_read": status_read,
              "status_read_fallback": "Authenticated browser read of Issue12/13, PM MINIMUM-HANDOFF, PR69/ACCEPTED receipt; no board mutation",
              "formal_task_status": json.loads((ROOT / "harness/phase2/tasks/P2-DATA-002.json").read_text("utf-8"))["status"],
              "registration_report_sha256": hashlib.sha256((OUT / "runs/verified/registration-checks.json").read_bytes()).hexdigest(),
              "original_dirty_files_preserved": run(["git", "-c", "core.quotepath=false", "status", "--short"]),
              "limited_to_registration": True, "model_calls": 0, "private_evaluation_read": False}
    destination = OUT / "runs/final"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "final-checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8", newline="\n")
    print(json.dumps({"result": report["result"], "checks": {name: r["exit_code"] for name, r in results.items()},
                      "project_status_cli": status_read["exit_code"], "task_status": report["formal_task_status"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
