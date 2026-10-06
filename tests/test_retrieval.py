import json
import math
import unicodedata
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.evidence_catalog import EvidenceCatalog
from lgax_core.retrieval import GroundedDemoStore, GroundedDocumentStore, bm25_search
from lgax_core.store import DemoStore

from tests.test_evidence_catalog import fixture


class RetrievalTests(unittest.TestCase):
    def test_korean_particle_matching_preserves_raw_text_and_locator(self):
        dataset = fixture(text=unicodedata.normalize("NFD", "청소가 번거롭다"))
        original = deepcopy(dataset)
        result = bm25_search(EvidenceCatalog([dataset]), "청소", model_id="SYNTH-M1", document_version="v1")
        self.assertEqual(result["search_method"], "bm25")
        self.assertGreater(result["items"][0]["score"], 0)
        self.assertEqual(result["items"][0]["evidence"], original["evidence"][0])
        self.assertEqual(dataset, original)

    def test_filter_before_statistics_scores_equal_scoped_only_corpus(self):
        one = fixture()
        other = fixture(model="OTHER-MODEL", suffix="2", text="청소 " * 1000)
        mixed = EvidenceCatalog([one, other])
        scoped = bm25_search(mixed, "청소", model_id="SYNTH-M1", document_version="v1")
        alone = bm25_search(EvidenceCatalog([one]), "청소", model_id="SYNTH-M1", document_version="v1")
        self.assertEqual(scoped, alone)
        self.assertEqual(scoped["corpus_size"], 1)

    def test_same_text_ties_stable_sort_detached_limit_and_total(self):
        catalog = EvidenceCatalog([fixture(suffix="3"), fixture(suffix="1", version="v2"),
                                   fixture(suffix="2", version="v3")])
        first = bm25_search(catalog, "청소", limit=2)
        self.assertEqual([m["evidence"]["id"] for m in first["items"]], ["E1", "E2"])
        self.assertEqual(first["total"], 3)
        first["items"][0]["evidence"]["text"] = "changed"
        self.assertEqual(bm25_search(catalog, "청소", limit=2)["items"][0]["evidence"]["text"], "청소가 간편하다")

    def test_unrelated_no_evidence_and_empty_invalid(self):
        catalog = EvidenceCatalog([fixture()])
        self.assertEqual(bm25_search(catalog, "Unrelated9876")["items"], [])
        self.assertEqual(bm25_search(EvidenceCatalog([]), "청소")["total"], 0)
        for q in ("", "  ", "!!!", "_", "x" * 501):
            with self.assertRaises(DomainError):
                bm25_search(catalog, q)

    def test_bad_scope_limits_and_settings(self):
        catalog = EvidenceCatalog([fixture()])
        for changes in ({"limit": True}, {"limit": 0}, {"k1": math.nan}, {"b": 2}, {"b": True},
                        {"document_version": "v2", "model_id": "SYNTH-M1"}, {"model_id": "OTHER"}):
            with self.assertRaises(DomainError):
                bm25_search(catalog, "청소", **changes)

    def test_public_response_stays_literal_and_internal_bm25_is_explicit(self):
        store = GroundedDocumentStore(fixture())
        literal = store.search_evidence("청소", "SYNTH-M1", "v1")
        validate("EvidenceSearchResponse", literal)
        self.assertEqual(literal["data"]["search_method"], "literal_token_count")
        self.assertEqual(store.search_ranked_evidence("청소")["search_method"], "bm25")

    def test_frozen_demo_multiple_document_versions_preserved(self):
        dataset = json.loads((Path(__file__).resolve().parents[1] / "data/demo/dataset.json").read_bytes())
        original, grounded = DemoStore(dataset), GroundedDemoStore(dataset)
        self.assertEqual(original.bootstrap(), grounded.bootstrap())
        for version in ("1.0", "2.0"):
            self.assertEqual(original.search_evidence("선반", "FRIDGE-A", version),
                             grounded.search_evidence("선반", "FRIDGE-A", version))
        self.assertEqual({match["evidence"]["document_version"] for match in
            grounded.search_ranked_evidence("트레이", model_id="FRIDGE-A", document_version="2.0")["items"]}, {"2.0"})
