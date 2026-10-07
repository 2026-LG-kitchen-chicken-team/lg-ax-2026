"""Additive public-source research contracts; legacy contracts stay unchanged."""

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


@lru_cache(maxsize=1)
def load_research_schema() -> dict[str, Any]:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packages/contracts/schemas/research-planning.schema.json"
        if candidate.is_file():
            schema = json.loads(candidate.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            return schema
    schema = json.loads(files("lgax_bootstrap_data").joinpath("research-planning.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_research(definition: str, value: Any) -> None:
    root = load_research_schema()
    if definition not in root["$defs"]:
        raise ValueError(f"Unknown research definition: {definition}")
    Draft202012Validator({**root, "$ref": f"#/$defs/{definition}"}, format_checker=FormatChecker()).validate(value)
    if definition == "ResearchBundle":
        sources = value["sources"]
        ids = [source["source_id"] for source in sources]
        if len(ids) != len(set(ids)):
            raise ValidationError("Research source IDs must be unique")
        for source in sources:
            allowed_roles = {
                "review": {"customer_experience"}, "qa": {"customer_question", "official_answer"},
                "faq": {"official_document", "official_answer"}, "manual": {"official_document"},
                "spec": {"official_specification"}, "installation": {"official_document"},
            }
            if source["source_role"] not in allowed_roles[source["source_type"]]:
                raise ValidationError("Source type and author role must be consistent")
            if source["product_group"] != value["product_group"]:
                raise ValidationError("Bundle and source product groups must match")
            if source["published_at"] is not None and source["date_kind"] != "posting":
                raise ValidationError("published_at is only a confirmed posting date")
            if value["analysis_scope"] == "exact_model" and source["source_type"] == "review" and not source["purchased_model"]:
                raise ValidationError("Exact-model review analysis requires a confirmed purchased model")


def validate_research_bundle(value: Any) -> None:
    validate_research("ResearchBundle", value)


def validate_planning_brief(value: Any) -> None:
    validate_research("PlanningBrief", value)
