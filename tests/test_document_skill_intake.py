"""Fixture dispatch preserves public source types without changing demo claims."""
import unittest
from copy import deepcopy

import tests.test_planning_agent as fixtures
from lgax_core.document_store import DocumentStore
from lgax_core.skill_runner import SkillRuntime


def document_fixture(payload):
    dataset = fixtures.dataset_for(payload)
    dataset.pop("manifest")
    dataset.update(artifact_kind="document_dataset", dataset_version=payload["request"]["dataset_version"])
    for collection in ("products", "reviews", "evidence"):
        for item in dataset[collection]:
            item["source_kind"] = "public"
    return dataset


class DocumentSkillIntakeTests(unittest.TestCase):
    setUp = fixtures.PlanningAgentTests.setUp
    agent = fixtures.PlanningAgentTests.agent

    def test_document_pipeline_preserves_original_types_and_observed_skill_trace(self):
        # Public labels here exercise the contract only. Every completion is a
        # MockTransport fixture, not an actual public review or quality result.
        agent, transport = self.agent()
        dataset = document_fixture(self.payload)
        agent.store = DocumentStore(dataset)
        for source in self.payload["sources"]:
            source["source_kind"] = "public"
        self.payload["product"]["source_kind"] = "public"
        before = deepcopy(self.payload)
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "completed", result["errors"])
        self.assertEqual(self.payload, before)
        self.assertEqual(len(transport.posts), 4)
        records = result["skill_trace"]["records"]
        self.assertEqual([record["skill_id"] for record in records], [
            "need_extract", "product_compare", "concept_draft"])
        for record in records:
            self.assertEqual(record["provenance"]["artifact_kind"], "document_dataset")
            self.assertIsNone(record["provenance"]["manifest"])
            self.assertEqual(record["output"]["data"]["source_kind"], "public")
            self.assertTrue(all(source["source_kind"] == "public"
                                for source in record["output"]["data"]["sources"]))
            self.assertEqual(record["tool"]["execution_kind"], "fixture")

    def test_public_manual_without_customer_reviews_holds_before_model(self):
        agent, transport = self.agent()
        dataset = document_fixture(self.payload)
        dataset["evidence"] = [e for e in dataset["evidence"] if e["source_type"] == "manual"]
        dataset["reviews"] = []
        agent.store = DocumentStore(dataset)
        self.payload["sources"] = deepcopy(dataset["evidence"])
        self.payload["product"] = deepcopy(dataset["products"][0])
        result = agent.run(self.payload)
        self.assertEqual(result["status"], "held")
        self.assertFalse(transport.posts)
        self.assertEqual(result["skill_trace"]["records"], [])
        self.assertEqual(result["errors"][-1]["code"], "VALIDATION_FAILED")

    def test_public_evidence_lookup_uses_same_source_kind_and_rejects_changed_snapshot(self):
        dataset = document_fixture(self.payload)
        store = DocumentStore(dataset)
        runtime = SkillRuntime(store, request=self.payload["request"])
        payload = {"model_id": self.payload["product"]["model_id"],
                   "document_version": self.payload["product"]["document_version"], "query": "선반"}
        response = runtime.execute("evidence_lookup", payload)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["source_kind"], "public")
        self.assertTrue(response["data"]["sources"])
        self.assertTrue(all(source["source_kind"] == "public" for source in response["data"]["sources"]))
        store._dataset["evidence"][0]["source_kind"] = "synthetic"
        response = runtime.execute("evidence_lookup", payload)
        self.assertFalse(response["ok"])
        self.assertFalse(runtime.records[-1]["tool"]["called"])


if __name__ == "__main__":
    unittest.main()
