"""CORE002 pipeline regressions with a pinned MockTransport, never live LLM."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
from lgax_core.no_candidate_review import CRITERIA as NO_CANDIDATE_CRITERIA
from lgax_core.planning_agent import PlanningAgent, generation_schema, main
from lgax_core.semantic_review import QUALITY
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/core-contract/development"
MODEL, DIGEST = "qwen3:8b", "a" * 64


def read(name):
    return json.loads((CASES / name).read_text("utf-8"))


def dataset_for(payload):
    reviews = [{"id": "ROW-" + e["id"], "evidence_id": e["id"],
                **{k: e[k] for k in ("model_id", "text", "source_kind", "document_version", "source_id", "locator")}}
               for e in payload["sources"] if e["source_type"] == "review"]
    return {"manifest": {"dataset_id": "core002-fixture", "version": payload["request"]["dataset_version"],
                         "description": "Synthetic pipeline regression only", "source_kind": "synthetic",
                         "model_count": 1, "review_count": len(reviews), "analysis_implemented": False},
            "products": [deepcopy(payload["product"])], "reviews": reviews,
            "evidence": deepcopy(payload["sources"]), "features": deepcopy(payload["features"])}


def stages_for(output):
    keys = {"need_extract": ("needs", "desired_outcomes", "unresolved"),
            "product_compare": ("gaps", "unresolved"), "concept_draft": ("concepts", "hold_reasons")}
    assessments = {"need_extract": "review_assessments", "product_compare": "gap_assessments",
                   "concept_draft": "concept_assessments"}
    return {skill: {"result": {key: deepcopy(output[key]) for key in fields},
                    assessments[skill]: deepcopy(output[assessments[skill]]),
                    **{key: deepcopy(output[key]) for key in ("questions", "hold_reasons", "no_candidate_reasons")}}
            for skill, fields in keys.items()}


def semantic_for(context):
    def row(candidate):
        return {"concept_id": candidate["id"], "verdict": "satisfied", "reason": "테스트가 작성한 검토 선언",
                "candidate_quote": candidate["title"], "source_quotes": [
                    {"evidence_id": source["id"], "quote": source["text"]}
                    for source in context.get("sources", [])]}
    result = {"input_sha256": context["input_sha256"], "output_sha256": context["output_sha256"],
            "exclusion_assessments": [{**row(c), "verdict": "compliant", "condition_index": i, "condition": condition}
                                      for c in context["concepts"]
                                      for i, condition in enumerate(context["request"]["exclusions"])],
            "quality_assessments": [{**row(c), "criterion": criterion}
                                    for c in context["concepts"] for criterion in QUALITY], "questions": []}
    if context.get("upstream_review_required"):
        def declarations(field):
            value = context[field]
            return ([dict(zip(value["columns"], row, strict=True)) for row in value["values"]]
                    if isinstance(value, dict) else value)
        comparisons = {row["gap_id"]: row for row in declarations("gap_assessments")}
        result["upstream_assessments"] = [
            {"entity_kind": kind, "entity_id": entity["id"], "verdict": "consistent",
             "reason": "Mock transport protocol fixture; not a semantic quality result",
             "judgement_quote": entity["pain"] if kind == "need" else comparisons[entity["id"]]["reason"],
             "source_quotes": [{"evidence_id": source["id"], "quote": source["text"]}
                               for source in context["sources"]]}
            for kind, field in (("need", "needs"), ("gap", "gaps")) for entity in declarations(field)]
    return result


def no_candidate_for(context):
    source = context["sources"][0]
    return {"input_sha256": context["input_sha256"], "output_sha256": context["output_sha256"],
            "assessments": [{"criterion": criterion, "verdict": "consistent", "reason": "테스트 검토 선언",
                             "candidate_quote": context["judgement"]["no_candidate_reasons"][0],
                             "missing_need_review_ids": [],
                             "source_quotes": [{"evidence_id": source["id"], "quote": source["text"]}]}
                            for criterion in NO_CANDIDATE_CRITERIA], "questions": [], "question_basis": []}


class Transport:
    def __init__(self, stages, alter=None):
        self.stages, self.alter = stages, alter
        self.posts = []
        self.digest = DIGEST

    def __call__(self, request):
        if request.method == "GET":
            body = {"models": [{"name": MODEL, "digest": self.digest}]}
        else:
            sent = json.loads(request.content)
            context = json.loads(sent["prompt"].split("DATA_JSON:\n", 1)[1])
            skill = sent["prompt"].split("업무=", 1)[1].split(".", 1)[0]
            self.posts.append({"skill": skill, "context": context, "request": sent})
            if skill == "review_revision":
                original = context
                context = {**original["context"], "previous": original["previous"],
                           "feedback": [json.loads(item) for item in original["previous"]["violations"]]}
                need, compare, concept = (self.stages[key] for key in
                                           ("need_extract", "product_compare", "concept_draft"))
                value = {"result": {"needs": deepcopy(need["result"]["needs"]),
                                    "gaps": deepcopy(compare["result"]["gaps"]),
                                    "concepts": deepcopy(concept["result"]["concepts"]),
                                    "unresolved": deepcopy(compare["result"]["unresolved"]),
                                    "revision_count": context["revision_count"], "changes": []},
                         "status": "completed", "desired_outcomes": deepcopy(need["result"]["desired_outcomes"]),
                         "review_assessments": deepcopy(need["review_assessments"]),
                         "gap_assessments": deepcopy(compare["gap_assessments"]),
                         "concept_assessments": deepcopy(concept["concept_assessments"]),
                         **{key: deepcopy(concept[key]) for key in
                            ("questions", "hold_reasons", "no_candidate_reasons")}}
            else:
                value = (semantic_for(context) if skill == "semantic_review" else
                         no_candidate_for(context) if skill == "no_candidate_review" else deepcopy(self.stages[skill]))
            if self.alter:
                value = self.alter(skill, context, value, len(self.posts))
            body = {"model": MODEL, "done": True, "done_reason": "stop",
                    "response": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False),
                    "prompt_eval_count": 100, "eval_count": 50, "total_duration": 1000}
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(body).encode()),
                              headers={"Content-Type": "application/json"})


class PlanningAgentTests(unittest.TestCase):
    def setUp(self):
        self.payload = read("normal.input.json")
        self.output = read("normal.fixture-output.json")

    def test_missing_outcome_retry_carries_need_ids_and_original_message(self):
        def alter(skill, context, value, _count):
            if skill == "need_extract" and context["revision_count"] == 0:
                need = deepcopy(value["result"]["needs"][0])
                need["id"] = "NEED-002"
                value["result"]["needs"].append(need)
            return value
        agent, transport = self.agent(alter)
        original = deepcopy(self.payload)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input"]["revision_count"], 1)
        feedback = transport.posts[1]["context"]["feedback"][0]
        self.assertEqual(feedback["details"]["missing_need_ids"], ["NEED-002"])
        self.assertEqual(feedback["details"]["expected_count"], 2)
        self.assertEqual(feedback["message"], "각 니즈에 대응하는 희망 결과가 필요합니다.")
        self.assertEqual(result["errors"][0]["details"], feedback["details"])
        self.assertEqual(len(result["model_calls"][0]["generated"]["data"]["result"]["needs"]), 2)
        self.assertEqual(self.payload, original)

    def test_repeated_missing_outcome_preserves_failed_responses_and_two_corrections(self):
        def alter(skill, _context, value, _count):
            if skill == "need_extract":
                value["result"]["desired_outcomes"] = []
            return value
        agent, transport = self.agent(alter)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual([row["skill"] for row in transport.posts], ["need_extract"] * 3)
        self.assertEqual(len(result["errors"]), 3)
        self.assertTrue(result["correction_budget"]["closed"])
        for call in result["model_calls"]:
            self.assertEqual(call["generated"]["data"]["result"]["desired_outcomes"], [])
        for post in transport.posts[1:]:
            self.assertEqual(post["context"]["feedback"][0]["details"]["missing_need_ids"],
                             [self.output["needs"][0]["id"]])

    def test_recorded_microwave_three_needs_one_outcome_keeps_original_and_reports_missing_ids(self):
        path = ROOT / "evals/pm-intake/20261006/live-quality/original-six/microwave-changed.output.json"
        original_bytes = path.read_bytes()
        recorded = json.loads(original_bytes)
        self.payload = deepcopy(recorded["original_input"])
        declarations = [call["generated"]["data"] for call in recorded["model_calls"]]
        self.assertTrue(all(len(value["result"]["needs"]) == 3 and
                            len(value["result"]["desired_outcomes"]) == 1 for value in declarations))

        def original_response(skill, context, value, count):
            self.assertEqual(skill, "need_extract")
            return deepcopy(declarations[count - 1])

        agent, transport = self.agent(original_response)
        result = agent.run(self.payload)
        self.assertEqual(result["execution_kind"], "fixture")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["input"]["revision_count"], 2)
        for index, post in enumerate(transport.posts[1:]):
            previous = declarations[index]["result"]
            expected = {row["id"] for row in previous["needs"]}
            present = {row["need_id"] for row in previous["desired_outcomes"]}
            feedback = post["context"]["feedback"][0]
            self.assertEqual(feedback["details"]["missing_need_ids"], sorted(expected - present))
            self.assertEqual(feedback["details"]["expected_count"], 3)
            self.assertEqual(feedback["details"]["actual_count"], 1)
            self.assertEqual(feedback["message"], "각 니즈에 대응하는 희망 결과가 필요합니다.")
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual([call["generated"]["data"] for call in result["model_calls"]], declarations)

    def test_need_generation_cannot_cite_manual_as_customer_review(self):
        review_ids = [source["id"] for source in self.payload["sources"] if source["source_type"] == "review"]
        schema = generation_schema("need_extract", review_evidence_ids=review_ids)
        value = stages_for(self.output)["need_extract"]
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(value)))
        value["result"]["needs"][0]["evidence_ids"].append(next(
            source["id"] for source in self.payload["sources"] if source["source_type"] == "manual"))
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def agent(self, alter=None, *, dataset=None, stages=None):
        transport = Transport(stages_for(self.output) if stages is None else stages, alter)
        adapter = OllamaAdapter(ModelConfig("http://127.0.0.1:18864", MODEL, DIGEST,
                                            max_output_tokens=2048, context_tokens=8192),
                                transport=httpx.MockTransport(transport))
        client = StructuredModelClient(adapter)
        self.addCleanup(client.close)
        store = DemoStore(dataset_for(self.payload) if dataset is None else dataset)
        return PlanningAgent(client, store, execution_kind="fixture"), transport

    def test_three_stages_original_data_and_sources_are_preserved(self):
        agent, transport = self.agent()
        original = deepcopy(self.payload)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["decision"]["action"], "accept")
        self.assertEqual(len(transport.posts), 4)
        self.assertEqual(self.payload, original)
        self.assertEqual(result["original_input"], original)
        self.assertEqual(result["output"]["concepts"], self.output["concepts"])
        self.assertEqual(result["execution_kind"], "fixture")
        self.assertEqual(result["output"]["input_sha256"], input_digest(original))
        self.assertTrue(review_judgement(result["input"], result["output"])["valid"])

    def test_log_includes_real_transmitted_prompt_raw_completion_metadata_and_tool_io(self):
        agent, transport = self.agent()
        result = agent.run(self.payload)
        for call, post in zip(result["model_calls"], transport.posts, strict=True):
            self.assertEqual(call["formatted_prompt"], post["request"]["prompt"])
            self.assertEqual(call["formatted_prompt_sha256"], hashlib.sha256(call["formatted_prompt"].encode()).hexdigest())
            self.assertEqual(json.loads(call["raw_response"]), call["generated"]["data"])
            self.assertEqual(call["metadata"]["revision"], DIGEST)
            self.assertEqual(call["generated"]["metadata"]["generation_settings"]["num_predict"], 2048)
            self.assertNotIn("endpoint", call)
        operations = [row["operation"] for row in result["trace"]]
        self.assertIn("plan", operations)
        self.assertEqual(operations.count("get_evidence"), len(self.payload["sources"]))
        self.assertIn("review_judgement", operations)

    def test_stage_schemas_fit_adapter_budget_and_validate_fixture_outputs(self):
        stages = stages_for(self.output)
        for skill, value in stages.items():
            schema = generation_schema(skill)
            Draft202012Validator.check_schema(schema)
            self.assertFalse(list(Draft202012Validator(schema).iter_errors(value)))
            self.assertLess(len(json.dumps(schema).encode()), 16384)
        with self.assertRaises(ValueError):
            generation_schema("arbitrary_tool")

    def test_changed_request_and_exclusions_reach_every_model_stage(self):
        agent, transport = self.agent()
        self.payload["request"]["improvement_task"] = "보관 중 식품을 덜 옮기는 청소 방식"
        self.payload["request"]["exclusions"] = ["자동 세척 시스템"]
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed")
        for post in transport.posts:
            self.assertEqual(post["context"]["request"], self.payload["request"])
        self.assertEqual(transport.posts[-1]["context"]["skill_input"]["constraints"], ["자동 세척 시스템"])

    def test_changed_manual_is_not_replaced_by_old_declared_snapshot(self):
        dataset = dataset_for(self.payload)
        dataset["evidence"][1]["text"] = "새 명세: 식품을 비우지 않아도 청소 가능"
        agent, transport = self.agent(dataset=dataset)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertFalse(transport.posts)

    def test_tampered_review_stops_before_model(self):
        agent, transport = self.agent()
        self.payload["sources"][0]["text"] += " 변조"
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertFalse(transport.posts)

    def test_wrong_model_scope_stops_before_model(self):
        agent, transport = self.agent()
        self.payload["sources"][0]["model_id"] = "OTHER"
        self.assertEqual(agent.run(self.payload)["status"], "held")
        self.assertFalse(transport.posts)

    def test_wrong_dataset_version_stops_before_model(self):
        agent, transport = self.agent()
        self.payload["request"]["dataset_version"] = "wrong"
        self.assertEqual(agent.run(self.payload)["status"], "held")
        self.assertFalse(transport.posts)

    def test_omitted_existing_feature_is_not_a_valid_duplicate_comparison_context(self):
        dataset = dataset_for(self.payload)
        feature = deepcopy(dataset["features"][0])
        feature["id"] = "SECOND-FEATURE"
        dataset["features"].append(feature)
        dataset["evidence"][1]["feature_ids"].append(feature["id"])
        self.payload["sources"][1] = deepcopy(dataset["evidence"][1])
        agent, transport = self.agent(dataset=dataset)
        self.assertEqual(agent.run(self.payload)["status"], "held")
        self.assertFalse(transport.posts)

    def test_no_review_stops_without_generation(self):
        agent, transport = self.agent()
        self.payload["sources"] = self.payload["sources"][1:]
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertFalse(transport.posts)

    def test_nonzero_initial_retry_counter_is_rejected(self):
        agent, transport = self.agent()
        self.payload["revision_count"] = 2
        self.assertEqual(agent.run(self.payload)["status"], "held")
        self.assertFalse(transport.posts)

    def test_positive_review_can_hold_without_invented_needs_or_concepts(self):
        def positive(skill, context, value, count):
            if skill != "need_extract":
                return value
            value["result"].update(needs=[], desired_outcomes=[], unresolved=["긍정 리뷰에서 확정된 불편이 없다"])
            value["review_assessments"][0]["polarity"] = "positive"
            value.update(questions=["불편을 경험한 리뷰가 있나요?"], hold_reasons=["불편 근거 없음"],
                         no_candidate_reasons=["확인된 불편 없음"])
            return value
        agent, transport = self.agent(positive)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held", result)
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])
        self.assertEqual(result["output"]["needs"], [])
        self.assertEqual(result["output"]["concepts"], [])

    def test_conflicting_reviews_hold_before_concept_generation(self):
        def conflicting(skill, context, value, count):
            if skill != "need_extract":
                return value
            value["review_assessments"][0]["polarity"] = "conflicting"
            value.update(questions=["사용 조건과 상충 원문을 확인할 수 있나요?"], hold_reasons=["상충 리뷰"],
                         no_candidate_reasons=["상충 확인 전 후보 보류"])
            return value
        agent, transport = self.agent(conflicting)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual([p["skill"] for p in transport.posts], ["need_extract", "no_candidate_review"])
        self.assertEqual(result["output"]["concepts"], [])

    def test_unmentioned_is_insufficient_and_stops_before_concepts(self):
        def uncertain(skill, context, value, count):
            if skill == "product_compare":
                value["result"]["gaps"][0].update(support_status="insufficient_evidence", questions=["사용 조건 근거가 있나요?"])
                value["gap_assessments"][0].update(support_basis="unmentioned", resolution="unknown")
                value.update(questions=["추가 설명서가 있나요?"], hold_reasons=["문서 미언급"],
                             no_candidate_reasons=["지원 여부 미확인"])
            return value
        agent, transport = self.agent(uncertain)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare", "no_candidate_review"])
        self.assertEqual(result["output"]["gaps"][0]["support_status"], "insufficient_evidence")

    def test_duplicate_correction_reruns_only_concepts_and_binds_new_input_hash(self):
        def duplicate_once(skill, context, value, count):
            if skill == "concept_draft" and context["revision_count"] == 0:
                value["concept_assessments"][0]["duplication"] = "duplicate"
            return value
        agent, transport = self.agent(duplicate_once)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "product_compare", "concept_draft", "concept_draft", "semantic_review"])
        self.assertEqual(result["input"]["revision_count"], 1)
        self.assertEqual(result["original_input"]["revision_count"], 0)
        self.assertNotEqual(result["model_calls"][0]["input_sha256"], result["model_calls"][-1]["input_sha256"])
        self.assertEqual(result["output"]["input_sha256"], input_digest(result["input"]))

    def test_persistent_duplicate_never_gets_third_revision_or_candidate_success(self):
        def duplicate(skill, context, value, count):
            if skill == "concept_draft":
                value["concept_assessments"][0]["duplication"] = "duplicate"
            return value
        agent, transport = self.agent(duplicate)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(transport.posts), 5)
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertEqual(result["output"]["concepts"], [])
        self.assertEqual(result["output"]["status"], "failed")
        self.assertIn("DUPLICATE_CONCEPT", result["output"]["unresolved"])
        self.assertTrue(result["rejected_output"]["concepts"])
        self.assertEqual(review_judgement(result["input"], result["output"])["action"], "unresolved")

    def test_bad_need_reference_is_retried_from_needs(self):
        def wrong_once(skill, context, value, count):
            if skill == "need_extract" and context["revision_count"] == 0:
                value["result"]["needs"][0]["evidence_ids"] = ["MISSING"]
            return value
        agent, transport = self.agent(wrong_once)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual([p["skill"] for p in transport.posts],
                         ["need_extract", "need_extract", "product_compare", "concept_draft", "semantic_review"])
        self.assertEqual(result["input"]["revision_count"], 1)

    def test_malformed_json_retries_twice_then_stops_with_raw_failures(self):
        agent, transport = self.agent(lambda *args: "{broken")
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(transport.posts), 3)
        self.assertIsNone(result["output"])
        self.assertEqual(result["input"]["revision_count"], 2)
        self.assertTrue(all(call["raw_response"] == "{broken" for call in result["model_calls"]))

    def test_pin_failure_stops_without_model_fallback(self):
        agent, transport = self.agent()
        transport.digest = "b" * 64
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(transport.posts)
        self.assertEqual(len(result["model_calls"]), 1)
        self.assertEqual(result["errors"][0]["details"]["reason"], "model_revision_mismatch")

    def test_each_run_has_fresh_counter_and_logs(self):
        agent, _transport = self.agent()
        first = agent.run(self.payload)
        second = agent.run(self.payload)
        self.assertEqual(first["status"], second["status"])
        self.assertEqual(len(first["model_calls"]), 4)
        self.assertEqual(len(second["model_calls"]), 4)
        self.assertEqual(second["input"]["revision_count"], 0)

    def test_cli_refuses_overwriting_input_without_environment_or_model_call(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps(self.payload), "utf-8")
            with patch.object(StructuredModelClient, "from_env") as configure:
                self.assertEqual(main(["--input", str(path), "--output", str(path)]), 2)
                configure.assert_not_called()
            self.assertEqual(json.loads(path.read_text("utf-8")), self.payload)

    def test_cli_missing_connection_fails_instead_of_registering_fake_success(self):
        with TemporaryDirectory() as tmp:
            inp, out = Path(tmp) / "input.json", Path(tmp) / "output.json"
            inp.write_text(json.dumps(self.payload), "utf-8")
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(main(["--input", str(inp), "--output", str(out)]), 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
