"""Five deterministic Skills with explicit evidence and model boundaries.

This is a demo rule engine, not an autonomous agent or product feasibility test.
Uploaded text remains data; no source text is evaluated as code or instructions.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

SKILLS = [
    {"id": "retrieve", "label": "자료 조회", "skill": "source_retrieve"},
    {"id": "structure", "label": "니즈 구조화", "skill": "needs_structure"},
    {"id": "compare", "label": "기능 대조", "skill": "feature_compare"},
    {"id": "concept", "label": "콘셉트 작성", "skill": "concept_draft"},
    {"id": "validate", "label": "검토·수정", "skill": "validate_revise"},
]
STAGE_IDS = [row["id"] for row in SKILLS]


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def key(value: Any) -> str:
    return re.sub(r"[\s_\-.:()\[\]]", "", text(value).lower())


def field(row: dict, names: list[str], default: Any = "") -> Any:
    normalized = {key(k): v for k, v in row.items()}
    return next((normalized[key(n)] for n in names if key(n) in normalized
                 and normalized[key(n)] is not None and normalized[key(n)] != ""), default)


def sequence(value: Any) -> list:
    return value if isinstance(value, list) else [] if value is None else [value]


def synthetic(value: Any) -> bool:
    return value is True or text(value).lower() in ("1", "true", "yes", "y", "예", "합성", "샘플", "가상")


def unique(items: list) -> list:
    return list(dict.fromkeys(items))


def common(summary: str, activity: str, **kwargs) -> dict:
    return {"summary": summary, "activity": activity, "items": [], "sources": [], "warnings": [], "assumptions": [], **kwargs}


def normalize_reviews(rows: Any) -> list[dict]:
    if isinstance(rows, str):
        rows = list(csv.DictReader(io.StringIO(rows.lstrip("\ufeff"))))
    elif isinstance(rows, dict):
        rows = rows.get("reviews", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("reviews는 리뷰 객체 배열 또는 CSV 문자열이어야 합니다.")
    output = []
    for index, row in enumerate(rows):
        item = {"id": text(field(row, ["id", "review_id", "reviewid", "리뷰id", "리뷰번호"])),
                "model": text(field(row, ["model", "model_id", "modelid", "product_id", "모델", "모델id", "모델명", "제품모델"])),
                "text": text(field(row, ["text", "review", "review_text", "content", "body", "원문", "리뷰", "리뷰원문", "내용", "불편"])),
                "source": text(field(row, ["source", "url", "origin", "출처", "출처url", "자료명"])) or f"업로드 리뷰 · 행 {index + 2}",
                "synthetic": synthetic(field(row, ["synthetic", "is_synthetic", "합성", "합성여부"]))}
        for name in ("page", "version", "documentVersion", "location"):
            if row.get(name) is not None:
                item[name] = row[name]
        output.append(item)
    return output


def normalize_models(rows: Any) -> list[dict]:
    if isinstance(rows, dict):
        rows = rows.get("models", [rows])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("models는 제품 모델 객체 배열이어야 합니다.")
    output = []
    for index, row in enumerate(rows):
        mid = text(field(row, ["id", "model_id", "modelid", "모델id", "제품id", "모델", "model"]))
        features = field(row, ["features", "기능", "기능목록", "명세", "specifications"], [])
        if isinstance(features, str):
            features = [f.strip() for f in re.split(r"[;\n]", features) if f.strip()]
        normalized = []
        for number, feature in enumerate(sequence(features)):
            if not isinstance(feature, (str, dict)):
                raise ValueError("제품 features는 기능 객체 또는 문자열 배열이어야 합니다.")
            entry = {"id": f"{mid}:F{number + 1}", "name": feature, "evidence": feature} if isinstance(feature, str) else {
                "id": text(feature.get("id")) or f"{mid}:F{number + 1}",
                "name": text(field(feature, ["name", "feature", "title", "기능", "기능명", "이름"])),
                "evidence": text(field(feature, ["evidence", "excerpt", "quote", "text", "원문", "근거", "인용", "설명"])),
                **{n: feature[n] for n in ("source", "page", "version", "documentVersion", "condition", "conditions", "location") if n in feature},
            }
            normalized.append(entry)
        output.append({"id": mid, "name": text(field(row, ["name", "model_name", "제품명", "모델명", "이름"])) or mid,
                       "features": normalized, "source": text(field(row, ["source", "url", "출처"])) or "업로드 제품 명세",
                       "synthetic": synthetic(field(row, ["synthetic", "is_synthetic", "합성", "합성여부"])),
                       **{n: row[n] for n in ("version", "documentVersion", "location") if n in row}})
    return output


def validate_data(reviews: list, models: list) -> dict:
    issues = []

    def add(code, severity, message):
        issues.append(dict(code=code, severity=severity, message=message))

    if not reviews:
        add("empty_reviews", "error", "분석할 리뷰가 없습니다.")
    if not models:
        add("empty_models", "error", "대조할 제품 모델이 없습니다.")
    for kind, rows in (("리뷰", reviews), ("모델", models)):
        seen = set()
        for row in rows:
            if not row["id"]:
                add("missing_id", "error", f"{kind} ID가 없습니다. 식별자를 추가해야 근거로 연결할 수 있습니다.")
            if key(row["id"]) in seen:
                add("duplicate_id", "error", f'{kind} ID {row["id"]}가 중복됩니다.')
            seen.add(key(row["id"]))
    for review in reviews:
        if not review["text"]:
            add("empty_text", "warning", f'{review["id"]}: 빈 리뷰 원문은 분석에서 보류합니다.')
        if not review["model"]:
            add("missing_model", "warning", f'{review["id"]}: 모델 식별자가 없습니다.')
    seen_features = set()
    for model in models:
        if not model.get("version") and not model.get("documentVersion"):
            add("missing_version", "warning", f'{model["id"]}: 문서 버전 미기재. 버전은 임의로 만들지 않습니다.')
        for feature in model["features"]:
            if not feature["name"] or not feature["evidence"]:
                add("missing_evidence", "warning", f'{feature["id"]}: 기능 원문 근거가 없어 판단에 사용하지 않습니다.')
            if key(feature["id"]) in seen_features:
                add("duplicate_feature_id", "error", f'{feature["id"]}: 기능 근거 ID가 중복됩니다.')
            seen_features.add(key(feature["id"]))
    return {"valid": not any(i["severity"] == "error" for i in issues), "issues": issues}


def review_source(review: dict) -> dict:
    return {"id": review["id"], "type": "review", "label": f'{review["id"]} · {review["model"]}',
            "model": review["model"], "modelId": review["model"], "text": review["text"], "excerpt": review["text"],
            "source": review["source"], "location": review.get("location", review["source"]),
            "synthetic": review["synthetic"], **{n: review[n] for n in ("page", "version", "documentVersion") if n in review}}


def feature_source(model: dict, feature: dict) -> dict:
    source = feature.get("source") or model["source"]
    return {"id": feature["id"], "type": "feature", "label": f'{model["id"]} · {feature["name"]}',
            "model": model["id"], "modelId": model["id"], "text": feature["evidence"], "excerpt": feature["evidence"],
            "source": source, "location": feature.get("location", source), "synthetic": model["synthetic"],
            **({"version": feature.get("version", model.get("version"))} if feature.get("version") is not None or model.get("version") is not None else {}),
            **{n: feature[n] for n in ("page", "documentVersion", "condition", "conditions") if n in feature}}


def source_retrieve(context: dict) -> dict:
    reviews = normalize_reviews(context.get("reviews", []))
    models = normalize_models(context.get("models", []))
    validation = validate_data(reviews, models)
    matched, unresolved = [], []
    for review in reviews:
        model = [m for m in models if key(m["id"]) == key(review["model"])]
        if len(model) != 1:
            model = [m for m in models if key(m["name"]) == key(review["model"])]
        if len(model) == 1 and review["text"] and validation["valid"]:
            matched.append({**review, "model": model[0]["id"]})
        else:
            unresolved.append({**review, "reason": "입력 자료 오류" if not validation["valid"] else
                               "리뷰 원문 없음" if not review["text"] else "정확히 일치하는 모델 ID·이름 없음"})
    sources = [review_source(r) for r in matched] + [feature_source(m, f) for m in models for f in m["features"]
                                                                  if f["name"] and f["evidence"]]
    return common(f"리뷰 {len(reviews)}개 중 {len(matched)}개를 {len(models)}개 모델에 연결했습니다.",
                  "리뷰 원문과 제품 기능의 ID·출처를 연결했습니다.", reviews=reviews, models=models,
                  matchedReviews=matched, unresolvedReviews=unresolved, sources=sources, validation=validation,
                  inputSignature=json.dumps({"reviews": reviews, "models": models}, ensure_ascii=False, sort_keys=True),
                  request=text(context.get("request")),
                  plan=["기획 조건 확인", "같은 모델의 리뷰·기능 원문 연결", "니즈 구조화 → 기능 대조 → 콘셉트 → 검사"],
                  items=[{"title": m["name"], "detail": f'{m["id"]} · 연결 리뷰 {sum(r["model"] == m["id"] for r in matched)}개', "modelId": m["id"]} for m in models],
                  warnings=[i["message"] for i in validation["issues"]] + [f'{r["id"]}: {r["reason"]}. 다른 모델의 명세를 대신 쓰지 않습니다.' for r in unresolved],
                  assumptions=["Python 로컬 규칙입니다. LLM 의미 해석·외부 검색·독립 에이전트는 연결되어 있지 않습니다.",
                               "합성 자료 빈도를 시장 수요 비율로 해석하지 않습니다."])


RULES = [
    {"category": "cleaning_transport", "label": "청소할 때 식품 이동 부담", "all": [r"청소|세척|닦|흘|국물|얼룩", r"모두|전부|다 꺼|다꺼|꺼내|옮겨|이동|비워|비우|무겁|쏟"],
     "pain": "일부 오염을 청소하기 위해 식품을 꺼내거나 옮기는 부담", "situation": "식품이 들어 있는 상태에서 선반 일부를 청소할 때", "feature": r"분리|탈착|탈부착|세척|청소|트레이"},
    {"category": "cleaning_guidance", "label": "선반 탈착 방법이 어려움", "all": [r"분리|탈착|뺄|빼|끼우", r"모르|몰라|방법|어떻게|헤매|설명|안내|요령"],
     "pain": "선반의 탈착·청소 방법을 이해하거나 찾기 어려움", "situation": "선반 분리·청소 절차를 확인할 때", "feature": r"분리|탈착|탈부착"},
    {"category": "organization_visibility", "label": "식재료 찾기·보관 관리", "all": [r"안 보|안보|보이지|못 찾|못찾|찾기|찾느|뒤쪽|깊숙|기한|잊|까먹|깜빡|중복|정리"],
     "not": r"설명서|탈착.*방법", "pain": "보관 위치나 사용 시점을 놓쳐 식재료 확인·정리에 어려움", "situation": "식재료를 찾고 사용할 순서를 정할 때", "feature": r"투명|내부.*확인|내부.*카메라|카메라|보기|재고|보관.*목록|확인.*창"},
    {"category": "storage_flex", "label": "큰 용기·다양한 크기 수납", "all": [r"높|큰|냄비|병|용기|밀폐통|수납|공간|끼워|자리"],
     "not": r"청소|세척|닦|얼룩|탈착.*방법", "pain": "용기의 크기와 선반 간격을 맞추고 배치하기 어려움", "situation": "큰 용기나 크기가 다른 식품을 수납할 때", "feature": r"높이|조절|접이|가변|접는|폴딩|수납.*배치"},
    {"category": "cleaning_unspecified", "label": "청소 불편의 조건 확인", "all": [r"청소|세척|닦|오염|얼룩"],
     "pain": "청소가 어렵다는 표현만으로 원인·상황이 부족함", "situation": "청소 불편의 실제 원인을 확인해야 하는 상황", "feature": r"분리|탈착|선반|트레이"},
]
POSITIVE = r"(?<!불)편해|(?<!불)편하|좋아|좋다|만족|잘 되|잘돼|수월|깨끗|넉넉|편리"
NEGATIVE = r"불편|어려|어렵|힘들|번거|없|안 |안돼|안되|못|모르|몰라|헷갈|귀찮|필요|잊|놓쳐|쏟|헤매|고민|다시"


def previous(context: dict, stage: str) -> dict:
    saved = context.get("results", {}).get(stage)
    return saved if saved is not None else run_stage(stage, context)


def needs_structure(context: dict) -> dict:
    data = previous(context, "retrieve")
    buckets, unknown, positive, mixed, out = {}, [], [], [], []
    conditions = context.get("conditions", {})
    categories = conditions.get("categories") if isinstance(conditions, dict) else None
    for review in data["matchedReviews"]:
        raw = review["text"]
        if re.search(POSITIVE, raw) and not re.search(NEGATIVE, raw):
            positive.append({**review, "reason": "불편 표현 없이 긍정 경험만 확인된 규칙 분류 · 원문 확인 필요"})
            continue
        if re.search(POSITIVE, raw) and re.search(NEGATIVE, raw):
            mixed.append({**review, "sentiment": "mixed", "positiveText": raw, "painText": raw,
                          "reason": "긍정·불편 표현이 함께 있어 전체 원문을 유지합니다."})
        matches = [r for r in RULES if all(re.search(p, raw) for p in r["all"]) and not re.search(r.get("not", r"(?!)"), raw)]
        if len(matches) > 1:
            matches = [r for r in matches if r["category"] != "cleaning_unspecified"]
        selected = [r for r in matches if not categories or r["category"] in categories]
        if not selected:
            (out if matches and categories else unknown).append(review)
        for rule in selected:
            buckets.setdefault((review["model"], rule["category"]), (rule, []))[1].append(review)
    needs = []
    for (mid, category), (rule, rows) in buckets.items():
        needs.append({"id": f"N-{mid}-{category}", "modelId": mid,
                      "modelName": next(m["name"] for m in data["models"] if m["id"] == mid),
                      "category": category, "label": rule["label"], "title": rule["label"], "pain": rule["pain"],
                      "situation": rule["situation"], "count": len(rows), "reviewIds": [r["id"] for r in rows],
                      "quotes": [{"reviewId": r["id"], "text": r["text"], "source": r["source"], "synthetic": r["synthetic"]} for r in rows],
                      "method": "한국어 키워드 규칙 · 원문 확인 필요"})
    selected_ids = {rid for n in needs for rid in n["reviewIds"]}
    return common(f"{len(needs)}개 불편 묶음 · 긍정 경험 {len(positive)}개 · 미분류 {len(unknown)}개",
                  "모델별 사용 상황을 묶고 긍정 경험·미분류·범위 밖 원문을 구분했습니다.",
                  needs=needs, unclassifiedReviews=unknown, positiveReviews=positive, mixedReviews=mixed, outOfScopeReviews=out,
                  categoryFilter=categories, invalidCategories=[],
                  items=[{"title": f'{n["modelId"]} · {n["label"]}', "detail": f'{n["count"]}개 원문 · {n["situation"]}', "id": n["id"]} for n in needs],
                  sources=[s for s in data["sources"] if s["type"] == "review" and s["id"] in selected_ids],
                  warnings=[f'{len(unknown)}개 원문은 현재 규칙으로 분류하지 못했습니다.'] if unknown else [],
                  assumptions=["같은 표현을 같은 원인으로 단정하지 않습니다.", "긍정·부정·상충 여부는 규칙 초안이며 원문 검토가 필요합니다."])


TEMPLATES = {
    "cleaning_transport": {"title": "구획별 탈착 트레이", "kind": "제품 구조", "mechanism": "내용물을 담은 채 오염된 구획의 트레이만 꺼내 세척하는 구조를 검토합니다.",
        "differentiation": "기존 선반의 분리 가능 여부와 식품 전체 이동 부담을 구분합니다.",
        "requirements": ["전체 식품을 옮기지 않고 오염된 구획만 분리하는 흐름을 설계한다.", "대상 모델의 기존 선반과 결합·간섭 조건을 확인한다.", "하중·누수·세척성·탈착 편의는 실물 검증 항목으로 남긴다."],
        "pattern": r"구획.*(탈착|분리).*트레이|칸별.*트레이|부분.*탈착.*트레이"},
    "cleaning_guidance": {"title": "상황별 선반 탈착 안내", "kind": "안내 서비스", "mechanism": "모델과 어려운 지점을 선택하면 원문에서 확인된 탈착 절차를 안내합니다.",
        "differentiation": "분리 기능 재제안 대신 기능 인지와 실제 사용 과정에 집중합니다.",
        "requirements": ["모델 ID와 설명서의 근거 위치를 안내에 연결한다.", "방법의 어려움과 식품 이동 부담을 구분한다.", "문서에 없는 조작은 생성하지 않고 확인 대상으로 표시한다."],
        "pattern": r"상황별.*탈착.*안내|맞춤.*탈착.*안내"},
    "organization_visibility": {"title": "보관 위치·사용 순서 가이드", "kind": "안내 서비스", "mechanism": "사용자가 입력한 식재료와 보관 구획을 연결해 찾기와 사용 순서 결정을 돕습니다.",
        "differentiation": "기존 내부 확인 기능과 별도로 위치를 잊거나 사용 시점을 놓치는 불편을 다룹니다.",
        "requirements": ["식재료와 구획을 사용자가 등록·수정할 수 있어야 한다.", "사용자 입력 보관일·소비기한을 확인할 식재료 안내에 사용한다.", "자동 인식 정확도와 식품 안전을 보장하지 않고 기록 확인을 요청한다."],
        "pattern": r"보관.*위치.*(가이드|안내)|식재료.*위치.*(가이드|안내)|사용.*순서.*가이드"},
    "storage_flex": {"title": "용기 조건별 수납 배치 도우미", "kind": "안내 서비스", "mechanism": "용기 크기와 확인된 선반 조절 조건을 받아 배치 순서와 간섭 확인 항목을 안내합니다.",
        "differentiation": "높이 조절 선반을 재제안하지 않고 실제 용기의 배치 과정에 집중합니다.",
        "requirements": ["용기의 높이·너비·수량을 입력받는다.", "모델 명세에서 확인된 조절 기능만 안내에 사용한다.", "치수 근거가 없는 조합은 적합하다고 단정하지 않고 실물 간섭 확인을 요청한다."],
        "pattern": r"용기.*(수납|배치).*(도우미|가이드)|수납.*배치.*(도우미|가이드)"},
}


def feature_compare(context: dict) -> dict:
    data, grouped = previous(context, "retrieve"), previous(context, "structure")
    comparisons, excluded, withheld, questions = [], [], [], []
    for need in grouped["needs"]:
        model = next((m for m in data["models"] if m["id"] == need["modelId"]), None)
        rule = next((r for r in RULES if r["category"] == need["category"]), None)
        features = [f for f in (model or {}).get("features", []) if f["name"] and f["evidence"]
                    and rule and re.search(rule["feature"], f'{f["name"]} {f["evidence"]}')]
        template = TEMPLATES.get(need["category"])
        duplicate = bool(template and any(re.search(template["pattern"], f'{f["name"]} {f["evidence"]}') for f in features))
        sufficient = bool(features and need["category"] != "cleaning_unspecified")
        status = "기존 기능 중복" if duplicate else "잔여 불편" if sufficient else "확인 필요"
        reason = "같은 작동 방식이 제품 근거에 있어 차별점 없는 후보를 제외합니다." if duplicate else "기능은 확인되지만 원문에 사용 과정의 불편이 남아 있습니다." if sufficient else "관련 기능 또는 불편의 조건이 부족합니다. 기능 부재로 단정하지 않고 추가 확인합니다."
        feature_ids = [f["id"] for f in features]
        ids = need["reviewIds"] + feature_ids
        row = {"id": f'CMP-{need["id"]}', "needId": need["id"], "modelId": need["modelId"], "model": need["modelId"],
               "label": need["label"], "title": f'{need["modelId"]} · {need["label"]}', "status": status,
               "classification": "duplicate" if duplicate else "residual" if sufficient else "unknown",
               "existing": " · ".join(f["name"] for f in features) or "관련 기능 확인 필요", "existingFeatures": features,
               "residual": need["pain"], "reason": reason, "reviewIds": need["reviewIds"][:], "featureIds": feature_ids,
               "eligible": sufficient and not duplicate, "need": need["label"],
               "existingFeature": " · ".join(f["name"] for f in features) or "관련 기능 확인 필요",
               "remainingPain": need["pain"], "sources": [s for s in data["sources"] if s["id"] in ids]}
        if need["category"] == "cleaning_unspecified":
            qid = f'clarify-{need["id"]}'
            decision = context.get("decisions", {}).get(qid)
            row["userDecision"] = decision
            if decision not in ("include", "hold"):
                questions.append({"id": qid, "stage": "compare", "needId": need["id"],
                                  "text": f'{need["modelId"]}의 청소 불편이 발생한 실제 상황을 확인할까요? 가정으로 포함해도 새 기능의 근거로 쓰지 않습니다.',
                                  "evidence": row["sources"]})
        comparisons.append(row)
        if not sufficient or duplicate:
            withheld.append({"title": row["title"], "needId": need["id"], "modelId": need["modelId"], "reason": reason})
        if duplicate:
            excluded.append({"title": template["title"], "modelId": need["modelId"], "needId": need["id"], "reason": reason, "featureIds": feature_ids})
    ids = {i for row in comparisons for i in row["reviewIds"] + row["featureIds"]}
    return common(f"{len(comparisons)}개 대조 · 검토 기회 {sum(r['eligible'] for r in comparisons)}개 · 보류 {len(withheld)}개",
                  "같은 모델의 기존 기능·사용 조건을 원문과 대조했습니다.", comparisons=comparisons,
                  excludedCandidates=excluded, withheld=withheld,
                  clarificationQuestions=questions,
                  items=[{"title": r["title"], "detail": f'{r["status"]} · {r["reason"]}', "id": r["id"]} for r in comparisons],
                  sources=[s for s in data["sources"] if s["id"] in ids], warnings=[w["reason"] for w in withheld],
                  assumptions=["문서에 언급이 없다고 기능이 없다고 단정하지 않습니다.", "기능이 있어도 실제 사용 불편이 해결됐다고 단정하지 않습니다."])


def concept_draft(context: dict) -> dict:
    data, grouped, compared = previous(context, "retrieve"), previous(context, "structure"), previous(context, "compare")
    concepts, withheld = [], copy.deepcopy(compared["withheld"])
    condition = context.get("conditions", {})
    condition = condition if isinstance(condition, dict) else {"text": text(condition)}
    terms = [text(t) for t in sequence(condition.get("excludedTerms", condition.get("exclusions", condition.get("exclude")))) if text(t)]
    request = f'{context.get("request", "")} {condition.get("text", "")} {" ".join(terms)}'
    hardware_excluded = bool(re.search(r"서비스만|서비스\s*중심|(?:구조|하드웨어|실기기)[^\n]{0,18}(?:제외|금지)|(?:제외|금지)[^\n]{0,18}(?:구조|하드웨어)", request))
    priority = {"cleaning_transport": 0, "organization_visibility": 1, "storage_flex": 2, "cleaning_guidance": 3}
    need_map = {n["id"]: n for n in grouped["needs"]}
    rows = sorted([r for r in compared["comparisons"] if r["eligible"]], key=lambda r: priority.get(need_map.get(r["needId"], {}).get("category"), 9))
    for row in rows:
        need = need_map.get(row["needId"])
        template = TEMPLATES.get((need or {}).get("category"))
        if not template:
            continue
        forbidden = next((term for term in terms if term in template["title"]), None)
        if forbidden or hardware_excluded and template["kind"] == "제품 구조":
            withheld.append({"title": template["title"], "modelId": row["modelId"], "needId": row["needId"], "reason": f"기획 제외 조건: {forbidden or '제품 구조 변경 제외'}"})
            continue
        earlier = next((c for c in concepts if c["category"] == need["category"]), None)
        if earlier:
            earlier["additionalModelIds"].append(need["modelId"])
            earlier["relatedNeeds"].append(need["id"])
            continue
        if len(concepts) >= 3:
            withheld.append({"title": template["title"], "modelId": row["modelId"], "needId": row["needId"], "reason": "최대 3개 상한. 추가 기회는 후속 검토로 보류합니다."})
            continue
        cid = f"C-{len(concepts) + 1:02d}"
        details = {k: copy.deepcopy(v) for k, v in template.items() if k != "pattern"}
        concepts.append({**details, "id": cid, "category": need["category"], "needId": need["id"], "modelId": need["modelId"],
                         "model": need["modelId"], "label": template["title"], "description": template["mechanism"],
                         "reviewIds": need["reviewIds"][:], "featureIds": row["featureIds"][:], "residual": need["pain"],
                         "evidence": need["quotes"][:3], "additionalModelIds": [], "relatedNeeds": [need["id"]], "sources": copy.deepcopy(row["sources"]),
                         "requirementEvidence": [{"id": f"{cid}:REQ{i + 1}", "text": req, "reviewIds": need["reviewIds"][:],
                                                  "featureIds": row["featureIds"][:], "type": "검증 조건" if i == 2 else "기획 요구사항"} for i, req in enumerate(template["requirements"])],
                         "assumptions": ["사용 편의·제조 가능성·치수 적합성은 미검증입니다.", "대표 모델 기준이며 추가 모델에는 별도 근거 대조가 필요합니다."]})
    ids = {i for c in concepts for i in c["reviewIds"] + c["featureIds"]}
    return common(f"근거가 연결된 콘셉트 {len(concepts)}개를 작성했습니다.", "잔여 불편에서 동작 방식·요구사항·확인할 가정을 작성했습니다.",
                  concepts=concepts, withheld=withheld, excludedCandidates=compared["excludedCandidates"],
                  items=[{"id": c["id"], "title": c["title"], "detail": f'{c["modelId"]} · {c["kind"]} · 요구사항 {len(c["requirements"])}개'} for c in concepts],
                  sources=[s for s in data["sources"] if s["id"] in ids], warnings=[w["reason"] for w in withheld],
                  assumptions=["후보는 최대 3개 상한이며 근거 부족 시 채우지 않습니다.", "원문 인용은 제안 근거이며 실제 수요·성능을 보증하지 않습니다."])


def validate_revise(context: dict) -> dict:
    data, grouped = source_retrieve(context), previous(context, "structure")
    compared, created = previous(context, "compare"), previous(context, "concept")
    checks, issues, accepted, rejected = [], [], [], []
    reviews = {r["id"]: r for r in data["matchedReviews"]}
    models = {m["id"]: m for m in data["models"]}
    features = {f["id"]: {**f, "modelId": m["id"]} for m in data["models"] for f in m["features"]}
    sources = {s["id"]: s for s in [review_source(r) for r in reviews.values()] + [feature_source(m, f) for m in models.values() for f in m["features"] if f["name"] and f["evidence"]]}

    def check(cid, label, passed, detail, code=None, repair="concept"):
        checks.append({"id": cid, "label": label, "passed": passed, "status": "통과" if passed else "실패", "detail": detail})
        if not passed:
            issues.append({"code": code or cid, "severity": "error", "message": detail, "repairStage": repair})

    check("input_ids", "입력 ID·자료 구성", data["validation"]["valid"], "입력 ID·필수 자료 구성 검사", repair="retrieve")
    cached = context.get("results", {}).get("retrieve", {})
    if cached:
        check("input_changed", "자료 변경 검사", cached.get("inputSignature") == data["inputSignature"], "현재 입력과 조회 시점의 자료·버전을 대조했습니다.", "stale_input", "retrieve")
    bad_needs = [n for n in grouped["needs"] if n["modelId"] not in models or any(rid not in reviews or reviews[rid]["model"] != n["modelId"] for rid in n.get("reviewIds", []))]
    check("model_link", "모델 혼동 검사", not bad_needs, f"모델 연결 오류 {len(bad_needs)}개", "model_mismatch", "structure")
    quotes = [q for n in grouped["needs"] for q in n.get("quotes", [])]
    bad_quotes = [q for q in quotes if q.get("reviewId") not in reviews or reviews[q["reviewId"]]["text"] != q.get("text")]
    check("raw_quotes", "원문 인용 검사", not bad_quotes, f"원문 불일치 {len(bad_quotes)}개", "quote_mismatch", "structure")
    citations = compared.get("sources", []) + created.get("sources", []) + [s for r in compared["comparisons"] for s in r.get("sources", [])] + [s for c in created["concepts"] for s in c.get("sources", [])]
    bad_citations = [s for s in citations if s.get("id") not in sources or any(s.get(n) != sources[s["id"]].get(n) for n in ("text", "model", "source", "page", "version", "documentVersion", "location", "condition", "conditions", "synthetic"))]
    check("citation_locations", "출처·페이지·버전 검사", not bad_citations, f"원문·출처 위치 불일치 {len(bad_citations)}개", "citation_mismatch", "compare")
    bad_compares = [r for r in compared["comparisons"] if any(fid not in features or not features[fid]["evidence"] or features[fid]["modelId"] != r["modelId"] for fid in r["featureIds"])]
    check("feature_evidence", "제품 기능 근거 검사", not bad_compares, f"기능 근거 오류 {len(bad_compares)}개", "feature_mismatch", "compare")
    for candidate in created["concepts"]:
        reasons = []
        model = models.get(candidate.get("modelId"))
        need = next((n for n in grouped["needs"] if n["id"] == candidate.get("needId")), None)
        if not model or not need or need["modelId"] != candidate.get("modelId"):
            reasons.append("대표 모델·불편 연결 오류")
        if not candidate.get("reviewIds") or any(rid not in reviews or reviews[rid]["model"] != candidate.get("modelId") for rid in candidate.get("reviewIds", [])):
            reasons.append("리뷰 인용 누락 또는 모델 혼동")
        if not candidate.get("featureIds") or any(fid not in features or not features[fid]["evidence"] or features[fid]["modelId"] != candidate.get("modelId") for fid in candidate.get("featureIds", [])):
            reasons.append("기능 근거 누락 또는 모델 혼동")
        if any(q.get("reviewId") not in reviews or reviews[q["reviewId"]]["text"] != q.get("text") for q in candidate.get("evidence", [])):
            reasons.append("콘셉트 인용이 원문과 다름")
        reqs, links = candidate.get("requirements", []), candidate.get("requirementEvidence", [])
        if not reqs or any(not text(r) for r in reqs):
            reasons.append("요구사항 누락")
        if len(links) != len(reqs) or any(link.get("text") != reqs[i] or not link.get("reviewIds") or not link.get("featureIds") or any(rid not in candidate.get("reviewIds", []) for rid in link.get("reviewIds", [])) or any(fid not in candidate.get("featureIds", []) for fid in link.get("featureIds", [])) for i, link in enumerate(links)):
            reasons.append("요구사항 근거 연결 누락")
        template = TEMPLATES.get((need or {}).get("category"))
        if model and template and any(f["evidence"] and re.search(template["pattern"], f'{f["name"]} {f["evidence"]}') for f in model["features"]):
            reasons.append("기존 기능과 동일한 콘셉트")
        if model and any(f["evidence"] and key(f["name"]) == key(candidate.get("title")) for f in model["features"]):
            reasons.append("기존 기능명과 같은 재제안")
        if reasons:
            rejected.append({**candidate, "rejectionReasons": unique(reasons)})
            issues.append({"code": "invalid_concept", "severity": "error", "message": f'{candidate.get("id")}: {" / ".join(unique(reasons))}', "repairStage": "concept"})
        elif len(accepted) < 3:
            accepted.append(candidate)
    check("concepts", "콘셉트 중복·요구사항 검사", not rejected and len(created["concepts"]) <= 3, f"검토 후보 {len(accepted)}개 · 제외 {len(rejected)}개", "invalid_concept")
    repair = bool(issues)
    return common(f"검사 오류 {len(issues)}개" if repair else f"근거 검사 완료 · 검토 가능한 콘셉트 {len(accepted)}개",
                  "모델·원문·중복·요구사항 근거의 일관성을 검사했습니다.", checks=checks, issues=issues, needsRepair=repair,
                  repairTargets=unique([i["repairStage"] for i in issues]), acceptedConcepts=accepted, rejectedConcepts=rejected,
                  concepts=accepted, status="수정 필요" if repair else "검토 완료", sources=created["sources"],
                  items=[{"id": c["id"], "title": c["label"], "detail": f'{c["status"]} · {c["detail"]}'} for c in checks],
                  warnings=[i["message"] for i in issues], assumptions=["최대 2회 수정과 사용자 확인은 실행기가 제어합니다.", "제품 성능·시장 수요·정확도·비용·시간 절감률은 측정하지 않았습니다."])


def validate_context(context: Any) -> None:
    if not isinstance(context, dict):
        raise ValueError("context는 JSON 객체여야 합니다.")
    if not isinstance(context.get("results", {}), dict):
        raise ValueError("context.results는 단계 결과 객체여야 합니다.")
    if not isinstance(context.get("decisions", {}), dict):
        raise ValueError("context.decisions는 질문 ID별 선택 객체여야 합니다.")
    if context.get("conditions") is not None and not isinstance(context["conditions"], (dict, str)):
        raise ValueError("conditions는 객체 또는 문자열이어야 합니다.")
    conditions = context.get("conditions", {})
    if isinstance(conditions, dict) and conditions.get("categories") is not None and not isinstance(conditions["categories"], list):
        raise ValueError("conditions.categories는 배열이어야 합니다.")


def run_stage(stage: str, context: dict) -> dict:
    validate_context(context)
    functions = dict(zip(STAGE_IDS, (source_retrieve, needs_structure, feature_compare, concept_draft, validate_revise)))
    if stage not in functions:
        raise ValueError(f"알 수 없는 단계: {stage}")
    return functions[stage](context)


def run_pipeline(context: dict, max_revisions: int = 2) -> dict:
    """Batch helper; browser/API can instead request one Skill at a time.

    Never silently consumes an ambiguous human decision. Unknown comparisons
    remain explicitly withheld; the interactive UI decides whether to continue.
    """
    work = copy.deepcopy(context)
    work["results"] = {}
    events, revisions = [], []
    run_id = text(context.get("runId")) or str(uuid.uuid4())
    for stage in STAGE_IDS:
        work["results"][stage] = run_stage(stage, work)
        events.append({"id": str(uuid.uuid4()), "runId": run_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                       "type": "stage_completed", "stage": stage, "message": work["results"][stage]["activity"]})
    for attempt in range(min(2, max(0, max_revisions))):
        checked = work["results"]["validate"]
        if not checked["needsRepair"]:
            break
        earliest = min(STAGE_IDS.index(stage) for stage in checked["repairTargets"])
        before = copy.deepcopy(work["results"])
        for stage in STAGE_IDS[earliest:]:
            work["results"].pop(stage, None)
        for stage in STAGE_IDS[earliest:]:
            work["results"][stage] = run_stage(stage, work)
        revisions.append({"attempt": attempt + 1, "fromStage": STAGE_IDS[earliest], "reason": checked["issues"],
                          "before": before, "after": copy.deepcopy(work["results"]), "resolved": not work["results"]["validate"]["needsRepair"]})
    return {"runId": run_id, "mode": "local_rules", "llm_connected": False, "results": work["results"], "events": events,
            "revisions": revisions, "requiresReview": bool(work["results"]["compare"]["withheld"]),
            "unresolved": work["results"]["validate"]["issues"]}
