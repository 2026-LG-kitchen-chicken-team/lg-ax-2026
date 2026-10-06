import importlib.util
import math
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.evidence_catalog import EvidenceCatalog

from tests.test_evidence_catalog import fixture

spec = importlib.util.spec_from_file_location("retrieval_benchmark", Path(__file__).resolve().parents[1] /
                                            "services/inference/retrieval_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class RetrievalBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.catalog = EvidenceCatalog([fixture()])
        self.pack = {"artifact_kind": "development_retrieval_cases", "development_only": True,
                     "independent_evaluation": False, "cases": [{"case_id": "one", "query": "청소",
                     "model_id": "SYNTH-M1", "document_version": "v1", "dataset_version": "pack-1",
                     "source_kind": "synthetic", "relevant_evidence_ids": ["E1"]}]}

    def artifact(self):
        result = benchmark.compare_retrievers(self.catalog, self.pack)
        return {"method": "bge-m3", "model": "fixture-only-not-a-model-run", "revision": "fixture-sha",
                "config": {"fixture": True}, "model_calls": 1, "latency_ms": 5,
                "input_sha256": result["input_sha256"], "catalog_sha256": result["catalog_sha256"],
                "responses": [{"case_id": "one", "query": "청소", "filters": benchmark.scope(self.pack["cases"][0]),
                               "ranked_evidence_ids": ["E1"]}]}

    def test_measured_cpu_and_unrun_models_have_null_metrics(self):
        original = deepcopy(self.pack)
        result = benchmark.compare_retrievers(self.catalog, self.pack)
        self.assertEqual(result["results"][0]["metrics"]["recall_at_k"], 1)
        self.assertEqual(result["results"][0]["model_calls"], 0)
        self.assertGreater(result["results"][0]["latency_ms"], 0)
        for model in result["results"][1:]:
            self.assertIsNone(model["metrics"])
            self.assertIsNone(model["latency_ms"])
            self.assertIsNone(model["model_calls"])
        self.assertEqual(self.pack, original)

    def test_given_artifact_computed_but_not_claimed_as_new_model_execution(self):
        result = benchmark.compare_retrievers(self.catalog, self.pack, responses=[self.artifact()])
        dense = result["results"][1]
        self.assertEqual(dense["metrics"]["mrr_at_k"], 1)
        self.assertEqual(dense["execution_kind"], "provided_artifact_not_run_here")
        self.assertEqual(dense["model"], "fixture-only-not-a-model-run")

    def test_input_catalog_query_scope_revision_and_cost_mismatch_rejected(self):
        for field, value in (("input_sha256", "wrong"), ("catalog_sha256", "wrong"),
                             ("revision", ""), ("latency_ms", math.nan), ("model_calls", 0)):
            artifact = self.artifact()
            artifact[field] = value
            with self.assertRaises(ValueError):
                benchmark.compare_retrievers(self.catalog, self.pack, responses=[artifact])
        for field, value in (("query", "다른 입력"), ("filters", {"model_id": "OTHER"}),
                             ("ranked_evidence_ids", ["OTHER"]), ("ranked_evidence_ids", ["E1", "E1"])):
            artifact = self.artifact()
            artifact["responses"][0][field] = value
            with self.assertRaises(ValueError):
                benchmark.compare_retrievers(self.catalog, self.pack, responses=[artifact])

    def test_empty_relevance_no_divide_by_zero_and_no_fake_score(self):
        self.pack["cases"][0].update(query="unrelated1234", relevant_evidence_ids=[])
        metrics = benchmark.compare_retrievers(self.catalog, self.pack)["results"][0]["metrics"]
        self.assertEqual(metrics["empty_query_results"], 1)
        self.assertIsNone(metrics["recall_at_k"])
        self.assertIsNone(metrics["ndcg_at_k"])

    def test_independent_answers_duplicate_and_out_of_scope_labels_rejected(self):
        for change in ({"independent_evaluation": True}, {"development_only": False},
                       {"cases": self.pack["cases"] * 2}):
            with self.assertRaises(ValueError):
                benchmark.compare_retrievers(self.catalog, {**self.pack, **change})
        self.pack["cases"][0]["relevant_evidence_ids"] = ["OTHER"]
        with self.assertRaises(ValueError):
            benchmark.compare_retrievers(self.catalog, self.pack)
