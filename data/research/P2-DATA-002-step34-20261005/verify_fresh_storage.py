"""Verify new validated inserts as well as resuming the existing STEP2 registrations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
EXTRACTOR = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"


def read(path):
    return json.loads(path.read_text("utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("Use the executed alphanumeric run-id")
    public = OUT / "runs" / args.run_id
    private = ROOT / "private/data002-step34" / args.run_id
    source = ROOT / "tmp" / ("data002-step34-source-" + args.run_id)
    destination = public / "fresh-storage-checks.json"
    fresh = private / "fresh-valid-registration"
    if destination.exists() or fresh.exists():
        raise ValueError("Preserve previously executed storage evidence")
    initial = read(public / "step34-checks.json")
    if initial["result"] != "pass":
        raise ValueError("Extraction/validation run must pass first")
    fresh.mkdir()
    before = {str(path): sha(path) for path in private.rglob("*") if path.is_file()}
    sys.path[:0] = [str(source / "packages/core/src"), str(source / "packages/contracts/src")]
    from lgax_core import documents, review_csv
    plan, dataset = read(private / "plan.json"), read(private / "dataset.json")
    source_pdf = documents.DocumentRepository(private / "pdf-store", plan, EXTRACTOR)
    source_csv = review_csv.ReviewCsvRepository(private / "csv-store", dataset)
    pdf_id, csv_id = plan["documents"][0]["document_id"], source_csv.source_id
    report = {"task_id": "P2-DATA-002", "stage": 4, "result": "running", "code_commit": initial["code_commit"],
              "execution_kind": "actual_repository_inserts_no_mocks", "checks": [], "model_calls": 0,
              "private_evaluation_read": False, "formal_task_completion": False,
              "runner_sha256": sha(Path(__file__))}
    (public / "executed-fresh-storage.py.txt").write_bytes(Path(__file__).read_bytes())

    def check(name, passed):
        report["checks"].append({"name": name, "passed": bool(passed)})
        if not passed:
            raise AssertionError(name)

    try:
        check("pinned_main_source", all(Path(m.__file__).resolve().is_relative_to(source) for m in (documents, review_csv)))
        for kind, source_repo, did in [("pdf", source_pdf, pdf_id), ("csv", source_csv, csv_id)]:
            directory = fresh / kind
            constructor = ((lambda directory: documents.DocumentRepository(directory, plan, EXTRACTOR))
                           if kind == "pdf" else (lambda directory: review_csv.ReviewCsvRepository(directory, dataset)))
            repo = constructor(directory)
            original, expected = source_repo.original(did), source_repo.metadata(did)
            record = repo.upload(did, original)  # Real parser + canonical validation + new SQLite insert.
            check(kind + "_fresh_valid_insert_matches_previous_registration", record == expected)
            with sqlite3.connect(repo.db) as db:
                count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            check(kind + "_one_logical_row_and_exact_original", count == 1 and repo.original(did) == original)
            reopened = constructor(directory)
            retained = reopened.store().bootstrap()["data"]
            check(kind + "_new_database_reopen_retains_validated_entities", reopened.metadata(did) == expected
                  and reopened.original(did) == original
                  and retained["evidence"] == (expected["dataset"]["evidence"] if kind == "pdf" else dataset["evidence"]))
        check("earlier_private_run_files_preserved", all(sha(Path(path)) == digest for path, digest in before.items()))
        report["result"] = "pass"
    except Exception as error:
        report["result"] = "fail"
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["checked_at_kst"] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"result": report["result"], "checks": len(report["checks"]),
                          "evidence": str(destination.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
