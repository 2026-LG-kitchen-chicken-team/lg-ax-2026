"""Native item recovery on real source fixtures; mocked transport, no model calls.

Protocol-only missing fields and retained observed faulty outputs are not new
customer reviews or accepted planning quality.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path

import test_model_client
from lgax_contracts.research import load_research_schema
from lgax_core.errors import DomainError
from lgax_core.public_planning import PublicPlanner, _output_schema, source_facts
from test_public_planning import real_bundle
from test_public_planning_isolation import wire_problem
from test_public_repair import PACK, observed_draft, request


def discovery_schema():
    return _output_schema({
        "problems": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/Problem"}},
        "summaries": deepcopy(load_research_schema()["$defs"]["PlanningBrief"]["properties"]["summaries"]),
    }, ("Problem", "SummaryItem"))


def planning_schema():
    return _output_schema({
        "comparisons": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/Comparison"}},
        "concepts": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"$ref": "#/$defs/Concept"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    }, ("Comparison", "Concept"))


class ModelClientItemBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = real_bundle()
        self.healthy = wire_problem(self.bundle, "test-only-source-copy", self.bundle["sources"][0]["text"])
        malformed = {key: value for key, value in self.healthy.items() if key != "title"}
        malformed["id"] = "test-only-missing-title"
        self.output = {"problems": [self.healthy, malformed],
                       "summaries": {"positive": [], "negative": [], "mixed": []}}

    def client(self, value, **kwargs):
        fixture = test_model_client.ModelClientTests()
        self.addCleanup(fixture.doCleanups)
        backend = test_model_client.Backend(response=json.dumps(value, ensure_ascii=False))
        return fixture.client(backend, **kwargs)

    def test_explicit_native_opt_in_retains_original_candidates_schema_pin_and_usage(self):
        schema = discovery_schema()
        before = deepcopy(self.output)
        client, backend = self.client(self.output)
        result = client.generate("TEST ONLY: 항목 경계", schema, test_model_client.MODEL,
                                 allow_item_validation=True)
        self.assertEqual(result.data, before)
        self.assertEqual(json.loads(backend.requests[1].content)["format"], schema)
        self.assertEqual([r.url.path for r in backend.requests], ["/api/tags", "/api/generate", "/api/tags"])
        self.assertFalse(result.metadata["locally_validated"])
        self.assertEqual(result.metadata["validation_state"], "candidate_items_require_validation")
        self.assertEqual(result.metadata["schema_validation_errors"],
                         [{"path": ["problems", 1], "validator": "required"}])
        self.assertEqual(result.metadata["revision"], test_model_client.DIGEST)
        self.assertEqual((result.metadata["prompt_eval_count"], result.metadata["eval_count"]), (31, 7))
        self.assertEqual(self.output, before)

    def test_default_and_unrecognized_patch_or_extended_schema_stay_strict(self):
        schema = discovery_schema()
        extended = {**schema, "description": "TEST ONLY: unknown extension is strict"}
        patch = _output_schema({"patch": {"type": "object", "properties": {"title": {"type": "string"}},
                                          "required": ["title"], "additionalProperties": False}}, ())
        altered = deepcopy(schema)
        altered["$defs"]["Problem"]["properties"]["title"] = {"type": "string", "minLength": 2}
        for chosen, opt_in in ((schema, False), (extended, True), (patch, True), (altered, True)):
            with self.subTest(schema=chosen, opt_in=opt_in):
                client, _ = self.client(self.output)
                with self.assertRaises(DomainError) as raised:
                    client.generate("TEST ONLY: 기본 검사는 엄격", chosen, test_model_client.MODEL,
                                    allow_item_validation=opt_in)
                self.assertEqual(raised.exception.details["reason"], "schema_mismatch")

    def test_envelope_shapes_and_cardinality_never_reach_item_recovery(self):
        values = [None, {**self.output, "extra": "TEST ONLY"}, {"problems": self.output["problems"]},
                  {**self.output, "problems": {}}, {**self.output, "problems": [self.healthy] * 4},
                  {**self.output, "summaries": {"positive": [], "negative": [], "mixed": None}},
                  {**self.output, "summaries": {"positive": [], "negative": [], "mixed": [], "extra": []}}]
        for value in values:
            with self.subTest(value=value):
                client, _ = self.client(value)
                with self.assertRaises(DomainError) as raised:
                    client.generate("TEST ONLY: 응답 외형", discovery_schema(), test_model_client.MODEL,
                                    allow_item_validation=True)
                self.assertEqual(raised.exception.details["reason"], "schema_mismatch")

    def test_plan_items_and_summary_items_recover_without_relaxing_other_arrays(self):
        values = [(planning_schema(), {"comparisons": [None], "concepts": [None], "uncertainties": []}),
                  (discovery_schema(), {"problems": [], "summaries": {"positive": [None], "negative": [], "mixed": []}})]
        for schema, value in values:
            with self.subTest(value=value):
                client, _ = self.client(value)
                result = client.generate("TEST ONLY: 후보만 전달", schema, test_model_client.MODEL,
                                         allow_item_validation=True)
                self.assertEqual(result.data, value)
                self.assertFalse(result.metadata["locally_validated"])
        for value in ({"comparisons": [], "concepts": [], "uncertainties": []},
                      {"comparisons": [], "concepts": [None], "uncertainties": [None]}):
            client, _ = self.client(value)
            with self.assertRaises(DomainError):
                client.generate("TEST ONLY: 기획 외형", planning_schema(), test_model_client.MODEL,
                                allow_item_validation=True)

    def test_failed_schema_and_json_keep_private_raw_usage_without_public_error_leak(self):
        for raw, reason in ((json.dumps(self.output, ensure_ascii=False), "schema_mismatch"),
                            ("{PRIVATE malformed provider text", "invalid_json")):
            with self.subTest(reason=reason):
                client, backend = self.client(self.output)
                backend.response = raw
                with self.assertRaises(DomainError) as raised:
                    client.generate("TEST ONLY: 실패 기록", discovery_schema(), test_model_client.MODEL)
                failure = raised.exception
                self.assertEqual(failure.details, {"reason": reason})
                private = failure.private_generation
                self.assertEqual(private["response"], raw)
                self.assertEqual(private["metadata"]["eval_count"], 7)
                self.assertEqual(private["metadata"]["total_duration_ns"], 1000000)
                if reason == "schema_mismatch":
                    self.assertEqual(private["parsed_data"], self.output)
                else:
                    self.assertNotIn("parsed_data", private)
                public = json.dumps(failure.response(), ensure_ascii=False)
                self.assertNotIn(raw, public)
                self.assertNotIn("private_generation", public)
                self.assertNotIn("eval_count", public)

    def test_public_planner_preserves_healthy_item_and_failed_patch_usage_with_shared_budget(self):
        client, _ = self.client(self.output)
        before = deepcopy(self.bundle)
        result = PublicPlanner.from_model_client(client).run(self.bundle, "TEST ONLY: native 항목 보존", [])
        self.assertEqual(result["problems"], [{**self.healthy, "id": "problem-1"}])
        trace = result["runtime"]["model_calls"]
        self.assertEqual([r["stage"] for r in trace], ["discover", "repair_fields", "plan"])
        self.assertEqual(trace[0]["response"], self.output)
        self.assertFalse(trace[0]["metadata"]["locally_validated"])
        self.assertEqual(trace[1]["error_reason"], "schema_mismatch")
        self.assertEqual(trace[1]["failed_generation"]["parsed_data"], self.output)
        self.assertEqual(trace[1]["failed_generation"]["metadata"]["eval_count"], 7)
        self.assertEqual(result["runtime"]["correction_budget"]["revision_count"], 1)
        self.assertEqual(result["source_facts"], source_facts(self.bundle))
        self.assertEqual(result["concepts"], [])
        self.assertFalse(result["runtime"]["independent_semantic_quality_verified"])
        self.assertEqual(self.bundle, before)

    def test_review_repair_failure_preserves_original_item_and_private_generation(self):
        bundle = json.loads(PACK.read_text("utf-8"))
        previous = observed_draft(bundle)
        before = deepcopy(previous)
        # A malformed patch response is a protocol test, not fabricated review data.
        client, _ = self.client({"patch": {"existing_response": None}}, context_tokens=16384)
        result = PublicPlanner.from_model_client(client).repair(bundle, previous, [request()])
        self.assertEqual(result["comparisons"], previous["comparisons"])
        record = result["runtime"]["model_calls"][0]
        self.assertEqual(record["error_reason"], "schema_mismatch")
        self.assertEqual(record["failed_generation"]["parsed_data"], {"patch": {"existing_response": None}})
        self.assertEqual(record["failed_generation"]["metadata"]["eval_count"], 7)
        self.assertEqual(result["runtime"]["repair_outcomes"][0]["status"], "failed")
        self.assertEqual(result["source_facts"], previous["source_facts"])
        self.assertEqual(previous, before)

    def test_pin_changes_and_truncation_still_reject_even_with_item_opt_in(self):
        for name, value, reason in (("after_digest", "c" * 64, "model_revision_mismatch"),
                                    ("done_reason", "length", "output_truncated")):
            with self.subTest(reason=reason):
                client, backend = self.client(self.output)
                setattr(backend, name, value)
                with self.assertRaises(DomainError) as raised:
                    client.generate("TEST ONLY: pin 경계", discovery_schema(), test_model_client.MODEL,
                                    allow_item_validation=True)
                self.assertEqual(raised.exception.details["reason"], reason)
                self.assertFalse(hasattr(raised.exception, "private_generation"))

    def test_real_care_excerpt_preserves_scope_unit_caution_and_unchanged_raw_facts(self):
        pack = (Path(__file__).resolve().parents[1] / "data/research/r8-public-research-20261007"
                / "d1-d2-01a10600/agent-input/dishwasher/research-bundle.json")
        bundle = json.loads(pack.read_text("utf-8"))
        source = next(row for row in bundle["sources"] if row["source_id"] == "D2-DUE-CARE-DW-STORAGE-P43")
        before = deepcopy(source)
        # No generation. The corrupted native text and its separate audit
        # caution remain distinguishable; the formatter does not repair units.
        context = PublicPlanner(lambda _prompt, _schema: None)._source_context(source)
        self.assertIn("50 7", context["text"])
        self.assertEqual(context["text"], source["text"])
        self.assertEqual(context["facts"], source["facts"])
        for field in ("applicability", "source_scope_notes", "native_unit_caution", "continuation_pages"):
            self.assertEqual(context["scope_metadata"][field], source["metadata"][field])
        context["scope_metadata"]["continuation_pages"].append(0)
        self.assertEqual(source, before)
