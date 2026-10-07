"""Adapt frozen official competitor excerpts to a separate ResearchBundle; no collection/model calls."""

import argparse
import json
import re
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from lgax_contracts.research import validate_research_bundle

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("data/research/r8-public-research-20261007/bundles/fridge.development.research-bundle.json")
SIDECAR = Path("data/research/r8-public-research-20261007/competitors/01a114f6")
OUTPUT = Path("data/research/r8-public-competitor-adapter-20261007")
BASE_SHA256 = "4f0f199294fdefeef2fdbaa2581981342a8a84c282d9abdd4ad1818473be08c7"
MANIFEST_SHA256 = "535c08e6009e873c3d09fc92b5fcb68b47f88bad562e34c33f15bca97bc9de6d"
VERSION = "r8-public-competitor-adapter.20261007.v1"
BUNDLE_ID = "LGE-R8-fridge-development-20261007-competitor-v1"
BUNDLE_FILE = "fridge.development.research-bundle.json"
# Installation labels/conditions and illustration caveats are official documents, not customer reports.
EXCERPT_TYPES = {
    "SS-CAP": "spec", "SS-DIMS": "spec", "SS-INSTALL": "installation", "SS-FOLD": "spec",
    "SS-GAP": "installation", "SS-COUNTER": "installation", "SS-ILLUSTRATION": "installation",
    "LG-CAP": "spec", "LG-DIMS": "spec", "LG-INSTALL": "installation",
    "LG-LAUNCH": "spec", "LG-FOLD": "spec",
}
PAGE_MODELS = {
    "samsung-rm70-spec": ("RM70F63R231", "Samsung", "www.samsung.com"),
    "samsung-rm70-product": ("RM70F63R231", "Samsung", "www.samsung.com"),
    "lg-t876-product": ("T876MEE1H1", "LG", "www.lge.co.kr"),
}
CONTEXT_QUOTES = {
    "installation_constraint": "구축 아파트라 사이즈가 맞지 않아 키친핏을 포기하고",
    "positive_comfort": "냉장실이 위에 있어 허리도 편하고 훨씬 만족스럽네요.",
    "positive_storage": "용량이 커서 식재료가 넉넉하게 들어가고 수납도 확 트였습니다.",
    "residual_reach": "안쪽 깊숙한 곳은 팔이 잘 닿지 않아 공간을 다 활용하기 어렵다는 아쉬움",
}


def digest(raw):
    return sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def pinned(path, expected):
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"Frozen input hash mismatch: {path.name}")
    return raw


def load_inputs(root=ROOT):
    base_raw = pinned(root / BASE, BASE_SHA256)
    manifest_raw = pinned(root / SIDECAR / "manifest.json", MANIFEST_SHA256)
    producer_manifest = json.loads(manifest_raw)
    entries = {entry["path"]: entry for entry in producer_manifest["files"]}
    inputs = {str(BASE): BASE_SHA256, str(SIDECAR / "manifest.json"): MANIFEST_SHA256}
    values = []
    for name in ("official-sources.json", "comparison.json"):
        entry = entries[name]
        raw = pinned(root / SIDECAR / name, entry["sha256"])
        if len(raw) != entry["bytes"]:
            raise ValueError(f"Frozen input size mismatch: {name}")
        inputs[str(SIDECAR / name)] = entry["sha256"]
        values.append(json.loads(raw))
    base = json.loads(base_raw)
    validate_research_bundle(base)
    if len(base["sources"]) != 54 or base["analysis_scope"] != "product_group" or base["product_group"] != "fridge":
        raise ValueError("Expected the fixed 54-source product-group fridge baseline")
    return base, values[0], values[1], {"producer_manifest": producer_manifest, "input_sha256": inputs}


def convert_sources(sidecar):
    if sidecar.get("schema_version") != "d3-official-source-excerpts.1" or len(sidecar["sources"]) != 3:
        raise ValueError("Expected the frozen three-page official sidecar")
    converted, lineage, seen = [], [], set()
    for page in sidecar["sources"]:
        model, brand, host = PAGE_MODELS[page["id"]]
        parsed = urlsplit(page["final_url"])
        if (page["model_id"] != model or parsed.scheme != "https" or parsed.hostname != host
                or parsed.username or parsed.password or page["http_status"] != 200):
            raise ValueError("Official page/model provenance mismatch")
        if (not re.fullmatch(r"[a-f0-9]{64}", page["source_sha256"])
                or page["capture_version"] != "html-sha256:" + page["source_sha256"]
                or not page["captured_at"]):
            raise ValueError("Official capture version/hash/time mismatch")
        page_origin = {key: deepcopy(value) for key, value in page.items() if key != "excerpts"}
        for excerpt in page["excerpts"]:
            excerpt_id = excerpt["id"]
            if excerpt_id not in EXCERPT_TYPES or excerpt_id in seen:
                raise ValueError("Unknown or duplicate official excerpt ID")
            seen.add(excerpt_id)
            if not excerpt["text"] or digest(excerpt["text"].encode("utf-8")) != excerpt["text_sha256"]:
                raise ValueError("Official excerpt text/hash mismatch")
            start, end = excerpt["normalized_text_range"]
            if not 0 <= start < end or end - start != len(excerpt["text"]) or not excerpt["locators"]:
                raise ValueError("Official excerpt normalized range/locator mismatch")
            locator = {key: deepcopy(excerpt[key]) for key in
                       ("normalized_text_range", "location_basis", "locators")}
            locator["excerpt_id"] = excerpt_id
            source_id = "D3-01a114f6-" + excerpt_id
            source_type = EXCERPT_TYPES[excerpt_id]
            source = {
                "source_id": source_id, "source_type": source_type, "source_kind": "public",
                "product_group": "fridge", "url": page["final_url"],
                "title": f"{model} 공식 {source_type} 발췌 {excerpt_id}", "text": excerpt["text"],
                "page_model": model, "purchased_model": None, "published_at": None, "date_kind": "unknown",
                "coverage": "excerpt",
                "source_role": "official_specification" if source_type == "spec" else "official_document",
                "document_version": page["capture_version"], "brand": brand,
                "collected_at": page["captured_at"], "locator": locator,
                "facts": [{"fact_id": source_id + "-document-fact", "kind": "document_fact",
                           "text": excerpt["text"], "locator": deepcopy(locator)}],
                "metadata": {
                    "adapter_author": "current_chat_manual_support", "adapter_version": VERSION,
                    "origin_page": page_origin, "origin_excerpt_id": excerpt_id,
                    "text_sha256": excerpt["text_sha256"], "hash_scope": "exact_UTF8_excerpt_only",
                    "full_document_captured_in_payload": False,
                    "raw_html_reverified_by_adapter": False, "customer_experience": False,
                    "official_page_claim_not_independent_physical_measurement": True,
                    "internal_reach_or_customer_resolution_inferred": False,
                },
            }
            converted.append(source)
            lineage.append({"source_id": source_id, "page_id": page["id"], "excerpt_id": excerpt_id,
                            "html_sha256": page["source_sha256"], "excerpt_sha256": excerpt["text_sha256"],
                            "document_version": page["capture_version"], "collected_at": page["captured_at"],
                            "locator": deepcopy(locator), "source_type": source_type,
                            "source_role": source["source_role"]})
    if seen != set(EXCERPT_TYPES):
        raise ValueError("Expected all twelve frozen official excerpts")
    return converted, lineage


def problem_focus(base, comparison):
    original = comparison["problem"]
    review = next(source for source in base["sources"]
                  if source["source_type"] == "review" and source["metadata"]["original_review_id"] == "848850")
    metadata = review["metadata"]
    if (digest(review["text"].encode("utf-8")) != original["original_text_sha256"]
            or review["published_at"] is not None or review["purchased_model"] is not None
            or metadata["split"] != "development"
            or metadata["strict_exact_model_eligible_for_model_input"] is not False
            or metadata["purchase_date"] != original["purchase_date"]):
        raise ValueError("Original customer context, split or model/date uncertainty changed")
    contexts = []
    for context_id, quote in CONTEXT_QUOTES.items():
        start = review["text"].find(quote)
        if start < 0:
            raise ValueError("Original installation/positive/residual context missing")
        contexts.append({"context_id": context_id, "source_id": review["source_id"], "quote": quote,
                         "text_range": [start, start + len(quote)], "kind": "literal_review_context"})
    return {
        "candidate_id": original["candidate_id"], "first_problem_id": original["first_problem_id"],
        "source_id": review["source_id"], "original_review_id": "848850",
        "original_text_sha256": original["original_text_sha256"], "literal_contexts": contexts,
        "purchased_model": None, "published_at": None, "purchase_date": metadata["purchase_date"],
        "split": "development", "strict_exact_model_eligible_for_model_input": False,
        "customer_report_not_verified_model_defect": True,
        "external_depth_is_internal_arm_reach": False, "customer_burden_resolved": False,
        "positive_experience_and_installation_constraints_preserved": True,
        "independent_semantic_quality_verified": False,
    }


def build_adapter(root=ROOT, output=None):
    root = Path(root)
    output = Path(output) if output is not None else root / OUTPUT
    target = output.resolve()
    protected = (root / BASE.parent.parent).resolve()
    if target.is_relative_to(protected) or protected.is_relative_to(target):
        raise ValueError("Frozen baseline/producer area cannot be used as output")
    base, sidecar, comparison, pins = load_inputs(root)
    additions, new_lineage = convert_sources(sidecar)
    focus = problem_focus(base, comparison)
    bundle = deepcopy(base)
    bundle["bundle_id"] = BUNDLE_ID
    bundle["sources"].extend(additions)
    collection = bundle["collection_manifest"]
    collection.update({
        "dataset_version": VERSION, "baseline_bundle_id": base["bundle_id"],
        "baseline_bundle_sha256": BASE_SHA256, "baseline_source_objects_preserved": True,
        "source_type_counts": dict(Counter(source["source_type"] for source in bundle["sources"])),
        "new_source_ids": [source["source_id"] for source in additions],
        "problem_focus": focus, "competitor_input_pins": pins["input_sha256"],
        "original_comparison_conditions": deepcopy(comparison["comparability"]),
        "comparison_interpretation_is_researcher_annotation": True,
        "comparison_interpretation": deepcopy(comparison["interpretation"]),
        "comparison_model_conditions": deepcopy(comparison["models"]),
        "manufacturer_release_period_comparability": "unverified_for_exact_Samsung_SKU",
        "independent_semantic_quality_verified": False,
        "next_step": "manual_registration_and_planning_intake_not_performed_by_adapter",
    })
    collection["limitations"].extend([
        "Official external dimensions do not establish internal reach, reduced burden or causal customer benefit.",
        "Different capacity, installation, handle bases and unverified release timing prevent controlled performance comparison.",
        "Product images/alt descriptions and folding-shelf mentions are partial page claims; manual conditions remain pending.",
        "The review's installation constraint and positive capacity/comfort coexist with residual reach discomfort.",
        "No new reviews, customer Q&A, posting dates, purchased SKUs, model calls or physical tests were added.",
    ])
    validate_research_bundle(bundle)
    if bundle["sources"][:54] != base["sources"] or len(bundle["sources"]) != 66:
        raise ValueError("Baseline sources were changed or unexpected source count")
    lineage = {
        "hash_scope": "canonical UTF8 JSON source object; original input file hash is pinned separately",
        "baseline_source_sha256": {source["source_id"]: digest(json_bytes(source)) for source in base["sources"]},
        "new_sources": new_lineage,
    }
    manifest = {
        "artifact_kind": "separate_public_competitor_research_adapter", "adapter_version": VERSION,
        "adapter_author": "current_chat_manual_support", "adapter_script_sha256": digest(Path(__file__).read_bytes()),
        "bundle_id": BUNDLE_ID, "bundle_file": BUNDLE_FILE, "input_sha256": pins["input_sha256"],
        "producer_version": pins["producer_manifest"]["version"],
        "producer_pr": 244, "producer_head": "3079455cb856462eb4ab466540884617f966f9c1",
        "baseline_source_count": 54, "added_source_count": 12, "source_count": 66, "review_count": 48,
        "source_type_counts": collection["source_type_counts"], "source_role_counts":
            dict(Counter(source["source_role"] for source in additions)),
        "baseline_source_objects_preserved": True, "original_review_holds_and_split_preserved": True,
        "problem_focus": focus, "synthetic_review_count": 0, "network_requests": 0, "model_calls": 0,
        "raw_html_retrieved": False, "operating_db_changed": False, "existing_api_bundles_replaced": False,
        "registered_for_api": False, "planning_run_executed": False,
        "independent_semantic_quality_verified": False, "parent_done": False,
        "completion_scope": "contract adapter and next manual planning input only",
    }
    readme = (
        "# 냉장고 실제 경쟁근거 계약 변환 인수\n\n"
        "기존 냉장고 development 입력 54개를 보존하고, PR244의 실제 공식 발췌 12개를 더한 별도 ResearchBundle이다. "
        "후기 48개·설명서 6개·공식 사양 7개·설치/연출 조건 5개이며 새 후기를 만들지 않았다.\n\n"
        "후기848850의 설치 제약·편안함/용량 만족·잔여 접근 불편을 원 source ID와 연결했다. 구매 SKU·게시일 미상, "
        "원문·facts·development 분할·기존 엄격한 모델 입력 보류를 유지한다.\n\n"
        "공식 외형 깊이와 설치 사양은 내부 팔 도달거리나 불편 해결을 입증하지 않는다. 용량·설치·핸들 기준·출시 시점·"
        "접이선반 적용 조건의 한계와 미확인 항목을 보존한다. 모든 추가 본문은 발췌이며 전체 문서가 아니다.\n\n"
        "현재 채팅의 수동 지원 구현이다. 원 HTML 재수집·모델 호출·운영 DB 변경·기존 API 등록 교체는 0이다. "
        "이 팩은 다음 수동 기획 입력 준비까지이며 실제 등록/기획 실행·독립 의미 품질·D3 전체 완료는 미완료다.\n\n"
        f"- 입력: [{BUNDLE_FILE}]({BUNDLE_FILE})\n"
        "- 추가 근거: [sources.json](sources.json)\n"
        "- 출처/검증 범위: [manifest.json](manifest.json), [lineage.json](lineage.json), [files.json](files.json)\n"
    ).encode()
    artifacts = {BUNDLE_FILE: json_bytes(bundle), "sources.json": json_bytes(additions),
                 "manifest.json": json_bytes(manifest), "lineage.json": json_bytes(lineage), "README.md": readme}
    # All pins, text/locator provenance and contracts are checked before any derived output is written.
    output.mkdir(parents=True, exist_ok=True)
    file_pins = {}
    for name, raw in artifacts.items():
        (output / name).write_bytes(raw)
        file_pins[name] = digest(raw)
    (output / "files.json").write_bytes(json_bytes(file_pins))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    args = parser.parse_args()
    result = build_adapter(output=args.output)
    print(json.dumps({"bundle_id": result["bundle_id"], "source_count": result["source_count"],
                      "added_source_count": result["added_source_count"], "model_calls": 0,
                      "network_requests": 0, "registered_for_api": False, "parent_done": False}))


if __name__ == "__main__":
    main()
