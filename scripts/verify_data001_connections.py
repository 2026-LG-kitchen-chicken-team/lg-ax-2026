"""Real loopback transport verification; full synthetic content stays in private/."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import lgax_core
from lgax_contracts import validate
from lgax_core.document_workspace import WorkspaceDocumentStore
from lgax_core.documents import digest
from lgax_core.review_csv import serialize_existing_reviews

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/research/P2-DATA-001-stage345-20261005"
PRIVATE = ROOT / "private/document-runs/stage345-connections"
MODEL_ENV = ("LGAX_MODEL_ADAPTER", "LGAX_MODEL_ENDPOINT", "LGAX_MODEL_ID", "LGAX_MODEL_DIGEST")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    if not Path(lgax_core.__file__).resolve().is_relative_to(ROOT):
        raise RuntimeError("Select this worktree through PYTHONPATH")
    if any(os.environ.get(k) for k in MODEL_ENV):
        raise RuntimeError("This failure-path verifier must not use a configured AI service")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    report = {"started_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "core_python": sys.version, "core_module": lgax_core.__file__, "commands": [],
              "requests": [], "checks": [], "models": [], "ai_model_calls": 0,
              "synthetic_originals_public": False, "publication": False, "success": False}
    private_requests = []

    def check(name, value, **details):
        report["checks"].append({"name": name, "passed": bool(value), **details})
        if not value:
            raise AssertionError(name)

    def call(base, token, method, path, data=None, *, binary=False, auth=True):
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode() if data else None
        headers = {"Authorization": "Bearer " + token} if auth else {}
        headers["Content-Type"] = "text/csv" if isinstance(data, bytes) else "application/json"
        request = Request(base + path, method=method, headers=headers, data=raw)
        try:
            with urlopen(request, timeout=30) as response:
                status, result = response.status, response.read()
        except HTTPError as error:
            status, result = error.code, error.read()
        body = None if binary else json.loads(result)
        report["requests"].append({"method": method, "url": base + path, "status": status,
                                   "input_bytes": len(raw or b""), "input_sha256": digest(raw) if raw else None,
                                   "response_bytes": len(result), "response_sha256": digest(result)})
        private_requests.append({"method": method, "path": path, "status": status, "response": body})
        return status, body, result

    def start(module, arguments, token, role):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        argv = [sys.executable, "-B", "-X", "utf8", "-m", module, *arguments, "--port", str(port)]
        report["commands"].append({"role": role, "argv": argv})
        log = (PRIVATE / (role + ".log")).open("w", encoding="utf-8")
        process = subprocess.Popen(argv, cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"{role} server stopped; inspect its private log")
                try:
                    if call(base, token, "GET", "/health")[0] == 200:
                        return process, log, base
                except URLError:
                    pass
                time.sleep(.15)
            raise RuntimeError(f"{role} health unavailable")
        except Exception:
            process.terminate()
            process.wait(timeout=10)
            log.close()
            raise

    def stop(process, log):
        process.terminate()
        process.wait(timeout=10)
        log.close()

    try:
        demo_path = ROOT / "data/demo/dataset.json"
        demo = json.loads(demo_path.read_text("utf-8"))
        csv_bytes = serialize_existing_reviews(demo)
        (PRIVATE / "derived-existing-reviews.csv").write_bytes(csv_bytes)
        token = secrets.token_urlsafe(32)
        token_file = PRIVATE / "csv-token.txt"
        token_file.write_text(token, encoding="utf-8")
        args = ["--directory", str(PRIVATE / "csv"), "--dataset", str(demo_path),
                "--token-file", str(token_file)]
        process, log, base = start("lgax_core.review_csv_server", args, token, "review-csv")
        source = demo["reviews"][0]["source_id"]
        path = "/api/documents/" + source
        try:
            check("csv_unauthorized_rejected", call(base, token, "GET", path, auth=False)[0] == 401)
            status, record, _ = call(base, token, "POST", path, csv_bytes)
            check("csv_actual_upload_parse_validate", status == 200 and record["data"]["review_count"] == 36)
            check("csv_synthetic_preserved", record["data"]["source_kind"] == "synthetic")
            check("csv_repeat_idempotent", call(base, token, "POST", path, csv_bytes)[1] == record)
            check("csv_original_bytes", call(base, token, "GET", path + "/original", binary=True)[2] == csv_bytes)
            check("csv_bad_header_rejected", call(base, token, "POST", path, b"id,text\nx,y\n")[0] == 400)
            refs = []
            for review in demo["reviews"]:
                status, body, _ = call(base, token, "GET", "/api/evidence/" + review["evidence_id"])
                evidence = body["data"]["evidence"]
                check("csv_original_row_" + review["id"], status == 200 and all(
                    evidence[k] == review[k] for k in
                    ("model_id", "source_kind", "document_version", "source_id", "locator", "text")))
                refs.append({k: evidence[k] for k in
                             ("id", "model_id", "source_id", "locator", "document_version", "source_kind")})
            first = demo["reviews"][0]
            q = urlencode({"q": first["text"], "model_id": first["model_id"], "document_version": first["document_version"]})
            # The request URL contains synthetic text, so keep that URL private too.
            status, body, _ = call(base, token, "GET", "/api/evidence/search?" + q)
            report["requests"][-1]["url"] = base + "/api/evidence/search?<synthetic-query-redacted>"
            check("csv_query_actual_path", status == 200 and first["evidence_id"] in
                  [x["id"] for x in body["data"]["items"]])
            report["synthetic_transport"] = {"derived_from_json_sha256": digest(demo_path.read_bytes()),
                                             "csv_sha256": digest(csv_bytes), "historical_csv_recovered": False,
                                             "model_count": 5, "review_count": 36, "evidence_count": 42,
                                             "review_references": refs}
        finally:
            stop(process, log)
        process, log, base = start("lgax_core.review_csv_server", args, token, "review-csv-reopen")
        try:
            check("csv_persistence_after_restart", call(base, token, "GET", path)[1] == record)
        finally:
            stop(process, log)

        doc_path = ROOT / "data/document_datasets/lg-three-models-20261005.json"
        dataset = json.loads(doc_path.read_text("utf-8"))
        document_store = WorkspaceDocumentStore(dataset)
        check("real_demo_separation", dataset["reviews"] == [] and
              all(x["source_kind"] == "public" for x in dataset["products"] + dataset["evidence"]))
        token = secrets.token_urlsafe(32)
        credentials = PRIVATE / "workspace-credentials.json"
        write(credentials, {"credentials": [{"principal_id": "data001-local-verifier", "role": "editor",
                                             "token_sha256": digest(token.encode())}]})
        args = ["--dataset", str(doc_path), "--db", str(PRIVATE / "workspace.sqlite"),
                "--credentials", str(credentials), "--enable-planning"]
        process, log, base = start("lgax_core.document_workspace", args, token, "real-workspace")
        snapshots = []
        try:
            check("workspace_auth_preserved", call(base, token, "GET", "/api/workspace/projects", auth=False)[0] == 401)
            queries = {"T876MEE1H1": "선반", "DUE6BGL2E": "바구니", "MW23FDI": "30초"}
            for product in dataset["products"]:
                model, version = product["model_id"], product["document_version"]
                payload = json.loads((ROOT / "data/research/P2-DATA-001-stage123-20261005/planning-inputs" /
                                      (model + ".json")).read_text("utf-8"))
                versions = {model: version}
                request = payload["request"]
                status, body, _ = call(base, token, "POST", "/api/workspace/projects",
                                      {"name": model + " 자료 연결 확인", "request": request, "document_versions": versions})
                validate("WorkspaceProjectResponse", body)
                check("workspace_project_" + model, status == 201 and body["data"]["document_versions"] == versions)
                project = body["data"]["project"]["id"]
                query_path = f"/api/workspace/projects/{project}/evidence?" + urlencode({"q": queries[model], "model_id": model})
                status, search, _ = call(base, token, "GET", query_path)
                validate("WorkspaceEvidenceResponse", search)
                items = search["data"]["search"]["data"]["items"]
                check("workspace_real_provenance_" + model, status == 200 and bool(items) and all(
                    e["model_id"] == model and e["document_version"] == version and e["source_kind"] == "public"
                    and e["source_id"] and e["locator"].get("page") for e in items))
                other = next(x["model_id"] for x in dataset["products"] if x["model_id"] != model)
                check("workspace_other_model_rejected_" + model, call(base, token, "GET",
                      f"/api/workspace/projects/{project}/evidence?" + urlencode({"q": "a", "model_id": other}))[0] == 422)
                bad_versions = {model: version + "-wrong"}
                check("workspace_wrong_version_rejected_" + model, call(base, token, "POST", "/api/workspace/projects",
                      {"name": "잘못된 버전 확인", "request": request, "document_versions": bad_versions})[0] == 422)
                status, run, _ = call(base, token, "POST", f"/api/workspace/projects/{project}/runs",
                                     {"request": request, "previous_run_id": None,
                                      "unconfirmed": ["실제 고객 리뷰 없음", "모델 서비스 연결 확인 대기"]})
                validate("WorkspaceRunResponse", run)
                snapshot = run["data"]
                check("workspace_failed_run_saved_" + model, status == 201 and snapshot["run"]["status"] == "failed")
                execution = snapshot["output"]["planning_execution"]
                check("workspace_no_false_AI_success_" + model, execution["status"] == "failed" and
                      execution["model_calls"] == [] and execution["output"] is None)
                check("workspace_full_scope_input_" + model, execution["original_input"] == payload)
                refs = [{k: e[k] for k in ("id", "model_id", "source_id", "locator", "document_version", "source_kind")}
                        for e in items]
                report["models"].append({"model_id": model, "document_version": version, "source_kind": "public",
                                         "project_id": project, "run_id": snapshot["run"]["id"],
                                         "query_evidence": refs, "feature_count": len(payload["features"]),
                                         "input_evidence_count": len(payload["sources"]), "real_review_count": 0,
                                         "AI_status": "failed", "error_codes": [e["code"] for e in execution["errors"]],
                                         "input_sha256": digest(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())})
                snapshots.append(snapshot)
        finally:
            stop(process, log)
        process, log, base = start("lgax_core.document_workspace", args, token, "real-workspace-reopen")
        try:
            for snapshot in snapshots:
                status, body, _ = call(base, token, "GET", "/api/workspace/runs/" + snapshot["run"]["id"])
                check("workspace_snapshot_persisted_" + snapshot["request"]["model_ids"][0],
                      status == 200 and body["data"] == snapshot)
        finally:
            stop(process, log)
        report["success"] = True
        report["document_dataset_sha256"] = digest(doc_path.read_bytes())
        report["document_container"] = document_store.bootstrap()["data"]["manifest"]
    except Exception as error:
        report["failure_type"] = type(error).__name__
        report["failure"] = str(error)
        raise
    finally:
        report["finished_at"] = datetime.now(timezone(timedelta(hours=9))).isoformat()
        report["servers_stopped"] = True
        write(PRIVATE / "full-http-responses.json", private_requests)
        write(PUBLIC / "connections-results.json", report)
        print(json.dumps({"success": report["success"], "checks": len(report["checks"]),
                          "requests": len(report["requests"]), "ai_model_calls": 0,
                          "public_report": str(PUBLIC / "connections-results.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
