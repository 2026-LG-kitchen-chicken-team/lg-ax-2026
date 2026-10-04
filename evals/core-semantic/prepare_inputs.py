"""Validate and freeze independent model-facing inputs; never call or score a model."""
import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from lgax_core import DemoStore
from lgax_core.judgement_contract import input_digest, review_judgement, schema_for

CATEGORIES = {"normal", "duplicate_feature", "model_version_confusion", "conflicting_reviews",
              "missing_evidence", "specification_change"}


def read(path: Path):
    return json.loads(path.read_text("utf-8"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def prepare_inputs(directory: Path, output_dir: Path) -> dict:
    root = Path(__file__).resolve().parents[2]
    manifest = read(directory / "manifest.json")
    require(manifest["schema_version"] == 1 and manifest["independent_from_development"] is True,
            "Manifest must declare schema version1 and independent inputs")
    cases = manifest["cases"]
    require(len(cases) == 6 and len({case["case_id"] for case in cases}) == 6, "Six unique cases required")
    require({case["category"] for case in cases} == CATEGORIES, "All six categories required")
    require(not output_dir.exists(), "Use a fresh output directory; earlier execution data must be preserved")
    baseline = (root / "evals/phase2/baseline-prompt.md").read_text("utf-8")
    template = baseline.split("```text\n", 1)[1].split("\n```", 1)[0]
    forbidden_ids, forbidden_texts = set(), set()
    for pattern in ("evals/core-contract/*/*.input.json", "evals/core-reexecution/examples/*.input.json"):
        for path in root.glob(pattern):
            for source in read(path)["sources"]:
                forbidden_ids.add(source["id"])
                forbidden_texts.add(source["text"])
    prepared = []
    for case in cases:
        material = read(directory / case["data_path"])
        require(set(material) in ({"input", "dataset"}, {"input", "dataset", "previous_input", "previous_dataset"}),
                "Only input/data and paired prior input/data may be exported to a model")
        value, data = material["input"], material["dataset"]
        require(case["request"] == value, "Manifest request and material input differ")
        Draft202012Validator(schema_for("input")).validate(value)
        output_contract = directory / case["output_contract_path"]
        require(read(output_contract) == schema_for("output"), "Output contract must equal CORE001 schema")
        store = DemoStore(data)
        require(data["manifest"]["version"] == value["request"]["dataset_version"], "Dataset version mismatch")
        require(data["features"] == value["features"], "Dataset features differ from input")
        require(value["product"] in store.list_products()["data"]["products"], "Product snapshot mismatch")
        for source in value["sources"]:
            require(source["id"] not in forbidden_ids and source["text"] not in forbidden_texts,
                    "Source ID or text overlaps an earlier contract/example input")
            require(store.get_evidence(source["id"])["data"]["evidence"] == source, "Source snapshot mismatch")
        errors = [item for item in review_judgement(value, {})["violations"] if item["code"] != "OUTPUT_SCHEMA"]
        if case["category"] == "model_version_confusion":
            require({e["code"] for e in errors} == {"SOURCE_SCOPE_MISMATCH", "FEATURE_SCOPE_MISMATCH"},
                    "Confusion case must retain its deliberate input scope violations")
        else:
            require(not errors, f"Unexpected preflight violations: {errors}")
        if "previous_input" in material:
            old = material["previous_input"]
            Draft202012Validator(schema_for("input")).validate(old)
            DemoStore(material["previous_dataset"])
            require(input_digest(old) != input_digest(value), "Specification case needs a changed input")
        replacements = {"REQUEST_JSON": value, "MODEL_SCOPE_JSON": value["product"],
                        "EVIDENCE_POOL_JSON": material, "RESULT_SCHEMA_JSON": read(output_contract)}
        prompt = template
        for name, content in replacements.items():
            prompt = prompt.replace("{{" + name + "}}", json.dumps(content, ensure_ascii=False, indent=2))
        require("{{" not in prompt and "review_checks" not in prompt and "actual_review" not in prompt,
                "Prompt contains unfilled placeholders or reviewer fields")
        prepared.append((case, material, prompt, errors))
    output_dir.mkdir(parents=True)
    inventory = []
    for case, material, prompt, errors in prepared:
        name = case["case_id"]
        input_path = output_dir / f"{name}.model-input.json"
        baseline_path = output_dir / f"{name}.baseline.txt"
        payload = {"input": material["input"], "materials": material,
                   "input_sha256": input_digest(material["input"]),
                   "output_contract": read(directory / case["output_contract_path"])}
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")
        baseline_path.write_text(prompt + "\n", "utf-8", newline="\n")
        inventory.append({"case_id": name, "category": case["category"],
                          "data_sha256": file_hash(directory / case["data_path"]),
                          "output_contract_sha256": file_hash(directory / case["output_contract_path"]),
                          "input_sha256": input_digest(material["input"]),
                          "model_input_sha256": file_hash(input_path), "baseline_file_sha256": file_hash(baseline_path),
                          "preflight_violations": errors})
    result = {"execution_kind": "fixture", "source_kind": "synthetic", "model_calls": 0,
              "live_results_created": False, "evaluation_complete": False, "cases": inventory,
              "notice": "Input/contract/store consistency and raw source separation only; no semantic accuracy score."}
    (output_dir / "inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                               "utf-8", newline="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_inputs(args.suite, args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
