"""Read frozen source copies; build a partial intake packet, never model scores."""

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path


BASE = "dc0ccc05916c637b2e0c2cc268a061dfa655c0b7"
REL = "evals/data-consumer-handoff/20261008-01a114f6-r9-consumer"
R9 = "data/research/r9-public-runtime-20261008/dishwasher.research-bundle.json"
D2 = "data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/dishwasher/research-bundle.json"
REPORT = "evals/pm-r9/20261008/semantic-review.json"
PM_LOG = "docs/작업기록/정이량/2026-10-08/정이량-20261008-009-FUNCTIONAL-PROTOTYPE.md"
PM_PROOF = "docs/작업근거/정이량/2026-10-08/정이량-E056-FUNCTIONAL-PROTOTYPE.md"
NATIVE = "evals/data-dish-manual-audit/20261007-01a1100e/manual-native-excerpts.json"
PDF = "data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf"
TABLE = "data/research/r8-public-research-20261007/table-grounding/01a114f6/table-evidence-sidecar.json"
ZIP_STATUS = "evals/data-input-delivery/20261008-153716-01a11628/intake-status.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load(path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def dump(root, name, value):
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_boundary(state):
    for run in state["latest_pair"]:
        assert run["actual_output_received"] is False
        assert run["actual_output_sha256"] is None
        assert run["actual_full_input_received"] is False
        assert run["actual_selected_source_ids"] is None
        assert run["model_effect_verified"] is False
        assert run["independent_quality_score"] is None
    assert state["controlled_ab_experiment"] is False
    table = state["table"]
    assert table["actual_automatic_graph_received"] is False
    assert table["approved_adapter_received"] is False
    assert table["automatic_accuracy"] is None
    assert table["automatic_error_count"] is None
    delivery = state["input_only"]
    assert delivery["transfer_attempted"] is False
    assert delivery["approved_transport_received"] is False
    assert delivery["actual_received_archive_sha256"] is None
    assert delivery["actual_received_archive_bytes"] is None
    assert delivery["actual_received_entries"] is None
    assert delivery["gold_approved"] is False
    assert delivery["independent_evaluation_score"] is None
    assert state["parent_done"] is False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tree, out = args.inputs / "tree", args.out
    out.mkdir(parents=True, exist_ok=True)
    pins = load(args.inputs / "input-pins.json")
    assert pins["base_main"] == BASE
    for pin in pins["files"]:
        relative = Path(pin["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        raw = (tree / relative).read_bytes()
        assert len(raw) == pin["bytes"] and digest(raw) == pin["sha256"]
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert blob == pin["git_blob"]
    spec = load(tree / REL / "spec.json")
    bundle, original, report = load(tree / R9), load(tree / D2), load(tree / REPORT)
    assert digest((tree / R9).read_bytes()) == spec["input_bundle_sha256"]
    assert bundle["bundle_id"] == report["bundle_id"]
    assert report["bundle_sha256"] == spec["input_bundle_sha256"]
    lookup = {source["source_id"]: source for source in bundle["sources"]}
    before = {source["source_id"]: source for source in original["sources"]}
    assert len(set(spec["source_ids"])) == 6
    audit_native = {entry["audit_evidence_id"]: entry for entry in load(tree / NATIVE)}
    native_sha = digest((tree / PDF).read_bytes())
    rows = []
    for sid in spec["source_ids"]:
        source = lookup[sid]
        assert source == before[sid], f"Changed reference source: {sid}"
        text_sha = digest(source["text"].encode("utf-8"))
        assert source["metadata"]["text_sha256"] == text_sha
        assert source["purchased_model"] is None and source["published_at"] is None
        row = {"source_id": sid, "source_type": source["source_type"], "source_role": source["source_role"],
               "source_object_sha256": digest(canonical(source)), "object_hash_encoding": "sorted UTF-8 JSON compact",
               "text_sha256": text_sha, "source_text_characters": len(source["text"]),
               "url": source["url"], "locator": source["locator"], "page_model": source.get("page_model"),
               "document_version": source["document_version"], "purchased_model": None, "published_at": None,
               "source_preserved_from_PR254": True, "latest_model_selected_membership_verified": False,
               "anchors": []}
        if source["source_type"] == "review":
            assert source["metadata"]["split"] == "development"
            row["binding_limit"] = source["metadata"]["sku_binding"]
            row["purchase_time_revision_verified"] = False
        else:
            native = audit_native[source["metadata"]["audit_evidence_id"]]
            assert native["native_exact_excerpt"] == source["text"]
            assert native["native_excerpt_sha256"] == text_sha
            assert native["pdf_sha256"] == native_sha
            assert source["locator"]["start_char"] == native["start_char"]
            assert source["locator"]["end_char"] == native["end_char"]
            row["pdf_sha256"] = native_sha
            row["binding_limit"] = source["metadata"]["applicability"]
            row["customer_diagnosis_or_recovery_proved"] = False
            row["visual_note"] = "Existing p49 image read: conditional symptom rows and cross-section references; not a diagnosis or complete cleaning procedure"
            row["native_heading_suffix_is_not_a_procedure_step"] = source["text"].endswith("증상 원인 및 해결책")
        for anchor in spec["anchors"]:
            if anchor["source_id"] != sid:
                continue
            quote = anchor["quote"]
            assert source["text"].count(quote) == 1, f"Nonunique anchor: {anchor['id']}"
            start = source["text"].index(quote)
            row["anchors"].append({"id": anchor["id"], "text_range": [start, start + len(quote)],
                                   "range_unit": "Unicode code points, 0-based half-open",
                                   "quote": quote, "quote_sha256": digest(quote.encode("utf-8")),
                                   "source_boundary": anchor["boundary"], "not_model_output_or_Gold": True})
        rows.append(row)
    assert sum(len(row["anchors"]) for row in rows) == len(spec["anchors"]) == 14
    dump(out, "source-boundaries.json", {"version": "data-r9-consumer-source-boundaries.20261008.01a114f6.v1",
         "source_scope": spec["source_scope"], "base_main": BASE, "rows": rows,
         "approved_annotation": False, "automatic_extraction_result": False})

    baseline_runs, findings = [], []
    for ri, run in enumerate(report["runs"]):
        assert re.fullmatch(r"[0-9a-f]{64}", run["public_output_sha256"])
        baseline_runs.append({"run_id": run["run_id"], "revision": run["revision"],
             "declared_public_output_sha256": run["public_output_sha256"],
             "actual_output_received": False, "actual_output_sha256": None,
             "reported_verdict": run["verdict"], "source": REPORT, "json_pointer": f"/runs/{ri}"})
        for fi, finding in enumerate(run["findings"]):
            sids = finding.get("source_ids", [])
            assert set(sids) <= set(spec["source_ids"])
            findings.append({"id": finding["id"], "run_id": run["run_id"], "priority": finding["priority"],
                 "code": finding["code"], "source_ids": sids, "affected_fields": finding.get("fields", []),
                 "report_pointer": f"/runs/{ri}/findings/{fi}", "original_report_reused": True,
                 "newly_rescored": False, "latest_pair_recurrence_verified": None})
    assert len(baseline_runs) == 5 and len(findings) == 16
    pm_log, pm_proof = (tree / PM_LOG).read_text(encoding="utf-8"), (tree / PM_PROOF).read_text(encoding="utf-8")
    latest = []
    for declared in spec["latest_reported_pair"]:
        sid = declared["run_id"]
        assert sid in pm_log and sid in pm_proof
        assert sid not in {run["run_id"] for run in baseline_runs}
        assert type(declared["reported_model_calls"]) is int
        latest.append({**declared, "confirmation_kind": "PM publication report only",
             "reported_selected_source_count": 6, "reported_status": "complete",
             "publication_commit": BASE, "actual_execution_code_commit": None,
             "actual_loaded_bundle_sha256": None, "actual_output_received": False,
             "actual_output_sha256": None, "actual_full_input_received": False,
             "actual_selected_source_ids": None, "actual_source_facts": None,
             "actual_parent_brief_id": None, "actual_model_digest_verified": None,
             "actual_usage": None, "actual_http_mcp_pair_received": False,
             "model_effect_verified": False, "independent_quality_score": None,
             "PM_semantic_approval": False, "reported_sources": [PM_LOG, PM_PROOF]})
    dump(out, "pm-findings-reuse.json", {"source_report": REPORT,
         "source_report_sha256": digest((tree / REPORT).read_bytes()), "findings": findings,
         "historical_actual_model_runs_repeated": 0, "old_findings_projected_to_latest_pair": False,
         "report_scope_note": "The report has five run entries despite initial two-retained-run scope prose; latest pair is in PM009/E056, not this report."})

    table = load(tree / TABLE)
    assert digest((tree / TABLE).read_bytes()) == "7b0d6ae500aeabc093600cdd950df4fe9903e2f1d0800234ea7526c7c559af99"
    assert len(table["cells"]) == 5 and table["automatic_producer_graph_received"] is False
    prior = load(tree / ZIP_STATUS)
    comments = load(args.inputs / "recipient-comments.json")
    receipt = {item["id"]: item for item in comments}
    for cid in (spec["table_receipt_comment_id"], spec["input_only_receipt_comment_id"]):
        assert receipt[cid]["author"] == "unknownamed"
        assert receipt[cid]["body_sha256"] == digest(receipt[cid]["body"].encode("utf-8"))
    table_reply, zip_reply = receipt[6042666462], receipt[6042536901]
    assert "7b0d6ae500aeabc093600cdd950df4fe9903e2f1d0800234ea7526c7c559af99" in table_reply["body"]
    assert prior["candidate"]["archive_sha256"] in zip_reply["body"]
    assert "11,106 bytes / 11 entries" in zip_reply["body"]
    assert "ZIP/실제 입력 수신은 0" in zip_reply["body"]
    state = {"version": "data-consumer-intake.20261008.01a114f6.v1", "base_main": BASE,
             "status": "partial_source_and_report_intake; actual result/graph/transport pending",
             "baseline_reported_runs": baseline_runs, "latest_pair": latest,
             "reported_run_count": 7, "actual_raw_outputs_received_by_this_session": 0,
             "controlled_ab_experiment": False, "supplemental_artifacts_received_from_user": False,
             "table": {"existing_sidecar": TABLE, "existing_sidecar_sha256": digest((tree / TABLE).read_bytes()),
                 "manual_cell_mapping_received_by_CORE": True, "recipient_receipt": table_reply["url"],
                 "recipient_receipt_kind": "authenticated existing file-read/manual preconsumption reply",
                 "old_sidecar_ack_pending_note_preserved": True,
                 "actual_automatic_graph_received": False, "approved_adapter_received": False,
                 "automatic_accuracy": None, "automatic_error_count": None, "actual_runtime_consumption_verified": False},
             "input_only": {"expected_archive_sha256": prior["candidate"]["archive_sha256"],
                 "expected_archive_bytes": prior["candidate"]["archive_bytes"], "expected_archive_entries": 11,
                 "original_sender_verification_reused": True, "original_private_archive_read_or_rebuilt": False,
                 "recipient_receipt": zip_reply["url"], "recipient_reported_zip_count": 0,
                 "recipient_checked_at_utc": "2026-10-07T16:44:02Z", "recipient_directory_read_by_this_session": False,
                 "transfer_attempted": False, "approved_transport_received": False,
                 "actual_received_archive_sha256": None, "actual_received_archive_bytes": None,
                 "actual_received_entries": None, "raw_input_producer_git_head": None,
                 "gold_approved": False, "independent_scorer_designated": False,
                 "independent_evaluation_score": None, "candidate_kind": prior["candidate"]["kind"]},
             "new_model_calls": 0, "new_ocr_calls": 0, "operating_restart": False, "parent_done": False}
    check_boundary(state)
    dump(out, "intake-status.json", state)
    compact_comments = [{key: value for key, value in item.items() if key != "body"} for item in comments]
    dump(out, "recipient-references.json", {"records": compact_comments,
         "retrieval_method": "authenticated GitHub API as ginaginaring; old recipient comments, not new replies",
         "receipt_is_approval_or_runtime": False})

    probes = []
    for name, change in [
        ("declared_run_is_not_received_output", lambda x: x["latest_pair"][0].update(actual_output_received=True)),
        ("condition_change_is_not_controlled_AB", lambda x: x.update(controlled_ab_experiment=True)),
        ("manual_sidecar_is_not_auto_accuracy", lambda x: x["table"].update(automatic_accuracy=1.0)),
        ("sender_SHA_is_not_receiver_SHA", lambda x: x["input_only"].update(actual_received_archive_sha256=x["input_only"]["expected_archive_sha256"])),
        ("Gold_missing_is_not_evaluation_score", lambda x: x["input_only"].update(independent_evaluation_score=1.0)),
        ("partial_intake_is_not_parent_Done", lambda x: x.update(parent_done=True)),
    ]:
        candidate = copy.deepcopy(state)
        change(candidate)
        try:
            check_boundary(candidate)
        except AssertionError:
            probes.append({"name": name, "rejected": True, "kind": "metadata-only protocol probe; not product/model execution"})
        else:
            raise AssertionError(f"Promoted an unreceived state: {name}")
    immutable = []
    for folder, name in ((args.inputs, "input_ro_probe"), (Path("/"), "root_ro_probe")):
        try:
            (folder / name).write_text("non-secret permissions probe", encoding="utf-8")
        except OSError:
            immutable.append(True)
        else:
            raise AssertionError("Read-only boundary is writable")
    assert os.getuid() == 65534
    dump(out, "verification.json", {"status": "PASS", "verified_input_files": len(pins["files"]),
         "reference_source_objects": 6, "exact_quote_anchors": 14,
         "PM_findings_referenced_without_rescoring": 16, "baseline_reported_runs": 5,
         "new_declared_runs": 2, "actual_raw_outputs_received": 0, "boundary_probes": probes,
         "uid": os.getuid(), "input_and_root_read_only_checked": immutable,
         "executed_script_sha256": digest(Path(__file__).read_bytes()),
         "new_product_model_calls": 0, "new_OCR_calls": 0, "quality_accuracy": None,
         "measurement_kind": "source hashes/ranges/report metadata and completion boundaries only"})
    dump(out, "input-pins.json", pins)
    artifacts = [{"path": p.name, "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}
                 for p in sorted(out.glob("*.json")) if p.name != "artifact-manifest.json"]
    dump(out, "artifact-manifest.json", {"record_id": spec["record_id"], "files": artifacts,
         "self_manifest_excluded_from_own_hashes": True})
    print(json.dumps({"status": "PASS", "sources": 6, "anchors": 14,
          "latest_reported_runs": 2, "actual_raw_outputs_received": 0,
          "automatic_table_accuracy": None, "independent_evaluation_score": None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
