"""Private, source-anchored candidates; provenance is not semantic approval.

An owner supplies records from an existing generation/review, never an extra
model call. Public contracts and original source facts remain unchanged. Schema
adoption in the native adapter is a separate PM integration boundary.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from jsonschema import Draft202012Validator
from lgax_contracts.research import validate_research_bundle


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


_SPAN = _object({"quote": {"type": "string", "minLength": 1},
                 "start": {"type": "integer", "minimum": 0},
                 "end": {"type": "integer", "minimum": 1}})
_OPTIONAL_SPAN = {"anyOf": [_SPAN, {"type": "null"}]}
_CUSTOMER = _object({
    "claim_id": {"type": "string", "minLength": 1},
    "source_id": {"type": "string", "minLength": 1},
    "kind": {"enum": ["observation", "expectation", "customer_inference", "planning_hypothesis"]},
    "anchor": _SPAN, "actor_anchor": _OPTIONAL_SPAN,
    "event_or_duration_role": {"enum": ["event", "total_use", "maintenance_mention", "expectation", "unknown"]},
    "approximate_value": _OPTIONAL_SPAN,
    "order_anchor": _OPTIONAL_SPAN,
    "order_status": {"enum": ["unknown", "explicit_anchor"]},
    "experienced_polarity": {"enum": ["positive", "negative", "unknown"]},
})
_THRESHOLD = _object({"anchor": _SPAN, "comparator_anchor": _SPAN, "unit_anchor": _SPAN,
                      "comparator": {"enum": ["gt", "ge", "lt", "le", "eq", "unknown"]}})
_OFFICIAL = _object({
    "claim_id": {"type": "string", "minLength": 1},
    "source_id": {"type": "string", "minLength": 1},
    "kind": {"const": "conditional_official_action"}, "anchor": _SPAN,
    "prerequisite": _SPAN,
    "ordered_steps": {"type": "array", "minItems": 1, "maxItems": 12, "items": _SPAN},
    "threshold": {"anyOf": [_THRESHOLD, {"type": "null"}]},
    "referenced_chapter": _OPTIONAL_SPAN,
})
_COLLECTIONS = {"Problem": "problems", "Comparison": "comparisons", "Concept": "concepts"}
_IMMUTABLE = {"id", "problem_id", "problem_ids"}
_MODES = {"observation", "hypothesis", "official_reference", "conditional_action"}
HYPOTHESIS_LABEL = "가상 기획(미검증): "


def evidence_record_schema() -> dict:
    """A private schema proposal, not a replacement native generation envelope."""
    return _object({"customer_claims": {"type": "array", "maxItems": 64, "items": deepcopy(_CUSTOMER)},
                    "official_actions": {"type": "array", "maxItems": 32, "items": deepcopy(_OFFICIAL)}})


def _customer(source: dict) -> bool:
    return (source["source_type"] == "review" and source["source_role"] == "customer_experience"
            or source["source_type"] == "qa" and source["source_role"] == "customer_question")


class PublicEvidence:
    """Isolate bad records while retaining raw candidates and exact source text.

    Offsets are Unicode code points within source.text, not PDF page offsets.
    Caller-supplied interpretation enums stay candidates even with exact spans.
    """

    def __init__(self, bundle: dict, records: dict):
        validate_research_bundle(bundle)
        if (not isinstance(records, dict) or set(records) != {"customer_claims", "official_actions"}
                or not isinstance(records["customer_claims"], list) or len(records["customer_claims"]) > 64
                or not isinstance(records["official_actions"], list) or len(records["official_actions"]) > 32):
            raise ValueError("Evidence requires two bounded private record arrays")
        self._bundle = deepcopy(bundle)
        self._catalog = {row["source_id"]: row for row in self._bundle["sources"]}
        self._raw = deepcopy(records)
        self._claims: dict[str, dict] = {}
        self._issues: list[dict] = []
        ids = Counter(row.get("claim_id") for rows in records.values() for row in rows
                      if isinstance(row, dict) and isinstance(row.get("claim_id"), str))
        for collection, schema in (("customer_claims", _CUSTOMER), ("official_actions", _OFFICIAL)):
            for index, raw in enumerate(records[collection]):
                errors = list(Draft202012Validator(schema).iter_errors(raw))
                codes = ["record_schema"] if errors else self._record_issues(raw, collection)
                if isinstance(raw, dict) and (not isinstance(raw.get("claim_id"), str)
                                             or ids.get(raw["claim_id"], 0) != 1):
                    codes.append("ambiguous_claim_id")
                if codes:
                    self._issues.append({"collection": collection, "index": index,
                                         "claim_id": raw.get("claim_id") if isinstance(raw, dict)
                                         and isinstance(raw.get("claim_id"), str) else None,
                                         "source_id": raw.get("source_id") if isinstance(raw, dict)
                                         and isinstance(raw.get("source_id"), str) else None,
                                         "codes": sorted(set(codes))})
                    continue
                record = deepcopy(raw)
                source = self._catalog[raw["source_id"]]
                record["provenance"] = {key: deepcopy(source.get(key)) for key in (
                    "url", "locator", "coverage", "document_version", "purchased_model")}
                record["provenance"]["applicability"] = deepcopy(source.get("metadata", {}).get("applicability"))
                record["provenance"]["native_unit_caution"] = deepcopy(
                    source.get("metadata", {}).get("native_unit_caution"))
                record["provenance_validated"] = True
                record["semantic_quality_verified"] = False
                self._claims[raw["claim_id"]] = record

    def _record_issues(self, row: dict, collection: str) -> list[str]:
        source = self._catalog.get(row["source_id"])
        if source is None:
            return ["unknown_source_id"]
        if collection == "customer_claims" and not _customer(source):
            return ["customer_claim_requires_customer_source"]
        if collection == "official_actions" and not (source["source_role"] in {
                "official_document", "official_answer"} and source["source_type"] in {
                    "manual", "faq", "spec", "installation", "qa"}):
            return ["official_action_requires_official_source"]
        spans = [row["anchor"]]
        if collection == "customer_claims":
            spans += [row[key] for key in ("actor_anchor", "approximate_value", "order_anchor") if row[key] is not None]
        else:
            spans += [row["prerequisite"], *row["ordered_steps"]]
            if row["threshold"] is not None:
                spans += [row["threshold"][key] for key in ("anchor", "comparator_anchor", "unit_anchor")]
            if row["referenced_chapter"] is not None:
                spans.append(row["referenced_chapter"])
        codes = []
        for span in spans:
            if span["start"] >= span["end"] or source["text"][span["start"]:span["end"]] != span["quote"]:
                codes.append("quote_span_mismatch")
            if span is not row["anchor"] and not (row["anchor"]["start"] <= span["start"] < span["end"] <= row["anchor"]["end"]):
                codes.append("component_outside_claim_anchor")
        if collection == "customer_claims":
            if row["kind"] != "observation" and row["experienced_polarity"] != "unknown":
                codes.append("non_observation_has_experienced_polarity")
            if (row["event_or_duration_role"] in {"total_use", "maintenance_mention", "expectation"}
                    and row["approximate_value"] is None):
                codes.append("duration_role_requires_literal_value")
            if (row["order_status"] == "explicit_anchor") != (row["order_anchor"] is not None):
                codes.append("order_requires_explicit_anchor")
        else:
            steps = row["ordered_steps"]
            if any(left["end"] > right["start"] for left, right in zip(steps, steps[1:])):
                codes.append("procedure_order_not_source_order")
        return codes

    def require_bundle(self, bundle: dict) -> None:
        if bundle != self._bundle:
            raise ValueError("Evidence must use the exact pinned research bundle")

    @property
    def audit(self) -> dict:
        return deepcopy({"raw_candidates": self._raw, "claims": list(self._claims.values()),
                         "issues": self._issues, "semantic_quality_verified": False,
                         "classification_approved": False, "model_calls": 0})

    def source_context(self, source_id: str) -> dict:
        if source_id not in self._catalog:
            raise ValueError("Unknown source")
        return {"claims": deepcopy([row for row in self._claims.values() if row["source_id"] == source_id]),
                "issues": deepcopy([row for row in self._issues if row["source_id"] == source_id]),
                "semantic_quality_verified": False}

    def summary_projection(self, processed_source_ids: set[str]) -> dict:
        """Literal experienced quotes only; rejected-source coverage stays unknown."""
        summaries = {"positive": [], "negative": [], "mixed": []}
        rejected = {row["source_id"] for row in self._issues if row["source_id"] is not None}
        classified = set()
        for source_id in self._catalog:
            if source_id not in processed_source_ids or source_id in rejected:
                continue
            claims = [row for row in self._claims.values() if row["source_id"] == source_id
                      and row["kind"] == "observation" and row["experienced_polarity"] != "unknown"]
            if not claims:
                continue
            polarities = {row["experienced_polarity"] for row in claims}
            polarity = "mixed" if len(polarities) == 2 else next(iter(polarities))
            summaries[polarity].append({"text": " / ".join(dict.fromkeys(row["anchor"]["quote"] for row in claims)),
                                        "source_ids": [source_id]})
            classified.add(source_id)
        return {"summaries": summaries, "classified_source_ids": sorted(classified),
                "unclassified_source_ids": sorted(processed_source_ids - classified),
                "classification_approved": False, "semantic_quality_verified": False}

    def consultation_context(self, source_id: str) -> dict:
        if source_id not in self._catalog or not _customer(self._catalog[source_id]):
            raise ValueError("Consultation history requires a customer source")
        rows = [row for row in self._claims.values() if row["source_id"] == source_id]
        return {"source_ids": [source_id] if rows else [],
                "observations": deepcopy([row for row in rows if row["kind"] == "observation"]),
                "expectations": deepcopy([row for row in rows if row["kind"] == "expectation"]),
                "customer_inferences": deepcopy([row for row in rows if row["kind"] == "customer_inference"]),
                "unknowns": ["관찰·주체·기간 역할은 원문에 연결한 해석 후보이며 고객 확인이 필요합니다.",
                             "원문에 명시되지 않은 조치 전후 순서·원인·지원 이력은 미확인입니다."],
                "customer_confirmed": False, "semantic_quality_verified": False}

    def official_reference(self, claim_id: str) -> str:
        row = self._claims[claim_id]
        if row["kind"] != "conditional_official_action":
            raise ValueError("Official reference requires an official action")
        provenance = row["provenance"]
        return (f"공식 원문 참조(실행 안내 아님): {row['anchor']['quote']} "
                f"[출처 {row['source_id']}; 버전 {provenance['document_version']}; "
                f"범위 {provenance['coverage']}; 적용 {provenance['applicability'] or '미확인'}]. "
                "정확 구매 모델·조건·절차 장 적용을 확인하고, 미해결·실행 곤란 상태도 상담 기록으로 전달합니다.")

    def field_issues(self, brief: dict, bindings: list[dict]) -> list[dict]:
        """Check declared dependencies, without claiming to read arbitrary prose."""
        if not isinstance(bindings, list) or len(bindings) > 128:
            raise ValueError("Dependencies must be a bounded list")
        issues = []
        seen = set()
        for binding in bindings:
            if (not isinstance(binding, dict) or set(binding) != {"item_kind", "item_id", "field", "claim_ids", "mode"}
                    or not isinstance(binding["item_kind"], str) or binding["item_kind"] not in _COLLECTIONS
                    or not isinstance(binding["mode"], str) or binding["mode"] not in _MODES
                    or not isinstance(binding["item_id"], str)
                    or not isinstance(binding["field"], str) or not isinstance(binding["claim_ids"], list)
                    or not binding["claim_ids"] or any(not isinstance(value, str) for value in binding["claim_ids"])
                    or len(set(binding["claim_ids"])) != len(binding["claim_ids"])):
                raise ValueError("Invalid field/claim dependency binding")
            kind, item_id, path = (binding[key] for key in ("item_kind", "item_id", "field"))
            identity = (kind, item_id, path)
            if identity in seen:
                raise ValueError("Duplicate field dependency binding")
            seen.add(identity)
            item = next((row for row in brief[_COLLECTIONS[kind]] if row["id"] == item_id), None)
            if item is None or path.split(".")[0] in _IMMUTABLE:
                raise ValueError("Binding must identify an existing mutable item field")
            text = _field_text(item, path)
            codes = []
            for claim_id in binding["claim_ids"]:
                row = self._claims.get(claim_id)
                if row is None:
                    codes.append("invalid_or_missing_claim")
                    continue
                if row["source_id"] not in item["source_ids"]:
                    codes.append("claim_source_not_in_item")
                mode = binding["mode"]
                if mode == "observation" and row["kind"] != "observation":
                    codes.append("non_observation_as_customer_history")
                if mode == "conditional_action":
                    # Span checks do not establish SKU, complete procedure or semantics.
                    codes.append("operational_applicability_requires_owner_review")
                if mode == "official_reference":
                    if row["kind"] != "conditional_official_action":
                        codes.append("official_reference_requires_document")
                    if "공식 원문 참조(실행 안내 아님)" not in text:
                        codes.append("official_reference_label_missing")
                if mode != "hypothesis" and row["anchor"]["quote"] not in text:
                    codes.append("literal_claim_not_preserved")
                if mode == "hypothesis" and (HYPOTHESIS_LABEL not in text
                                             or not item.get("assumptions")):
                    codes.append("hypothesis_requires_local_label_and_assumptions")
            if codes:
                issues.append({"kind": kind, "item_id": item_id, "field": path.split(".")[0],
                               "path": path, "claim_ids": deepcopy(binding["claim_ids"]),
                               "codes": sorted(set(codes))})
        return issues


def _field_text(item: dict, path: str) -> str:
    value = item
    try:
        for component in path.split("."):
            value = value[int(component)] if isinstance(value, list) and component.isdecimal() else value[component]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Dependency path does not exist") from error
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(row, str) for row in value):
        return "\n".join(value)
    raise ValueError("Dependency must address text or a text list")


def affected_feedback(issues: list[dict], *, message: str) -> list[dict]:
    """Existing item repair requests, never a scheduler or a new budget."""
    grouped: dict[tuple[str, str], set[str]] = {}
    for issue in issues:
        grouped.setdefault((issue["kind"], issue["item_id"]), set()).add(issue["field"])
    return [{"item_kind": kind, "item_id": item_id, "fields": sorted(fields), "message": message}
            for (kind, item_id), fields in grouped.items()]
