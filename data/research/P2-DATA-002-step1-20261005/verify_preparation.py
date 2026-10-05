"""Check step-1 artifacts and existing repository rules without changing task state."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PYTHON = ROOT / ".venv/Scripts/python.exe"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv):
    result = subprocess.run([str(a) for a in argv], cwd=ROOT, capture_output=True,
                            encoding="utf-8", errors="replace")
    return {"argv": [str(a) for a in argv], "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    initial = read(OUT / "runs/initial/verification.json")
    sources = {name: sha(ROOT / name) == value
               for name, value in initial["source_hashes_preserved"].items()}
    outputs = {item["path"]: sha(ROOT / item["path"]) == item["sha256"]
               for item in initial["outputs"]}
    builder_matches = sha(ROOT / initial["builder"]["path"]) == initial["builder"]["sha256"]
    pdf = next(item for item in read(OUT / "input-selection.json")["inputs"]
               if item["format"] == "pdf")
    pdf_matches = sha(Path(pdf["local_path"])) == pdf["sha256"]
    checks = {}
    for name, tail in [
        ("agent_rules", ["scripts/sync_agent_rules.py", "--check"]),
        ("contracts", ["scripts/check_contracts.py"]),
        ("phase2", ["scripts/phase2.py", "validate"]),
    ]:
        checks[name] = command([PYTHON, "-B", "-X", "utf8", *tail])
    checks["diff_whitespace"] = command(["git", "diff", "--check"])
    harness = json.loads(checks["phase2"]["stdout"]) if checks["phase2"]["exit_code"] == 0 else {}
    passed = (all(sources.values()) and all(outputs.values()) and builder_matches
              and pdf_matches and all(item["exit_code"] == 0 for item in checks.values())
              and harness.get("valid") is True)
    report = {
        "task_id": "P2-DATA-002", "stage": 1, "result": "pass" if passed else "fail",
        "checked_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        "execution_kind": "preparation_integrity_only", "service_executed": False,
        "source_hashes_match_initial": sources, "output_hashes_match_initial": outputs,
        "builder_hash_matches_initial": builder_matches, "pdf_hash_matches": pdf_matches,
        "checks": checks, "phase2_valid": harness.get("valid"),
        "task_status": read(ROOT / "harness/phase2/tasks/P2-DATA-002.json")["status"],
        "working_tree": command(["git", "status", "--short"]),
        "code_commit": command(["git", "rev-parse", "HEAD"])["stdout"].strip(),
        "not_run": ["production ingestion/parser/API/MCP", "model inference",
                    "independent evaluation", "web checks", "full regression"],
    }
    destination = OUT / "runs/final"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "final-checks.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"result": report["result"], "checks": {name: item["exit_code"]
                     for name, item in checks.items()}, "phase2_valid": report["phase2_valid"],
                     "task_status": report["task_status"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
