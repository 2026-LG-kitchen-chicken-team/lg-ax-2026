"""Three fixed live cases via file IPC; host alone owns gateway authentication.

Run in an immutable, zero-auth Docker snapshot with network=none. IPC returns
actual gateway bytes, with no mock model responses, labels or answer templates.
"""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
from lgax_core.planning_agent import PlanningAgent
from lgax_core.store import DemoStore


def raw_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


class FileGatewayTransport(httpx.BaseTransport):
    """Exchange exact HTTP bytes with the pinned authenticated host guardian."""

    def __init__(self, queue):
        self.queue = Path(queue)
        self.sequence = 0

    def handle_request(self, request):
        self.sequence += 1
        assert request.url.host == "127.0.0.1" and request.url.port == 18873
        assert (request.method, request.url.path) in {
            ("GET", "/api/tags"), ("POST", "/api/generate")}
        request_raw = raw_json({"method": request.method, "path": request.url.path,
                                "body_base64": base64.b64encode(request.read()).decode("ascii")})
        stem = f"{self.sequence:04d}"
        temp = self.queue / (stem + ".pending")
        with temp.open("xb") as destination:
            destination.write(request_raw)
        temp.rename(self.queue / (stem + ".request.json"))
        response_path = self.queue / (stem + ".response.json")
        deadline = time.monotonic() + 210
        while not response_path.is_file():
            if time.monotonic() >= deadline:
                raise httpx.ReadTimeout("bounded host gateway exchange timed out", request=request)
            time.sleep(0.1)
        response = json.loads(response_path.read_bytes())
        assert response["request_sha256"] == hashlib.sha256(request_raw).hexdigest()
        return httpx.Response(response["status_code"],
                              stream=httpx.ByteStream(base64.b64decode(response["body_base64"], validate=True)),
                              headers={"Content-Type": "application/json"}, request=request)


def main():
    source, queue, output = map(Path, sys.argv[1:4])
    source_commit = sys.argv[4]
    selected_case_ids = set(sys.argv[5:])
    provenance = json.loads((source / "input-provenance.json").read_bytes())
    assert provenance["max_batch_runs"] == 3 and provenance["max_batch_generations"] == 24
    assert provenance["digest"] == "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
    assert provenance["independent_evaluation_answers_used"] is False
    assert selected_case_ids <= {case["case_id"] for case in provenance["cases"]}
    output.mkdir(parents=True, exist_ok=True)
    # A positive mounted canary and negative auth/network probes prove this
    # process uses only the bounded source/output/IPC mounts.
    assert (queue / "work-canary.txt").read_text("ascii") == "LGAX harmless file relay boundary\n"
    assert not Path("/publisher-boundary.canary").exists()
    assert not Path("/host-state/worker.token").exists()
    assert not Path("/var/run/docker.sock").exists()
    transport = FileGatewayTransport(queue)
    config = ModelConfig(endpoint="http://127.0.0.1:18873", model_id=provenance["model"],
                         expected_digest=provenance["digest"], timeout_seconds=205,
                         max_response_bytes=1048576, max_output_tokens=8192,
                         context_tokens=16384, thinking=False, temperature=0)
    adapter = OllamaAdapter(config, transport=transport)
    rows = []
    try:
        for case in provenance["cases"]:
            if selected_case_ids and case["case_id"] not in selected_case_ids:
                continue
            input_raw = (source / case["input"]).read_bytes()
            dataset_raw = (source / case["dataset"]).read_bytes()
            assert hashlib.sha256(input_raw).hexdigest() == case["input_sha256"]
            assert hashlib.sha256(dataset_raw).hexdigest() == case["dataset_sha256"]
            started = time.monotonic()
            result = PlanningAgent(StructuredModelClient(adapter), DemoStore(json.loads(dataset_raw))).run(json.loads(input_raw))
            result.update(case_id=case["case_id"], execution_source_commit=source_commit,
                          input_sha256=case["input_sha256"], dataset_sha256=case["dataset_sha256"],
                          elapsed_seconds=round(time.monotonic() - started, 3),
                          transport_kind="actual authenticated shared Ollama via zero-auth file IPC",
                          source_kind="synthetic", development_only=True)
            target = output / (case["case_id"] + ".json")
            with target.open("xb") as destination:
                destination.write(raw_json(result))
            row = {"case_id": case["case_id"], "status": result["status"],
                   "corrections": result["input"]["revision_count"], "stage_attempts": len(result["model_calls"]),
                   "output_file_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                   "elapsed_seconds": result["elapsed_seconds"]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        with (output / "case-summary.json").open("xb") as destination:
            destination.write(raw_json({"source_commit": source_commit, "cases": rows,
                                        "formal_quality_acceptance": False, "pm_done": False}))
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
