"""Execute bounded DATA002 stage 5 on actual registered CSV/PDF HTTP services."""
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
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMMIT = "bbf4e1c1da0106e140c6c7e87f7159e6f0fe3532"
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PREVIOUS = ROOT / "private/data002-step34/initial"
EXTRACTOR = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text("utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")


def stamp(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_closed(port):
    # Timeout is unknown. On Windows separately inspect successful native netstat.
    with socket.socket() as sock:
        sock.settimeout(0.5)
        code = sock.connect_ex(("127.0.0.1", port))
    result = {"port": port, "connect_code": code, "closed": code in {10061, 111},
              "closure_basis": "explicit_connection_refusal" if code in {10061, 111} else "unknown"}
    if os.name == "nt":
        observed = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=10, check=False)
        rows = [line.split() for line in observed.stdout.splitlines() if line.strip().startswith("TCP ")]
        valid = observed.returncode == 0 and bool(rows) and all(len(row) == 5 and row[-1].isdigit() for row in rows)
        own_rows = [row for row in rows if row[1] == f"127.0.0.1:{port}"]
        listeners = [row for row in own_rows if row[3] == "LISTENING"]
        result.update(native_netstat_exit=observed.returncode, native_netstat_valid=valid,
                      own_port_rows=own_rows, listener_pids=[int(row[-1]) for row in listeners])
        if valid:
            result["closed"] = not listeners
            result["closure_basis"] = "successful_native_netstat_no_listener" if not listeners else "native_netstat_listener_present"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        raise ValueError("Use a new alphanumeric run-id")
    public = OUT / "runs" / args.run_id
    private = ROOT / "private/data002-step5" / args.run_id
    source = ROOT / "tmp" / ("data002-step5-source-" + args.run_id)
    if any(p.exists() for p in (public, private, source)):
        raise ValueError("Previous run evidence must not be overwritten")
    for folder in (public, private, source):
        folder.mkdir(parents=True)
    report = {"task_id": "P2-DATA-002", "stage": 5, "result": "running", "code_commit": COMMIT,
              "model_calls": 0, "ocr_used": False, "private_evaluation_read": False,
              "formal_task_completion": False, "published": False, "three_product_flow_executed": False,
              "checks": [], "http_requests": 0, "private_output": str(private.relative_to(ROOT))}
    processes, clients, handles, ports, traces = [], [], [], {}, []
    preserved_files = [ROOT / name for name in ("data/demo/dataset.json", "packages/contracts/schemas/lgax.schema.json",
                                               "harness/phase2/tasks/P2-DATA-001.json", "harness/phase2/tasks/P2-DATA-002.json")]
    for folder in [PREVIOUS, ROOT / "private/data002-step2/verified", *[ROOT / "data/research" / name for name in
                   ("P2-DATA-002-step1-20261005", "P2-DATA-002-step2-20261005", "P2-DATA-002-step34-20261005")]]:
        preserved_files.extend(p for p in folder.rglob("*") if p.is_file())
    preserved = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in preserved_files}

    def check(name, passed, **details):
        report["checks"].append({"name": name, "passed": bool(passed), **details})
        if not passed:
            raise AssertionError(name)

    try:
        archive = subprocess.run(["git", "archive", "--format=tar", COMMIT], cwd=ROOT, capture_output=True, check=True).stdout
        report["source_archive_sha256"] = sha(archive)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(source, filter="data")
        package_paths = [source / "packages/core/src", source / "packages/contracts/src"]
        sys.path[:0] = list(map(str, package_paths))
        import httpx
        from lgax_contracts import validate
        from lgax_core import documents, review_csv, store
        check("imports_from_pinned_source", all(Path(m.__file__).resolve().is_relative_to(source)
                                               for m in (documents, review_csv, store)))
        names = ("documents.py", "document_store.py", "documents_server.py", "review_csv.py",
                 "review_csv_server.py", "store.py", "pdf_text_worker.py")
        report["source_files"] = [stamp(source / "packages/core/src/lgax_core" / name) for name in names]
        report["source_files"].append(stamp(source / "packages/contracts/schemas/lgax.schema.json"))
        report["runner"] = stamp(Path(__file__))
        (public / "executed-runner.py.txt").write_bytes(Path(__file__).read_bytes())
        previous_report = ROOT / "data/research/P2-DATA-002-step34-20261005/runs/initial/completion-review.json"
        check("STEP34_scope_execution_passed", read(previous_report)["requested_scope_result"] == "pass")
        report["previous_completion_report"] = stamp(previous_report)
        plan, dataset = read(PREVIOUS / "plan.json"), read(PREVIOUS / "dataset.json")
        spec = plan["documents"][0]
        for kind in ("pdf", "csv"):
            shutil.copytree(PREVIOUS / (kind + "-store"), private / (kind + "-store"))
        write(private / "plan.json", plan)
        write(private / "dataset.json", dataset)
        pdf_repo = documents.DocumentRepository(private / "pdf-store", plan, str(EXTRACTOR))
        csv_repo = review_csv.ReviewCsvRepository(private / "csv-store", dataset)
        repositories = {"pdf": pdf_repo, "csv": csv_repo}
        ids = {"pdf": spec["document_id"], "csv": csv_repo.source_id}
        originals = {kind: repo.original(ids[kind]) for kind, repo in repositories.items()}
        metadata = {kind: repo.metadata(ids[kind]) for kind, repo in repositories.items()}
        check("copied_registration_hashes", all(sha(originals[k]) == metadata[k]["sha256"] for k in ids))
        token = secrets.token_urlsafe(32)
        (private / "token.txt").write_text(token, "utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(map(str, package_paths))
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def start(kind, port):
            argv = [sys.executable, "-B", "-X", "utf8", "-m", "lgax_core." +
                    ("documents_server" if kind == "pdf" else "review_csv_server"),
                    "--directory", str(private / (kind + "-store")), "--token-file", str(private / "token.txt"),
                    "--port", str(port)]
            if kind == "pdf":
                argv += ["--plan", str(private / "plan.json"), "--extractor-python", str(EXTRACTOR)]
            else:
                argv += ["--dataset", str(private / "dataset.json")]
            handle = (private / (kind + "-server-" + str(len(processes)) + ".log")).open("w", encoding="utf-8")
            handles.append(handle)
            process = subprocess.Popen(argv, cwd=source, env=env, stdout=handle, stderr=handle,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            processes.append(process)
            report.setdefault("server_commands", []).append({"argv": argv, "pid": process.pid})
            client = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"Authorization": "Bearer " + token},
                                  timeout=30, trust_env=False)
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

        def get(client, path, *, params=None, status=200, code=None, headers=None):
            response = client.get(path, params=params, headers=headers)
            value = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            report["http_requests"] += 1
            ordinal = report["http_requests"]
            target = private / (f"http-{ordinal}.body")
            target.write_bytes(response.content)
            safe_params = {key: sha(val.encode()) if key == "q" else val for key, val in (params or {}).items()}
            check("HTTP-" + str(ordinal), response.status_code == status and
                  (code is None or value.get("error", {}).get("code") == code),
                  boundary="actual_loopback_HTTP", path=path, params_q_is_sha256=safe_params,
                  expected_status=status, actual_status=response.status_code, expected_error=code,
                  response_sha256=sha(response.content), private_body=str(target.relative_to(ROOT)))
            if status == 200 and path.startswith("/api/evidence/"):
                validate("EvidenceSearchResponse" if path == "/api/evidence/search" else "EvidenceResponse", value)
            return response, value

        running = {}
        for kind in ids:
            ports[kind] = free_port()
            running[kind] = start(kind, ports[kind])
            observation = port_closed(ports[kind])
            check("own_listener_observed_running_" + kind, not observation["closed"]
                  and bool(observation.get("listener_pids")) if os.name == "nt" else observation["connect_code"] == 0,
                  port_observation=observation)
        report["ports"] = ports
        downloaded = {}
        for kind, document_id in ids.items():
            client = running[kind][1]
            _, body = get(client, "/api/documents/" + document_id)
            response, _ = get(client, "/api/documents/" + document_id + "/original")
            downloaded[kind] = response.content
            check("HTTP_original_and_metadata_" + kind, body["data"] == metadata[kind]
                  and response.content == originals[kind] and sha(response.content) == metadata[kind]["sha256"])
        csv_rows = list(csv.DictReader(io.StringIO(downloaded["csv"].decode("utf-8"), newline="")))
        pdf_pages = pdf_repo._parse(downloaded["pdf"])
        write(private / "fresh-pdf-extraction.json", pdf_pages)
        check("actual_pdf_reextraction_40_pages", len(pdf_pages["pages"]) == 40 and not pdf_pages["ocr_used"])
        evidence_map = {item["id"]: item for item in dataset["evidence"]}

        # Every registered review is searched and fetched from the running CSV service.
        for review in dataset["reviews"]:
            params = {"q": review["text"], "model_id": review["model_id"],
                      "document_version": review["document_version"], "limit": 50}
            _, result = get(running["csv"][1], "/api/evidence/search", params=params)
            data = result["data"]
            check("CSV_scope_" + review["id"], bool(data["items"]) and data["model_id"] == review["model_id"]
                  and data["document_version"] == review["document_version"] and
                  all(e["model_id"] == review["model_id"] and e["document_version"] == review["document_version"]
                      and e["source_kind"] == "synthetic" and e == evidence_map[e["id"]] for e in data["items"])
                  and review["evidence_id"] in {e["id"] for e in data["items"]})
            _, fetched = get(running["csv"][1], "/api/evidence/" + review["evidence_id"])
            evidence = fetched["data"]["evidence"]
            row_number = review["locator"]["row"]
            row = csv_rows[row_number - 2]
            check("CSV_original_row_trace_" + review["id"], evidence == evidence_map[review["evidence_id"]]
                  and row["id"] == review["id"] and row["evidence_id"] == evidence["id"]
                  and int(row["row"]) == row_number and evidence["source_type"] == "review"
                  and all(row[k] == review[k] == evidence[k] for k in
                          ("model_id", "document_version", "source_kind", "source_id", "text")))
            traces.append({"review_id": review["id"], "evidence_id": evidence["id"], "model_id": evidence["model_id"],
                           "document_version": evidence["document_version"], "source_kind": evidence["source_kind"],
                           "source_id": evidence["source_id"], "locator": evidence["locator"],
                           "text_sha256": sha(evidence["text"].encode()), "original_sha256": sha(downloaded["csv"]),
                           "search_query_sha256": sha(review["text"].encode()), "raw_row_exact": True})

        # The selected public excerpt must trace through metadata into freshly parsed original bytes.
        pdf_params = {"q": "선반", "model_id": spec["product"]["model_id"],
                      "document_version": spec["document_version"], "limit": 50}
        _, pdf_search = get(running["pdf"][1], "/api/evidence/search", params=pdf_params)
        check("PDF_search_exact_registered_scope", pdf_search["data"]["items"] == metadata["pdf"]["dataset"]["evidence"]
              and pdf_search["data"]["total"] == 1 and pdf_search["data"]["search_method"] == "literal_token_count")
        for origin in metadata["pdf"]["origins"]:
            _, result = get(running["pdf"][1], "/api/evidence/" + origin["evidence_id"])
            evidence = result["data"]["evidence"]
            text = pdf_pages["pages"][origin["page"] - 1][origin["start_char"]:origin["end_char"]]
            check("PDF_original_page_span_trace", text == evidence["text"] and sha(text.encode()) == origin["text_sha256"]
                  and evidence["locator"]["page"] == origin["page"] == 19 and evidence["model_id"] == spec["product"]["model_id"]
                  and evidence["source_id"] == ids["pdf"] and evidence["document_version"] == origin["document_version"]
                  and evidence["source_kind"] == "public" and evidence["feature_ids"] == []
                  and origin["sha256"] == sha(downloaded["pdf"]))
            traces.append({"evidence_id": evidence["id"], "model_id": evidence["model_id"],
                           "document_version": evidence["document_version"], "source_kind": evidence["source_kind"],
                           "source_id": evidence["source_id"], "locator": evidence["locator"],
                           "start_char": origin["start_char"], "end_char": origin["end_char"],
                           "text_sha256": origin["text_sha256"], "original_sha256": origin["sha256"],
                           "raw_page_span_exact": True, "model_feature_applicability_confirmed": False})

        # Positive isolation includes two existing versions of the same synthetic model.
        isolation = []
        for model in [p["model_id"] for p in dataset["products"]]:
            versions = sorted({e["document_version"] for e in dataset["evidence"] if e["model_id"] == model})
            for version in versions:
                query = "분리 청소 버튼 세척 선반"
                _, result = get(running["csv"][1], "/api/evidence/search",
                                params={"q": query, "model_id": model, "document_version": version, "limit": 50})
                items = result["data"]["items"]
                check("positive_model_version_isolation_" + model + "_" + version,
                      bool(items) and all(e["model_id"] == model and e["document_version"] == version for e in items))
                isolation.append({"model_id": model, "document_version": version, "returned_ids": [e["id"] for e in items]})
        _, broad = get(running["csv"][1], "/api/evidence/search", params={"q": "분리 청소 버튼 세척 선반", "limit": 50})
        check("unfiltered_search_requires_explicit_consumer_scope", len({e["model_id"] for e in broad["data"]["items"]}) > 1)
        _, limited = get(running["csv"][1], "/api/evidence/search", params={"q": "선반", "limit": 1})
        check("limit_changes_items_but_keeps_total", len(limited["data"]["items"]) == 1 and limited["data"]["total"] > 1)
        for kind in ids:
            client = running[kind][1]
            model = spec["product"]["model_id"] if kind == "pdf" else dataset["products"][0]["model_id"]
            version = spec["document_version"] if kind == "pdf" else "1.0"
            cases = [({"q": "선반", "model_id": "NO-SUCH-MODEL"}, 404, "INVALID_MODEL_ID"),
                     ({"q": "선반", "model_id": model, "document_version": "NO-SUCH-VERSION"}, 400, "INVALID_DOCUMENT_VERSION"),
                     ({"q": "선반", "document_version": version}, 400, "INVALID_ARGUMENT"),
                     ({"q": " "}, 400, "INVALID_ARGUMENT"), ({"q": "!"}, 400, "INVALID_ARGUMENT"),
                     ({"q": "가" * 501}, 400, "INVALID_ARGUMENT"),
                     ({"q": "선반", "limit": 0}, 400, "INVALID_ARGUMENT"),
                     ({"q": "선반", "limit": 51}, 400, "INVALID_ARGUMENT"),
                     ({"q": "선반", "limit": "bad"}, 422, None), ({}, 422, None)]
            for params, status, code in cases:
                get(client, "/api/evidence/search", params=params, status=status, code=code)
            get(client, "/api/evidence/NO-SUCH-EVIDENCE", status=404, code="INVALID_EVIDENCE_ID")
            _, empty = get(client, "/api/evidence/search",
                           params={"q": "DATA002ABSENTKEYWORD20261005", "model_id": model, "document_version": version})
            check("zero_results_are_empty_evidence_" + kind, empty["data"]["items"] == [] and empty["data"]["total"] == 0
                  and "supported" not in empty["data"] and "unsupported" not in empty["data"])
        get(running["csv"][1], "/api/evidence/" + spec["selections"][0]["evidence_id"], status=404, code="INVALID_EVIDENCE_ID")
        get(running["pdf"][1], "/api/evidence/" + dataset["reviews"][0]["evidence_id"], status=404, code="INVALID_EVIDENCE_ID")
        get(running["csv"][1], "/api/evidence/search", params={"q": "선반", "model_id": spec["product"]["model_id"]},
            status=404, code="INVALID_MODEL_ID")
        get(running["pdf"][1], "/api/evidence/search", params={"q": "선반", "model_id": "FRIDGE-A"},
            status=404, code="INVALID_MODEL_ID")
        get(running["pdf"][1], "/api/evidence/search", params=pdf_params,
            headers={"Authorization": "Bearer invalid"}, status=401, code="UNAUTHORIZED")
        get(running["pdf"][1], "/api/evidence/search", params=pdf_params,
            headers={"Origin": "https://example.invalid"}, status=403, code="INVALID_ORIGIN")
        check("public_unmentioned_features_not_claimed", metadata["pdf"]["dataset"]["features"] == []
              and metadata["pdf"]["dataset"]["reviews"] == [])

        for process, client in running.values():
            client.close()
            process.terminate()
            process.wait(timeout=10)
        for kind, document_id in ids.items():
            observation = port_closed(ports[kind])
            check("own_listener_closed_before_restart_" + kind, observation["closed"], port_observation=observation)
            _, client = start(kind, ports[kind])
            params = pdf_params if kind == "pdf" else {"q": dataset["reviews"][0]["text"], "model_id": "FRIDGE-A",
                                                       "document_version": "1.0", "limit": 50}
            _, result = get(client, "/api/evidence/search", params=params)
            expected_id = spec["selections"][0]["evidence_id"] if kind == "pdf" else dataset["reviews"][0]["evidence_id"]
            _, evidence = get(client, "/api/evidence/" + expected_id)
            response, _ = get(client, "/api/documents/" + document_id + "/original")
            check("restart_search_evidence_original_preserved_" + kind,
                  expected_id in {e["id"] for e in result["data"]["items"]}
                  and evidence["data"]["evidence"] == (metadata["pdf"]["dataset"]["evidence"][0] if kind == "pdf" else evidence_map[expected_id])
                  and response.content == downloaded[kind] and repositories[kind].metadata(document_id) == metadata[kind])
        report["preserved_sources"] = {name: sha((ROOT / name).read_bytes()) == digest for name, digest in preserved.items()}
        check("previous_inputs_evidence_data_tasks_contracts_unchanged", all(report["preserved_sources"].values()))
        write(public / "original-traces.json", {"csv_review_traces": traces[:-1], "pdf_excerpt_trace": traces[-1],
                                                "csv_row_numbering": "Header row1; records rows2..37",
                                                "full_text_in_private_only": True})
        write(public / "filter-isolation.json", {"positive_model_versions": isolation,
                                                  "unfiltered_search_can_include_other_models": True,
                                                  "get_evidence_accepts_id_only": True,
                                                  "consumer_must_check_selected_model_and_version": True})
        report["summary"] = {"review_original_traces": len(traces) - 1, "registered_pdf_excerpt_traces": 1,
                             "actual_pdf_pages": 40, "csv_models": 5, "model_version_combinations": len(isolation),
                             "search_method": "literal_token_count", "public_feature_claims": 0,
                             "real_customer_reviews": 0, "search_quality_evaluation": False}
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
        report["servers_stopped"] = all(p.poll() is not None for p in processes)
        report["port_closure"] = [port_closed(port) for port in ports.values()]
        report["all_own_listeners_closed"] = all(p["closed"] for p in report["port_closure"])
        if not report["servers_stopped"] or not report["all_own_listeners_closed"]:
            report["result"] = "fail"
        report["checked_at_kst"] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        write(public / "search-checks.json", report)
        print(json.dumps({"result": report["result"], "checks": len(report["checks"]), "http_requests": report["http_requests"],
                          "servers_stopped": report["servers_stopped"], "listeners_closed": report["all_own_listeners_closed"],
                          "evidence": str((public / "search-checks.json").relative_to(ROOT))}, ensure_ascii=False))
    if report["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
