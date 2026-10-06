"""Real loopback HTTP and preserved public PDFs; no model, central job or OCR.

Run in a fresh output directory. An ephemeral owned socket and SQLite scope are
stopped and reopened. Tokens and retained originals stay outside the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from lgax_core.documents import DocumentRepository
from lgax_core.documents_server import create_app

ROOT = Path(__file__).resolve().parents[3]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pin = json.loads((ROOT / "evals/pm-data-intake/20261006/parser-wheel.json").read_bytes())
    wheel = ROOT / pin["path"]
    assert sha(wheel.read_bytes()) == pin["sha256"]
    previous_path = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(wheel) + os.pathsep + (previous_path or "")
    plan_path = ROOT / "data/research/PM-DATA-intake-20261006/generated/plan.json"
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    token = secrets.token_urlsafe(48)
    receipt = {"execution_kind": "actual_loopback_http", "source_kind": "public",
               "plan_path": str(plan_path.relative_to(ROOT)).replace("\\", "/"),
               "plan_sha256": sha(plan_raw), "dataset_version": plan["dataset_version"],
               "parser": pin, "model_calls": 0, "ocr_used": False, "central_reservations": 0,
               "requests": [], "documents": [], "restarted": False}

    def launch():
        repository = DocumentRepository(output / "repository", plan, sys.executable)
        owned_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        owned_socket.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(create_app(repository, token), log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [owned_socket]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Owned HTTP server did not start")
            time.sleep(0.02)
        client = httpx.Client(base_url=f"http://127.0.0.1:{owned_socket.getsockname()[1]}",
                              headers={"Authorization": "Bearer " + token}, timeout=90)
        return repository, server, thread, owned_socket, client

    def stop(active):
        _, server, thread, owned_socket, client = active
        client.close()
        server.should_exit = True
        thread.join(10)
        assert not thread.is_alive()
        owned_socket.close()

    def request(client, method, path, expected=200, code=None, **kwargs):
        response = client.request(method, path, **kwargs)
        entry = {"method": method, "path": path, "params": kwargs.get("params"),
                 "http_status": response.status_code, "response_sha256": sha(response.content)}
        assert response.status_code == expected, (path, response.status_code, response.text[:200])
        if code:
            assert response.json()["error"]["code"] == code
            entry["error_code"] = code
        elif response.headers.get("content-type", "").startswith("application/json"):
            entry["response"] = response.json()
        receipt["requests"].append(entry)
        return response

    active = None
    try:
        active = launch()
        repository, _, _, _, client = active
        specs = plan["documents"]
        originals = {s["document_id"]: (ROOT / "data/sources/lg-manuals-20261005" /
                     (s["product"]["model_id"] + "-" + s["sha256"][:12] + ".pdf")).read_bytes()
                     for s in specs}
        request(client, "POST", "/api/documents/" + specs[0]["document_id"], 400, "SOURCE_MISMATCH",
                content=originals[specs[1]["document_id"]])
        request(client, "POST", "/api/documents/UNREGISTERED", 404, "INVALID_DOCUMENT_ID",
                content=originals[specs[0]["document_id"]])
        with httpx.Client(base_url=str(client.base_url), timeout=5) as anonymous:
            request(anonymous, "GET", "/health", 401, "UNAUTHORIZED")
        for spec in specs:
            did = spec["document_id"]
            raw = originals[did]
            assert sha(raw) == spec["sha256"]
            response = request(client, "POST", "/api/documents/" + did, content=raw)
            record = response.json()["data"]
            downloaded = request(client, "GET", "/api/documents/" + did + "/original").content
            assert raw == downloaded == repository.original(did)
            items = []
            for selection in spec["selections"]:
                evidence = request(client, "GET", "/api/evidence/" + selection["evidence_id"]).json()["data"]["evidence"]
                assert evidence["text"] == selection["excerpt"]
                assert (evidence["source_id"], evidence["model_id"], evidence["document_version"]) == (
                    did, spec["product"]["model_id"], spec["document_version"])
                origin = next(o for o in record["origins"] if o["evidence_id"] == evidence["id"])
                assert sha(evidence["text"].encode()) == origin["text_sha256"]
                items.append({"evidence_id": evidence["id"], "text_sha256": origin["text_sha256"],
                              "locator": evidence["locator"], "exact_text": True})
            q = spec["selections"][0]["excerpt"].split()[0][:100]
            params = {"q": q, "model_id": spec["product"]["model_id"], "document_version": spec["document_version"]}
            found = request(client, "GET", "/api/evidence/search", params=params).json()["data"]
            assert found["items"] and all(e["source_id"] == did for e in found["items"])
            request(client, "GET", "/api/evidence/search", 400, "INVALID_DOCUMENT_VERSION",
                    params={**params, "document_version": "NONEXISTENT-VERSION"})
            receipt["documents"].append({"document_id": did, "model_id": spec["product"]["model_id"],
                "sha256": sha(raw), "bytes": len(raw), "download_exact": True, "evidence": items,
                "search_params": params, "search_response": found})
        request(client, "GET", "/api/evidence/search", 404, "INVALID_MODEL_ID", params={"q": "설치", "model_id": "OTHER-MODEL"})
        empty = request(client, "GET", "/api/evidence/search", params={"q": "xyz987UnrelatedNoMatch"}).json()["data"]
        assert empty["items"] == [] and empty["total"] == 0
        stop(active)
        active = None
        active = launch()
        repository, _, _, _, client = active
        for doc in receipt["documents"]:
            found = request(client, "GET", "/api/evidence/search", params=doc["search_params"]).json()["data"]
            assert found == doc["search_response"]
            assert request(client, "GET", "/api/documents/" + doc["document_id"] + "/original").content == originals[doc["document_id"]]
        receipt["restarted"] = True
        target = output / "repository" / (specs[0]["sha256"] + ".pdf")
        raw = target.read_bytes()
        target.write_bytes(raw + b"\nchanged")
        request(client, "GET", "/api/evidence/search", 400, "SOURCE_CHANGED", params={"q": "설치"})
        target.write_bytes(raw)
        target.unlink()
        request(client, "GET", "/api/evidence/search", 400, "SOURCE_CHANGED", params={"q": "설치"})
        target.write_bytes(raw)
        receipt["status"] = "passed"
        receipt["exact_evidence_count"] = sum(len(d["evidence"]) for d in receipt["documents"])
        receipt["request_count"] = len(receipt["requests"])
    finally:
        if active:
            stop(active)
        if previous_path is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous_path
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({k: result[k] for k in ("status", "exact_evidence_count", "request_count", "restarted")}, ensure_ascii=False))
