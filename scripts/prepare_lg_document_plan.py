"""Curate bounded submission features from the approved reference pack and exact manual text."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/research/P2-DATA-001-stage123-20261005"

RECIPES = {
    "T876MEE1H1": [
        ("F08", 18, "냉장실 접이식 선반 사용하기\n이 기능이 적용된 모델에만 해당하는 내용입니다.\n보관 식품의 높이와 크기에 따라 접이식 선반을 조절하여 \n공간을 활용할 수 있습니다.",
         "접이식 선반", "folding-shelf", "공용 설명서의 적용 모델에서 접이식 선반으로 식품 높이·크기에 맞게 공간 활용"),
        ("F10", 19, "아랫부분을 받친 후 위로 살짝 들어 올리며 홈에서 선반 \n고리를 빼내세요.", "선반 분리", "shelf-removal",
         "선반 위 식품을 치운 뒤 선반 양쪽을 받쳐 홈에서 고리를 분리"),
        ("F11", 21, "내부 청소하기\n• 제품 내 구성품 분리 시 보관된 식품을 모두 꺼내세요.  \n꺼내지 않으면 보관된 식품의 무게로 인해 다칠 수  \n있습니다.\n• 냉장고 안의 선반이나 냉장고 문에 있는 바구니, 냉장고 \n문의 고무 패킹은 부드러운 수건에 물을 묻혀서  \n닦으세요.\n• 냉장고 청소 후 물기를 완전히 닦지 않으면 냉장고 안이 \n얼 수 있으므로 물기를 완전히 제거하세요.",
         "내부 청소", "inside-cleaning", None),
    ],
    "DUE6BGL2E": [
        ("D12", 20, "하단 식기 바구니에 식기 배열하기\n하단 식기 바구니는 큰 접시, 냄비, 프라이팬, 오목한 그릇 \n등 부피가 큰 식기를 세척하기에 좋습니다.\n상단 식기 바구니에 식기 배열하기\n상단 식기 바구니는 오목한 그릇, 작은 접시, 컵, 유리잔  \n등을 세척하기에 좋습니다.\n• 컵 선반에는 컵, 작은 식기 등을 놓을 수 있습니다.\n최상단 식기 바구니에 식기 배열하기\n최상단 식기 바구니는 수저류, 칼, 포크 등을 세척하기에  \n좋습니다.",
         "식기 배열", "basket-assignment", None),
        ("D09", 23, "높이를 3단계로 조절", "상단 바구니 높이", "basket-height", "높이를 3단계로 조절"),
        ("D13", 23, "반드시 식기 바구니를 모두 비운 후 높이를 조절하세요.", "높이 조절 조건", "basket-height", None),
        ("D14", 24, "상단 식기 바구니를 먼저 밀어 넣은 후 하단 식기  \n바구니를 밀어 넣으세요. 식기 크기가 크면 상단 노즐에 \n닿아 잘 돌아가지 않습니다.", "노즐 간섭 조건", "nozzle-clearance",
         "상단 바구니를 먼저 넣고 큰 식기가 상단 노즐 회전을 가리는지 확인"),
    ],
    "MW23FDI": [
        ("M11", 25, "버튼을 누를 때마다 1000 W ~ 800 W ~ 600 W ~ \n400 W ~ 200 W ~ 1000 W 순으로 진행표시부에 \n표시됩니다.", "출력 조절", "power-selection",
         "200/400/600/800/1000 W의 조리 출력 선택"),
        ("M14", 17, "2 문을 닫고 시작/선택  버튼을 세 번 누르세요.\n• 자동으로 조리가 시작됩니다.\n• 버튼을 누를 때마다 30초씩 올라가며", "간편조리 시간", "quick-time", "시작/선택 누름마다 30초 증가"),
        ("M15", 18, "지정된 음식의 종류에 따라 조리시간이 기억되어 있어  \n자동으로 조리됩니다.\n1 음식물을 제품 중앙에 넣으세요.\n2 자동요리  버튼을 한 번 눌러서 자동데우기 를  \n선택하세요.\n3 시작/선택  버튼을 누르면 1-1이 진행표시부에  \n표시됩니다.\n4 시간/무게 조절  버튼(다이얼)으로 원하는 메뉴를  \n선택하세요.\n• + 버튼(다이얼): 1-1 즉석밥 ~ 1-z 국/찌개 ~  \n1-3 우유  순으로 진행표시부에 표시됩니다.", "자동데우기 메뉴", "auto-reheating",
         "제조사가 지정한 즉석밥·국/찌개·우유 메뉴"),
    ],
}

SUPPLEMENTAL = {
    "T876MEE1H1": [
        ("F10-P18", 18, "1 냉장실 선반을 빼낼 때는 한 손으로 냉장실 선반 한쪽의 \n바깥부분을 잡고 다른 손으로 선반 다른 쪽의", "선반 양쪽 받치기", "shelf-removal"),
        ("F10-FOOD", 19, "유리 선반은 무거우므로 선반을 분리할때 주의하세요.\n• 선반을 분리할 때, 선반 위에 있는 식품을 치운 후  \n분리하세요.", "유리 선반·식품 제거", "shelf-removal"),
        ("F11-P05", 5, "청소 또는 제품 실내등 교체 시에는 전원 플러그를 빼세요.", "청소 전 플러그 분리", "inside-cleaning"),
    ],
    "DUE6BGL2E": [
        ("D13-P24", 24, "식기 바구니의 양쪽 높이가 동일한지 확인한 후 제품  \n안쪽으로 밀어 넣으세요.", "양쪽 높이 확인", "basket-height"),
        ("D14-P20", 20, "상단 식기 바구니를 제품에서 빼낸 상태에서 식기를  \n세척하지 마세요.", "상단 바구니 없는 세척 금지", "nozzle-clearance"),
    ],
    "MW23FDI": [],
}

CONDITIONS = {
    "folding-shelf": ["공용 설명서의 일부 적용 모델 안내; 정확 모델 적용·선반 수량은 이 인용만으로 미확인"],
    "shelf-removal": ["선반 위 식품 제거; 무거운 유리 선반 분리 시 주의"],
    "inside-cleaning": ["구성품 분리 전 식품 제거(p21); 청소 전 전원 플러그 분리(p5)"],
    "basket-assignment": ["공용 DUE6****E 설명서의 바구니별 식기 배치 안내"],
    "basket-height": ["식기 바구니를 모두 비운 뒤 높이 조절(p23); 양쪽 높이 동일 확인(p24)"],
    "nozzle-clearance": ["상단 바구니를 빼낸 상태에서 세척하지 않음(p20)"],
    "power-selection": ["조리 출력 선택 안내이며 개인 시간/출력 조합 저장 지원 여부는 이 인용으로 미확인"],
    "quick-time": ["간편조리의 시작/선택 버튼 조작; 개인 프리셋 저장 지원 여부는 이 인용으로 미확인"],
    "auto-reheating": ["제조사 지정 메뉴의 기억된 조리시간; 개인 설정 저장 지원 여부는 이 인용으로 미확인"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-directory", type=Path, default=RUN)
    args = parser.parse_args()
    run = args.run_directory.resolve()
    if not run.is_relative_to(ROOT / "data/research"):
        raise ValueError("Run evidence must remain in data/research")
    run.mkdir(parents=True, exist_ok=True)
    pack = json.loads((ROOT / "data/research/P2-DATA-001-real-reference-20261004/reference-pack.json")
                      .read_text(encoding="utf-8"))
    products = {p["model_id"]: p for p in pack["products"]}
    facts = {f["id"]: f for f in pack["facts"]}
    downloads = json.loads((RUN / "download.json").read_text(encoding="utf-8"))
    limitations = ["실제 고객 리뷰 미수집; 고객 불편 빈도·수요·효과는 입증하지 않음",
                  "정의한 사례 기능 전체이며 LG 제품의 전체 기능 카탈로그가 아님",
                  "DemoDataset Manifest는 합성 전용이므로 별도 document_dataset container 사용",
                  "원문 PDF/전체 추출 텍스트/이미지는 private에만 보존"]
    plan = {"artifact_kind": "trusted_document_plan", "dataset_version": "lg-manual-scope-20261005.2",
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
            conditions = CONDITIONS[suffix]
            if fid not in features:
                features[fid] = {"id": fid, "model_id": model, "document_version": product["document_version"],
                                 "name": section, "description": description, "conditions": conditions,
                                 "evidence_ids": []}
            features[fid]["evidence_ids"].append(eid)
            mapping.append({"research_fact_id": factid, "canonical_feature_id": fid,
                            "canonical_evidence_id": eid, "document_id": did, "model_id": model,
                            "document_version": product["document_version"], "source_kind": "public"})
        for key, page, excerpt, section, suffix in SUPPLEMENTAL[model]:
            if texts[page - 1].count(excerpt) != 1:
                raise ValueError(f"Excerpt not uniquely located: {model}/{page}/{key}")
            fid, eid = model + "-FEATURE-" + suffix, model + "-MANUAL-" + key
            selections.append({"evidence_id": eid, "page": page, "excerpt": excerpt,
                               "section": section, "feature_ids": [fid]})
            features[fid]["evidence_ids"].append(eid)
            mapping.append({"research_fact_id": key.split("-")[0], "canonical_feature_id": fid,
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
              "other_facts_preserved_in_reference_pack": 60 - len({m["research_fact_id"] for m in mapping}),
              "not_silently_converted": ["제품 페이지·판매처를 manual/review로 표시하지 않음",
                                         "미확인 M16을 미지원 기능으로 만들지 않음",
                                         "공용 설명서의 프라이팬 거치대 D10을 실제 모델 기능으로 넣지 않음"],
              "references_gaps": len(pack["gaps"]), "references_conflicts": len(pack["conflicts"]),
              "feature_count": sum(len(d["features"]) for d in plan["documents"]),
              "evidence_count": sum(len(d["selections"]) for d in plan["documents"]),
              "original_reviews": 0, "ocr_used": False, "limitations": limitations,
              "cover_and_spec_pages_visually_checked": ["T876MEE1H1 p1", "DUE6BGL2E p1/p57", "MW23FDI p1/p37"]}
    (run / "mapping.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({"models": list(products), "features": report["feature_count"],
                      "evidence": report["evidence_count"], "original_reviews": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
