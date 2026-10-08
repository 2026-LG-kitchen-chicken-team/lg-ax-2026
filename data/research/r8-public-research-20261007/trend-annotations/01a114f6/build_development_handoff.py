"""Offline development-only draft authoring and existing-collector consumption.

Run in the repository's authentication-free, network-free validator container.
The PAGE- namespace is an observational compatibility projection for a legacy
collector. It is neither a purchased SKU nor an approved canonical/runtime input.
Draft topic annotations are never injected into the collector.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

DATA_COMMIT = "94b560de72f91795cfd50aada9e17d6773383ae1"
PM_COMMIT = "ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f"
BASE = "data/research/r8-public-research-20261007/"
DELIVERY = BASE + "d1-d2-01a10600/"
VERSION = "r8-development-topic-draft.20261008.01a114f6.v1"
PROJECTION_VERSION = "r8-development-page-date-only.20261008.01a114f6.v1"
LABELS = {
    "storage_access": "수납 접근·찾기", "capacity": "수납 용량", "design": "디자인·색상",
    "installation_fit": "설치 공간 적합성", "installation_service": "설치·초기 안내 서비스",
    "delivery_service": "배송·회수", "price": "가격·혜택", "usability": "일반 사용 편의",
    "cooling": "냉장·냉동", "heating": "데우기·해동", "controls": "조작·표시·설정",
    "dish_cleaning": "식기 세척 결과", "drying": "건조", "cleaning": "청소·소모품·관리",
    "odor": "냄새", "noise": "소음", "door_handling": "문·손잡이·닫힘",
    "reliability": "손상·내구 인식", "time_saving": "작업 부담·소요시간",
    "energy": "전력·효율 인식", "connectivity": "앱·연결 편의",
    "loading": "식기 적재·배치", "after_sales": "AS·환불 응대", "general": "세부 주제 미상·종합 의견",
}
SERVICE_TOPICS = {"installation_service", "delivery_service", "after_sales"}
POLARITIES = {"positive", "negative", "neutral", "uncertain"}
OPINIONS = POLARITIES | {"mixed"}
COUNTERPAIRS = [
    ("storage_access", "848850", "856502", "different_page_models", "깊이 접근의 아쉬움과 안쪽 찾기 만족; 용량·사용자·배치 조건 차이 미확인"),
    ("capacity", "772640", "723068", "different_page_models", "냉동공간 부족과 넓은 냉동실 만족; 가족·물품·제품 조건 차이"),
    ("price", "855415", "766814", "different_page_models", "상대적으로 비쌈과 특가 만족; 구매 시기·할인 조건 차이"),
    ("door_handling", "767601", "861821", "same_displayed_page_only", "닫힘 인지 불편과 자동닫힘 만족; 실제 구매SKU·사용조건 미확인"),
    ("installation_service", "798666", "770195", "same_displayed_page_only", "제품 만족/설치 불만과 친절한 설치; 기사·설치 장소·시기 차이"),
    ("heating", "837305", "859746", "same_displayed_page_only", "냉동상태/불규칙 가열 보고와 빠른 가열 만족; 식품·질량·시간·설정·전원·판본 조건 미확인"),
    ("heating", "760282", "817841", "different_page_models", "느린 데우기 인식과 빠른 데우기 인식; 실제 구매SKU·시험조건 미확인"),
    ("controls", "853726", "631655", "different_page_models", "적응시간 필요와 다이얼 편리함; 이전 사용기기·조작 체계 차이"),
    ("drying", "440531", "773516", "same_displayed_page_only", "건조 실패 보고와 건조 만족; 코스·열풍·적재·세제·사용시간 조건 미확인"),
    ("loading", "691193", "773516", "same_displayed_page_only", "적재 방식에 따른 세척 차이와 배치의 초기 낯섦; 후자는 건조/용량 만족도 함께 보고"),
    ("installation_service", "503624", "859044", "different_page_models", "경도/소모품 초기 세팅 요구와 친절한 설명; 다른 요구를 포괄 서비스 품질로 단정하지 않음"),
    ("noise", "738414", "800073", "same_displayed_page_only", "조금 더 큰 소리와 적은 소음; 비교기기·거리·코스 조건 미확인"),
]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read(path: Path):
    return json.loads(path.read_bytes())


def write(root: Path, name: str, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return sha(raw)


def inputs(source: Path):
    pins = read(source / "source-pins.json")
    for pin in pins:
        raw = (source / pin["kind"] / pin["path"]).read_bytes()
        assert sha(raw) == pin["sha256"] and len(raw) == pin["bytes"], pin["path"]
        assert pin["source_commit"] == (DATA_COMMIT if pin["kind"] == "data" else PM_COMMIT)
    data = source / "data"
    records = read(data / (BASE + "records.json"))
    membership = read(data / (DELIVERY + "d1-membership.json"))
    delivery_manifest = read(data / (DELIVERY + "d1-delivery-manifest.json"))
    assert delivery_manifest["observations"] == 239
    assert delivery_manifest["unique_reviews"] == 238
    assert delivery_manifest["duplicate_observations"] == 1
    assert len(records) == len(membership) == 238
    by_id = {row["original_review_id"]: row for row in records}
    members = {row["original_review_id"]: row for row in membership}
    assert len(by_id) == len(members) == 238 and set(by_id) == set(members)
    selected = {key: row for key, row in by_id.items() if row["split"] == "development"}
    assert len(selected) == 141
    for key, row in by_id.items():
        assert row["text_sha256"] == sha(row["text"].encode("utf-8")), key
        assert members[key]["text_sha256"] == row["text_sha256"], key
        assert members[key]["actual_purchased_model_id"] == row["actual_purchased_model_id"] is None
        assert members[key]["published_at"] == row["published_at"] is None
        assert members[key]["displayed_model_id"] == row["displayed_model_id"]
        assert members[key]["split"] == row["split"]
    bundles = {}
    sources = {}
    for group in ("fridge", "dishwasher", "microwave"):
        bundle = read(data / (DELIVERY + f"agent-input/{group}/research-bundle.json"))
        bundles[group] = bundle
        for item in bundle["sources"]:
            if item["source_type"] != "review":
                continue
            key = item["metadata"]["original_review_id"]
            assert key in selected and key not in sources
            record = selected[key]
            assert item["product_group"] == members[key]["product_group"] == group
            assert item["metadata"]["split"] == "development"
            assert item["text"] == record["text"]
            assert item["metadata"]["text_sha256"] == record["text_sha256"]
            if "original_text_sha256" in record:
                assert item["metadata"]["original_text_sha256"] == record["original_text_sha256"]
            else:
                # New-v2 records omit this field. Producer explicitly carries an
                # unredacted text digest; preserve the record's absence below.
                assert not record["redactions"]
                assert item["metadata"]["original_text_sha256"] == record["text_sha256"]
            assert item["source_id"] == "LGE-R8-REVIEW-" + key
            assert item["url"] == record["source_url"]
            assert item["locator"]["selector"] == record["source_locator"]
            assert item["page_model"] == record["displayed_model_id"]
            assert item["document_version"] == members[key]["document_version"]
            assert item["document_version"] == record.get("document_version", record["manual_version"])
            assert item["purchased_model"] is None and item["published_at"] is None
            assert item["metadata"]["strict_exact_model_eligible_for_model_input"] is False
            sources[key] = item
    assert set(sources) == set(selected)
    return pins, by_id, members, selected, bundles, sources


def make_draft(seed, selected, members, sources):
    assert seed["status"] == "draft"
    assert len(seed["rows"]) == len(selected) == 141
    seen, rows = set(), []
    for entry in seed["rows"]:
        key, opinion, aspects, *notes = entry
        assert key in selected and key not in seen and opinion in OPINIONS, key
        seen.add(key)
        record, source = selected[key], sources[key]
        statements = []
        for aspect in aspects:
            topic, polarity, anchor, *basis = aspect
            assert topic in LABELS and polarity in POLARITIES
            start = record["text"].find(anchor)
            assert start >= 0 and anchor, (key, anchor)
            assert record["text"].find(anchor, start + 1) == -1, (key, "ambiguous anchor", anchor)
            statements.append({"topic_id": topic, "polarity": polarity,
                "domain": "service" if topic in SERVICE_TOPICS else "commercial" if topic == "price" else "product",
                "basis": basis[0] if basis else "customer_report_or_evaluation",
                "quote": anchor, "text_range": {"start": start, "end": start + len(anchor),
                    "unit": "unicode_codepoint", "end_exclusive": True},
                "quote_sha256": sha(anchor.encode("utf-8"))})
        assert statements
        rows.append({"original_review_id": key, "record_review_id": record.get("review_id"),
            "projection_review_id": "OBS-R8-REVIEW-" + key,
            "source_id": source["source_id"], "product_group": members[key]["product_group"],
            "status": "draft", "approved": False, "overall_opinion": opinion,
            "topic_ids": sorted({item["topic_id"] for item in statements}), "aspects": statements,
            "displayed_page_model": record["displayed_model_id"], "actual_purchased_model_id": None,
            "published_at": None, "date_precision": "unknown", "date_provenance": None,
            "reference_document_version": source["document_version"],
            "record_document_version": record.get("document_version"),
            "document_version_basis": "page_model_reference_only_not_review_edition_or_purchase_time_manual",
            "source_url": source["url"], "source_locator": deepcopy(source["locator"]),
            "raw_capture_declared_sha256": {"server_html": record.get("source_sha256"),
                "private_dom_capture": record.get("private_capture_file_sha256"),
                "message_dom_fragment": record.get("public_message_DOM_fragment_sha256")},
            "raw_capture_verified_here": False,
            "record_original_text_sha256": record.get("original_text_sha256"),
            "bundle_original_text_sha256": source["metadata"]["original_text_sha256"],
            "original_text_sha256_basis": "record_declared" if "original_text_sha256" in record else "bundle_declared_unredacted_body_digest_record_field_absent",
            "text_sha256": record["text_sha256"],
            "research_source_sha256": sha(canonical(source)),
            "split": "development", "split_version": record["split_version"],
            "dedup_group_id": source["duplicate_group"],
            "input_hold_reasons": deepcopy(record["input_hold_reasons"]),
            "exact_sku_judgement_eligible": False,
            "known_historical_development_exposure": source["metadata"]["known_historical_development_exposure"],
            "independent_evaluation_approved": False,
            "interpretation_note": notes[0] if notes else "고객 보고/평가이며 구매SKU·성능·원인·시장대표성을 확정하지 않는다."})
    assert seen == set(selected)
    rows.sort(key=lambda item: item["original_review_id"])
    by_id = {row["original_review_id"]: row for row in rows}
    pairs = []
    for topic, left, right, relation, note in COUNTERPAIRS:
        assert topic in by_id[left]["topic_ids"] and topic in by_id[right]["topic_ids"]
        assert by_id[left]["product_group"] == by_id[right]["product_group"]
        pairs.append({"topic_id": topic, "original_review_ids": [left, right],
            "page_relation": relation, "status": "draft", "condition_comparison": note,
            "causal_or_same_sku_conclusion": False})
    return {"artifact_kind": "development_topic_opinion_draft", "annotation_version": VERSION,
        "status": "draft", "pm_approved": False, "gold": False,
        "classification_method": seed["method"], "author": seed["author"],
        "topic_taxonomy_version": "r8-topics-draft.20261008.01a114f6.v1",
        "analysis_scope": "product_group_and_displayed_page_association",
        "rules": ["별점으로 감정·토픽을 추정하지 않는다", "혼합 의견의 긍정·불편·판단한계를 함께 남긴다",
                  "배송·설치·가격을 제품 사용 성능 불만과 구분한다", "이전 제품/다른 후보/기대/우려는 현재 제품 결함이 아니다",
                  "원문 표현·조건·불확실성을 보존한다", "유사 페이지 모델은 구매SKU 확인값이 아니다"],
        "taxonomy": [{"topic_id": key, "label": value, "status": "draft"} for key, value in LABELS.items()],
        "rows": rows, "counterexample_pairs": pairs,
        "counterexample_limits": ["대조 ID는 반대·혼합 맥락을 보여주며 결함 보고를 반박/무효화하지 않는다",
            "동일 페이지에서도 실제 구매SKU·판본·시기·조건 일치는 미확인",
            "냉장고 소음/식기 냄새 등 대응 반례가 없는 주제는 외부 반례를 만들지 않는다"]}


def verify_draft(draft, selected, sources):
    assert draft["status"] == "draft" and not draft["pm_approved"] and not draft["gold"]
    rows = draft["rows"]
    assert len(rows) == len({row["original_review_id"] for row in rows}) == 141
    assert {row["original_review_id"] for row in rows} == set(selected)
    quote_count = 0
    for row in rows:
        key = row["original_review_id"]
        original = selected[key]
        assert row["split"] == "development" and row["status"] == "draft" and row["approved"] is False
        assert row["actual_purchased_model_id"] is None and row["published_at"] is None
        assert row["date_precision"] == "unknown" and row["date_provenance"] is None
        assert row["record_review_id"] == original.get("review_id")
        assert row["projection_review_id"] == "OBS-R8-REVIEW-" + key
        assert row["source_id"] == sources[key]["source_id"]
        assert row["text_sha256"] == sha(original["text"].encode("utf-8"))
        assert row["research_source_sha256"] == sha(canonical(sources[key]))
        assert row["topic_ids"] == sorted({aspect["topic_id"] for aspect in row["aspects"]})
        for aspect in row["aspects"]:
            span = aspect["text_range"]
            assert span["unit"] == "unicode_codepoint" and span["end_exclusive"] is True
            assert 0 <= span["start"] < span["end"] <= len(original["text"])
            assert original["text"][span["start"]:span["end"]] == aspect["quote"]
            assert sha(aspect["quote"].encode("utf-8")) == aspect["quote_sha256"]
            assert aspect["topic_id"] in LABELS and aspect["polarity"] in POLARITIES
            quote_count += 1
    return quote_count


def guard_probes(draft, selected, sources):
    probes = []
    mutations = {
        "wrong_original_id": lambda d: d["rows"][0].update(original_review_id="NONDEVELOPMENT-ID"),
        "wrong_source_id": lambda d: d["rows"][0].update(source_id="OTHER-SOURCE"),
        "quote_range_shift": lambda d: d["rows"][0]["aspects"][0]["text_range"].update(start=0, end=1),
        "purchase_date_as_posting_date": lambda d: d["rows"][0].update(published_at="2026-09-19"),
        "page_model_as_purchased_sku": lambda d: d["rows"][0].update(actual_purchased_model_id=d["rows"][0]["displayed_page_model"]),
        "draft_as_approved": lambda d: d.update(pm_approved=True),
    }
    for name, mutate in mutations.items():
        changed = deepcopy(draft)
        mutate(changed)
        try:
            verify_draft(changed, selected, sources)
        except (AssertionError, KeyError):
            probes.append({"probe": name, "rejected": True})
        else:
            raise AssertionError("guard failed: " + name)
    return probes


def make_projection(selected, sources):
    reviews, evidence, metadata_rows, mapping = [], [], [], []
    for key in sorted(selected):
        record, source = selected[key], sources[key]
        page_scope = "PAGE-" + record["displayed_model_id"]
        eid = "OBS-R8-EVIDENCE-" + key
        rid = "OBS-R8-REVIEW-" + key
        common = {"model_id": page_scope, "document_version": source["document_version"],
            "source_kind": "public", "source_id": source["source_id"],
            "locator": deepcopy(source["locator"]), "text": record["text"]}
        reviews.append({"id": rid, "evidence_id": eid, **common})
        evidence.append({"id": eid, "source_type": "review", "feature_ids": [], **common})
        metadata_rows.append({"review_id": rid, "evidence_id": eid,
            **{field: common[field] for field in ("source_id", "model_id", "document_version", "source_kind")},
            "text_sha256": record["text_sha256"], "published_at": None, "date_precision": "unknown",
            "date_provenance": None, "topic_ids": [], "classification_status": "unclassified",
            "dedup_key": source["duplicate_group"]})
        mapping.append({"original_review_id": key, "record_review_id": record.get("review_id"), "projection_review_id": rid,
            "research_source_id": source["source_id"], "projection_evidence_id": eid,
            "collector_page_scope_id": page_scope, "displayed_page_model": record["displayed_model_id"],
            "actual_purchased_model_id": None, "canonical_evidence_assigned": False,
            "eligible_for_exact_model_judgement": False})
    return {"artifact_kind": "offline_observational_compatibility_projection",
        "manifest": {"version": PROJECTION_VERSION,
            "description": "PAGE namespace denotes displayed-page association only. Not an approved DemoDataset or runtime pack."},
        "reviews": reviews, "evidence": evidence}, metadata_rows, mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=Path, required=True)
    args = parser.parse_args()
    for path in ("apps/api/src", "packages/contracts/src", "packages/core/src"):
        sys.path.insert(0, str(args.source / "pm" / path))
    from lgax_api.review_trends import build_review_trend_collection, canonical_dataset_sha256
    from lgax_api.trend_validation import annotation_digest, canonical_annotation
    from lgax_contracts import validate

    pins, records, members, selected, bundles, sources = inputs(args.source)
    draft = make_draft(read(args.seeds), selected, members, sources)
    quote_count = verify_draft(draft, selected, sources)
    probes = guard_probes(draft, selected, sources)
    hashes = {}
    hashes["source-pins.json"] = write(args.output, "source-pins.json", pins)
    hashes["development-sources.json"] = write(args.output, "development-sources.json", {
        "source_commit": DATA_COMMIT, "original_dataset_version": "r8-public-research.20261007.v1",
        "annotation_version": VERSION, "selection": "development only",
        "sources": [deepcopy(sources[key]) for key in sorted(sources)]})
    hashes["annotation.draft.json"] = write(args.output, "annotation.draft.json", draft)
    group_ids = {group: sorted(key for key in selected if members[key]["product_group"] == group)
                 for group in bundles}
    topic_members = {topic: {polarity: sorted({row["original_review_id"] for row in draft["rows"]
        if any(aspect["topic_id"] == topic and aspect["polarity"] == polarity for aspect in row["aspects"])})
        for polarity in sorted(POLARITIES)} for topic in LABELS}
    hashes["draft-memberships.json"] = write(args.output, "draft-memberships.json", {
        "annotation_version": VERSION, "status": "draft", "denominator_scope": "selected development sample only",
        "selected_development_count": 141, "selected_original_review_ids": sorted(selected),
        "group_memberships": group_ids, "overall_opinion_counts": dict(Counter(row["overall_opinion"] for row in draft["rows"])),
        "topic_polarity_memberships": topic_members, "topic_ratios": {key: None for key in LABELS},
        "ratio_null_reason": "annotations not PM-approved; publication dates unconfirmed; no population inference"})
    partition_ids = {split: sorted(row["original_review_id"] for row in members.values() if row["split"] == split)
                     for split in sorted({row["split"] for row in members.values()})}
    assert sorted(key for ids in partition_ids.values() for key in ids) == sorted(records)
    assert len(set(key for ids in partition_ids.values() for key in ids)) == 238
    hashes["partition-memberships.json"] = write(args.output, "partition-memberships.json", {
        "source_commit": DATA_COMMIT, "partition_source": DELIVERY + "d1-membership.json",
        "original_review_id_memberships": partition_ids,
        "note": "Nondevelopment IDs only; evaluation/demonstration/quarantine text is not annotated or copied."})
    dataset, metadata_rows, mapping = make_projection(selected, sources)
    metadata = {"dataset_version": PROJECTION_VERSION, "dataset_sha256": canonical_dataset_sha256(dataset),
        "annotation_version": "r8-date-only-unclassified.20261008.01a114f6.v1", "annotation_sha256": "0" * 64,
        "topic_taxonomy_version": "date-only-no-topic-classification.v1", "dedup_policy_version": "original-review-id-and-group-preserved.v1",
        "classification": {"method": "unclassified", "model_id": None, "revision": None}, "rows": metadata_rows}
    metadata["annotation_sha256"] = annotation_digest(metadata)
    metadata = canonical_annotation(metadata)
    validate("ReviewTrendMetadata", metadata)
    hashes["projection.date-only.dataset.json"] = write(args.output, "projection.date-only.dataset.json", dataset)
    hashes["date-only.metadata.json"] = write(args.output, "date-only.metadata.json", metadata)
    hashes["review-id-map.json"] = write(args.output, "review-id-map.json", {
        "projection_version": PROJECTION_VERSION, "runtime_approved": False, "mappings": mapping})
    query_results = []
    model_groups = defaultdict(list)
    for review in dataset["reviews"]:
        model_groups[review["model_id"]].append(review)
    for model, rows in sorted(model_groups.items()):
        versions = {row["document_version"] for row in rows}
        assert len(versions) == 1
        project_id = "OFFLINE-DATE-CHECK-" + model
        project = {"project": {"id": project_id, "request": {"model_ids": [model]}},
                   "document_versions": {model: versions.pop()}}
        for granularity, start, end in (("month", "2026-10-01", "2026-11-01"),
                                        ("season", "2026-12-01", "2027-03-01")):
            filters = {"project_id": project_id, "model_id": model,
                "source_ids": sorted({row["source_id"] for row in rows}), "dataset_version": PROJECTION_VERSION,
                "start_date": start, "end_date_exclusive": end, "granularity": granularity,
                "topic_ids": ["cleaning"], "source_kind": "public", "timezone": "Asia/Seoul"}
            collection = build_review_trend_collection(project, dataset, filters, metadata)
            validate("ReviewTrendAggregate", collection.aggregate)
            counts = collection.aggregate["counts"]
            assert counts["input_review_count"] == 141 and counts["in_scope_review_count"] == len(rows)
            assert counts["excluded_undated_count"] == len(rows) and counts["eligible_unique_review_count"] == 0
            assert counts["duplicate_count"] == 0
            for bucket in collection.aggregate["buckets"]:
                assert bucket["total_reviews"] == 0
                assert all(topic["ratio"] is None and topic["evidence_ids"] == [] for topic in bucket["topics"])
                assert all(ids == [] for ids in collection.memberships[bucket["bucket_id"]].values())
            query_results.append({"page_scope": model, "purpose": "empty-date contract check, not a dated trend",
                "project": project, "aggregate": collection.aggregate, "memberships": collection.memberships})
    assert len(query_results) == 36
    hashes["empty-collector-checks.json"] = write(args.output, "empty-collector-checks.json", {
        "pm_code_commit": PM_COMMIT, "collector": "lgax_api.review_trends.build_review_trend_collection",
        "scope": "offline legacy PAGE association projection only; no server registration, DB or API",
        "draft_topic_annotations_consumed": False, "display_as_monthly_or_seasonal_trend": False,
        "queries": query_results})
    counts = {split: len(ids) for split, ids in partition_ids.items()}
    summary = {"annotation_version": VERSION, "status": "draft", "data_commit": DATA_COMMIT,
        "pm_implementation_commit": PM_COMMIT, "original_dataset_version": "r8-public-research.20261007.v1",
        "delivery_manifest_version": read(args.source / "data" / (DELIVERY + "d1-delivery-manifest.json"))["version"],
        "annotation_file_sha256": hashes["annotation.draft.json"],
        "date_sidecar_file_sha256": hashes["date-only.metadata.json"],
        "date_sidecar_canonical_annotation_sha256": metadata["annotation_sha256"],
        "source_snapshot_file_sha256": hashes["development-sources.json"],
        "source_pins_file_sha256": hashes["source-pins.json"],
        "sample": {"observations": 239, "unique_original_review_ids": 238, "reobserved_original_review_ids": ["860977"],
            "pre_split_observation_accounting_basis": "pinned D1 delivery manifest; no raw collection repeated",
            "pre_split_duplicate_observations": 1, "partition_counts": counts,
            "development_selected": 141, "excluded_nondevelopment_unique_ids": 97,
            "development_group_counts": {group: len(ids) for group, ids in group_ids.items()},
            "development_unknown_publication_date_count": 141,
            "development_monthly_eligible_denominator": 0, "development_seasonal_eligible_denominator": 0,
            "time_eligible_original_review_ids": [], "ratio": None, "draft_annotation_count": 141,
            "confirmed_purchased_sku_count": 0},
        "bundles": {group: {"bundle_id": bundle["bundle_id"], "source_count": len(bundle["sources"]),
            "development_reviews_used": len(group_ids[group]), "nonreview_sources_annotated": 0} for group, bundle in bundles.items()},
        "approval": {"topic_draft_pm_approved": False, "independent_evaluation_gold": False,
            "exact_model_runtime_projection_approved": False, "runtime_registered": False,
            "web_receipt_confirmed": False, "parent_done": False},
        "limitations": ["추천순/별점순/최신순의 목적 표본, 모집단/시장 수요 비율 아님",
            "개발141만 주제 초안 작성; 평가36/시연49/격리12는 ID membership만 확인",
            "날짜미상141은 선택 후 시간분모 제외; scope제외97과 중복 합산하지 않음",
            "입력 관측중복1과 collector 기간내 duplicate_count0는 다른 계산 단계",
            "문서버전은 페이지 모델의 연결 참고자료; 후기판/구매당시 설명서 아님",
            "PAGE namespace 및 OBS Evidence IDs는 별도검수용 기대 대응이며 canonical 신규 등록 성공 아님",
            "cleaning 필터의 빈 count0은 승인된 토픽 언급0의 증거가 아니라 미상 날짜 분모0 결과"],
        "execution": {"new_product_model_calls": 0, "new_ocr_calls": 0, "network_access": False,
            "operating_db_api_restarts": 0, "production_files_modified": 0}, "files": hashes}
    write(args.output, "handoff-summary.json", summary)
    verification = {"status": "PASS", "development_rows": 141, "exact_quote_ranges_checked": quote_count,
        "counterexample_pairs_checked": len(draft["counterexample_pairs"]),
        "metadata_tamper_probes": probes, "existing_collector_empty_queries": 36,
        "all_dated_memberships_empty": True, "all_dated_denominators_zero": True, "all_ratios_null": True,
        "unapproved_topic_metadata_injected": False, "original_or_shared_files_modified": 0,
        "topic_semantic_accuracy": None, "pm_approval": False,
        "scope": "source binding and deterministic accounting; no Gold/actual runtime acceptance"}
    write(args.output, "verification.json", verification)
    print(json.dumps({"status": "PASS", "rows": 141, "quotes": quote_count,
        "counterpairs": len(COUNTERPAIRS), "collector_queries": 36,
        "annotation_sha256": hashes["annotation.draft.json"], "source_snapshot_sha256": hashes["development-sources.json"]}))


if __name__ == "__main__":
    main()
