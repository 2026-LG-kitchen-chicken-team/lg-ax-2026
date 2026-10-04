"""Data boundary failures use the existing synthetic pack, with no new example originals."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.document_workspace import WorkspaceDocumentStore
from lgax_core.errors import DomainError
from lgax_core.review_csv import ReviewCsvRepository, serialize_existing_reviews
from lgax_core.workspace import WorkspaceStore
from lgax_core.workspace_planning import build_planning_input

ROOT = Path(__file__).resolve().parents[1]


class ConnectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.demo = json.loads((ROOT / "data/demo/dataset.json").read_text("utf-8"))
        self.docs = json.loads((ROOT / "data/document_datasets/lg-three-models-20261005.json").read_text("utf-8"))
        self.repo = ReviewCsvRepository(Path(self.directory.name) / "csv", self.demo)
        self.source = self.demo["reviews"][0]["source_id"]
        self.raw = serialize_existing_reviews(self.demo)

    def test_original_is_parsed_and_retained_across_repository_reopen(self):
        with self.assertRaises(DomainError):
            self.repo.store()
        record = self.repo.upload(self.source, self.raw)
        reopened = ReviewCsvRepository(self.repo.directory, self.demo)
        self.assertEqual(record, reopened.metadata(self.source))
        self.assertEqual(self.raw, reopened.original(self.source))
        self.assertEqual(reopened.store().bootstrap()["data"]["reviews"], self.demo["reviews"])

    def test_other_model_version_kind_and_row_are_rejected_before_persistence(self):
        r = self.demo["reviews"][0]
        for old, new in [(r["model_id"], "OTHER-MODEL"), (",synthetic,", ",public,"),
                         (",1.0,", ",2.0,"), (",2,REVIEW-EVIDENCE-001", ",9,REVIEW-EVIDENCE-001")]:
            with self.subTest(change=new):
                modified = self.raw.replace(old.encode(), new.encode(), 1)
                self.assertNotEqual(self.raw, modified)
                with self.assertRaises(DomainError) as error:
                    self.repo.upload(self.source, modified)
                self.assertEqual(error.exception.code, "PARSING_FAILED")
                self.assertFalse(list(self.repo.directory.glob("*.csv")))

    def test_duplicate_review_and_missing_review_fail_closed(self):
        lines = self.raw.splitlines(keepends=True)
        for modified in [self.raw + lines[1], b"".join(lines[:-1])]:
            with self.assertRaises(DomainError):
                self.repo.upload(self.source, modified)

    def test_changed_preserved_original_blocks_reads(self):
        record = self.repo.upload(self.source, self.raw)
        (self.repo.directory / (record["sha256"] + ".csv")).write_bytes(b"changed")
        with self.assertRaises(DomainError) as error:
            self.repo.store()
        self.assertEqual(error.exception.code, "SOURCE_CHANGED")

    def test_document_adapter_keeps_scope_and_detects_later_dataset_changes(self):
        store = WorkspaceDocumentStore(self.docs)
        workspace = WorkspaceStore(Path(self.directory.name) / "workspace.sqlite", evidence_store=store)
        payload = json.loads((ROOT / "data/research/P2-DATA-001-stage123-20261005/planning-inputs/T876MEE1H1.json").read_text("utf-8"))
        versions = {"T876MEE1H1": payload["product"]["document_version"]}
        self.assertEqual(build_planning_input(payload["request"], versions, store), payload)
        project = workspace.create_project("자료 범위 확인", payload["request"], "local-verifier", versions)
        self.assertEqual(store.bootstrap()["data"]["artifact_kind"], "document_dataset")
        self.assertEqual(store.bootstrap()["data"]["reviews"], [])
        changed = deepcopy(self.docs)
        changed["features"][0]["conditions"].append("changed document condition")
        workspace.evidence_store = WorkspaceDocumentStore(changed)
        with self.assertRaises(DomainError) as error:
            workspace.create_run(project["project"]["id"], payload["request"], "local-verifier", "api")
        self.assertEqual(error.exception.code, "DATASET_MISMATCH")


if __name__ == "__main__":
    unittest.main()
