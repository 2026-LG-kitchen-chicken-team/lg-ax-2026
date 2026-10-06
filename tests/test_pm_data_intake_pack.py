"""Fresh PDF registration and consumers of the PM's immutable public packs."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lgax_core.document_store import DocumentStore
from lgax_core.documents import DocumentRepository
from lgax_core.errors import DomainError
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data/research/PM-DATA-intake-20261006/generated"


def read(name):
    return json.loads((PACK / name).read_bytes())


class PMDataIntakePackTests(unittest.TestCase):
    def test_fresh_pdf_registration_reproduces_the_pack(self):
        plan = read("plan.json")
        metadata = json.loads((ROOT / "evals/pm-data-intake/20261006/parser-wheel.json").read_bytes())
        wheel = ROOT / metadata["path"]
        self.assertEqual(hashlib.sha256(wheel.read_bytes()).hexdigest(), metadata["sha256"])
        pythonpath = str(wheel) + os.pathsep + os.environ.get("PYTHONPATH", "")
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"PYTHONPATH": pythonpath}):
            repo = DocumentRepository(Path(temporary), plan, sys.executable)
            for doc in plan["documents"]:
                original = ROOT / "data/sources/lg-manuals-20261005" / (
                    doc["product"]["model_id"] + "-" + doc["sha256"][:12] + ".pdf")
                record = repo.upload(doc["document_id"], original.read_bytes())
                self.assertFalse(record["ocr_used"])
                self.assertEqual(record["sha256"], doc["sha256"])
                self.assertTrue(repo.upload(doc["document_id"], original.read_bytes())["idempotent"])
            actual = repo.store().bootstrap()["data"]
            actual.pop("contract_version")
            self.assertEqual(actual, read("dataset.json"))

    def test_six_previously_missing_evidence_records_are_registered(self):
        proposal = json.loads((ROOT / "evals/data003-independent/20261005-01a10834/missing-evidence-proposal.json").read_bytes())
        store = DocumentStore(read("dataset.json"))
        origins = {item["evidence_id"]: item for item in read("origins.json")}
        self.assertEqual(len(proposal["selections"]), 6)
        for proposed in proposal["selections"]:
            actual = store.get_evidence(proposed["evidence_id"])["data"]["evidence"]
            self.assertEqual(actual["text"], proposed["excerpt"])
            self.assertEqual(actual["document_version"], proposed["document_version"])
            self.assertEqual(actual["source_id"], proposed["document_id"])
            self.assertEqual(actual["model_id"], proposed["model_id"])
            self.assertEqual(origins[actual["id"]]["start_char"], proposed["start_char"])
            self.assertEqual(origins[actual["id"]]["end_char"], proposed["end_char"])
            self.assertEqual(origins[actual["id"]]["text_sha256"], proposed["text_sha256"])

    def test_three_normal_changed_inputs_preserve_scope_and_originals(self):
        for model in read("pack-summary.json")["models"]:
            scoped = read(model + "/dataset.json")
            store = DocumentStore(scoped)
            normal, changed = read(model + "/normal.input.json"), read(model + "/changed.input.json")
            version = {model: scoped["products"][0]["document_version"]}
            for payload in (normal, changed):
                self.assertEqual(build_planning_input(payload["request"], version, store), payload)
                self.assertTrue(payload["sources"])
                self.assertTrue(all(e["model_id"] == model and e["source_kind"] == "public"
                                    for e in payload["sources"]))
            self.assertEqual(normal["sources"], changed["sources"])
            self.assertEqual(normal["features"], changed["features"])
            self.assertNotEqual(normal["request"]["exclusions"], changed["request"]["exclusions"])
            returned = store.get_evidence(normal["sources"][0]["id"])
            returned["data"]["evidence"]["text"] = "mutated-return-value"
            self.assertEqual(build_planning_input(normal["request"], version, store), normal)

    def test_corrupted_original_refused_before_registration(self):
        plan = read("plan.json")
        doc = plan["documents"][0]
        original = ROOT / "data/sources/lg-manuals-20261005" / (
            doc["product"]["model_id"] + "-" + doc["sha256"][:12] + ".pdf")
        with tempfile.TemporaryDirectory() as temporary:
            repo = DocumentRepository(Path(temporary), plan, sys.executable)
            with self.assertRaises(DomainError) as raised:
                repo.upload(doc["document_id"], original.read_bytes() + b"changed")
            self.assertEqual(raised.exception.code, "SOURCE_MISMATCH")

    def test_scoped_search_and_absent_customer_dates_are_honest(self):
        dataset = read("dataset.json")
        store = DocumentStore(dataset)
        for product in dataset["products"]:
            model, version = product["model_id"], product["document_version"]
            result = store.search_evidence("제품", model, version)
            self.assertEqual(result["data"]["search_method"], "literal_token_count")
            self.assertTrue(all(e["model_id"] == model and e["document_version"] == version
                                for e in result["data"]["items"]))
            self.assertEqual(store.search_evidence("UNMATCHED-CASE-20261006", model, version)["data"]["items"], [])
        coverage = read("review-field-coverage.json")
        self.assertEqual(coverage["original_rows"], 36)
        self.assertEqual(coverage["imported_scoped_synthetic_rows"], 36)
        self.assertEqual(coverage["source_kind_counts"], {"synthetic": 36})
        self.assertEqual(coverage["review_timestamp_present"], 0)
        self.assertEqual(coverage["monthly_or_seasonal_eligible_rows"], 0)
        self.assertEqual(coverage["real_customer_reviews"], 0)
        self.assertFalse(coverage["dates_fabricated"])
        self.assertEqual(dataset["reviews"], [])
        original = (ROOT / coverage["original_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), coverage["original_sha256"])


if __name__ == "__main__":
    unittest.main()
