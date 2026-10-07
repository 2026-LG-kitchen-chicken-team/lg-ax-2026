"""Require source-bound meaning review of every Need and Gap, including resolved ones.

Coverage, quote provenance and retry routing are deterministic. Whether a source
actually supports the claimed object, condition or outcome remains a model task.
"""
from .errors import DomainError

INSTRUCTIONS = (
    "upstream_assessments에는 후보 유무와 관계없이 모든 Need와 모든 Gap을 각각 정확히 한 번 검수하세요. "
    "entity_kind=need는 pain/situation, 연결 리뷰의 극성 사유와 desired_outcome을 원문과 비교합니다. "
    "리뷰의 욕구와 실제 경험을 구분하고, 희망만 말한 문장에 경험한 제약을 추가하지 마세요. "
    "entity_kind=gap는 현재 기능의 대상·조건·근거 유형 및 resolution을 함께 비교합니다. "
    "리뷰는 그 사용자 경험이며 매뉴얼의 기능 명세가 아닙니다. 설명서와 리뷰가 같은 모델이어도 "
    "선반·바구니 같은 대상 또는 분리 시·국소 청소 같은 조건이 다르면 같은 기능 근거가 아닙니다. "
    "방법이 설명돼 있다는 사실은 사용자가 그 방법을 찾기 쉽다는 입증이 아닙니다. "
    "resolved는 해당 Need의 desired_outcome과 사용 조건이 실제 충족되는 근거가 있어야 합니다. "
    "기능 지원 또는 문서 존재만으로 발견성·접근성·사용 과정의 불편을 지우지 마세요. "
    "judgement_quote는 해당 Need 또는 Gap/그 gap_assessments.reason의 원문 문자열 일부입니다. "
    "각 verdict=consistent는 원문과 판단 일치, violation은 수정할 해석 오류, uncertain은 실제 자료 부족입니다. "
    "consistent인 Need에는 연결 리뷰, consistent인 Gap에는 연결 Need의 리뷰와 명시 지원을 주장한 "
    "각 기능의 같은 대상·조건 매뉴얼을 source_quotes로 대조하세요. 인용 존재는 의미 승인이 아닙니다. "
    "원문에 없는 제약을 만들거나 대상/자료 유형을 혼용한 문구는 violation으로 수정하고, "
    "존재하는 자료를 없다고 읽은 오류는 사용자 질문으로 미루지 마세요. "
    "uncertain이면 구체 questions가 필요합니다. 모든 Need/Gap과 후보를 검수한 뒤에만 통과를 선언하세요. "
)


def assessment_schema(payload: dict, output: dict) -> dict:
    text = {"type": "string", "minLength": 1, "pattern": r"\S"}
    ids = [row["id"] for field in ("needs", "gaps") for row in output[field]]
    citation = {"type": "object", "properties": {
        "evidence_id": {"enum": [row["id"] for row in payload["sources"]]}, "quote": text},
        "required": ["evidence_id", "quote"], "additionalProperties": False}
    fields = {"entity_kind": {"enum": ["need", "gap"]}, "entity_id": {"enum": ids or ["_no_upstream"]},
              "verdict": {"enum": ["consistent", "violation", "uncertain"]}, "reason": text,
              "judgement_quote": text, "source_quotes": {"type": "array", "minItems": 1, "items": citation}}
    return {"type": "array", "minItems": len(ids), "maxItems": len(ids),
            "items": {"type": "object", "properties": fields, "required": list(fields),
                      "additionalProperties": False}}


def feedback(report: dict) -> list[dict]:
    return [{"code": f"UPSTREAM_{row['entity_kind'].upper()}_{row['verdict'].upper()}",
             "stage": "needs" if row["entity_kind"] == "need" else "compare", "details": row}
            for row in report.get("upstream_assessments", []) if row["verdict"] != "consistent"]


def validate(payload: dict, output: dict, rows: list[dict]) -> None:
    def invalid(reason, **details):
        raise DomainError("VALIDATION_FAILED", "Need·Gap 의미 검토의 원문·범위를 확인해야 합니다.",
                          {"reason": reason, **details})

    needs = {row["id"]: row for row in output["needs"]}
    gaps = {row["id"]: row for row in output["gaps"]}
    features = {row["id"]: row for row in payload["features"]}
    assessments = {row["gap_id"]: row for row in output["gap_assessments"]}
    sources = {row["id"]: row for row in payload["sources"]}
    expected = {("need", key) for key in needs} | {("gap", key) for key in gaps}
    seen = set()
    for row in rows:
        pair = row["entity_kind"], row["entity_id"]
        if pair not in expected or pair in seen:
            invalid("upstream_entity_coverage", entity_kind=pair[0], entity_id=pair[1])
        seen.add(pair)
        entity = needs[pair[1]] if pair[0] == "need" else gaps[pair[1]]
        fields = ("pain", "situation") if pair[0] == "need" else ("remaining_pain",)
        wording = [entity[field] for field in fields]
        if pair[0] == "gap":
            wording.append(assessments[pair[1]]["reason"])
        if not any(row["judgement_quote"] in value for value in wording):
            invalid("upstream_judgement_quote_not_literal", entity_id=pair[1])
        cited = set()
        for citation in row["source_quotes"]:
            source = sources[citation["evidence_id"]]
            if (citation["quote"] not in source["text"]
                    or any(source[key] != payload["product"][key] for key in ("model_id", "document_version"))
                    or (source["source_kind"] == "synthetic") != (payload["product"]["source_kind"] == "synthetic")):
                invalid("upstream_source_quote_not_scoped_literal", entity_id=pair[1])
            cited.add(source["id"])
        if row["verdict"] != "consistent":
            continue
        need = entity if pair[0] == "need" else needs[entity["need_id"]]
        reviews = {eid for eid in need["evidence_ids"] if sources[eid]["source_type"] == "review"}
        if not cited & reviews:
            invalid("upstream_requires_linked_review", entity_id=pair[1])
        if pair[0] == "gap" and assessments[pair[1]]["support_basis"].startswith("explicit_"):
            for feature_id in entity["feature_ids"]:
                manuals = {eid for eid in features[feature_id]["evidence_ids"]
                           if eid in sources and sources[eid]["source_type"] == "manual"}
                if not cited & manuals:
                    invalid("upstream_requires_feature_manual", entity_id=pair[1], feature_id=feature_id)
    if seen != expected:
        invalid("upstream_entity_coverage", missing=[list(pair) for pair in sorted(expected - seen)])
