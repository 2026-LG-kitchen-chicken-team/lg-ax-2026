"""Record stage-5 execution, relevant regressions and required project checks separately."""
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline-evidence", type=Path,
                        help="Reuse an actual preserved baseline failure instead of repeating an unchanged full suite")
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("Use the executed alphanumeric run-id")
    source = ROOT / "tmp" / ("data002-step5-source-" + args.run_id)
    public = OUT / "runs" / args.run_id
    destination = public / "final-checks.json"
    if destination.exists():
        raise ValueError("Preserve existing verification evidence")
    snapshot = public / ("executed-finisher-" + digest(Path(__file__))[:12] + ".py.txt")
    if not snapshot.exists():
        snapshot.write_bytes(Path(__file__).read_bytes())
    python = [sys.executable, "-B", "-X", "utf8"]
    paths = ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src")

    def run(tail, *, cwd=ROOT, pinned=False, timeout=240):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if pinned:
            env["PYTHONPATH"] = os.pathsep.join(str(source / path) for path in paths)
        try:
            result = subprocess.run(python + tail, cwd=cwd, env=env, capture_output=True,
                                    encoding="utf-8", errors="replace", timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            def decode(value):
                return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
            return {"argv": python + tail, "cwd": str(cwd), "exit_code": 124,
                    "stdout": decode(error.stdout), "stderr": decode(error.stderr),
                    "pinned_source": pinned, "timed_out": True, "timeout_seconds": timeout}
        return {"argv": python + tail, "cwd": str(cwd), "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "pinned_source": pinned}

    checks = {}
    checks["relevant_evidence_document_regression"] = run(
        ["-m", "unittest", "discover", "-s", "tests", "-p", "test_core.py", "-v"], cwd=source, pinned=True)
    checks["document_registration_regression"] = run(
        ["-m", "unittest", "discover", "-s", "tests", "-p", "test_document_registration.py", "-v"], cwd=source, pinned=True)
    for name, tail in [("pinned_contracts", ["scripts/check_contracts.py"]),
                       ("pinned_agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
                       ("pinned_phase2", ["scripts/phase2.py", "validate"])]:
        checks[name] = run(tail, cwd=source, pinned=True)
    for name, tail in [("own_lint", ["-m", "ruff", "check", str(OUT / "run_search.py"), str(Path(__file__))]),
                       ("current_contracts", ["scripts/check_contracts.py"]),
                       ("current_agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
                       ("current_phase2", ["scripts/phase2.py", "validate"])]:
        checks[name] = run(tail)
    whitespace = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True,
                                encoding="utf-8", errors="replace", check=False)
    checks["diff_whitespace"] = {"exit_code": whitespace.returncode, "stdout": whitespace.stdout, "stderr": whitespace.stderr}
    # This unchanged shared baseline is not conflated with requested search/trace validation.
    if args.baseline_evidence:
        baseline_path = args.baseline_evidence.resolve()
        if not baseline_path.is_relative_to(public.resolve()):
            raise ValueError("Baseline evidence must belong to this run")
        baseline = json.loads(baseline_path.read_text("utf-8"))
        if baseline["code_commit"] != json.loads((public / "search-checks.json").read_text("utf-8"))["code_commit"]:
            raise ValueError("Baseline commit must match executed code")
        baseline = {**baseline, "reused_actual_evidence": str(baseline_path.relative_to(ROOT)),
                    "reused_evidence_sha256": digest(baseline_path)}
    else:
        baseline = run(["-m", "unittest", "discover", "-s", "tests", "-v"], cwd=source, pinned=True)
    status_read = run(["scripts/project_report.py", "status", "--member", "신진하"], cwd=source, pinned=True)
    evidence_path = public / "search-checks.json"
    evidence = json.loads(evidence_path.read_text("utf-8"))
    passed = (evidence["result"] == "pass" and evidence["servers_stopped"] and evidence["all_own_listeners_closed"]
              and all(c["passed"] for c in evidence["checks"]) and all(c["exit_code"] == 0 for c in checks.values())
              and evidence["runner"]["sha256"] == digest(OUT / "run_search.py"))
    report = {"task_id": "P2-DATA-002", "stage": 5, "requested_scope_result": "pass" if passed else "fail",
              "code_commit": evidence["code_commit"], "checks": checks,
              "baseline_full_regression": baseline, "whole_suite_passed": baseline["exit_code"] == 0,
              "project_status_cli_read": status_read,
              "browser_fallback": {"issue13": "Open; owner ginaginaring; Project Todo; DATA001 dependency; completion unchecked",
                                   "pm_instruction": "PM-20261005-DATA-001-CITATION-FIX",
                                   "pr74": "Open; PM review pending; observed head5af64e93b1ca413317a91893e530901fc7f5874e",
                                   "mutated": False},
              "execution_report_sha256": digest(evidence_path), "actual_check_count": len(evidence["checks"]),
              "actual_HTTP_requests": evidence["http_requests"], "runner_sha256": digest(OUT / "run_search.py"),
              "finisher_sha256": digest(Path(__file__)), "formal_task_completion": False, "published": False,
              "model_calls": 0, "private_evaluation_read": False,
              "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")
    print(json.dumps({"requested_scope_result": report["requested_scope_result"],
                      "checks": {n: c["exit_code"] for n, c in checks.items()},
                      "whole_suite_passed": report["whole_suite_passed"], "actual_HTTP_requests": report["actual_HTTP_requests"],
                      "project_status_cli_exit": status_read["exit_code"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
