"""Intake only the newly published PM264 report and quoted examples."""

import hashlib
import json
import os
from pathlib import Path


def load(name):
    return json.loads((Path("/inputs") / name).read_bytes().decode("utf-8-sig"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, value):
    (Path("/out") / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


report = load("compact-guide-live-semantic-review.json")
actions = load("core-next-actions.json")
prior = load("source-boundaries.json")
pins = load("pins.json")
for pin in pins["files"]:
    raw = (Path("/inputs") / pin["filename"]).read_bytes()
    assert sha(raw) == pin["sha256"]
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == pin["git_blob"]
assert sha((Path("/inputs") / "compact-guide-live-semantic-review.json").read_bytes()) == "f7d69e6fbd9ac43cd08754c7c7dfd51032b02472df90be37db160f17cb2f55fa"
assert actions["evidence_review_sha256"] == "f7d69e6fbd9ac43cd08754c7c7dfd51032b02472df90be37db160f17cb2f55fa"
bundle = load("dishwasher.research-bundle.json")
sources = {s["source_id"]: s for s in bundle["sources"]}
old = {row["source_id"]: row for row in prior["rows"]}
for sid, row in old.items():
    assert sha(sources[sid]["text"].encode("utf-8")) == row["text_sha256"]
    assert sources[sid]["document_version"] == row["document_version"]
    assert sources[sid]["purchased_model"] is None and sources[sid]["published_at"] is None
anchors = {a["id"]: a for row in prior["rows"] for a in row["anchors"]}
added = []
for name, sid, quote, limit in [
    ("residual-water-excess", "D2-DUE-CARE-DW-ODOR-DEVICE-P49", "80 ml ~ 100 ml보다 많은 경우", "초과량에 해당할 때의 조건이며 모든 냄새 사례의 보편 기준이 아님"),
    ("power-before-cancel", "D2-DUE-CARE-DW-ODOR-DEVICE-P49", "제품의 전원을 켜고 전원 버튼을 3초간 눌러 취소\r\n옵션을 선택하면 물을 배수할 수 있습니다.", "전원 켜기→전원버튼3초→취소선택 순서를 보존. 단순 전원3초로 바꾸지 않음"),
    ("food-alkaline-detergent-acidic", "D2-DUE-CARE-DW-ODOR-FISHY-P49", "트리메틸아민은 염기성 성분으로 산성이 \r\n주 성분인 세제가 냄새를 중화시켜 주지만", "제조사 문구의 식품 성분/세제 역할을 구분. 모든 세제의 성질이나 이 고객의 원인을 확정하지 않음"),
]:
    text = sources[sid]["text"]
    assert text.count(quote) == 1
    start = text.index(quote)
    row = {"id": name, "source_id": sid, "quote": quote, "quote_sha256": sha(quote.encode("utf-8")),
           "text_range": [start, start + len(quote)], "range_unit": "Unicode code points; 0-based half-open",
           "document_version": sources[sid]["document_version"], "locator": sources[sid]["locator"],
           "source_text_sha256": sha(text.encode("utf-8")), "condition_boundary": limit,
           "automatic_numeric_facts": False, "approved_operating_instruction": False}
    added.append(row)
    anchors[name] = row
mapping = {
    "CG-N-01": ["buyer-wife", "purchase-hope"],
    "CG-N-02": ["cleaning-mentioned", "odor-onset", "total-use-return"],
    "CG-N-03": ["purchase-hope", "mixed-praise", "mixed-burden"],
    "CG-N-04": ["fishy-condition", "fishy-procedure-reference", "residual-water-excess", "power-before-cancel"],
    "CG-N-05": ["cleaning-mentioned", "fishy-condition", "fishy-procedure-reference"],
    "CG-C-01": ["buyer-wife", "cleaning-mentioned", "odor-onset"],
    "CG-C-02": ["cleaning-mentioned", "odor-onset", "total-use-return"],
    "CG-C-03": ["cleaning-mentioned", "total-use-return"],
    "CG-C-04": ["purchase-hope", "mixed-praise", "mixed-burden", "installer-perception"],
    "CG-C-05": ["residual-water-excess", "power-before-cancel", "food-alkaline-detergent-acidic", "fishy-condition", "fishy-procedure-reference"]}
rows, run_rows = [], []
for ri, run in enumerate(report["runs"]):
    assert run["independent_semantic_quality_verified"] is False
    run_rows.append({"run_id": run["run_id"], "revision": run["revision"],
         "declared_public_output_sha256": run["public_output_sha256"],
         "declared_bundle_id": run["bundle_id"], "declared_parent_run_id": run.get("parent_run_id"),
         "declared_previous_brief_id": run.get("previous_brief_id"), "declared_constraints": run["constraints"],
         "reported_structural_status": run["reported_structural_status"],
         "reported_semantic_verdict": run["semantic_verdict"],
         "declared_model_trace": run["trace_observations"],
         "actual_generation_commit": None, "actual_model_digest_verified": None,
         "actual_public_output_bytes_received": False, "actual_public_output_sha256": None,
         "actual_full_input_or_native_trace_received": False, "actual_HTTP_MCP_received": False,
         "model_effect_verified_by_DATA": False, "DATA_independent_score": None})
    for fi, finding in enumerate(run["findings"]):
        fid = finding["id"]
        assert fid in mapping and set(finding["source_ids"]) <= set(old)
        refs = mapping[fid]
        assert all(a in anchors for a in refs)
        examples = finding.get("output_examples", [])
        rows.append({"finding_id": fid, "run_id": run["run_id"], "source_ids": finding["source_ids"],
             "affected_fields": finding["fields"], "source_anchor_ids": refs,
             "PM_report_pointer": f"/runs/{ri}/findings/{fi}",
             "received_PM_output_examples": examples, "quoted_example_count": len(examples),
             "quotation_scope": "PM selected/possibly abbreviated examples; not directly received model response",
             "full_quote_contiguity_in_actual_model_output_verified": False,
             "source_boundary_linked": True, "classification_absence_independently_verified": False,
             "PM_findings_reused_not_newly_AI_scored": True, "whole_run_semantics_approved": False})
assert len(run_rows) == 2 and len(rows) == 10 and sum(r["quoted_example_count"] for r in rows) == 23
assert run_rows[1]["declared_parent_run_id"] == run_rows[0]["run_id"]
assert run_rows[1]["declared_previous_brief_id"] == "brief-fe7412d6635c4822988f8d42ae6acddc"
assert run_rows[0]["declared_constraints"] != run_rows[1]["declared_constraints"]
action_rows = [{"id": a["id"], "title": a["title"], "owner_recommendation": a["owner_recommendation"],
                "evidence_finding_ids": a["evidence"], "dependencies": a["dependencies"],
                "DATA_scope": "Original source IDs/spans/condition boundaries only; CORE production code remains read-only"}
               for a in actions["actions"]]
assert {a["id"] for a in action_rows} == {"CORE-NEXT-01", "CORE-NEXT-02", "CORE-NEXT-03"}
write("compact-intake.json", {"version": "data-r9-compact-intake.20261008.01a114f6.v1", "source_pins": pins,
      "prior_source_packet_commit": "2672f00b2a9ac5bad38e7b523f67e2814d0ec144", "prior_PR": 269,
      "actual_received_kind": "PM264 source-linked review report bytes and quoted examples only",
      "run_rows": run_rows, "new_report_findings": rows, "reused_prior_anchors": 14,
      "new_official_condition_anchors": added, "CORE_next_actions": action_rows,
      "controlled_AB": False, "operating_guide_approval": False, "automatic_table_accuracy": None,
      "input_only_delivery_or_Gold_changed": False, "independent_evaluation_score": None, "parent_done": False})
assert os.getuid() == 65534
write("verification.json", {"status": "PASS", "uid": os.getuid(), "source_pins_checked": len(pins["files"]),
      "prior_source_text_sha_versions_reused": 6, "new_run_declarations": 2,
      "PM_new_finding_source_links": 10, "PM_selected_example_strings": 23,
      "new_exact_official_anchors": 3, "existing_14_anchor_checks_replayed": False,
      "actual_raw_model_outputs_received": 0, "new_model_OCR_calls": 0,
      "measurement_kind": "New report metadata and source boundaries; no full-run meaning/quality score",
      "executed_script_sha256": sha(Path(__file__).read_bytes())})
print(json.dumps({"status": "PASS", "new_runs": 2, "new_findings": 10, "received_PM_example_strings": 23,
                  "new_official_source_anchors": 3, "actual_raw_outputs_received": 0}))
