"""Shared trend schema fixtures, deliberately separate from source/semantic approval."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import ValidationError
from lgax_contracts import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packages/contracts/fixtures/review-trends.v1.json"


def fixture_value(fixture, case):
    """Apply identical explicit fixture edits in Python and the Ajv contract suite."""
    value = deepcopy(fixture["templates"][case["template"]])
    for change in case["changes"]:
        target = value
        for part in change["path"][:-1]:
            target = target[part]
        key = change["path"][-1]
        if change.get("remove", False):
            del target[key]
        else:
            target[key] = deepcopy(change["value"])
    return value


class ReviewTrendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_shared_valid_and_invalid_fixtures(self):
        cases = self.fixture["cases"]
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertTrue(any(case["valid"] for case in cases))
        self.assertTrue(any(not case["valid"] for case in cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                value = fixture_value(self.fixture, case)
                if case["valid"]:
                    validate(case["definition"], value)
                else:
                    with self.assertRaises(ValidationError):
                        validate(case["definition"], value)

    def test_schema_success_does_not_certify_semantic_examples(self):
        # These MUST pass shape validation: arithmetic, scope, membership and
        # canonical IDs are server-side checks, not properties proved by JSON Schema.
        for case in self.fixture["semantic_cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["schema_valid"])
                self.assertIn(case["semantic_error"], {"INVALID_INPUT", "FORBIDDEN", "CONTRACT_MISMATCH"})
                validate(case["definition"], fixture_value(self.fixture, case))
        self.assertIn("schema-only", self.fixture["purpose"])

    def test_all_existing_source_kinds_and_multiple_topics_are_supported(self):
        for kind in ("synthetic", "public", "licensed", "private"):
            with self.subTest(kind=kind):
                row = deepcopy(self.fixture["templates"]["row_day"])
                row["source_kind"] = kind
                row["topic_ids"] = ["cleaning", "storage"]
                validate("ReviewTrendMetadataRow", row)

    def test_size_limits_and_non_negative_integer_counts(self):
        cases = [
            ("ReviewTrendMetadataRow", "row_day", ["topic_ids"], [f"TOPIC-{index}" for index in range(51)]),
            ("ReviewTrendRequest", "request", ["source_ids"], [f"SOURCE-{index}" for index in range(51)]),
            ("ReviewTrendRequest", "request", ["topic_ids"], [f"TOPIC-{index}" for index in range(51)]),
            ("ReviewTrendAggregate", "aggregate", ["notes"], "n" * 801),
            ("ReviewTrendAggregate", "aggregate", ["counts", "duplicate_count"], True),
            ("ReviewTrendAggregate", "aggregate", ["counts", "duplicate_count"], 0.5),
            ("ReviewTrendAggregate", "aggregate", ["buckets", 0, "topics", 0, "evidence_ids"], [f"EVIDENCE-{index}" for index in range(51)]),
        ]
        for definition, template, path, value in cases:
            with self.subTest(definition=definition, path=path):
                case = {"template": template, "changes": [{"path": path, "value": value}]}
                with self.assertRaises(ValidationError):
                    validate(definition, fixture_value(self.fixture, case))
        aggregate = deepcopy(self.fixture["templates"]["aggregate"])
        aggregate["buckets"] = [deepcopy(aggregate["buckets"][0]) for _ in range(121)]
        with self.assertRaises(ValidationError):
            validate("ReviewTrendAggregate", aggregate)

    def test_empty_and_truncated_evidence_shapes(self):
        response = deepcopy(self.fixture["templates"]["evidence_response"])
        response["data"].update({"evidence": [], "total": 0, "next_offset": None})
        validate("WorkspaceTrendEvidenceResponse", response)
        aggregate = deepcopy(self.fixture["templates"]["aggregate"])
        topic = aggregate["buckets"][0]["topics"][0]
        topic.update({"evidence_count": 51, "evidence_ids_truncated": True})
        validate("ReviewTrendAggregate", aggregate)
        # The shortened shape is valid; membership and count agreement must be
        # independently checked by the trusted collector/gateway.

    def test_success_and_unimplemented_error_envelopes_are_distinct(self):
        success = {"ok": True, "data": {"aggregate": deepcopy(self.fixture["templates"]["aggregate"]), "contract_version": "0.1.0"}}
        validate("WorkspaceReviewTrendResponse", success)
        error = {"ok": False, "error": {"code": "NOT_IMPLEMENTED", "message": "Review trend collector is not connected.", "details": {}}}
        validate("ErrorResponse", error)
        with self.assertRaises(ValidationError):
            validate("WorkspaceReviewTrendResponse", error)
        error["error"]["code"] = "INVALID_INPUT"
        validate("ErrorResponse", error)

    def test_canonical_review_and_planning_input_are_not_extended(self):
        schema = load_schema()
        review = schema["$defs"]["Review"]
        planning = schema["$defs"]["PlanningRequest"]
        self.assertFalse(review["additionalProperties"])
        self.assertFalse(planning["additionalProperties"])
        self.assertEqual(set(review["properties"]), {"id", "model_id", "text", "source_kind", "document_version", "source_id", "locator", "evidence_id"})
        self.assertNotIn("aggregate_id", planning["properties"])
        self.assertNotIn("published_at", review["properties"])
        self.assertEqual(schema["x-contract-version"], "0.1.0")
        metadata = schema["$defs"]["ReviewTrendMetadataRow"]
        self.assertNotIn("text", metadata["properties"])


if __name__ == "__main__":
    unittest.main()
