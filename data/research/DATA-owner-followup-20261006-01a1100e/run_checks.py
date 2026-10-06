"""Record actual bounded DATA regressions and repository integrity checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
TESTS = ["test_evidence_catalog", "test_retrieval", "test_retrieval_benchmark", "test_upload_query_integration",
         "test_data_followup_handoff", "test_document_registration", "test_document_plan_history",
         "test_document_store_snapshot", "test_document_skill_intake", "test_review_import",
         "test_source_ranges", "test_review_trends", "test_review_trend_contracts"]


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(ROOT / path) for path in (
        "packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src", "tests")), "PYTHONUTF8": "1"}
    commands = [["-m", "unittest", *["tests." + name for name in TESTS], "-v"],
                ["scripts/check_contracts.py"], ["scripts/sync_agent_rules.py", "--check"],
                ["scripts/migrate_member_logs.py", "--verify"], ["scripts/phase2.py", "validate"],
                ["services/inference/build_manifest.py", "--check"]]
    receipts = []
    for index, args in enumerate(commands, 1):
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", *args], cwd=ROOT, env=env,
                                encoding="utf-8", capture_output=True, timeout=120, check=False)
        combined = (result.stdout + result.stderr).replace(str(ROOT), "<checkout>")
        log = (combined + "\n").encode()
        name = f"check-{index:02d}.log"
        (output / name).write_bytes(log)
        count = re.search(r"Ran (\d+) tests", combined)
        receipts.append({"command": ["python311", *args], "exit_code": result.returncode,
                         "test_count": int(count[1]) if count else None,
                         "log": name, "log_sha256": hashlib.sha256(log).hexdigest()})
    manifest = {"observed_at": datetime.now(UTC).isoformat(), "checks": receipts,
                "all_passed": all(row["exit_code"] == 0 for row in receipts),
                "model_calls": 0, "production_runtime_injection": False}
    (output / "checks.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["all_passed"] else 1)
