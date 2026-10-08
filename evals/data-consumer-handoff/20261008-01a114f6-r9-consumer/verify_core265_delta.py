"""Compare newly received CORE report metadata; do not replay old checks."""

import hashlib
import json
import os
from pathlib import Path


def read(name):
    return json.loads((Path("/delta") / name).read_bytes().decode("utf-8-sig"))


context = read("core-context.json")
pin = read("core-pin.json")
source = read("source-boundaries.json")
findings = read("pm-findings-reuse.json")
state = read("intake-status.json")
raw = (Path("/delta") / "core-context.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == pin["git_blob"]
assert context["semantic_review_sha256"] == findings["source_report_sha256"]
lookup = {row["source_id"]: row for row in source["rows"]}
assert {row["source_id"] for row in context["source_pins"]} == set(lookup)
for row in context["source_pins"]:
    other = lookup[row["source_id"]]
    assert row["text_sha256"] == other["text_sha256"]
    assert row["document_version"] == other["document_version"]
    assert row["purchased_model"] is None
previous = {row["run_id"]: row for row in state["baseline_reported_runs"]}
assert {row["run_id"] for row in context["run_references"]} == set(previous)
for row in context["run_references"]:
    assert row["public_output_sha256"] == previous[row["run_id"]]["declared_public_output_sha256"]
latest = [row["run_id"] for row in state["latest_pair"]]
assert not set(latest) & set(previous)
assert context["full_raw_response_received"] is False
assert context["same_live_HTTP_MCP_received"] is False
assert context["actual_model_quality_verified"] is False
assert os.getuid() == 65534
result = {"source_pin": pin, "kind": "new CORE265 metadata receipt compared with prior DATA source packet",
          "status": "PASS", "reference_source_ids_sha_versions_match": 6,
          "older_declared_run_ids_sha_match": 5, "latest_pair_not_in_CORE265_run_manifest": latest,
          "CORE_reported_full_raw_received": False, "CORE_reported_same_live_HTTP_MCP_received": False,
          "this_session_full_model_outputs_received": 0, "this_session_official_guide_archive_received": False,
          "official_guide_archive_scope": "PR265 has reference5 deterministic guide bytes; another user window owns its integrity intake",
          "raw_output_sha_for_latest_pair": None, "latest_pair_semantic_effect_verified": False,
          "model_OCR_old_tests_rerun": 0, "uid": os.getuid(),
          "executed_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(Path("/out") / "core265-intake.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": "PASS", "new_CORE_reference_source_pins": 6, "prior_run_pins": 5,
                  "latest_pair_raw_received": False, "old_checks_replayed": 0}))
