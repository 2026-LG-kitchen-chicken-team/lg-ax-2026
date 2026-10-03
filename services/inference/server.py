"""Private lab health and opt-in local Ollama generation; never mounted on public MCP."""

import argparse
import json
import os
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="LG AX private lab bootstrap", version="0.1.0")
OLLAMA_URL = os.environ.get("LGAX_OLLAMA_URL", "http://127.0.0.1:18864")
EXPECTED_DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
SOURCE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
if OLLAMA_URL != "http://127.0.0.1:18864":
    raise ValueError("The bootstrap only permits its dedicated loopback Ollama endpoint")


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)


def _get(path):
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=5) as response:
        return json.load(response)


@app.get("/health")
def health():
    try:
        models = _get("/api/tags")["models"]
        selected = next((m for m in models if m["name"] == "qwen3:8b"), None)
        status = "model_not_downloaded" if selected is None else "ready" if selected.get("digest") == EXPECTED_DIGEST else "model_revision_changed"
    except (OSError, urllib.error.URLError, KeyError):
        models, status = [], "unavailable"
    return {"service": "lgax-private-lab", "generation_status": status, "models": [m["name"] for m in models], "expected_model_digest": EXPECTED_DIGEST, "source_sha256": SOURCE_SHA256,
            "agent_implemented": False, "access_boundary": "loopback-only", "authentication": "not_configured", "public_mcp_connected": False}


@app.get("/bootstrap/retrieval-results")
def results():
    path = Path("evals/bootstrap-models/retrieval-results.json")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="retrieval experiment not completed")
    return json.loads(path.read_text("utf-8"))


@app.post("/generate")
def generate(request: GenerationRequest):
    # Explicit private HTTP invocation incurs GPU work; no call from the public demo tools.
    if health()["generation_status"] != "ready":
        raise HTTPException(status_code=503, detail="verified local model unavailable or revision changed")
    payload = {"model": "qwen3:8b", "prompt": request.prompt, "stream": False, "think": False,
               "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 256}, "keep_alive": "5m"}
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            output = json.load(response)
    except (OSError, urllib.error.URLError) as error:
        raise HTTPException(status_code=503, detail="local model unavailable") from error
    return {"model": output.get("model"), "response": output.get("response"), "done": output.get("done"),
            "verified_model_digest": EXPECTED_DIGEST,
            "prompt_eval_count": output.get("prompt_eval_count"), "eval_count": output.get("eval_count"),
            "total_duration_ns": output.get("total_duration"), "agent_implemented": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18865)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
