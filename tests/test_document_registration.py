"""Contract and failure checks; PDF transport is also exercised in the private real HTTP run."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from lgax_core.document_store import DocumentStore
from lgax_core.documents import DocumentRepository, digest
from lgax_core.documents_server import create_app
from lgax_core.errors import DomainError
from lgax_core.store import DemoStore
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[1]


class DocumentRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.plan = json.loads((ROOT / "data/document_plans/lg-three-models-20261005.json").read_text(encoding="utf-8"))
        self.plan["documents"] = self.plan["documents"][:1]
        self.spec = self.plan["documents"][0]
        self.raw = b"%PDF-fixture-transport-not-a-real-PDF"
        self.spec["sha256"] = digest(self.raw)
        pages = ["" for _ in range(40)]
        for selection in self.spec["selections"]:
            pages[selection["page"] - 1] += selection["excerpt"] + "\n"
        self.parsed = {"pages": pages, "parser": "fixture", "parser_version": "0", "ocr_used": False}
        self.repo = DocumentRepository(Path(self.temp.name), self.plan, "not-invoked")
        self.token = "unit-test-token-" * 3
        self.client = TestClient(create_app(self.repo, self.token))
        self.headers = {"Authorization": "Bearer " + self.token}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self):
        with patch.object(self.repo, "_parse", return_value=self.parsed):
            return self.repo.upload(self.spec["document_id"], self.raw)

    def test_original_registration_persists_and_repeat_is_idempotent(self):
        first = self.upload()
        reopened = DocumentRepository(Path(self.temp.name), self.plan, "not-invoked")
        second = reopened.upload(self.spec["document_id"], self.raw)
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(reopened.original(self.spec["document_id"]), self.raw)
        self.assertEqual(first["dataset"], second["dataset"])

    def test_wrong_document_bytes_cannot_be_registered(self):
        response = self.client.post("/api/documents/" + self.spec["document_id"],
                                    content=b"%PDF-other-model", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "SOURCE_MISMATCH")
        self.assertEqual(self.repo.store().bootstrap()["data"]["products"], [])

    def test_auth_and_browser_origin_are_checked_before_upload(self):
        path = "/api/documents/" + self.spec["document_id"]
        self.assertEqual(self.client.post(path, content=self.raw).status_code, 401)
        self.assertEqual(self.client.post(path, content=self.raw,
                         headers={**self.headers, "Origin": "https://unrelated.example"}).status_code, 403)

    def test_missing_and_ambiguous_excerpt_roll_back_registration(self):
        selection = self.spec["selections"][0]
        for content in ["", selection["excerpt"] + "\n" + selection["excerpt"]]:
            parsed = deepcopy(self.parsed)
            parsed["pages"][selection["page"] - 1] = content
            with (patch.object(self.repo, "_parse", return_value=parsed),
                  self.assertRaisesRegex(DomainError, "유일하게")):
                self.repo.upload(self.spec["document_id"], self.raw)
        self.assertEqual(self.repo.store().bootstrap()["data"]["evidence"], [])

    def test_public_source_is_preserved_and_demo_policy_is_unchanged(self):
        record = self.upload()
        store = self.repo.store()
        eid = record["dataset"]["evidence"][0]["id"]
        evidence = store.get_evidence(eid)["data"]["evidence"]
        self.assertEqual(evidence["source_kind"], "public")
        self.assertEqual(evidence["source_id"], self.spec["document_id"])
        self.assertEqual(store.bootstrap()["data"]["reviews"], [])
        demo = DemoStore().bootstrap()["data"]
        demo.pop("contract_version")
        demo["products"][0]["source_kind"] = "public"
        with self.assertRaisesRegex(ValueError, "synthetic"):
            DemoStore(demo)

    def test_cross_model_version_and_nonreciprocal_link_rejected(self):
        dataset = self.upload()["dataset"]
        for field, value in [("model_id", "OTHER"), ("document_version", "other-version")]:
            bad = deepcopy(dataset)
            bad["features"][0][field] = value
            with self.assertRaises(ValueError):
                DocumentStore(bad)
        bad = deepcopy(dataset)
        bad["evidence"][0]["feature_ids"] = []
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            DocumentStore(bad)

    def test_build_scope_includes_all_originals_and_rejects_wrong_version(self):
        self.upload()
        product = self.spec["product"]
        request = {"product_group": product["product_group"], "target_customer": "검증용 사용 상황",
                   "use_situation": "선반 분리", "improvement_task": "근거 확인", "exclusions": [],
                   "model_ids": [product["model_id"]], "dataset_version": self.plan["dataset_version"]}
        payload = build_planning_input(request, {product["model_id"]: product["document_version"]}, self.repo.store())
        self.assertEqual(len(payload["sources"]), len(self.spec["selections"]))
        self.assertEqual(len(payload["features"]), len(self.spec["features"]))
        self.assertTrue(all(s["source_kind"] == "public" for s in payload["sources"]))
        with self.assertRaisesRegex(DomainError, "문서 버전"):
            build_planning_input(request, {product["model_id"]: "other-version"}, self.repo.store())

    def test_scope_change_and_missing_extractor_are_explicit_failures(self):
        changed = deepcopy(self.plan)
        changed["dataset_version"] = "different-curation"
        with self.assertRaisesRegex(ValueError, "separate registration"):
            DocumentRepository(Path(self.temp.name), changed, "not-invoked")
        with self.assertRaisesRegex(DomainError, "PDF 추출 환경"):
            self.repo.upload(self.spec["document_id"], self.raw)
        self.assertEqual(self.repo.store().bootstrap()["data"]["products"], [])


if __name__ == "__main__":
    unittest.main()
