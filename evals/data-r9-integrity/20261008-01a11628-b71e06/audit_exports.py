"""Offline receipt comparison only; never starts API, DB, MCP or a model."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

root, receipt_path, out = map(Path, sys.argv[1:])
sha = lambda raw: hashlib.sha256(raw).hexdigest()
read = lambda path: json.loads((root / path).read_bytes())
receipt = json.loads(receipt_path.read_bytes())
checks = []


def check(label, condition):
    checks.append({"check": label, "passed": bool(condition)})


for row in receipt["files"]:
    raw = (root / row["staged_path"]).read_bytes()
    check("receipt:" + row["staged_path"],
          len(raw) == row["bytes"] and sha(raw) == row["sha256"])
check("pr266_inputs_unchanged", all(r["same_bytes"] for r in receipt["reused_pr266_inputs"]))

manifest = read("core265/archive-manifest.json")
raw_zip = (root / "core265/r9-microwave-reference.zip").read_bytes()
check("zip_sha_and_size", sha(raw_zip) == manifest["sha256"] and len(raw_zip) == manifest["bytes"])
archive_entries = []
with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
    expected = {x["name"]: x for x in manifest["entries"]}
    check("zip_exact_unique_listing", len(archive.namelist()) == len(expected)
          and set(archive.namelist()) == set(expected))
    for name, item in expected.items():
        raw = archive.read(name)
        check("zip_entry:" + name, sha(raw) == item["sha256"] and len(raw) == item["bytes"])
        archive_entries.append({"name": name, "bytes": len(raw), "sha256": sha(raw)})
    check("zip_json_equals_received_json",
          archive.read("r9-microwave-reference.json")
          == (root / "core265/r9-microwave-reference.json").read_bytes())
    check("zip_intake_equals_received_intake",
          archive.read("official-reference-intake.json")
          == (root / "core265/official-reference-intake.json").read_bytes())
    html = archive.read("r9-microwave-reference.html")
guide = read("core265/r9-microwave-reference.json")
bundle = read("r9/microwave.manual-reference.research-bundle.json")
intake = read("core265/official-reference-intake.json")
check("five_source_objects_exact_and_ordered",
      len(guide["sources"]) == 5 and guide["sources"] == bundle["sources"])
check("reference_bundle_pin", intake["bundle_sha256"] ==
      sha((root / "r9/microwave.manual-reference.research-bundle.json").read_bytes()))
check("not_a_planning_proposal", guide["proposal"] is None
      and guide["guide_kind"] == "official_reference"
      and guide["exact_sku_applicability_confirmed"] is False)
check("core_marks_live_receipt_unconfirmed",
      intake["same_live_API_MCP_verified"] is False and intake["PM_acceptance"] is False)
pm_evidence = (root / "references/정이량-E057-KITCHEN-INTAKE.md").read_text("utf-8")
check("received_html_matches_pm_reported_hash_size",
      sha(html) in pm_evidence and str(len(html)) in pm_evidence)

context = read("core265/context.json")
original_semantic_bytes = (root / "pm/semantic-review.json").read_bytes()
check("original_five_case_report_unchanged",
      context["semantic_review_sha256"] == sha(original_semantic_bytes))
dishwasher_bytes = (root / "r9/dishwasher.research-bundle.json").read_bytes()
dishwasher = json.loads(dishwasher_bytes)
sources = {x["source_id"]: x for x in dishwasher["sources"]}
check("core_six_source_bundle_pin", context["bundle_sha256"] == sha(dishwasher_bytes))
for pin in context["source_pins"]:
    source = sources[pin["source_id"]]
    check("core_source_pin:" + pin["source_id"],
          sha(source["text"].encode()) == pin["text_sha256"]
          and source["document_version"] == pin["document_version"]
          and source["purchased_model"] == pin["purchased_model"])

run_ledger = []
for report_file in ["semantic-review.json", "compact-guide-live-semantic-review.json"]:
    report = read("pm/" + report_file)
    check("quality_unapproved:" + report_file, report["independent_semantic_quality_verified"] is False)
    for run in report["runs"]:
        trace, scope = run.get("trace_observations", {}), run.get("scope", {})
        run_ledger.append({
            "run_id": run["run_id"], "reported_public_output_sha256": run["public_output_sha256"],
            "report_file": "evals/pm-r9/20261008/" + report_file,
            "report_file_sha256": sha((root / "pm" / report_file).read_bytes()),
            "revision": run["revision"],
            "reported_parent_run_id": run.get("parent_run_id"),
            "reported_previous_brief_id": run.get("previous_brief_id"),
            "reported_model_calls": trace.get("model_calls", scope.get("model_calls")),
            "reported_generated_output_tokens": trace.get("generated_output_tokens"),
            "actual_input_token_usage": None,
            "reported_verdict": run.get("semantic_verdict", run.get("verdict")),
            "raw_public_output_received": False,
            "raw_model_response_usage_received": False,
            "stored_db_row_received": False, "same_db_restart_pair_received": False,
            "data_independent_runtime_comparison": "UNCONFIRMED",
        })
check("seven_distinct_reported_runs", len(run_ledger) == len({x["run_id"] for x in run_ledger}) == 7)
latest = read("pm/compact-guide-live-semantic-review.json")
normal, revised = latest["runs"]
check("reported_parent_ids_consistent", revised["parent_run_id"] == normal["run_id"]
      and revised["revision"] == normal["revision"] + 1)
for r in latest["runs"]:
    check("reported_bundle_id_matches:" + r["run_id"], r["bundle_id"] == dishwasher["bundle_id"])
reviewed = {sid for x in latest["sources_reviewed"]
            for sid in ([x["source_id"]] if "source_id" in x else x["source_ids"])}
check("reported_six_source_references_exist",
      reviewed == {x["source_id"] for x in context["source_pins"]} and reviewed <= sources.keys())

out.mkdir(parents=True, exist_ok=True)
write = lambda name, obj: (out / name).write_bytes(
    (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode())
write("run-receipt-ledger.json", run_ledger)
write("export-checks.json", {
    "status": "PASS" if all(x["passed"] for x in checks) else "FAIL",
    "scope": "Received CORE guide archive and pinned report consistency, not operating wire/run/DB proof",
    "audit_code_sha256": sha(Path(__file__).read_bytes()),
    "checks": checks, "archive_entries": archive_entries,
    "actual_received_guide_zip_sha256": sha(raw_zip),
    "actual_received_html_sha256": sha(html), "actual_received_html_bytes": len(html),
    "pm_reported_same_html_hash_correlated": True,
    "operating_http_mcp_envelopes_received": False, "runtime_integrity": "UNCONFIRMED",
    "semantic_quality_approved": False, "pm_audit_acceptance": None,
    "new_model_calls": 0, "new_ocr_calls": 0, "server_restarts": 0,
})
print(json.dumps({"checks": len(checks), "passed": sum(x["passed"] for x in checks),
                  "failed": [x for x in checks if not x["passed"]]}, ensure_ascii=False))
raise SystemExit(int(not all(x["passed"] for x in checks)))
