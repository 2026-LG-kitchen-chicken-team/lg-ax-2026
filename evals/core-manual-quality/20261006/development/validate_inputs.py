"""Validate six development inputs against unchanged originals; never call a model."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from lgax_core.feature_scope import select_feature_scope
from lgax_core.judgement_contract import schema_for


def main():
    base = Path(__file__).resolve().parent
    repo = base.parents[3]
    provenance = json.loads((base / "provenance.json").read_text("utf-8"))
    dataset = json.loads((base / "synthetic.dataset.json").read_text("utf-8"))

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert sha(repo / provenance["original_dataset"]) == provenance["original_dataset_sha256"]
    assert sha(base / "synthetic.dataset.json") == provenance["development_dataset_sha256"]
    original_dataset = json.loads((repo / provenance["original_dataset"]).read_text("utf-8"))
    assert {key: value for key, value in dataset.items() if key != "manifest"} == {
        key: value for key, value in original_dataset.items() if key != "manifest"}
    for row in provenance["cases"]:
        assert sha(repo / row["original"]) == row["original_sha256"]
        assert sha(base / row["input"]) == row["input_sha256"]
        payload = json.loads((base / row["input"]).read_text("utf-8"))
        original = json.loads((repo / row["original"]).read_text("utf-8"))
        assert {key: value for key, value in payload.items() if key != "request"} == {
            key: value for key, value in original.items() if key != "request"}
        Draft202012Validator(schema_for("input")).validate(payload)
        selected = select_feature_scope(payload["request"],
                                        {payload["product"]["model_id"]: payload["product"]["document_version"]}, dataset)
        scoped = selected["inputs"][0]
        for key in ("product", "sources", "features"):
            if key == "product":
                assert scoped[key] == payload[key]
            else:
                assert {item["id"]: item for item in scoped[key]} == {item["id"]: item for item in payload[key]}
    print(json.dumps({"valid_inputs": len(provenance["cases"]), "source_text_unchanged": True,
                      "dataset_version": provenance["dataset_version"], "model_calls": 0}))


if __name__ == "__main__":
    main()
