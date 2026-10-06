"""Offline fixed-output audit and separately identified constructed-date demo.

No model calls, hidden answers, original edits or inference-runtime injection.
Date provenance refers to a new constructed source containing text AND dates,
never the old eight-column CSV that has no date field.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from lgax_api.review_trends import build_review_trend_collection, canonical_dataset_sha256
from lgax_api.trend_validation import annotation_digest, validate_trend_collection
from lgax_core.judgement_contract import input_digest
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
PREFIX = "SYNTH-DATED-"
SOURCE_ID = "SYNTH-REVIEWS-DATED-DEMO-v1"
VERSION = "synthetic-dated-demo.20261006.v1"
LABELS = {"cleaning": "청소", "temporary_storage": "임시 보관", "food_findability": "식품 찾기",
          "manual_guidance": "설명서·사용 안내", "dish_loading_guidance": "식기 적재 안내",
          "rotating_arm_clearance": "회전 노즐 간섭", "heating_preset_management": "가열 출력·설정 관리"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_bytes())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def audit_r4():
    manifest_path = "evals/core-manual-quality/20261006/r4/execution-manifest.json"
    manifest = read(manifest_path)
    rows = []
    for case in manifest["cases"]:
        relative = "evals/core-manual-quality/20261006/r4/" + case["output"]
        raw = (ROOT / relative).read_bytes()
        result = json.loads(raw)
        input_path = "evals/core-manual-quality/20261006/r2/inputs/" + case["case_id"] + ".input.json"
        input_raw = (ROOT / input_path).read_bytes()
        dataset_path = ("evals/core-manual-quality/20261006/r2/inputs/missing-manual.dataset.json"
                        if case["case_id"] == "fridge-missing-manual"
                        else "evals/core-manual-quality/20261006/r2/inputs/synthetic.dataset.json")
        dataset_raw = (ROOT / dataset_path).read_bytes()
        dataset = json.loads(dataset_raw)
        originals = {e["id"]: e for e in dataset["evidence"]}
        sources = result["original_input"]["sources"]
        assert sha(raw) == case["output_sha256"]
        assert sha(input_raw) == case["input_sha256"] == result["input_sha256"]
        assert sha(dataset_raw) == case["dataset_sha256"] == result["dataset_sha256"]
        assert result["original_input"] == json.loads(input_raw)
        assert input_digest(result["input"]) == result["output"]["input_sha256"]
        assert all(source == originals[source["id"]] for source in sources)
        calls = []
        for call, pin in zip(result["model_calls"], case["calls"], strict=True):
            assert sha(call["raw_response"].encode()) == pin["raw_response_sha256"]
            assert call["formatted_prompt_sha256"] == pin["prompt_sha256"] == sha(call["formatted_prompt"].encode())
            assert call["request_context"]["sources"] == sources
            calls.append({"revision_count": call["revision_count"], "prompt_sha256": pin["prompt_sha256"],
                "raw_response_sha256": pin["raw_response_sha256"], "unresolved": pin["unresolved"],
                "questions": pin["questions"], "hold_reasons": pin["hold_reasons"]})
        cited = {eid for need in result["output"]["needs"] for eid in need["evidence_ids"]}
        assert cited <= {s["id"] for s in sources}
        needs = []
        for need in result["output"]["needs"]:
            linked = [originals[eid] for eid in need["evidence_ids"]]
            exact = len(linked) == 1 and need["pain"] == linked[0]["text"]
            assert all(e["model_id"] == need["model_id"] for e in linked)
            note = "근거 ID·원문 일치. 요구의 의미 강도는 별도 판정."
            if "REVIEW-EVIDENCE-008" in need["evidence_ids"]:
                note = "원문은 빠른 청소를 바라는 문장. 실제 발생 불편·빈도·효과로 확대할 수 없음."
            elif "REVIEW-EVIDENCE-003" in need["evidence_ids"]:
                note = "원문은 안쪽 식품 찾기·수납 정리. 고정 situation의 선반 청소 맥락과 차이."
            elif "REVIEW-EVIDENCE-007" in need["evidence_ids"]:
                note = "원문은 가족의 정리 표시 이해 차이. 선반 청소 맥락을 직접 뒷받침하지 않음."
            needs.append({"need_id": need["id"], "evidence_ids": need["evidence_ids"], "pain_exact_text": exact,
                          "source_locators": [e["locator"] for e in linked], "observation": note})
        omitted = sorted(s["id"] for s in sources if s["source_type"] == "review" and s["id"] not in cited)
        rows.append({"case_id": case["case_id"], "output_path": relative, "output_sha256": sha(raw),
            "input_path": input_path, "input_file_sha256": sha(input_raw), "dataset_path": dataset_path,
            "dataset_file_sha256": sha(dataset_raw), "source_exact_match_count": len(sources),
            "source_ids": [s["id"] for s in sources], "status": result["status"],
            "decision_violations": result["decision"]["violations"], "calls": calls, "needs": needs,
            "uncited_review_ids": omitted,
            "uncited_review_observation": "006 원문은 선반을 쉽게 꺼내 청소하며 크게 불편하지 않다는 긍정 문장. 빠진 불편 근거라고 단정하지 않음.",
            "questions": result["output"]["questions"], "unresolved": result["output"]["unresolved"],
            "feature_gap_concept_count": [len(result["output"][k]) for k in ("gaps", "concepts", "gap_assessments")],
            "manual_feature_explanations_assessed": False,
            "semantic_conclusion": "질문 없는 보류 및 맥락 차이를 확인. 신규 실모델 성공/전체 의미 품질 통과 아님."})
    write(FOLDER / "r4-original-audit.json", {"observed_at": datetime.now(UTC).isoformat(),
        "manifest_path": manifest_path, "manifest_sha256": sha((ROOT / manifest_path).read_bytes()),
        "new_model_calls": 0, "originals_rewritten": 0, "independent_evaluation_answers_used": False,
        "cases": rows, "prior_27b_clarification": "GAP003/006 unmentioned + unsupported = SUPPORT_BASIS_MISMATCH. "
        "계약상 unmentioned는 insufficient_evidence. 원 unsupported 판정/질문[]을 성공으로 바꾸지 않음."})
    lines = ["# 새 R4 고정 결과별 원문 대조", "", "새 모델 호출 0. 원 출력·입력·데이터·9개 prompt/raw SHA를 대조했다.", "",
             "|결과|원문 ID/텍스트 일치|상태·질문|인용·빠진 근거·기능 설명 검토|",
             "|---|---:|---|---|"]
    for row in rows:
        lines.append(f"|{row['case_id']}|{row['source_exact_match_count']}/{row['source_exact_match_count']}|"
                     "failed / HOLD_WITHOUT_QUESTIONS / questions[]|"
                     "Need 9개의 ID는 원문에 존재. 003·007은 선반 청소 situation과 맥락 차이, 008은 희망 문장. "
                     "006은 긍정 문장이므로 누락 불편으로 단정 불가. 기능·gap·concept 단계 미도달.|" )
    lines.extend(["", "## Need별 연결", "", "|결과|Need|원문 ID|pain 원문 동일|관찰|", "|---|---|---|---|---|"])
    for row in rows:
        for need in row["needs"]:
            lines.append(f"|{row['case_id']}|{need['need_id']}|{', '.join(need['evidence_ids'])}|"
                         f"{need['pain_exact_text']}|{need['observation']}|")
    lines.extend(["", ("기능 설명·기존 기능 지지·잔여 불편·콘셉트가 비어 있어 그 의미 정확성은 이번 결과에서 평가할 수 없다. "
                  "정상/조건변경/설명서 누락의 적절한 accept/hold는 미완료다."), "",
                  ("기존 27B GAP003/006의 unmentioned/unsupported 조합은 SUPPORT_BASIS_MISMATCH이며 계약상 "
                  "insufficient_evidence로 구분한다. 원 고정 결과는 수정하지 않았다.")])
    (FOLDER / "r4-original-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_dated_demo():
    original = read("data/demo/dataset.json")
    dataset = deepcopy(original)
    dataset["manifest"].update(dataset_id="constructed-dated-review-demo", version=VERSION,
        description="기존 합성 문장에 별도로 구성한 날짜 시연. 실제 고객 날짜·수요·불편 비율 아님.")
    baseline = read("data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json")
    by_review = {row["review_id"]: row for row in baseline["rows"]}
    evidence_map = {e["id"]: e for e in dataset["evidence"]}
    dates = {"REVIEW-001": ("2026-09-30T14:59:59Z", "instant"),
             "REVIEW-002": ("2026-09-30T15:00:00Z", "instant"), "REVIEW-003": ("2026-10-31", "day"),
             "REVIEW-004": ("2026-11-01", "day"), "REVIEW-006": ("2026-10-01", "day"),
             "REVIEW-007": ("2026-10-15", "day"), "REVIEW-008": ("2024-02-29", "day"),
             "REVIEW-009": ("2026-12-01", "day"), "REVIEW-010": ("2027-02-28", "day")}
    source_rows, rows = [], []
    for review in dataset["reviews"]:
        old_id, old_eid = review["id"], review["evidence_id"]
        review.update(id=PREFIX + old_id, evidence_id=PREFIX + old_eid,
                      source_id=SOURCE_ID, locator={"section": PREFIX + old_id})
        evidence_map[old_eid].update(id=review["evidence_id"], source_id=SOURCE_ID, locator=deepcopy(review["locator"]))
        date, precision = dates.get(old_id, (None, "unknown"))
        source_rows.append({**deepcopy(review), "published_at": date, "date_precision": precision,
                            "date_is_constructed": date is not None, "original_review_id": old_id})
        row = deepcopy(by_review[old_id])
        row.update(review_id=review["id"], evidence_id=review["evidence_id"], source_id=SOURCE_ID,
                   published_at=date, date_precision=precision, date_provenance=None)
        row["dedup_key"] = "exact-text:" + sha(json.dumps([SOURCE_ID, review["model_id"],
            review["document_version"], review["text"]], ensure_ascii=False).encode())
        rows.append(row)
    source = {"artifact_kind": "constructed_synthetic_review_source", "document_id": SOURCE_ID,
              "source_kind": "synthetic", "purpose": "계산·원문 drilldown 시연용 구성 날짜; 실제 게시일 아님",
              "original_dataset_sha256": canonical_dataset_sha256(original), "rows": source_rows}
    write(FOLDER / "source.synthetic-dated-demo.v1.json", source)
    source_sha256 = sha((FOLDER / "source.synthetic-dated-demo.v1.json").read_bytes())
    for row in rows:
        if row["published_at"] is not None:
            row["date_provenance"] = {"source_id": SOURCE_ID, "locator": {"section": row["review_id"]},
                                      "source_sha256": source_sha256}
    metadata = {**{key: deepcopy(baseline[key]) for key in ("classification", "topic_taxonomy_version", "dedup_policy_version")},
                "dataset_version": VERSION, "dataset_sha256": canonical_dataset_sha256(dataset),
                "annotation_version": VERSION, "annotation_sha256": "0" * 64, "rows": rows}
    metadata["annotation_sha256"] = annotation_digest(metadata)
    DemoStore(dataset)
    write(FOLDER / "dataset.synthetic-dated-demo.v1.json", dataset)
    write(FOLDER / "annotation.synthetic-dated-demo.v1.json", metadata)
    write(FOLDER / "topic-display-labels.preview.v1.json", {"status": "preview_human_classification",
        "taxonomy_version": baseline["topic_taxonomy_version"], "measure_label": "주제 언급 비율",
        "polarity_labelled": False, "topics": [{"topic_id": key, "label_ko": label} for key, label in LABELS.items()]})
    request = read("data/demo/planning_requests.json")[0]
    request.update(model_ids=["FRIDGE-A"], dataset_version=VERSION)
    project = {"project": {"id": "data-dated-demo", "name": "별도 합성 날짜 시연", "request": request,
                           "status": "draft", "dataset_version": VERSION}, "owner_id": "data-dated-demo-owner",
               "document_versions": {"FRIDGE-A": "1.0"}, "created_at": "2026-10-06T00:00:00Z",
               "dataset_sha256": metadata["dataset_sha256"]}
    filters = {"project_id": "data-dated-demo", "model_id": "FRIDGE-A", "source_ids": [SOURCE_ID],
               "dataset_version": VERSION, "start_date": "2026-10-01", "end_date_exclusive": "2026-11-01",
               "granularity": "month", "topic_ids": [], "source_kind": "synthetic", "timezone": "Asia/Seoul"}
    for name, period in (("october", {}), ("winter", {"start_date": "2026-12-01", "end_date_exclusive": "2027-03-01", "granularity": "season"}),
                         ("empty", {"start_date": "2026-01-01", "end_date_exclusive": "2026-02-01"})):
        collection = build_review_trend_collection(project, dataset, {**filters, **period}, metadata)
        validate_trend_collection(collection.aggregate, collection.metadata, collection.memberships, project,
                                  dataset, metadata["dataset_sha256"])
        if name == "october":
            assert collection.aggregate["counts"]["eligible_unique_review_count"] == 4
            assert collection.aggregate["counts"]["excluded_undated_count"] == 1
        elif name == "winter":
            assert collection.aggregate["counts"]["eligible_unique_review_count"] == 2
        else:
            assert all(topic["ratio"] is None for bucket in collection.aggregate["buckets"] for topic in bucket["topics"])
        write(FOLDER / ("demo-" + name + ".json"), {"aggregate": collection.aggregate, "memberships": collection.memberships})
    write(FOLDER / "demo-handoff.json", {"status": "constructed_demo_for_pm_approval", "model_calls": 0,
        "production_runtime_injected": False, "date_provenance": "새 source JSON의 구성 날짜와 text; 원 CSV 날짜 아님",
        "dataset_version": VERSION, "dataset_sha256": metadata["dataset_sha256"],
        "annotation_sha256": metadata["annotation_sha256"], "source_sha256": source_sha256,
        "review_count": 36, "original_texts_exact": all(a["text"] == b["text"] for a, b in zip(original["reviews"], dataset["reviews"], strict=True)),
        "original_dataset_file_sha256": sha((ROOT / "data/demo/dataset.json").read_bytes()),
        "original_csv_file_sha256": sha((ROOT / "data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv").read_bytes()),
        "original_csv_columns": 8, "taxonomy_status": "preview", "measure": "주제 언급 비율"})


def development_cases():
    dataset = read("data/research/PM-DATA-intake-20261006/generated/dataset.json")
    choices = [("fridge-folding", "접이식 선반", "T876MEE1H1-MANUAL-F08"),
               ("dishwasher-height", "양쪽 높이 동일", "DUE6BGL2E-MANUAL-D13-P24"),
               ("microwave-output", "고주파 출력", "DATA003-MW23FDI-M06")]
    by_id = {item["id"]: item for item in dataset["evidence"]}
    cases = []
    for case_id, query, eid in choices:
        item = by_id[eid]
        cases.append({"case_id": case_id, "query": query, "model_id": item["model_id"],
            "document_version": item["document_version"], "source_kind": item["source_kind"],
            "dataset_version": dataset["dataset_version"], "relevant_evidence_ids": [eid]})
    cases.append({**deepcopy(cases[0]), "case_id": "unrelated-empty", "query": "xyzUnrelated98765", "relevant_evidence_ids": []})
    write(ROOT / "evals/retrieval/development-cases.json", {"artifact_kind": "development_retrieval_cases",
        "development_only": True, "independent_evaluation": False,
        "label_basis": "공개 원문 위치를 소비하는 작은 개발 예시. 기존45/225행 고정 비교/독립평가를 대체하지 않음.", "cases": cases})


if __name__ == "__main__":
    audit_r4()
    prepare_dated_demo()
    development_cases()
    print("R4 audit 3 cases; constructed date demo 36; development retrieval cases 4; new model calls 0")
