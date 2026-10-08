"""Check new CORE source-linked candidates; never execute CORE or call a model."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from values(item)
    elif isinstance(value, list):
        for item in value:
            yield from values(item)
    else:
        yield value


def anchor_objects(value, path=""):
    if isinstance(value, dict):
        if {"quote", "start", "end"} <= value.keys():
            yield path, value
        for key, item in value.items():
            yield from anchor_objects(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from anchor_objects(item, f"{path}[{index}]")


def main():
    input_root, output_path = map(Path, sys.argv[1:3])
    assert os.getuid() == 65534
    assert len(list(input_root.iterdir())) == 10
    pin_rows = read_json(input_root / "input-pins.json")
    assert len(pin_rows) == 9
    for pin in pin_rows:
        raw = (input_root / pin["filename"]).read_bytes()
        assert len(raw) == pin["bytes"]
        assert sha(raw) == pin["sha256"]
        assert hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw
        ).hexdigest() == pin["git_blob"]

    # All checks below target newly received candidates, using the existing
    # source bundle. Old DATA/CORE suite results are neither rerun nor inherited.
    artifact = read_json(input_root / "core-artifact-verification.json")
    context = read_json(input_root / "core-verification-context.json")
    bundle_raw = (input_root / "dishwasher.research-bundle.json").read_bytes()
    bundle = json.loads(bundle_raw)
    sources = {row["source_id"]: row for row in bundle["sources"]}
    assert artifact["source_bundle_file_sha256"] == sha(bundle_raw)
    assert artifact["artifact_kind"] == "real_source_anchored_output_stubs"
    assert artifact["classification_approved"] is False
    assert artifact["actual_model_quality_verified"] is False
    assert context["actual_native_generation_integrated"] is False
    assert context["PM_acceptance"] is False
    assert context["new_model_calls"] == 0
    assert len(artifact["source_pins"]) == 6
    for pin in artifact["source_pins"]:
        source = sources[pin["source_id"]]
        assert sha(source["text"].encode()) == pin["text_sha256"]
        facts = json.dumps(
            source["facts"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode()
        assert sha(facts) == pin["source_facts_sha256"]
        assert source["document_version"] == pin["document_version"]
        assert pin["purchased_model"] is None
    for filename in (
        "candidate-records.json", "candidate-summary-projection.json",
        "candidate-consultation-context.json",
    ):
        assert sha((input_root / filename).read_bytes()) == artifact["output_sha256"][filename]

    records = read_json(input_root / "candidate-records.json")
    all_records = records["customer_claims"] + records["official_actions"]
    assert len(records["customer_claims"]) == 13
    assert len(records["official_actions"]) == 1
    by_id = {record["claim_id"]: record for record in all_records}
    assert len(by_id) == len(all_records)
    rows, span_count = [], 0
    for record in all_records:
        source = sources[record["source_id"]]
        checked = []
        for path, anchor in anchor_objects(record):
            assert type(anchor["start"]) is int and type(anchor["end"]) is int
            assert 0 <= anchor["start"] < anchor["end"] <= len(source["text"])
            assert source["text"][anchor["start"]:anchor["end"]] == anchor["quote"]
            checked.append(path)
            span_count += 1
        rows.append({
            "claim_id": record["claim_id"], "source_id": record["source_id"],
            "declared_kind": record["kind"], "checked_anchor_fields": checked,
            "new_candidate_exact_source_match": True,
            "actual_model_record_received": False,
        })
    assert by_id["wife"]["actor_anchor"]["quote"] == "집사람"
    assert by_id["hope"]["kind"] == "expectation"
    assert by_id["hope"]["experienced_polarity"] == "unknown"
    assert by_id["maintenance"]["event_or_duration_role"] == "maintenance_mention"
    assert by_id["total"]["event_or_duration_role"] == "total_use"
    assert by_id["intent"]["kind"] == "customer_inference"
    assert by_id["intent"]["experienced_polarity"] == "unknown"
    assert all(row["order_status"] == "unknown" for row in records["customer_claims"])
    drain = by_id["drain"]
    assert drain["threshold"]["comparator"] == "gt"
    assert drain["threshold"]["unit_anchor"]["quote"] == "ml"
    assert [row["quote"] for row in drain["ordered_steps"]] == [
        "제품의 전원을 켜고", "전원 버튼을 3초간 눌러", "취소\r\n옵션을 선택하면",
    ]

    projection = read_json(input_root / "candidate-summary-projection.json")
    assert projection["classification_approved"] is False
    assert projection["semantic_quality_verified"] is False
    assert projection["summaries"]["mixed"][0]["source_ids"] == [
        "LGE-R8-REVIEW-853593"
    ]
    mixed_text = projection["summaries"]["mixed"][0]["text"]
    assert all(by_id[key]["anchor"]["quote"] in mixed_text
               for key in ("convenience", "preparation", "performance"))
    consultation = read_json(input_root / "candidate-consultation-context.json")
    assert consultation["customer_confirmed"] is False
    assert consultation["semantic_quality_verified"] is False
    for field in ("observations", "expectations", "customer_inferences"):
        for record in consultation[field]:
            original = by_id[record["claim_id"]]
            assert all(record[key] == value for key, value in original.items())
            assert record["provenance"]["purchased_model"] is None
            assert record["provenance"]["applicability"] is None
            assert record["semantic_quality_verified"] is False

    archive_meta = read_json(input_root / "official-reference-archive.json")
    archive_path = input_root / "conditional-official-reference.zip"
    assert sha(archive_path.read_bytes()) == archive_meta["archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == [archive_meta["entry"]]
        entry = archive.read(archive_meta["entry"])
    assert len(entry) == archive_meta["entry_bytes"]
    assert sha(entry) == archive_meta["entry_sha256"]
    assert sha(entry) == artifact["output_sha256"]["conditional-official-reference.txt"]
    assert drain["anchor"]["quote"] in entry.decode()

    prior = read_json(input_root / "prior-compact-intake.json")
    finding_ids = {item for item in values(prior)
                   if isinstance(item, str) and re.fullmatch(r"CG-[NC]-0[1-5]", item)}
    mapping = [
        (["wife"], ["CG-N-01", "CG-C-01"], "증상 주체는 집사람; 질환·통증 완화 추론 미확인"),
        (["hope"], ["CG-N-03", "CG-C-04"], "구매 기대와 실제 만족 분리"),
        (["maintenance", "odor"], ["CG-N-02", "CG-C-02"], "청소·냄새 언급을 조치 실패의 시간순서로 확정하지 않음"),
        (["total"], ["CG-C-03"], "1개월 청소 언급과 약3개월 전체 사용을 분리"),
        (["convenience", "preparation", "performance"], ["CG-N-03", "CG-C-04"], "동일 후기의 장점과 불편을 함께 유지"),
        (["intent"], ["CG-C-04"], "기사의 의도는 고객 추정"),
        (["drain"], ["CG-N-04", "CG-C-05"], "잔수 초과 조건·ml·전원→3초→취소·참조 장을 보존"),
        (["maintenance", "drain"], ["CG-N-05"], "고객 경험과 조건부 설명서 조치를 분리"),
    ]
    links = []
    for claims, findings, boundary in mapping:
        assert set(claims) <= by_id.keys()
        assert set(findings) <= finding_ids
        links.append({
            "candidate_claim_ids": claims, "existing_PM_finding_ids": findings,
            "source_boundary_review": boundary,
            "scope": "new CORE source-linked test candidate only",
            "actual_run_claim_fixed": None,
            "independent_classification_approval": False,
        })
    report = {
        "version": "data-r9-new-core-intake.20261008.01a114f6.cde529.v1",
        "received_kind": "CORE PR271 source-anchored test candidates, not model outputs",
        "core_head": "548a1fa5629eb5d0e6d145b8e7dc8da8e78c4186",
        "checks": {
            "input_files": len(pin_rows), "source_metadata_pins": 6,
            "new_candidate_records": len(rows), "new_exact_anchor_fields": span_count,
            "candidate_summary_projection": True, "candidate_consultation_context": True,
            "conditional_reference_archive_entries": 1, "changed_claim_boundary_links": len(links),
        },
        "records": rows, "changed_claim_boundary_links": links,
        "limits": {
            "original_latest_two_outputs_received": 0,
            "actual_model_record_received": False, "actual_run_semantic_review_complete": False,
            "automatic_table_graph_received": False, "approved_table_adapter_received": False,
            "automatic_table_accuracy": None, "private_evaluation_ZIP_receiver_receipt": None,
            "independent_score": None, "PM_approval": False, "whole_parent_done": False,
            "new_model_calls": 0, "new_OCR_calls": 0, "operating_restarts": 0,
            "old_62_suite_reexecuted": False,
        },
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"PASS new_CORE_candidates={len(rows)} exact_anchor_fields={span_count} "
          f"finding_boundary_links={len(links)} actual_latest_outputs=0")


if __name__ == "__main__":
    main()
