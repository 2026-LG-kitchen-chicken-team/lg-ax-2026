"""Execute only DATA002 extraction and validation/persistence on approved STEP2 inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMMIT = "f88dd7ac6448ef863a8cdc418804b7838eff0e24"
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STEP2 = ROOT / "data/research/P2-DATA-002-step2-20261005"
OLD_PRIVATE = ROOT / "private/data002-step2/verified"
EXTRACTOR = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def stamp(path):
    return {"path": str(path), "sha256": sha(path.read_bytes())}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("Use a new alphanumeric run-id")
    public = OUT / "runs" / args.run_id
    private = ROOT / "private/data002-step34" / args.run_id
    baseline = ROOT / "tmp" / ("data002-step34-source-" + args.run_id)
    if any(p.exists() for p in (public, private, baseline)):
        raise ValueError("Existing run evidence must not be overwritten")
    for path in (public, private, baseline):
        path.mkdir(parents=True)
    report = {"task_id": "P2-DATA-002", "stages": [3, 4], "result": "running", "code_commit": COMMIT,
              "formal_task_completion": False, "model_calls": 0, "ocr_used": False,
              "search_executed": False, "three_product_flow_executed": False,
              "checks": [], "servers_stopped": False, "private_output": str(private.relative_to(ROOT))}
    processes, clients, handles = [], [], []
    source_paths = [ROOT / "harness/phase2/tasks/P2-DATA-001.json", ROOT / "harness/phase2/tasks/P2-DATA-002.json",
                    ROOT / "data/demo/dataset.json", ROOT / "packages/contracts/schemas/lgax.schema.json"]
    for folder in [ROOT / "data/research/P2-DATA-002-step1-20261005", STEP2, OLD_PRIVATE]:
        source_paths.extend(path for path in folder.rglob("*") if path.is_file())
    preserved = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in source_paths}

    def check(name, passed, *, boundary="observation", **details):
        report["checks"].append({"name": name, "passed": bool(passed), "boundary": boundary, **details})
        if not passed:
            raise AssertionError(name)

    try:
        archive = subprocess.run(["git", "archive", "--format=tar", COMMIT], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        report["source_archive_sha256"] = sha(archive)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            source.extractall(baseline, filter="data")
        paths = [baseline / "packages/core/src", baseline / "packages/contracts/src"]
        sys.path[:0] = [str(path) for path in paths]
        import httpx
        from jsonschema.exceptions import ValidationError
        from lgax_core import documents, review_csv
        from lgax_core.document_store import DocumentStore
        from lgax_core.errors import DomainError
        from lgax_core.store import DemoStore
        check("pinned_latest_main_imports", all(Path(m.__file__).resolve().is_relative_to(baseline)
                                               for m in (documents, review_csv)))
        report["source_files"] = [stamp(baseline / "packages/core/src/lgax_core" / name) for name in
                                  ("documents.py", "document_store.py", "documents_server.py", "review_csv.py",
                                   "review_csv_server.py", "pdf_text_worker.py", "store.py")]
        report["source_files"].append(stamp(baseline / "packages/contracts/schemas/lgax.schema.json"))
        report["runner"] = stamp(Path(__file__))
        (public / "executed-runner.py.txt").write_bytes(Path(__file__).read_bytes())
        step2_report = read(STEP2 / "runs/verified/registration-checks.json")
        check("STEP2_registered_inputs_passed", step2_report["result"] == "pass" and step2_report["servers_stopped"])
        report["previous_registration_report"] = stamp(STEP2 / "runs/verified/registration-checks.json")
        plan = read(STEP2 / "runs/verified/trusted-document-plan.json")
        spec = plan["documents"][0]
        dataset = read(OLD_PRIVATE / "dataset.json")
        for kind in ("pdf", "csv"):
            shutil.copytree(OLD_PRIVATE / (kind + "-store"), private / (kind + "-store"))
        write(private / "plan.json", plan)
        write(private / "dataset.json", dataset)
        pdf_repo = documents.DocumentRepository(private / "pdf-store", plan, str(EXTRACTOR))
        csv_repo = review_csv.ReviewCsvRepository(private / "csv-store", dataset)
        pdf_id, csv_id = spec["document_id"], csv_repo.source_id
        pdf_original, csv_original = pdf_repo.original(pdf_id), csv_repo.original(csv_id)
        check("copied_registered_original_hashes", sha(pdf_original) == spec["sha256"]
              and sha(csv_original) == step2_report["registered"]["csv"]["sha256"])
        pdf_metadata, csv_metadata = pdf_repo.metadata(pdf_id), csv_repo.metadata(csv_id)

        # Stage 3: actual extraction, no parser mocks or search endpoints.
        pdf_extracted = pdf_repo._parse(pdf_original)
        write(private / "fresh-pdf-extraction.json", pdf_extracted)
        check("PDF_all_40_pages_extracted", len(pdf_extracted["pages"]) == pdf_metadata["page_count"] == 40,
              boundary="actual_pdf_parser", parser=pdf_extracted["parser"], parser_version=pdf_extracted["parser_version"])
        check("PDF_parser_provenance_matches_registration", pdf_extracted["parser"] == pdf_metadata["parser"]
              and pdf_extracted["parser_version"] == pdf_metadata["parser_version"] and not pdf_extracted["ocr_used"])
        page_records = [{"page": i, "chars": len(text), "text_sha256": sha(text.encode())}
                        for i, text in enumerate(pdf_extracted["pages"], 1)]
        excerpt_records = []
        for evidence, origin in zip(pdf_metadata["dataset"]["evidence"], pdf_metadata["origins"], strict=True):
            page_text = pdf_extracted["pages"][origin["page"] - 1]
            selected = page_text[origin["start_char"]:origin["end_char"]]
            check("PDF_exact_registered_span_" + evidence["id"], selected == evidence["text"]
                  and sha(selected.encode()) == origin["text_sha256"]
                  and evidence["locator"]["page"] == origin["page"]
                  and evidence["model_id"] == spec["product"]["model_id"]
                  and evidence["document_version"] == spec["document_version"]
                  and evidence["source_id"] == pdf_id and evidence["source_kind"] == "public",
                  boundary="actual_pdf_parser")
            excerpt_records.append({"evidence_id": evidence["id"], "page": origin["page"],
                                    "start_char": origin["start_char"], "end_char": origin["end_char"],
                                    "text_sha256": origin["text_sha256"], "model_id": evidence["model_id"],
                                    "document_version": evidence["document_version"], "source_kind": "public"})
        csv_parsed = csv_repo._parse(csv_original)
        write(private / "fresh-csv-extraction.json", csv_parsed)
        input_rows = list(csv.DictReader(io.StringIO(csv_original.decode("utf-8"), newline="")))
        evidence_map = {e["id"]: e for e in csv_parsed["evidence"]}
        review_records = []
        for index, (review, row) in enumerate(zip(csv_parsed["reviews"], input_rows, strict=True), 2):
            origin = evidence_map[review["evidence_id"]]
            check("CSV_exact_row_" + review["id"], review["locator"]["row"] == int(row["row"]) == index
                  and all(review[k] == row[k] == origin[k] for k in
                          ("model_id", "document_version", "source_kind", "source_id", "text"))
                  and review["id"] == row["id"] and review["evidence_id"] == row["evidence_id"]
                  and review["locator"] == origin["locator"], boundary="actual_csv_parser")
            review_records.append({"review_id": review["id"], "evidence_id": review["evidence_id"],
                                   "row": index, "model_id": review["model_id"],
                                   "document_version": review["document_version"], "source_kind": review["source_kind"],
                                   "text_sha256": sha(review["text"].encode())})
        check("CSV_all_36_rows_and_existing_dataset_equal", len(review_records) == 36 and csv_parsed == dataset,
              boundary="actual_csv_parser")
        check("public_and_synthetic_kept_separate", pdf_metadata["dataset"]["reviews"] == []
              and all(r["source_kind"] == "synthetic" for r in csv_parsed["reviews"]))
        check("unmentioned_feature_remains_unclaimed", pdf_metadata["dataset"]["features"] == []
              and all(e["feature_ids"] == [] for e in pdf_metadata["dataset"]["evidence"]))
        write(public / "extraction-records.json", {"pdf_pages": page_records, "pdf_registered_excerpts": excerpt_records,
                                                   "csv_rows": review_records, "row_numbering": "CSV record, header is row 1"})

        # Contract checks use corrupted copies of actual registered entities.
        def reject(name, action, *, boundary):
            try:
                action()
            except (DomainError, ValidationError, ValueError, KeyError, TypeError) as error:
                check(name, True, boundary=boundary, exception_type=type(error).__name__,
                      error_code=getattr(error, "code", None), message=str(error)[:250])
            else:
                check(name, False, boundary=boundary)

        actual_pdf_dataset = pdf_metadata["dataset"]
        DocumentStore(actual_pdf_dataset)
        DemoStore(csv_parsed)
        for field in ("id", "model_id", "document_version", "source_kind", "source_id", "locator"):
            bad = deepcopy(actual_pdf_dataset)
            bad["evidence"][0].pop(field)
            reject("PDF_missing_evidence_" + field, lambda bad=bad: DocumentStore(bad), boundary="canonical_entity_validator")
        for field, value in [("model_id", "OTHER-MODEL"), ("document_version", "OTHER-VERSION"),
                             ("source_kind", "synthetic"), ("feature_ids", ["UNREGISTERED-FEATURE"])]:
            bad = deepcopy(actual_pdf_dataset)
            bad["evidence"][0][field] = value
            reject("PDF_inconsistent_evidence_" + field, lambda bad=bad: DocumentStore(bad), boundary="canonical_entity_validator")
        for collection in ("products", "evidence"):
            bad = deepcopy(actual_pdf_dataset)
            bad[collection].append(deepcopy(bad[collection][0]))
            reject("PDF_duplicate_" + collection, lambda bad=bad: DocumentStore(bad), boundary="canonical_entity_validator")
        for collection in ("reviews", "features", "evidence"):
            bad = deepcopy(csv_parsed)
            bad[collection].append(deepcopy(bad[collection][0]))
            if collection == "reviews":
                bad["manifest"]["review_count"] += 1
            reject("CSV_duplicate_canonical_" + collection, lambda bad=bad: DemoStore(bad), boundary="canonical_entity_validator")
        for field, value in [("model_id", "DISHWASHER-A"), ("document_version", "2.0")]:
            bad = deepcopy(csv_parsed)
            bad["features"][0][field] = value
            reject("CSV_cross_scope_feature_" + field, lambda bad=bad: DemoStore(bad), boundary="canonical_entity_validator")

        for field in ("document_version", "source_kind", "product"):
            bad_plan = deepcopy(plan)
            bad_plan["documents"][0].pop(field)
            reject("trusted_plan_missing_" + field,
                   lambda field=field, bad_plan=bad_plan: documents.DocumentRepository(private / ("plan-missing-" + field), bad_plan, str(EXTRACTOR)),
                   boundary="trusted_server_configuration")
        bad_plan = deepcopy(plan)
        bad_plan["dataset_version"] += "-other"
        reject("changed_plan_cannot_reuse_registered_directory",
               lambda: documents.DocumentRepository(private / "pdf-store", bad_plan, str(EXTRACTOR)),
               boundary="trusted_server_configuration")
        bad_dataset = deepcopy(dataset)
        bad_dataset["manifest"]["version"] += "-other"
        reject("changed_CSV_dataset_cannot_reuse_registered_directory",
               lambda: review_csv.ReviewCsvRepository(private / "csv-store", bad_dataset),
               boundary="trusted_server_configuration")

        # Actual PDF parsing must fail before writing logical records/originals.
        for name, mutate in [
            ("page_zero", lambda s: s.update(page=0)),
            ("page_past_end", lambda s: s.update(page=41)),
            ("wrong_page", lambda s: s.update(page=18)),
            ("missing_excerpt", lambda s: s.update(excerpt="DATA002 deliberate absent excerpt")),
        ]:
            bad_plan = deepcopy(plan)
            mutate(bad_plan["documents"][0]["selections"][0])
            directory = private / ("invalid-pdf-" + name)
            repo = documents.DocumentRepository(directory, bad_plan, str(EXTRACTOR))
            reject("PDF_real_parse_rejects_" + name, lambda repo=repo: repo.upload(pdf_id, pdf_original),
                   boundary="actual_pdf_parser_and_persistence")
            with sqlite3.connect(repo.db) as db:
                count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            check("PDF_failure_atomic_" + name, count == 0 and not list(directory.glob("*.pdf")),
                  boundary="persistence", document_rows=count)

        token = secrets.token_urlsafe(32)
        (private / "token.txt").write_text(token, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(map(str, paths))
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def start(kind, number):
            argv = [sys.executable, "-B", "-X", "utf8", "-m", "lgax_core." +
                    ("documents_server" if kind == "pdf" else "review_csv_server"),
                    "--directory", str(private / (kind + "-store")),
                    "--token-file", str(private / "token.txt"), "--port", str(number)]
            if kind == "pdf":
                argv += ["--plan", str(private / "plan.json"), "--extractor-python", str(EXTRACTOR)]
            else:
                argv += ["--dataset", str(private / "dataset.json")]
            log = (private / (kind + "-server-" + str(len(processes)) + ".log")).open("w", encoding="utf-8")
            handles.append(log)
            process = subprocess.Popen(argv, cwd=baseline, env=env, stdout=log, stderr=log,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            processes.append(process)
            report.setdefault("server_commands", []).append({"argv": argv, "pid": process.pid})
            client = httpx.Client(base_url=f"http://127.0.0.1:{number}",
                                  headers={"Authorization": "Bearer " + token}, timeout=100)
            clients.append(client)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Server exited; see private server log")
                try:
                    if client.get("/health", timeout=0.5).status_code == 200:
                        return process, client
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            raise RuntimeError("Server readiness timeout")

        def exchange(client, method, path, *, content=None, status=200, code=None):
            response = client.request(method, path, content=content)
            value = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            ordinal = report.setdefault("http_requests", 0) + 1
            report["http_requests"] = ordinal
            (private / (f"http-{ordinal}.body")).write_bytes(response.content)
            check(method + " " + path, response.status_code == status
                  and (code is None or value.get("error", {}).get("code") == code), boundary="actual_loopback_HTTP",
                  expected_status=status, actual_status=response.status_code, expected_error=code,
                  response_sha256=sha(response.content))
            return response, value

        def state(repo):
            record = repo.metadata(repo.source_id if hasattr(repo, "source_id") else pdf_id)
            with sqlite3.connect(repo.db) as db:
                count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            raw = repo.original(record["document_id"])
            return {"document_rows": count, "record_sha256": sha(json.dumps(record, sort_keys=True).encode()),
                    "original_sha256": sha(raw)}

        pdf_port, csv_port = free_port(), free_port()
        while pdf_port == csv_port:
            csv_port = free_port()
        pdf_process, pdf_client = start("pdf", pdf_port)
        csv_process, csv_client = start("csv", csv_port)
        pdf_path, csv_path = "/api/documents/" + pdf_id, "/api/documents/" + csv_id
        good_states = {"pdf": state(pdf_repo), "csv": state(csv_repo)}
        for kind, client, path, original, metadata in [("pdf", pdf_client, pdf_path, pdf_original, pdf_metadata),
                                                     ("csv", csv_client, csv_path, csv_original, csv_metadata)]:
            _, received = exchange(client, "GET", path)
            response, _ = exchange(client, "GET", path + "/original")
            check("latest_HTTP_registered_" + kind, received["data"] == metadata and response.content == original)

        mutations = []
        for field, value in [("id", ""), ("model_id", ""), ("document_version", ""), ("source_kind", ""),
                             ("source_id", ""), ("evidence_id", ""), ("row", ""), ("text", ""),
                             ("model_id", "WRONG-MODEL"), ("document_version", "2.0"),
                             ("source_kind", "public"), ("row", "999"), ("evidence_id", "WRONG-EVIDENCE")]:
            rows = deepcopy(input_rows)
            rows[0][field] = value
            mutations.append(("missing_" + field if value == "" else "altered_" + field, rows))
        rows = deepcopy(input_rows)
        rows[1]["id"] = rows[0]["id"]
        mutations.append(("duplicate_review_id", rows))
        rows = deepcopy(input_rows)
        rows[1]["evidence_id"] = rows[0]["evidence_id"]
        mutations.append(("duplicate_evidence_id", rows))
        mutations.append(("missing_review_record", deepcopy(input_rows[:-1])))
        mutations.append(("extra_review_record", deepcopy(input_rows + [input_rows[0]])))
        for name, rows in mutations:
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=review_csv.FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            raw = stream.getvalue().encode()
            (private / ("invalid-csv-" + name + ".csv")).write_bytes(raw)
            exchange(csv_client, "POST", csv_path, content=raw, status=400, code="PARSING_FAILED")
            check("CSV_failure_preserves_registration_" + name, state(csv_repo) == good_states["csv"], boundary="persistence")
        for name, raw, code in [("empty", b"", "INVALID_DOCUMENT"),
                                ("non_pdf", b"CSV is not a PDF", "INVALID_DOCUMENT"),
                                ("wrong_original", pdf_original + b"\nother", "SOURCE_MISMATCH")]:
            exchange(pdf_client, "POST", pdf_path, content=raw, status=400, code=code)
            check("PDF_failure_preserves_registration_" + name, state(pdf_repo) == good_states["pdf"], boundary="persistence")
        exchange(pdf_client, "POST", "/api/documents/WRONG-MODEL", content=pdf_original, status=404, code="INVALID_DOCUMENT_ID")
        check("wrong_document_id_does_not_persist", state(pdf_repo) == good_states["pdf"], boundary="persistence")

        for process in (pdf_process, csv_process):
            process.terminate()
            process.wait(timeout=10)
        _, pdf_reopened = start("pdf", pdf_port)
        _, csv_reopened = start("csv", csv_port)
        for kind, client, path, original, repo in [("pdf", pdf_reopened, pdf_path, pdf_original, pdf_repo),
                                                  ("csv", csv_reopened, csv_path, csv_original, csv_repo)]:
            _, received = exchange(client, "GET", path)
            response, _ = exchange(client, "GET", path + "/original")
            check("all_failures_then_restart_preserves_" + kind, received["data"] == repo.metadata(path.rsplit("/", 1)[-1])
                  and response.content == original and state(repo) == good_states[kind], boundary="persistence")
        report["persisted_after_all_checks"] = good_states
        report["preserved_previous_sources"] = {name: sha((ROOT / name).read_bytes()) == expected
                                                for name, expected in preserved.items()}
        check("STEP1_STEP2_and_unrelated_files_unchanged", all(report["preserved_previous_sources"].values()))
        report["extraction_summary"] = {"csv_reviews": 36, "csv_models": 5, "pdf_pages": 40,
                                        "registered_pdf_excerpts": len(excerpt_records), "pdf_features_claimed": 0,
                                        "CSV_negative_HTTP_cases": len(mutations), "PDF_atomic_failure_cases": 4}
        report["result"] = "pass"
    except Exception as error:
        report["result"] = "fail"
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        for client in clients:
            client.close()
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        for handle in handles:
            handle.close()
        report["servers_stopped"] = all(process.poll() is not None for process in processes)
        report["checked_at_kst"] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        write(public / "step34-checks.json", report)
        print(json.dumps({"result": report["result"], "checks": len(report["checks"]),
                          "http_requests": report.get("http_requests", 0), "servers_stopped": report["servers_stopped"],
                          "evidence": str((public / "step34-checks.json").relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
