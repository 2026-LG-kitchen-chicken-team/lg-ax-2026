"""JSON Schema validation; there is one canonical schema, not Python-only models."""

from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_VERSION = "0.1.0"


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packages/contracts/schemas/lgax.schema.json"
        if candidate.is_file():
            schema = json.loads(candidate.read_text(encoding="utf-8"))
            break
    else:
        schema = json.loads(files("lgax_bootstrap_data").joinpath("lgax.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate(definition: str, value: Any) -> None:
    """Raise ValidationError for invalid data, including nested contract references."""
    root = load_schema()
    if definition not in root["$defs"]:
        raise ValueError(f"Unknown contract definition: {definition}")
    schema = {**root, "$ref": f"#/$defs/{definition}"}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
