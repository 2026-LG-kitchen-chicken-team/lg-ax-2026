"""Run the approved three originals through real local HTTP; never call an AI model."""

import argparse
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import lgax_core
from lgax_contracts import validate
from lgax_core.documents import DocumentRepository, digest
from lgax_core.errors import DomainError
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/research/P2-DATA-001-stage123-20261005"
PLAN = ROOT / "data/document_plans/lg-three-models-20261005.json"
SITUATIONS = {
    "T876MEE1H1": ("선반 청소·분리 조건 확인", "선반 분리와 내부 청소의 조건을 기존 기능과 대조", "선반"),
    "DUE6BGL2E": ("큰 접시와 냄비의 적재 조건 확인", "바구니 높이와 노즐 간섭 조건 대조", "바구니"),
    "MW23FDI": ("반복 가열 설정의 기존 지원 확인", "간편조리·출력 선택·제조사 메뉴와 개인 설정 저장을 구분", "30초"),
}


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor-python", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if not Path(lgax_core.__file__).resolve().is_relative_to(ROOT):
        raise RuntimeError("PYTHONPATH must select this worktree, not the original editable install")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    args.directory = args.directory.resolve()
    if not args.directory.is_relative_to(ROOT / "private"):
        raise ValueError("Originals and token must stay inside this worktree private directory")
    args.directory.mkdir(parents=True, exist_ok=True)
    token_file = args.directory / "local-token.txt"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    argv = [sys.executable, "-B", "-X", "utf8", "-m", "lgax_core.documents_server",
            "--directory", str(args.directory), "--plan", str(PLAN),
            "--extractor-python", args.extractor_python, "--token-file", str(token_file), "--port", str(port)]
    report = {"started_at": now(), "argv": argv, "scope": "approved three models / local HTTP",
              "core_python": sys.version, "core_executable": sys.executable, "core_module": lgax_core.__file__,
              "packages": {k: importlib.metadata.version(k) for k in ("jsonschema", "fastapi", "uvicorn")},
              "plan_sha256": digest(PLAN.read_bytes()), "requests": [], "checks": [],
              "authorization_header_recorded": False, "ai_model_calls": 0, "publication": False,
              "server_stopped": False, "success": False}
    base = f"http://127.0.0.1:{port}"
    token = ""

    def call(method, path, data=None, auth=True, extra_headers=None):
        headers = {"Authorization": "Bearer " + token} if auth else {}
        if data is not None:
            headers["Content-Type"] = "application/pdf"
        headers.update(extra_headers or {})
        request = Request(base + path, method=method, data=data, headers=headers)
        try:
            with urlopen(request, timeout=100) as response:
                status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        item = {"method": method, "url": base + path, "checked_at": now(),
                "input_bytes": len(data or b""), "input_sha256": digest(data) if data is not None else None,
                "status": status, "response_bytes": len(raw), "response_sha256": digest(raw)}
        body = json.loads(raw) if not raw.startswith(b"%PDF") else None
        if body is not None:
            item["response"] = body
        report["requests"].append(item)
        return status, body, raw

    def check(name, condition, **details):
        report["checks"].append({"name": name, "passed": bool(condition), **details})
        if not condition:
            raise AssertionError(name)

    log_path = args.directory / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(argv, cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError("Local document server exited before health check; inspect private server.log")
                if token_file.exists():
                    token = token_file.read_text(encoding="utf-8").strip()
                    try:
                        status, body, _ = call("GET", "/health")
                        if status == 200 and body["ok"]:
                            break
                    except URLError:
                        pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Local document server did not become ready")
            status, body, _ = call("GET", "/health", auth=False)
            check("missing_bearer_rejected", status == 401 and body["error"]["code"] == "UNAUTHORIZED")
            status, body, _ = call("GET", "/health", extra_headers={"Origin": "https://unrelated.example"})
            check("browser_origin_rejected", status == 403 and body["error"]["code"] == "INVALID_ORIGIN")
            records = []
            for spec in plan["documents"]:
                model, did = spec["product"]["model_id"], spec["document_id"]
                pdf = (ROOT / "private/documents-source" / (model + ".pdf")).read_bytes()
                status, body, _ = call("POST", "/api/documents/" + did, pdf)
                check(model + "_upload_parse_validate", status == 200 and body["ok"])
                record = body["data"]
                check(model + "_text_parser", record["parser"] == "pypdf" and not record["ocr_used"],
                      pages=record["page_count"], parser_version=record["parser_version"])
                records.append(record)
                status, metadata, _ = call("GET", "/api/documents/" + did)
                check(model + "_stored_metadata", status == 200 and metadata["data"] == record)
                status, _, original = call("GET", "/api/documents/" + did + "/original")
                check(model + "_original_round_trip", status == 200 and digest(original) == spec["sha256"])
                status, repeat, _ = call("POST", "/api/documents/" + did, pdf)
                check(model + "_idempotent", status == 200 and repeat["data"]["idempotent"]
                      and repeat["data"]["dataset"] == record["dataset"])
                query = {"q": SITUATIONS[model][2], "model_id": model, "document_version": spec["document_version"]}
                status, search, _ = call("GET", "/api/evidence/search?" + urlencode(query))
                check(model + "_scoped_search", status == 200 and search["data"]["total"] > 0)
                validate("EvidenceSearchResponse", search)
                for item in search["data"]["items"]:
                    check(item["id"] + "_metadata", item["model_id"] == model
                          and item["document_version"] == spec["document_version"]
                          and item["source_kind"] == "public" and item["source_id"] == did
                          and item["source_type"] == "manual" and item["locator"]["page"] > 0)
                for evidence in record["dataset"]["evidence"]:
                    status, fetched, _ = call("GET", "/api/evidence/" + evidence["id"])
                    check(evidence["id"] + "_retrieved_exact", status == 200 and fetched["data"]["evidence"] == evidence)
                    origin = next(o for o in record["origins"] if o["evidence_id"] == evidence["id"])
                    pages = json.loads((ROOT / "private/documents-source" / (model + ".pages.json"))
                                       .read_text(encoding="utf-8"))
                    check(evidence["id"] + "_original_location", pages[origin["page"] - 1]
                          [origin["start_char"]:origin["end_char"]] == evidence["text"]
                          and digest(evidence["text"].encode()) == origin["text_sha256"])
            wrong_pdf = (ROOT / "private/documents-source/DUE6BGL2E.pdf").read_bytes()
            status, body, _ = call("POST", "/api/documents/" + plan["documents"][0]["document_id"], wrong_pdf)
            check("wrong_model_original_rejected", status == 400 and body["error"]["code"] == "SOURCE_MISMATCH")
            for query, expected, code in [
                ({"q": "선반", "model_id": "OTHER"}, 404, "INVALID_MODEL_ID"),
                ({"q": "선반", "model_id": "T876MEE1H1", "document_version": "other-version"},
                 400, "INVALID_DOCUMENT_VERSION"),
            ]:
                status, body, _ = call("GET", "/api/evidence/search?" + urlencode(query))
                check(code, status == expected and body["error"]["code"] == code)
            status, body, _ = call("GET", "/api/evidence/unknown-evidence")
            check("unknown_evidence_rejected", status == 404 and body["error"]["code"] == "INVALID_EVIDENCE_ID")
            status, body, _ = call("GET", "/api/evidence/search?" + urlencode({"q": "unmatched-phrase-xyz", "model_id": "T876MEE1H1"}))
            check("valid_empty_query", status == 200 and body["data"]["total"] == 0)
            repository = DocumentRepository(args.directory, plan, args.extractor_python)
            dataset = repository.store().bootstrap()["data"]
            write(ROOT / "data/document_datasets/lg-three-models-20261005.json", dataset)
            write(RUN / "original-locations.json", {"documents": [{k: r[k] for k in
                  ("document_id", "sha256", "document_version", "source_kind", "url", "checked_at", "origins")}
                  for r in records]})
            planning_results = []
            for spec in plan["documents"]:
                product = spec["product"]
                model = product["model_id"]
                request = {"product_group": product["product_group"], "target_customer": "제출 원고 사용 상황 확인용 조사",
                           "use_situation": SITUATIONS[model][0], "improvement_task": SITUATIONS[model][1],
                           "model_ids": [model], "dataset_version": plan["dataset_version"],
                           "exclusions": ["실제 고객 리뷰 없음: 불편 빈도·수요·효과 추정 금지",
                                          "정의한 사례 기능 범위이며 LG 전체 기능 목록이 아님",
                                          "설명서에 없음은 기능 미지원의 증거가 아님",
                                          "다른 모델·문서 버전 근거 혼합 금지",
                                          "차이 2건·미확인 7건은 reference-pack sidecar에서 유지",
                                          "개인 설정 저장/호출 M16은 미확인; 미지원으로 단정 금지"]}
                validate("PlanningRequest", request)
                payload = build_planning_input(request, {model: product["document_version"]}, repository.store())
                check(model + "_full_defined_scope", {s["id"] for s in payload["sources"]}
                      == {s["evidence_id"] for s in spec["selections"]}
                      and {f["id"] for f in payload["features"]} == {f["id"] for f in spec["features"]})
                write(RUN / "planning-inputs" / (model + ".json"), payload)
                planning_results.append({"model_id": model, "version": product["document_version"],
                                         "source_ids": [s["id"] for s in payload["sources"]],
                                         "feature_ids": [f["id"] for f in payload["features"]],
                                         "public_sources_only": all(s["source_kind"] == "public" for s in payload["sources"]),
                                         "input_sha256": digest(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()),
                                         "actual_ai_execution": False})
                for scope_request, versions in [(request, {model: "other-version"}),
                                                ({**deepcopy(request), "model_ids": [model, "OTHER"]},
                                                 {model: product["document_version"]})]:
                    try:
                        build_planning_input(scope_request, versions, repository.store())
                    except DomainError as error:
                        check(model + "_invalid_planning_scope_rejected", error.code == "NOT_IMPLEMENTED", reason=error.details)
                    else:
                        check(model + "_invalid_planning_scope_rejected", False)
            write(RUN / "planning-contract.json", {"success": True, "models": planning_results,
                  "all_defined_sources_features_included": True, "actual_ai_execution": False,
                  "missing_original_reviews": 3, "does_not_prove": "AI judgement or demand validation or PM acceptance"})
            report["success"] = True
        except Exception as error:
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            report["server_stopped"] = process.poll() is not None
            report["finished_at"] = now()
            write(RUN / "http-flow.json", report)
    # Reopen after the serving process exits, rather than infer persistence from HTTP.
    repository = DocumentRepository(args.directory, plan, args.extractor_python)
    persistent = repository.store().search_evidence("선반", "T876MEE1H1")
    check("restart_persistence", persistent["data"]["total"] > 0)
    report["finished_at"] = now()
    write(RUN / "http-flow.json", report)
    print(json.dumps({"success": report["success"], "http_requests": len(report["requests"]),
                      "checks_passed": len(report["checks"]), "products": len(dataset["products"]),
                      "features": len(dataset["features"]), "evidence": len(dataset["evidence"]),
                      "original_reviews": len(dataset["reviews"]), "server_stopped": report["server_stopped"]}))


if __name__ == "__main__":
    main()
