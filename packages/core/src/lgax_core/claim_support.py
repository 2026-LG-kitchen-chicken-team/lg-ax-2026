"""Field coverage and source roles for active meaning review, not entailment.

The model judges object/condition alignment and the truth of each claim. These
guards cannot turn a quoted word or a valid evidence ID into factual support.
"""
from .errors import DomainError

INSTRUCTIONS = (
    "active claim checks: upstream_assessments의 claims는 Need마다 pain/situation, "
    "Gap마다 remaining_pain/reason(gap_assessments.reason)을 각각 한 번 검사합니다. "
    "unsupported_factual_claims의 claims는 후보 differentiation와 같은 concept_id의 "
    "concept_assessments.reason을 각각 한 번 검사하고 다른 quality의 claims는 빈 배열입니다. "
    "field는 해당 실제 필드 전체의 주장입니다. 제목 한 구절로 사유의 사실 검사를 대신하지 마세요. "
    "basis는 review_observation(사용자 경험), review_desire(욕구), manual_fact(문서 사실), "
    "mixed(경험과 문서 사실), hypothesis(신규 가설), empty(빈 필드)입니다. "
    "source_ids는 그 판단의 source_quotes에 실제 인용한 연결 근거만 선택하세요. "
    "사용자 경험/욕구를 제품 명세로, 문서 존재를 발견성 해결로, 미언급을 부재로 확대하지 마세요. "
    "scope는 주장과 원문 대상·조건이 같은 aligned, 다른 mismatch, 확인 불가 unconfirmed입니다. "
    "verdict는 supported/violation/uncertain이며 reason에 대상·조건·근거 역할 대조를 설명합니다. "
    "가설은 제품 사실이 아닙니다. 빈 필드는 empty이며 근거를 만들지 않습니다. "
    "claims의 위반은 상위 consistent/satisfied 선언으로 숨길 수 없습니다. "
)


def item_schema(source_ids: list[str]) -> dict:
    text = {"type": "string", "minLength": 1, "pattern": r"\S"}
    fields = {
        "field": {"enum": ["pain", "situation", "remaining_pain", "reason", "differentiation"]},
        "basis": {"enum": ["review_observation", "review_desire", "manual_fact", "mixed", "hypothesis", "empty"]},
        "verdict": {"enum": ["supported", "violation", "uncertain"]},
        "scope": {"enum": ["aligned", "mismatch", "unconfirmed"]},
        "source_ids": {"type": "array", "items": {"enum": source_ids}, "uniqueItems": True},
        "reason": text,
    }
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def array_schema(*, minimum: int = 2) -> dict:
    return {"type": "array", "minItems": minimum, "maxItems": 2,
            "items": {"$ref": "#/$defs/claim_check"}}


def targets(output: dict, kind: str, identifier: str) -> tuple[dict, set[str]]:
    if kind == "need":
        entity = next(row for row in output["needs"] if row["id"] == identifier)
        fields = {field: entity[field] for field in ("pain", "situation")}
    elif kind == "gap":
        entity = next(row for row in output["gaps"] if row["id"] == identifier)
        assessment = next(row for row in output["gap_assessments"] if row["gap_id"] == identifier)
        fields = {"remaining_pain": entity["remaining_pain"], "reason": assessment["reason"]}
    else:
        entity = next(row for row in output["concepts"] if row["id"] == identifier)
        assessment = next(row for row in output["concept_assessments"] if row["concept_id"] == identifier)
        fields = {"differentiation": entity["differentiation"], "reason": assessment["reason"]}
    return fields, set(entity["evidence_ids"])


def validate(payload: dict, output: dict, row: dict, kind: str, identifier: str) -> None:
    stage = {"need": "needs", "gap": "compare", "concept": "concepts"}[kind]

    def invalid(reason: str, **details):
        raise DomainError("VALIDATION_FAILED", "실제 판단 필드의 주장과 근거 역할을 확인해야 합니다.",
                          {"reason": reason, "stage": stage, "entity_kind": kind,
                           "entity_id": identifier, **details})

    fields, granted = targets(output, kind, identifier)
    checks = row["claims"]
    if len(checks) != len(fields) or {check["field"] for check in checks} != set(fields):
        invalid("claim_field_coverage", required_fields=list(fields))
    cited = {citation["evidence_id"] for citation in row["source_quotes"]}
    sources = {source["id"]: source for source in payload["sources"]}
    product = payload["product"]
    for check in checks:
        field, basis = check["field"], check["basis"]
        ids = set(check["source_ids"])
        if not ids <= granted & cited:
            invalid("claim_source_not_linked_and_quoted", field=field, source_ids=sorted(ids))
        if any(any(sources[eid][key] != product[key] for key in ("model_id", "document_version"))
               or (sources[eid]["source_kind"] == "synthetic") != (product["source_kind"] == "synthetic")
               for eid in ids):
            invalid("claim_source_scope", field=field)
        if not fields[field].strip():
            if basis != "empty" or ids or check["verdict"] != "supported" or check["scope"] != "aligned":
                invalid("claim_empty_field", field=field)
            continue
        if basis == "empty":
            invalid("claim_nonempty_field", field=field)
        if check["verdict"] != "supported" or check["scope"] != "aligned":
            # A rejected claim can cite counterevidence; it is not asserting
            # that the cited source supports the declared factual role.
            continue
        if basis == "hypothesis":
            if kind != "concept":
                invalid("claim_hypothesis_as_upstream_fact", field=field)
            continue
        types = {sources[eid]["source_type"] for eid in ids}
        required = ({"review"} if basis.startswith("review_") else
                    {"manual"} if basis == "manual_fact" else {"review", "manual"})
        if types != required or (kind == "need" and basis not in ("review_observation", "review_desire")):
            invalid("claim_evidence_role_mismatch", field=field, basis=basis,
                    required_source_types=sorted(required), actual_source_types=sorted(types))


def feedback(row: dict, kind: str, identifier: str) -> list[dict]:
    result = []
    stage = {"need": "needs", "gap": "compare", "concept": "concepts"}[kind]
    for check in row.get("claims", []):
        verdict = ("uncertain" if check["scope"] == "unconfirmed" else
                   "violation" if check["scope"] == "mismatch" else check["verdict"])
        if verdict != "supported":
            result.append({"code": f"CLAIM_{kind.upper()}_{verdict.upper()}", "stage": stage,
                           "details": {"entity_kind": kind, "entity_id": identifier, **check}})
    return result
