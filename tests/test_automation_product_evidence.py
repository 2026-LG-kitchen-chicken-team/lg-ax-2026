"""Admission/budget adversaries using explicit fixtures, not live model proof."""
import base64
import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.automation.completion import PM, ArtifactRef, CompletionError, assess_parent, digest
from services.automation.parent_collector import EvidenceStore
from services.automation.pm import PMDriverBusy, PMError, canonical, fingerprint
from services.automation.product_evidence import (
    CASES,
    DATASET,
    RUNNER,
    SUPPORTED,
    TASK,
    ProductCaseBinding,
    ProductEvidenceProducer,
)
from services.automation.product_rpc import DIGEST, MODEL, FileTransport, encode
from tests.test_automation_completion import MAIN, Fixture
from tests.test_automation_product_rpc import SETTINGS, completion, generation

REQUIREMENTS = ("R01", "R09", "R10", "R11", "R12", "R15", "R16", "R26")
OPTIONS = {"enabled": True, "case_ids": list(CASES), "max_generations_per_case": 8,
           "max_product_tokens_per_case": 1000, "max_product_cases_per_task": 4,
           "timeout_seconds": 120, "settings": SETTINGS}


def boundary(role):
    return {"backend": "docker", "role": role, "image_id": "sha256:" + "a" * 64, "uid": 1000,
            "readonly_root": True, "caps_dropped": True, "no_new_privileges": True,
            "publisher_credentials_mounted": False, "ai_profile_mounted": role == "model",
            "network": "bridge" if role == "model" else "none"}


class FixtureDriver:
    def __init__(self, root):
        self.root = root
        self.calls = []
        self.busy = False
        self.verdict = "approve"
        self.bad_usage = self.bad_proof = self.bad_boundary = self.missing_action = False
        self.session = "product-review-fixture"

    @contextmanager
    def reserve_profile(self):
        if self.busy:
            raise PMDriverBusy("fixture contention")
        yield

    def call(self, context, schema, timeout, *, purpose):
        self.calls.append((context, schema, timeout, purpose))
        run = self.root / "driver" / self.session
        run.mkdir(parents=True, exist_ok=True)
        events = b'{"fixture_event":true}\n'
        (run / "events.jsonl").write_bytes(events)
        verdicts = {key: {"outcome": self.verdict, "reason": "Independent fixture criterion decision"}
                    for key in schema["required"] if key != "task_actions"}
        if "task_actions" in schema["required"]:
            verdicts["task_actions"] = {key: {"outcome": "missing" if self.missing_action else "approve",
                                              "reason": "Independent source action decision"}
                                        for key in schema["properties"]["task_actions"]["required"]}
        record = {"session_id": self.session, "engine": "fixture", "usage": {"input_tokens": 7, "output_tokens": 3},
                  "result": verdicts, "events_sha256": digest(events), "boundary": boundary("model")}
        if self.bad_usage:
            record["usage"] = {}
        if self.bad_boundary:
            record["boundary"]["publisher_credentials_mounted"] = True
        original = {**record, "result": {}} if self.bad_proof else record
        (run / "proof.json").write_text(canonical(original), encoding="utf-8")
        return record


class ProductEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.fixture = Fixture()
        f = self.fixture
        f.task["requirement_ids"] = list(REQUIREMENTS)
        f.task["allowed_execution_kinds"] = ["live_model"]
        f.cap["requirement_ids"] = list(REQUIREMENTS)
        f.policy["tasks"][TASK]["requirement_ids"] = list(REQUIREMENTS)
        f.load()
        f.unit = f.make_unit()
        self.store = EvidenceStore(self.root / "evidence")
        for (path, commit), raw in f.store.items():
            self.store.blob(path, commit, raw)
        self.store.index["admissions"] = {key: {"kind": value.kind, "commit": value.commit,
                                                "collected_by": value.collected_by}
                                         for key, value in f.admissions.items()}
        self.store.save()
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.journal = self.state_dir / "pm.sqlite"
        with closing(sqlite3.connect(self.journal)) as db:
            db.execute("CREATE TABLE budgets(scope TEXT PRIMARY KEY,tokens INTEGER,model_calls INTEGER)")
            db.commit()
        self.on, self.main = True, MAIN
        self.driver = FixtureDriver(self.state_dir)
        limits = {"max_model_calls_per_day": 20, "max_model_tokens_per_day": 10000,
                  "max_model_calls_per_task": 10, "max_model_tokens_per_task": 1000,
                  "decision_timeout_seconds": 30}
        self.broker = SimpleNamespace(state_dir=self.state_dir, config={"product_evidence": copy.deepcopy(OPTIONS),
                "journal_file": str(self.journal)}, policy={"limits": limits}, state={"budgets": {}},
            executor=SimpleNamespace(config=SimpleNamespace(image="sha256:" + "a" * 64, model_network="bridge")),
            authenticate=lambda: {"account": PM, "operator": True}, enabled=lambda: self.on,
            github=SimpleNamespace(request=lambda *_args: {"sha": self.main}), driver=self.driver, save=lambda: None)
        self.producer = ProductEvidenceProducer(self.broker)
        self.case_calls = []

    def fixture_case(self, case_id, main, run_id, settings, store, origin):
        self.case_calls.append((case_id, main, run_id, settings, origin))
        source = [store.blob("evals/fixture/" + name, main, encode(value)).as_dict()
                  for name, value in (("dataset.json", {"fixture": "authorized dataset"}),
                                      (case_id + ".json", {"fixture": case_id}))]
        output = {"execution_kind": "live_model", "status": "held", "trace": [{"tool": "fixture_lookup"}],
                  "original_input": {"fixture": case_id}, "semantic_reviews": [{"self_claim": "pass"}],
                  "model_calls": [{"stage": "fixture", "raw_response": "Complete fixture response",
                                  "formatted_prompt": "Large fixture protocol prompt", "schema": {"fixture": True}}]}
        refs = {name: store.blob("control/fixture/" + run_id + "/" + name + ".json", main, raw).as_dict()
                for name, raw in (("output", encode(output)), ("relay", b'{"fixture_relay":true}'), ("process", b"fixture log"))}
        binding = self.producer.bindings[case_id]
        return {"case_id": case_id, "refs": refs, "code_versions": [store.blob("packages/core/" + file, main,
                b"# fixed test fixture, not product source evidence\n").as_dict()
                    for file in ("planning_agent.py", "model_client.py")], "source_versions": source, "model": {"model_id": MODEL,
                "revision": DIGEST, "license": "test fixture", "runtime": "unit test only", "settings": settings},
                "actual_product_calls": 1 if binding.execution_mode == "live_model" else 0,
                "execution_mode": binding.execution_mode, "requirement_ids": list(binding.requirement_ids),
                "actual_product_tokens": 18 if binding.execution_mode == "live_model" else 0, "boundary": boundary("validator")}

    def run_fixture(self):
        with patch.object(self.producer, "_case", side_effect=self.fixture_case):
            return self.producer(self.fixture.contract, self.main, (self.fixture.unit,), self.store)

    def test_partial_independent_acceptance_never_completes_parent_or_uses_self_review(self):
        bundle = self.run_fixture()
        self.assertEqual({row.requirement_id for row in bundle.coverage}, set(SUPPORTED))
        self.assertIsNone(bundle.parent_acceptance)
        result = assess_parent(self.fixture.contract, (self.fixture.unit,), bundle.coverage, None, (),
                               self.store.registry, self.store.read, MAIN)
        self.assertFalse(result.complete)
        self.assertEqual(set(result.missing_requirements), {"R10", "R11", "R16"})
        self.assertEqual(result.issues, ("independent parent acceptance required",))
        self.assertEqual(len(self.case_calls), 2)
        context = self.driver.calls[0][0]
        self.assertIn("semantic_reviews are self-review", context["notice"])
        self.assertNotIn("expected_answers", canonical(context))
        self.assertEqual(context["cases"][0]["actual_output"]["model_calls"][0]["raw_response"], "Complete fixture response")
        self.assertNotIn("formatted_prompt", context["cases"][0]["actual_output"]["model_calls"][0])
        self.assertEqual(self.broker.state["budgets"][next(iter(self.broker.state["budgets"]))]["tokens"], 10)
        execution = json.loads(self.store.read(bundle.coverage[0].execution))
        self.assertEqual(execution["model"]["model_id"], MODEL)
        self.assertIn("PM CLI review tokens are separate", " ".join(execution["limitations"]))

    def test_off_or_stale_main_makes_no_product_call_or_budget_reservation(self):
        for main, on in ((MAIN, False), ("f" * 40, True)):
            self.main, self.on = main, on
            with self.subTest(main=main, on=on), self.assertRaises(CompletionError):
                self.producer(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
        self.assertFalse(self.producer.state["runs"])
        self.assertFalse(self.broker.state["budgets"])

    def test_protected_external_progress_changes_fingerprint_without_running_a_model(self):
        original = self.producer.state_fingerprint
        state = {"schema_version": 1, "runs": {"fixed-operator-recovery": {"state": "executed"}}}
        self.producer.state_path.write_bytes(encode(state))
        self.assertNotEqual(self.producer.state_fingerprint, original)
        self.assertEqual(self.producer.state_fingerprint, fingerprint({
            "state": state, "evaluator_versions": self.producer.evaluator_versions}))
        self.assertFalse(self.driver.calls)
        self.assertFalse(self.producer.state["runs"])

    def test_unaccepted_forged_or_incomplete_unit_chain_never_executes(self):
        self.assertFalse(self.producer(self.fixture.contract, MAIN, (), self.store).coverage)
        self.store.index["admissions"].pop(self.fixture.unit.review.sha256)
        with self.assertRaises(CompletionError):
            self.run_fixture()
        self.assertFalse(self.case_calls)

    def test_unavailable_product_is_recorded_failed_and_not_retried_on_same_tick_or_restart(self):
        precreated = ProductEvidenceProducer(self.broker)
        with patch.object(self.producer, "_case", side_effect=PMError("fixture service unavailable")) as case:
            result = self.producer(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            self.assertFalse(result.coverage)
            result = self.producer(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            self.assertEqual(case.call_count, 1)
        restarted = ProductEvidenceProducer(self.broker)
        with patch.object(restarted, "_case") as case:
            restarted(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            case.assert_not_called()
        with patch.object(precreated, "_case") as case:
            precreated(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            case.assert_not_called()
        entry = next(iter(restarted.state["runs"].values()))
        self.assertEqual(entry["state"], "failed")
        self.assertEqual(len(entry["case_ids_reserved"]), 2)
        self.assertFalse(entry["full_task_complete"])

    def test_reviewed_evaluator_change_appends_attempt_and_preserves_original_failure_and_quota(self):
        from services.automation import product_rpc

        with patch.object(self.producer, "_case", side_effect=PMError("fixture pre-generation failure")):
            self.assertFalse(self.producer(self.fixture.contract, MAIN, (self.fixture.unit,), self.store).coverage)
        original = copy.deepcopy(self.producer.state["runs"])
        unchanged = ProductEvidenceProducer(self.broker)
        with patch.object(unchanged, "_case") as case:
            unchanged(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            case.assert_not_called()
        rpc_source = self.root / "reviewed-product-rpc.py"
        rpc_source.write_bytes(Path(product_rpc.__file__).read_bytes() + b"\n# reviewed host fixture revision\n")
        with patch.object(product_rpc, "__file__", str(rpc_source)):
            changed = ProductEvidenceProducer(self.broker)
            self.assertNotEqual(changed.evaluator_versions, unchanged.evaluator_versions)
            self.producer = changed
            self.assertEqual(len(self.run_fixture().coverage), 5)
            self.assertEqual(len(self.run_fixture().coverage), 5)
            self.assertEqual(len(self.case_calls), 2)
            self.assertEqual(len(self.driver.calls), 1)
            self.assertEqual(len(changed.state["runs"]), 2)
            for key, value in original.items():
                self.assertEqual(changed.state["runs"][key], value)
            self.assertEqual(sum(len(value["case_ids_reserved"]) for value in changed.state["runs"].values()), 4)
            # Another reviewed version cannot bypass the cumulative case cap.
            rpc_source.write_bytes(rpc_source.read_bytes() + b"# next reviewed revision\n")
            exhausted = ProductEvidenceProducer(self.broker)
            with patch.object(exhausted, "_case") as case, self.assertRaises(CompletionError):
                exhausted(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            case.assert_not_called()

    def test_reviewer_missing_criteria_produces_explicit_missing_not_artificial_pass(self):
        self.driver.verdict = "missing"
        bundle = self.run_fixture()
        self.assertFalse(bundle.coverage)
        entry = next(iter(self.producer.state["runs"].values()))
        self.assertEqual(entry["state"], "partial")
        self.assertTrue(all(row["outcome"] == "missing" for row in entry["verdicts"].values()))

    def test_busy_reviewer_before_reservation_reuses_real_cases_without_spending_review(self):
        self.driver.busy = True
        self.assertFalse(self.run_fixture().coverage)
        self.assertFalse(self.broker.state["budgets"])
        self.assertEqual(len(self.case_calls), 2)
        self.assertTrue(self.producer.pending_review)
        self.driver.busy = False
        bundle = self.run_fixture()
        self.assertEqual(len(bundle.coverage), 5)
        self.assertEqual(len(self.case_calls), 2)
        self.assertFalse(self.producer.pending_review)

    def test_crashed_pending_review_holds_original_day_task_and_blocks_new_main_without_retry(self):
        day = "2026-10-04"
        pending = {"state": "review_started", "main": MAIN, "task_id": TASK, "job_id": "fixture-job",
            "review_reservation": {"day": day, "task_id": TASK, "day_token_ceiling": 10000, "task_token_ceiling": 1000}}
        self.producer.state["runs"]["crashed-paid-call"] = pending
        self.producer._save()  # Crash checkpoint after durable stamp, before CLI finally.
        self.broker.state["budgets"][day] = {"calls": 1, "tokens": 11, "tasks": {TASK: 11}, "task_calls": {TASK: 1}}
        restarted = ProductEvidenceProducer(self.broker)
        budget = self.broker.state["budgets"][day]
        self.assertEqual(budget["tokens"], 10000)
        self.assertEqual(budget["tasks"][TASK], 1000)
        self.assertEqual(budget["calls"], 1)
        self.assertTrue(restarted.state["review_halt"])
        self.assertFalse(restarted.pending_review)
        self.main = "f" * 40
        with patch.object(restarted, "_case") as case:
            result = restarted(self.fixture.contract, self.main, (self.fixture.unit,), self.store)
            self.assertFalse(result.coverage)
            case.assert_not_called()
        again = ProductEvidenceProducer(self.broker)
        self.assertTrue(again.state["review_halt"])
        self.assertEqual(budget["tokens"], 10000)
        self.assertEqual(list(self.broker.state["budgets"]), [day])
        self.assertFalse(self.driver.calls)

    def test_crash_between_debit_and_handled_marker_is_idempotent(self):
        day = "2026-10-03"
        self.producer.state["runs"]["pending"] = {"state": "review_started", "review_reservation": {
            "day": day, "task_id": TASK, "day_token_ceiling": 9000, "task_token_ceiling": 900}}
        self.producer._save()
        with patch.object(self.producer, "_save", side_effect=SystemExit("fixture hard interruption")), self.assertRaises(SystemExit):
            self.producer._recover_unknown_reviews()
        self.assertEqual(self.broker.state["budgets"][day]["tokens"], 9000)
        restarted = ProductEvidenceProducer(self.broker)
        self.assertTrue(restarted.state["review_halt"])
        self.assertEqual(self.broker.state["budgets"][day]["tokens"], 9000)
        self.assertEqual(self.broker.state["budgets"][day]["tasks"][TASK], 900)

    def test_unbound_old_pending_review_halts_without_inventing_current_day_charge(self):
        self.producer.state["runs"]["old"] = {"state": "review_started"}
        self.producer._save()
        restarted = ProductEvidenceProducer(self.broker)
        self.assertTrue(restarted.state["review_halt"])
        self.assertFalse(self.broker.state["budgets"])
        with patch.object(restarted, "_case") as case:
            restarted(self.fixture.contract, MAIN, (self.fixture.unit,), self.store)
            case.assert_not_called()

    def test_review_reservation_is_durable_before_driver_and_known_completion_settles(self):
        original = self.driver.call

        def verify_before_call(*args, **kwargs):
            saved = json.loads(self.producer.state_path.read_bytes())
            entry = next(iter(saved["runs"].values()))
            self.assertEqual(entry["state"], "review_started")
            reservation = entry["review_reservation"]
            self.assertEqual(reservation["task_id"], TASK)
            self.assertEqual(reservation["day_token_ceiling"], 10000)
            self.assertEqual(reservation["task_token_ceiling"], 1000)
            self.assertEqual(self.broker.state["budgets"][reservation["day"]]["calls"], 1)
            return original(*args, **kwargs)
        self.driver.call = verify_before_call
        self.assertEqual(len(self.run_fixture().coverage), 5)
        entry = next(iter(self.producer.state["runs"].values()))
        self.assertEqual(entry["state"], "partial")
        self.assertEqual(entry["review_verified_usage"], {"input_tokens": 7, "output_tokens": 3})
        restarted = ProductEvidenceProducer(self.broker)
        self.assertNotIn("review_halt", restarted.state)

    def test_unknown_review_usage_spends_remaining_quota_and_cannot_retry(self):
        self.driver.bad_usage = True
        self.assertFalse(self.run_fixture().coverage)
        budget = next(iter(self.broker.state["budgets"].values()))
        self.assertEqual(budget["tokens"], 10000)
        self.assertEqual(budget["tasks"][TASK], 1000)
        self.run_fixture()
        self.assertEqual(len(self.driver.calls), 1)

    def test_original_review_tamper_and_credentials_mount_refused(self):
        original = copy.deepcopy(self.store.index["admissions"])
        self.driver.bad_proof = True
        self.assertFalse(self.run_fixture().coverage)
        self.assertEqual(self.store.index["admissions"], original)
        budget = next(iter(self.broker.state["budgets"].values()))
        self.assertEqual(budget["tokens"], 10000)
        self.assertEqual(budget["tasks"][TASK], 1000)
        self.assertIn("review_halt", self.producer.state)
        self.main = "b" * 40
        self.assertFalse(self.run_fixture().coverage)
        self.assertEqual(len(self.driver.calls), 1)
        self.assertEqual(len(self.case_calls), 2)
        with self.assertRaises(CompletionError):
            self.producer._boundary({**boundary("validator"), "publisher_credentials_mounted": True}, "validator")
        with self.assertRaises(CompletionError):
            self.producer._boundary({**boundary("validator"), "network": "bridge"}, "validator")

    def test_driver_profile_reservation_is_mandatory(self):
        self.driver.reserve_profile = None
        self.assertFalse(self.run_fixture().coverage)
        self.assertFalse(self.driver.calls)
        self.assertFalse(self.broker.state["budgets"])

    def test_logical_product_and_review_budget_does_not_reset_for_new_main_or_day(self):
        self.run_fixture()
        self.main = "b" * 40
        self.run_fixture()
        self.main = "c" * 40
        with self.assertRaises(CompletionError):
            self.run_fixture()
        self.assertEqual(len(self.case_calls), 4)
        with closing(sqlite3.connect(self.journal)) as db:
            db.execute("INSERT INTO budgets VALUES(?, ?, ?)", ("task:" + TASK, 1000, 10))
            db.commit()
        with self.assertRaises(CompletionError):
            self.producer._review_budget(TASK)

    def test_exact_source_criterion_scope_and_options_only(self):
        self.producer.options["endpoint"] = "http://example.invalid"
        with self.assertRaises(CompletionError):
            self.run_fixture()
        self.assertFalse(self.case_calls)
        self.producer.options.pop("endpoint")
        self.producer.options["settings"]["seed"] = 43
        with self.assertRaises(ValueError):
            self.run_fixture()
        self.assertFalse(self.case_calls)
        # Mutating the supplied host config does not mutate a running producer.
        self.broker.config["product_evidence"]["enabled"] = False
        self.assertTrue(self.producer.options["enabled"])

    def test_actual_upstream_correlation_rejects_fake_calls_schema_tokens_and_raw_response(self):
        prompt, raw = generation()["prompt"], completion()
        call = {"formatted_prompt": prompt, "formatted_prompt_sha256": digest(prompt.encode()),
                "schema": generation()["format"], "raw_response": json.loads(raw)["response"],
                "metadata": {"model_id": MODEL, "revision": DIGEST, "generation_settings": SETTINGS,
                             "thinking_enabled": False, "prompt_eval_count": 11, "eval_count": 7}}
        state = {"requests": [{"generation": True, "state": "completed", "request": {"body": generation()},
                               "response_base64": base64.b64encode(raw).decode(),
                               "usage": {"prompt_eval_count": 11, "eval_count": 7}}]}
        ProductEvidenceProducer._verify_calls({"model_calls": [call]}, state, SETTINGS)
        for change in ({"raw_response": "Invented output"}, {"schema": {"type": "string"}},
                       {"formatted_prompt_sha256": "f" * 64}, {"metadata": {**call["metadata"], "eval_count": 0}}):
            with self.subTest(change=change), self.assertRaises(CompletionError):
                ProductEvidenceProducer._verify_calls({"model_calls": [{**call, **change}]}, state, SETTINGS)
        with self.assertRaises(CompletionError):
            ProductEvidenceProducer._verify_calls({"model_calls": []}, state, SETTINGS)

    def test_bounded_guest_runner_is_static_and_uses_real_agent_not_expected_answers(self):
        compile(RUNNER, "fixed-product-runner", "exec")
        self.assertIn("PlanningAgent(client,DemoStore(dataset),execution_kind=", RUNNER)
        self.assertIn(").run(payload)", RUNNER)
        self.assertNotIn("role=\"model\"", RUNNER)
        self.assertNotIn("expected_answer", RUNNER)
        self.assertNotIn("OPENAI_API_KEY", RUNNER)
        with self.assertRaises(CompletionError):
            self.producer._boundary({**boundary("model"), "image_id": "sha256:" + "f" * 64}, "model")

    def test_case_wiring_keeps_validator_noauth_original_upstream_bytes_and_failed_output(self):
        """Fixture executor drives actual RPC; does not attest Docker/model quality."""
        import httpx

        source = self.root / "fixed-source"
        for name, value in (("evals/core-planning/examples/dataset.json", {"fixture": "source"}),
                (CASES["fridge-normal"], {"fixture": "fridge"}),
                ("evals/bootstrap-models/models-manifest.json", {"models": [{"model_id": MODEL, "revision": DIGEST,
                     "license": "test fixture", "license_text_sha256": "f" * 64}]})):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(encode(value))
        core = source / "packages/core/src/lgax_core/fixture.py"
        core.parent.mkdir(parents=True)
        core.write_text("# Fixture, never executed on host\n", encoding="utf-8")
        work = self.root / "isolated/workspace"
        artifacts = self.root / "isolated/artifacts"
        shutil.copytree(source, work)
        artifacts.mkdir()
        self.broker._source = lambda *_args: (work, artifacts)
        executor_calls = []
        status = "held"

        def fixture_executor(argv, **kwargs):
            executor_calls.append((argv, kwargs))
            cfg = json.loads((artifacts / "result-schema.json").read_bytes())
            payload = generation()
            with httpx.Client(transport=FileTransport(artifacts, cfg["run_id"], timeout_seconds=3)) as client:
                client.get("http://127.0.0.1:18873/api/tags")
                raw = client.post("http://127.0.0.1:18873/api/generate", json=payload).json()
            product = {"execution_kind": "live_model", "status": status, "trace": [{"fixture_tool": True}],
                       "original_input": {"fixture": "fridge"}, "model_calls": [{"formatted_prompt": payload["prompt"],
                        "formatted_prompt_sha256": digest(payload["prompt"].encode()), "schema": payload["format"],
                        "raw_response": raw["response"], "metadata": {"model_id": MODEL, "revision": DIGEST,
                            "generation_settings": SETTINGS, "thinking_enabled": False,
                            "prompt_eval_count": raw["prompt_eval_count"], "eval_count": raw["eval_count"]}}]}
            (artifacts / "result.json").write_bytes(encode(product))
            kwargs["output"].write_bytes(b"fixture container process output\n")
            return SimpleNamespace(returncode=0 if status == "held" else 2, stopped_reason=None)

        self.broker.executor.run = fixture_executor
        self.broker.executor.last_boundary = boundary("validator")
        self.producer.upstream = lambda method, _path, _body: completion() if method == "POST" else encode(
            {"models": [{"name": MODEL, "digest": DIGEST}]})
        origin = {"task_id": TASK, "job_id": "fixture-job", "tested_commit": MAIN,
                  "contract_fingerprint": self.fixture.contract.fingerprint, "owner": "unknownamed"}
        run_id = "product-" + "d" * 40
        case = self.producer._case("fridge-normal", MAIN, run_id, SETTINGS, self.store, origin)
        self.assertEqual(case["actual_product_tokens"], 18)
        self.assertEqual(case["actual_product_calls"], 1)
        argv, kwargs = executor_calls[0]
        self.assertEqual(argv, ["python", "_trusted_product_runner.py"])
        self.assertEqual(kwargs["role"], "validator")
        self.assertTrue(kwargs["readonly_workspace"])
        self.assertEqual(kwargs["env"], {})
        retained = self.producer.state["case_runs"][run_id]
        self.assertEqual(retained["status"], "held")
        relay = json.loads(self.store.read(ArtifactRef.parse(retained["refs"]["relay"])))
        self.assertEqual(relay["approved_origin"], origin)
        self.assertEqual(base64.b64decode(relay["requests"][1]["response_base64"]), completion())
        # New fixed run: an actual failed process must retain bytes, not coverage.
        status = "failed"
        other_work = self.root / "other/workspace"
        other_artifacts = self.root / "other/artifacts"
        shutil.copytree(source, other_work)
        other_artifacts.mkdir()
        work, artifacts = other_work, other_artifacts
        failed_id = "product-" + "e" * 40
        with self.assertRaises(CompletionError):
            self.producer._case("fridge-normal", MAIN, failed_id, SETTINGS, self.store, origin)
        failed = self.producer.state["case_runs"][failed_id]
        self.assertEqual(failed["status"], "unverified")
        self.assertEqual(set(failed["refs"]), {"output", "relay", "process"})
        self.assertFalse(any(row["collected_by"] != PM for row in self.store.index["admissions"].values()))

    def test_fixed_extended_cases_enable_full_candidate_only_after_whole_action_review(self):
        bindings = tuple(ProductCaseBinding(key, path, DATASET, SUPPORTED) for key, path in CASES.items()) + (
            ProductCaseBinding("fridge-insufficient", "evals/core-planning/examples/insufficient.input.json", DATASET,
                               ("R10", "R11", "R16")),)
        options = {**OPTIONS, "case_ids": [case.case_id for case in bindings], "max_product_cases_per_task": 6}
        self.producer = ProductEvidenceProducer(self.broker, options=options, case_bindings=bindings)
        self.driver.missing_action = True
        first = self.run_fixture()
        self.assertEqual(len(first.coverage), 8)
        self.assertIsNone(first.parent_acceptance)
        held = assess_parent(self.fixture.contract, (self.fixture.unit,), first.coverage, None, (),
                             self.store.registry, self.store.read, MAIN)
        self.assertFalse(held.complete)
        # A separately pinned main may be evaluated later, not a forced retry.
        self.main = "b" * 40
        self.driver.missing_action = False
        final = self.run_fixture()
        self.assertIsNotNone(final.parent_acceptance)
        assessed = assess_parent(self.fixture.contract, (self.fixture.unit,), final.coverage, final.parent_acceptance, (),
                                 self.store.registry, self.store.read, self.main)
        self.assertTrue(assessed.complete)
        self.assertFalse(assessed.receipt.payload["dependency_release_allowed"])
        self.assertNotIn("published_completions", self.store.index)
        context = self.driver.calls[-1][0]
        self.assertEqual(set(context["task_actions"]), set(self.fixture.contract.action_criteria))
        self.assertEqual(len(context["fixed_core_source"]), 2)

    def test_unregistered_answer_assets_or_dynamically_selected_scope_refused(self):
        for path in ("private/answers.input.json", "evals/core-planning/examples/reviewer-only.input.json",
                     "evals/core-planning/examples/../bad.input.json"):
            with self.subTest(path=path), self.assertRaises(CompletionError):
                ProductCaseBinding("bad-case", path, DATASET, ("R10",))
        with self.assertRaises(CompletionError):
            ProductCaseBinding("bad-case", CASES["fridge-normal"], DATASET, ("R30",))

    def test_deterministic_guard_binding_has_no_generation_permission(self):
        from services.automation.product_rpc import REQUEST, FileRelay, RPCError, write_file
        from tests.test_automation_product_rpc import RUN, request

        artifacts, private = self.root / "guard-artifacts", self.root / "guard-private"
        artifacts.mkdir()
        private.mkdir()
        calls = []
        relay = FileRelay(artifacts, private / "relay.json", RUN, settings=SETTINGS, max_generations=1,
                         max_tokens=100, enabled=lambda: True, upstream=lambda *args: calls.append(args),
                         allow_generation=False)
        write_file(artifacts / REQUEST, request())
        with self.assertRaises(RPCError):
            relay.step()
        self.assertFalse(calls)
        self.assertEqual(relay.state["generations"], 0)


if __name__ == "__main__":
    unittest.main()
