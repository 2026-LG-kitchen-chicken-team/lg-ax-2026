"""Validate the canonical schema, synthetic inputs and current adapter envelopes."""

from hashlib import sha256
import json
from pathlib import Path

from lgax_contracts import load_schema, validate
from lgax_core import DemoStore
from lgax_core.errors import not_implemented


def main():
    root = Path(__file__).resolve().parents[1]
    schema = load_schema()
    store = DemoStore()
    data = store.bootstrap()["data"]
    validate("BootstrapResponse", store.bootstrap())
    validate("ProductsResponse", store.list_products())
    validate("EvidenceSearchResponse", store.search_evidence("청소", "FRIDGE-A"))
    validate("EvidenceResponse", store.get_evidence("MANUAL-001"))
    validate("ErrorResponse", not_implemented())
    requests = json.loads((root / "data/demo/planning_requests.json").read_text("utf-8"))
    for request in requests:
        validate("PlanningRequest", request)
    manifest = json.loads((root / "data/demo/manifest.json").read_text("utf-8"))
    if sha256((root / "data/demo/dataset.json").read_bytes()).hexdigest() != manifest["files"]["dataset.json"]:
        raise ValueError("Demo dataset hash does not match manifest")
    if data["manifest"]["model_count"] != len(data["products"]) or data["manifest"]["review_count"] != len(data["reviews"]):
        raise ValueError("Manifest counts do not match dataset")
    print(json.dumps({"status": "pass", "definitions": len(schema["$defs"]),
                      "models": len(data["products"]), "reviews": len(data["reviews"]),
                      "planning_requests": len(requests), "analysis_implemented": False}))


if __name__ == "__main__":
    main()
