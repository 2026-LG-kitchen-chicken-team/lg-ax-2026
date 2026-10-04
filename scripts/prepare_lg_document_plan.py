"""Curate bounded submission features from the approved reference pack and exact manual text."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/research/P2-DATA-001-stage123-20261005"

RECIPES = {
    "T876MEE1H1": [
        ("F08", 18, "냉장실 접이식 선반 사용하기", "접이식 선반", "folding-shelf", "접이식 선반 1개"),
        ("F10", 19, "선반 위에 있는 식품을 치운 후", "선반 분리", "shelf-removal", None),
        ("F11", 21, "내부 청소하기", "내부 청소", "inside-cleaning", None),
    ],
    "DUE6BGL2E": [
        ("D12", 20, "하단 식기 바구니에 식기 배열하기", "식기 배열", "basket-assignment", None),
        ("D09", 23, "높이를 3단계로 조절", "상단 바구니 높이", "basket-height", "높이를 3단계로 조절"),
        ("D13", 23, "바구니를 모두 비운 후", "높이 조절 조건", "basket-height", None),
        ("D14", 24, "식기 크기가 크면 상단 노즐에", "노즐 간섭 조건", "nozzle-clearance", None),
    ],
    "MW23FDI": [
        ("M11", 25, "출력을 선택하여 조리하는 기능입니다.", "출력 조절", "power-selection",
         "200/400/600/800/1000 W의 조리 출력 선택"),
        ("M14", 17, "버튼을 누를 때마다 30초씩", "간편조리 시간", "quick-time", "시작/선택 누름마다 30초 증가"),
        ("M15", 18, "지정된 음식의 종류에 따라 조리시간이 기억되어 있어", "자동데우기 메뉴", "auto-reheating",
         "제조사가 지정한 즉석밥·국/찌개·우유 메뉴"),
    ],
}


def main():
    pack = json.loads((ROOT / "data/research/P2-DATA-001-real-reference-20261004/reference-pack.json")
                      .read_text(encoding="utf-8"))
    products = {p["model_id"]: p for p in pack["products"]}
    facts = {f["id"]: f for f in pack["facts"]}
    downloads = json.loads((RUN / "download.json").read_text(encoding="utf-8"))
    limitations = ["실제 고객 리뷰 미수집; 고객 불편 빈도·수요·효과는 입증하지 않음",
                  "정의한 사례 기능 전체이며 LG 제품의 전체 기능 카탈로그가 아님",
                  "DemoDataset Manifest는 합성 전용이므로 별도 document_dataset container 사용",
                  "원문 PDF/전체 추출 텍스트/이미지는 private에만 보존"]
    plan = {"artifact_kind": "trusted_document_plan", "dataset_version": "lg-manual-scope-20261005.1",
            "documents": [], "original_review_count": 0, "limitations": limitations}
    mapping = []
    for download in downloads:
        model = download["model_id"]
        product = products[model]
        texts = json.loads((ROOT / download["private_path"]).with_suffix(".pages.json").read_text(encoding="utf-8"))
        did = model + "-manual-" + download["sha256"][:12]
        features, selections = {}, []
        for factid, page, excerpt, section, suffix, description in RECIPES[model]:
            if texts[page - 1].count(excerpt) != 1:
                raise ValueError(f"Excerpt not uniquely located: {model}/{page}/{factid}")
            fid, eid = model + "-FEATURE-" + suffix, model + "-MANUAL-" + factid
            fact = facts[factid]
            selections.append({"evidence_id": eid, "page": page, "excerpt": excerpt,
                               "section": section, "feature_ids": [fid]})
            description = description or fact["value"]
            conditions = [fact["conditions"]] if fact["conditions"] else []
            if factid == "F08":
                conditions += ["공용 설명서의 일부 모델 기능; 동일 모델 제품 페이지 F08의 선반 1개 표기와 연결",
                               "제품 페이지 값은 설명서 원문 인용으로 표시하지 않음"]
            if fid not in features:
                features[fid] = {"id": fid, "model_id": model, "document_version": product["document_version"],
                                 "name": section, "description": description, "conditions": conditions,
                                 "evidence_ids": []}
            elif factid == "D13":
                features[fid]["conditions"] += [description] + conditions
            features[fid]["evidence_ids"].append(eid)
            mapping.append({"research_fact_id": factid, "canonical_feature_id": fid,
                            "canonical_evidence_id": eid, "document_id": did, "model_id": model,
                            "document_version": product["document_version"], "source_kind": "public"})
        plan["documents"].append({"document_id": did, "product": product,
                                  "document_version": product["document_version"], "source_kind": "public",
                                  "url": download["url"], "checked_at": download["checked_at"],
                                  "sha256": download["sha256"], "features": list(features.values()),
                                  "selections": selections, "applicability": {
                                      "basis": "approved same-model LG product-to-manual link and source mapping",
                                      "exact_model_text_in_pdf": model == "MW23FDI",
                                      "family_in_pdf": "DUE6****E" if model == "DUE6BGL2E" else
                                      ("상냉장 하냉동 냉장고" if model == "T876MEE1H1" else "MW23FDI"),
                                      "cover_version_visually_confirmed": True,
                                      "not_all_family_optional_features_assumed": True}})
    out = ROOT / "data/document_plans"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lg-three-models-20261005.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8", newline="\n")
    report = {"mapped_use_case_facts": mapping, "total_reference_facts": 60,
              "other_facts_preserved_in_reference_pack": 60 - len(mapping),
              "not_silently_converted": ["제품 페이지·판매처를 manual/review로 표시하지 않음",
                                         "미확인 M16을 미지원 기능으로 만들지 않음",
                                         "공용 설명서의 프라이팬 거치대 D10을 실제 모델 기능으로 넣지 않음"],
              "references_gaps": len(pack["gaps"]), "references_conflicts": len(pack["conflicts"]),
              "feature_count": sum(len(d["features"]) for d in plan["documents"]),
              "evidence_count": sum(len(d["selections"]) for d in plan["documents"]),
              "original_reviews": 0, "ocr_used": False, "limitations": limitations,
              "cover_and_spec_pages_visually_checked": ["T876MEE1H1 p1", "DUE6BGL2E p1/p57", "MW23FDI p1/p37"]}
    (RUN / "mapping.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({"models": list(products), "features": report["feature_count"],
                      "evidence": report["evidence_count"], "original_reviews": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
