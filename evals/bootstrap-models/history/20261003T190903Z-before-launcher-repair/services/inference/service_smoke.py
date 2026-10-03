"""Verify the actual private API routes without exposing it or claiming Agent completion."""

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

URL = "http://127.0.0.1:18865"


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            code, result = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        code, result = error.code, json.load(error)
    return {"status_code": code, "body": result, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}


def main():
    checks = {"health": request("/health"), "retrieval_results": request("/bootstrap/retrieval-results"),
              "generation": request("/generate", {"prompt": "한국어 문장 '전자레인지'만 출력하세요."}),
              "invalid_prompt": request("/generate", {"prompt": ""})}
    passed = (checks["health"]["status_code"] == 200 and checks["health"]["body"]["generation_status"] == "ready"
              and checks["retrieval_results"]["status_code"] == 200 and checks["retrieval_results"]["body"]["query_count"] == 6
              and checks["generation"]["status_code"] == 200 and checks["generation"]["body"]["done"] is True
              and checks["invalid_prompt"]["status_code"] == 422)
    # The full retrieval artifact already exists separately, so do not duplicate all rankings here.
    checks["retrieval_results"]["body"] = {key: checks["retrieval_results"]["body"][key] for key in ["status", "experiment_kind", "query_count", "dataset_sha256"]}
    output = {"status": "passed" if passed else "failed", "timestamp_utc": datetime.now(UTC).isoformat(),
              "benchmark_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "endpoint": "loopback:18865", "checks": checks, "authentication": "not_configured", "agent_implemented": False,
              "limits": ["Private transport/readiness/input validation smoke only", "No public MCP connection or 31-requirement Agent coverage"]}
    Path("evals/bootstrap-models/service-smoke.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": output["status"], "statuses": {key: value["status_code"] for key, value in checks.items()}}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
