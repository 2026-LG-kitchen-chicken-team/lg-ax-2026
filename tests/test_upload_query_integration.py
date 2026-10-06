"""New CSV and parsed-PDF fixtures through real repository/HTTP entrypoints."""
import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unicodedata
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from lgax_core.document_workspace import WorkspaceDocumentStore
from lgax_core.documents import DocumentRepository
from lgax_core.documents_server import create_app
from lgax_core.errors import DomainError
from lgax_core.review_csv import FIELDS, ReviewDocumentRepository

from tests.test_evidence_catalog import fixture

ROOT = Path(__file__).resolve().parents[1]


class UploadQueryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.product = fixture()["products"][0]
        self.raw_text = unicodedata.normalize("NFD", "청소가 번거롭다") + '\n"한글, 원문"'
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerow({"id": "NEW-R", "model_id": "SYNTH-M1", "text": self.raw_text,
                         "source_kind": "synthetic", "document_version": "v1", "source_id": "NEW-CSV",
                         "row": 2, "evidence_id": "NEW-E"})
        self.raw = b"\xef\xbb\xbf" + stream.getvalue().encode()
        self.source = {"document_id": "NEW-CSV", "product": self.product, "document_version": "v1",
                       "source_kind": "synthetic", "sha256": hashlib.sha256(self.raw).hexdigest()}

    def repository(self):
        return ReviewDocumentRepository(self.directory, products=[self.product], sources=[self.source],
                                        dataset_version="new-development-csv-v1")

    def test_csv_upload_lookup_version_search_original_and_restart(self):
        repo = self.repository()
        with TestClient(create_app(repo, "t" * 40, original_media_type="text/csv")) as client:
            headers = {"Authorization": "Bearer " + "t" * 40}
            response = client.post("/api/documents/NEW-CSV", content=self.raw, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"]["origins"][0]["end_row"], 3)
            self.assertEqual(client.get("/api/documents/NEW-CSV/original", headers=headers).content, self.raw)
            evidence = client.get("/api/evidence/NEW-E", headers=headers).json()["data"]["evidence"]
            self.assertEqual(evidence["text"], self.raw_text)
            response = client.get("/api/evidence/search", params={"q": "한글", "model_id": "SYNTH-M1",
                                 "document_version": "v1"}, headers=headers)
            self.assertEqual(response.json()["data"]["items"][0]["id"], "NEW-E")
        reopened = self.repository()
        self.assertEqual(reopened.original("NEW-CSV"), self.raw)
        ranked = reopened.store().search_ranked_evidence("청소", model_id="SYNTH-M1", document_version="v1")
        self.assertEqual(ranked["items"][0]["evidence"]["text"], self.raw_text)
        self.assertTrue(reopened.upload("NEW-CSV", self.raw)["idempotent"])

    def test_changed_id_file_model_version_and_frozen_scope_rejected(self):
        repo = self.repository()
        repo.upload("NEW-CSV", self.raw)
        for did, raw in (("OTHER-CSV", self.raw), ("NEW-CSV", self.raw + b"changed")):
            with self.assertRaises(DomainError):
                repo.upload(did, raw)
        for scope in ({"model_id": "OTHER-MODEL"}, {"model_id": "SYNTH-M1", "document_version": "v2"}):
            with self.assertRaises(DomainError):
                repo.store().search_ranked_evidence("청소", **scope)
        changed_product = {**self.product, "document_version": "v2"}
        with self.assertRaises(ValueError):
            ReviewDocumentRepository(self.directory, products=[changed_product],
                sources=[{**self.source, "product": changed_product, "document_version": "v2"}], dataset_version="v2")

    def test_missing_and_tampered_original_rejected_on_query(self):
        repo = self.repository()
        record = repo.upload("NEW-CSV", self.raw)
        cached = repo.store()
        path = self.directory / (record["sha256"] + ".csv")
        for raw in (self.raw + b"changed", None):
            if raw is None:
                path.unlink()
            else:
                path.write_bytes(raw)
            with self.assertRaises(DomainError) as caught:
                repo.store()
            self.assertEqual(caught.exception.code, "SOURCE_CHANGED")
            with self.assertRaises(DomainError):
                cached.get_evidence("NEW-E")

    def test_second_document_cannot_reuse_review_or_evidence_id(self):
        other_raw = self.raw.replace(b"NEW-CSV", b"NEXT-CSV")
        other_source = {**self.source, "document_id": "NEXT-CSV", "sha256": hashlib.sha256(other_raw).hexdigest()}
        repo = ReviewDocumentRepository(self.directory, products=[self.product],
            sources=[self.source, other_source], dataset_version="two-csv-fixture")
        repo.upload("NEW-CSV", self.raw)
        with self.assertRaises(DomainError) as caught:
            repo.upload("NEXT-CSV", other_raw)
        self.assertEqual(caught.exception.code, "DUPLICATE_ID")

    def test_concurrent_duplicate_upload_keeps_one_immutable_registration(self):
        repo = self.repository()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: repo.upload("NEW-CSV", self.raw), range(2)))
        self.assertEqual(sum(result["idempotent"] for result in results), 1)
        self.assertEqual(repo.original("NEW-CSV"), self.raw)
        self.assertEqual(len(repo.store().catalog.select()), 1)

    def test_workspace_injection_keeps_registered_source_reader_after_creation(self):
        repo = self.repository()
        repo.upload("NEW-CSV", self.raw)
        store = WorkspaceDocumentStore.from_repository(repo)
        self.assertEqual(store.bootstrap()["data"]["manifest"]["version"], "new-development-csv-v1")
        self.assertEqual(store.get_evidence("NEW-E")["data"]["evidence"]["text"], self.raw_text)
        record = repo.metadata("NEW-CSV")
        (self.directory / (record["sha256"] + ".csv")).unlink()
        with self.assertRaises(DomainError):
            store.get_evidence("NEW-E")
        with self.assertRaises(DomainError):
            store.bootstrap()

    def test_pdf_new_selection_source_range_catalog_and_query(self):
        plan = json.loads((ROOT / "data/document_plans/lg-three-models-20261005.json").read_bytes())
        spec = deepcopy(plan["documents"][0])
        raw = b"%PDF development fixture"
        spec["sha256"] = hashlib.sha256(raw).hexdigest()
        spec["selections"] = [spec["selections"][0]]
        spec["selections"][0].update(page=1, excerpt="합성 청소 안내", feature_ids=[])
        spec["features"] = []
        plan["documents"] = [spec]
        repo = DocumentRepository(self.directory, plan, "python")
        with patch.object(repo, "_parse", return_value={"pages": ["제목\n합성 청소 안내\n끝"],
                          "parser": "fixture", "parser_version": "1"}):
            repo.upload(spec["document_id"], raw)
        store = repo.store()
        self.assertEqual(store.search_ranked_evidence("청소")["items"][0]["evidence"]["locator"]["page"], 1)
        self.assertEqual(store.catalog.get_evidence(spec["selections"][0]["evidence_id"])["text"], "합성 청소 안내")
        reopened = DocumentRepository(self.directory, plan, "python")
        self.assertEqual(reopened.store().search_evidence("청소"), store.search_evidence("청소"))
        with closing(sqlite3.connect(repo.db)) as db, db:
            record = json.loads(db.execute("SELECT record FROM documents").fetchone()[0])
            record["dataset"]["evidence"][0]["text"] += "다른 원문"
            db.execute("UPDATE documents SET record=?", (json.dumps(record),))
        with self.assertRaises(DomainError) as caught:
            reopened.store()
        self.assertEqual(caught.exception.code, "SOURCE_MISMATCH")
