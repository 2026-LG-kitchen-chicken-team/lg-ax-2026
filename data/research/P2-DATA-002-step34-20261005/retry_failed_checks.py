"""Retry only the two CI API probe checks that failed in the unchanged pinned main suite."""
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / "tmp/data002-step34-source-initial"
DESTINATION = OUT / "runs/initial/failed-checks-retry.json"
if DESTINATION.exists():
    raise ValueError("Previous retry evidence is preserved")
env = os.environ.copy()
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONPATH"] = os.pathsep.join(str(BASE / path) for path in
                                  ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src", "tests"))
argv = [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
        "test_ci_web_e2e.CiWebE2ETests.test_actual_api_probe_auth_origin_and_cleanup",
        "test_ci_web_e2e.CiWebE2ETests.test_failed_auth_gate_reaps_children_and_removes_material", "-v"]
result = subprocess.run(argv, cwd=BASE, env=env, capture_output=True, encoding="utf-8", errors="replace",
                        timeout=130, check=False)
report = {"result": "pass" if result.returncode == 0 else "fail", "argv": argv, "cwd": str(BASE),
          "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
          "source_modified": False, "original_suite_failure_preserved": True,
          "limitation": "An isolated retry does not replace the original full-suite result or prove its failure cause."}
DESTINATION.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"result": report["result"], "exit_code": result.returncode}))
raise SystemExit(result.returncode)
