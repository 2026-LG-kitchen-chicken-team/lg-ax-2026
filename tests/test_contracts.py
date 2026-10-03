"""Contract boundaries that protect the submitted scope and cross-client agreement."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import ValidationError

from lgax_contracts import load_schema, validate
from lgax_core import DemoStore


class ContractTests(unittest.TestCase):
    def test_demo_and_envelopes_validate(self):
        store = DemoStore()
        validate("BootstrapResponse", store.bootstrap())
        validate("ProductsResponse", store.list_products())
        validate("EvidenceSearchResponse", store.search_evidence("청소"))
        validate("EvidenceResponse", store.get_evidence("MANUAL-001"))

    def test_three_requests_share_contract(self):
        root = Path(__file__).resolve().parents[1]
        requests = json.loads((root / "data/demo/planning_requests.json").read_text("utf-8"))
        self.assertEqual({request["product_group"] for request in requests}, {"fridge", "dishwasher", "microwave"})
        for request in requests:
            validate("PlanningRequest", request)

    def test_run_declares_submitted_limits(self):
        schema = load_schema()["$defs"]["Run"]
        self.assertEqual(schema["properties"]["concepts"]["maxItems"], 3)
        self.assertEqual(schema["properties"]["revision_count"]["maximum"], 2)
        run = {"id": "RUN-1", "project_id": "PROJECT-1", "dataset_version": "0.1.0", "contract_version": "0.1.0",
               "status": "not_implemented", "stage": "plan", "revision_count": 0, "max_revisions": 2,
               "concepts": [], "unresolved": ["analysis not implemented"], "evidence_ids": [], "events": []}
        validate("Run", run)
        run["revision_count"] = 3
        with self.assertRaises(ValidationError):
            validate("Run", run)

    def test_no_evidence_without_locator(self):
        evidence = deepcopy(DemoStore().get_evidence("MANUAL-001")["data"]["evidence"])
        evidence["locator"] = {}
        with self.assertRaises(ValidationError):
            validate("Evidence", evidence)


if __name__ == "__main__":
    unittest.main()
