"""Evidence integrity, product/version isolation and honest unfinished behavior."""

import unittest

from fastapi.testclient import TestClient
from lgax_api.server import app
from lgax_core import DemoStore
from lgax_core.errors import DomainError


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()

    def test_model_filter_does_not_mix_products(self):
        items = self.store.search_evidence("청소", "FRIDGE-A")["data"]["items"]
        self.assertTrue(items)
        self.assertEqual({item["model_id"] for item in items}, {"FRIDGE-A"})

    def test_empty_query_results_differ_from_invalid_identifier(self):
        result = self.store.search_evidence("존재하지않는키워드", "FRIDGE-A")
        self.assertEqual(result["data"]["items"], [])
        self.assertEqual(result["data"]["total"], 0)
        with self.assertRaises(DomainError) as error:
            self.store.search_evidence("청소", "WRONG")
        self.assertEqual(error.exception.code, "INVALID_MODEL_ID")

    def test_version_filter_and_missing_version(self):
        result = self.store.search_evidence("분리", "FRIDGE-A", "2.0")
        self.assertTrue(result["data"]["items"])
        self.assertEqual({item["document_version"] for item in result["data"]["items"]}, {"2.0"})
        with self.assertRaises(DomainError) as error:
            self.store.search_evidence("분리", "FRIDGE-A", "9.0")
        self.assertEqual(error.exception.code, "INVALID_DOCUMENT_VERSION")

    def test_bad_limits_and_blank_input(self):
        for kwargs in [{"q": " "}, {"q": "청소", "limit": 0}, {"q": "청소", "limit": 51},
                       {"q": "청소", "document_version": "1.0"}]:
            with self.assertRaises(DomainError):
                self.store.search_evidence(**kwargs)

    def test_returns_copies_not_mutable_state(self):
        fetched = self.store.get_evidence("MANUAL-001")
        fetched["data"]["evidence"]["text"] = "changed"
        self.assertNotEqual(self.store.get_evidence("MANUAL-001")["data"]["evidence"]["text"], "changed")

    def test_missing_evidence_and_cross_model_link_rejected(self):
        with self.assertRaises(DomainError) as error:
            self.store.get_evidence("missing")
        self.assertEqual(error.exception.code, "INVALID_EVIDENCE_ID")
        dataset = self.store.bootstrap()["data"]
        dataset.pop("contract_version")
        dataset["evidence"][0]["feature_ids"] = ["FEATURE-005"]
        with self.assertRaisesRegex(ValueError, "Cross-model"):
            DemoStore(dataset)

    def test_new_manual_cannot_reference_a_feature_from_another_version(self):
        dataset = self.store.bootstrap()["data"]
        dataset.pop("contract_version")
        manual = next(item for item in dataset["evidence"]
                      if item["source_type"] == "manual" and item["feature_ids"])
        dataset["evidence"].append({
            **manual,
            "id": "MANUAL-VERSION-REGRESSION",
            "source_id": f"{manual['model_id']}-MANUAL-v9.0",
            "document_version": "9.0",
        })
        with self.assertRaisesRegex(ValueError, "Cross-version feature"):
            DemoStore(dataset)

    def test_public_bootstrap_rejects_private_data(self):
        dataset = self.store.bootstrap()["data"]
        dataset.pop("contract_version")
        dataset["evidence"][0]["source_kind"] = "private"
        with self.assertRaisesRegex(ValueError, "only accepts synthetic"):
            DemoStore(dataset)

    def test_review_original_link_and_counts_are_checked(self):
        dataset = self.store.bootstrap()["data"]
        dataset.pop("contract_version")
        dataset["reviews"][0]["model_id"] = "FRIDGE-B"
        with self.assertRaisesRegex(ValueError, "Review evidence model_id mismatch"):
            DemoStore(dataset)
        dataset = self.store.bootstrap()["data"]
        dataset.pop("contract_version")
        dataset["manifest"]["review_count"] = 999
        with self.assertRaisesRegex(ValueError, "Manifest review count mismatch"):
            DemoStore(dataset)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_api_is_same_core(self):
        self.assertEqual(self.client.get("/api/products").json(), DemoStore().list_products())
        response = self.client.get("/api/evidence/search", params={"q": "청소", "model_id": "FRIDGE-A"})
        self.assertEqual(response.json(), DemoStore().search_evidence("청소", "FRIDGE-A"))
        self.assertFalse(self.client.get("/health").json()["analysis_implemented"])

    def test_invalid_id_and_empty_result_http_semantics(self):
        invalid = self.client.get("/api/evidence/search", params={"q": "청소", "model_id": "WRONG"})
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_MODEL_ID")
        empty = self.client.get("/api/evidence/search", params={"q": "절대없는검색어"})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["data"]["items"], [])

    def test_future_analysis_is_explicitly_not_implemented(self):
        response = self.client.post("/api/planning-requests", json={"product_group": "fridge"})
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["error"]["code"], "NOT_IMPLEMENTED")

    def test_cors_only_local_web(self):
        allowed = self.client.get("/api/products", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:5173")
        other = self.client.get("/api/products", headers={"Origin": "https://untrusted.example"})
        self.assertNotIn("access-control-allow-origin", other.headers)


if __name__ == "__main__":
    unittest.main()
