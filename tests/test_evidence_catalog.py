import hashlib
import unittest
from copy import deepcopy

from lgax_core.errors import DomainError
from lgax_core.evidence_catalog import EvidenceCatalog


def fixture(model="SYNTH-M1", version="v1", suffix="1", text="청소가 간편하다"):
    product = {"model_id": model, "name": "합성 냉장고", "product_group": "fridge",
               "document_version": version, "source_kind": "synthetic"}
    evidence = {"id": "E" + suffix, "model_id": model, "document_version": version,
                "source_kind": "synthetic", "source_type": "review", "source_id": "CSV" + suffix,
                "locator": {"row": 2}, "text": text, "feature_ids": []}
    review = {k: deepcopy(evidence[k]) for k in ("model_id", "document_version", "source_kind",
                                               "source_id", "locator", "text")}
    review.update(id="R" + suffix, evidence_id=evidence["id"])
    return {"artifact_kind": "document_dataset", "dataset_version": "pack-" + suffix,
            "products": [product], "reviews": [review], "features": [], "evidence": [evidence]}


class EvidenceCatalogTests(unittest.TestCase):
    def test_new_registration_detached_scopes_and_related_review(self):
        one, two = fixture(), fixture(version="v2", suffix="2")
        before = deepcopy(one)
        catalog = EvidenceCatalog([one, two])
        self.assertEqual(one, before)
        one["evidence"][0]["text"] = "changed"
        rows = catalog.select(model_id="SYNTH-M1", document_version="v2", dataset_version="pack-2")
        self.assertEqual([e["id"] for e in rows], ["E2"])
        rows[0]["text"] = "changed"
        self.assertEqual(catalog.get_evidence("E2")["locator"], {"row": 2})
        self.assertEqual(catalog.related(collection="reviews", document_version="v1", model_id="SYNTH-M1")[0]["id"], "R1")

    def test_same_id_different_pack_or_content_is_rejected(self):
        for datasets in ([fixture(), fixture(version="v2", suffix="1")],
                         [{**fixture(), "evidence": fixture()["evidence"] * 2}]):
            with self.assertRaises(DomainError) as caught:
                EvidenceCatalog(datasets)
            self.assertEqual(caught.exception.code, "DUPLICATE_ID")

    def test_wrong_model_version_dataset_and_swapped_id(self):
        catalog = EvidenceCatalog([fixture(), fixture(model="SYNTH-M2", suffix="2")])
        for scope, code in [({"model_id": "OTHER"}, "INVALID_MODEL_ID"),
                            ({"document_version": "v1"}, "INVALID_ARGUMENT"),
                            ({"model_id": "SYNTH-M1", "document_version": "v9"}, "INVALID_DOCUMENT_VERSION"),
                            ({"dataset_version": "OTHER"}, "INVALID_DATASET_VERSION")]:
            with self.assertRaises(DomainError) as caught:
                catalog.select(**scope)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(DomainError) as caught:
            catalog.get_evidence("E1", model_id="SYNTH-M2")
        self.assertEqual(caught.exception.code, "SOURCE_MISMATCH")

    def test_missing_retired_and_cross_scope_source_are_rejected(self):
        dataset = fixture()
        source = {"document_id": "CSV1", "product": dataset["products"][0],
                  "document_version": "v1", "source_kind": "synthetic", "sha256": "a" * 64}
        for sources, code in [([], "UNKNOWN_SOURCE"), ([{**source, "status": "retired"}], "SOURCE_RETIRED"),
                              ([{**source, "document_version": "v2"}], "UNKNOWN_SOURCE")]:
            with self.assertRaises(DomainError) as caught:
                EvidenceCatalog([dataset], sources=sources)
            self.assertEqual(caught.exception.code, code)

    def test_live_original_deletion_and_change_not_hidden_by_cache(self):
        dataset = fixture()
        raw = {"CSV1": "한글 원문".encode()}
        source = {"document_id": "CSV1", "product": dataset["products"][0], "document_version": "v1",
                  "source_kind": "synthetic", "sha256": hashlib.sha256(raw["CSV1"]).hexdigest()}
        catalog = EvidenceCatalog([dataset], sources=[source], source_reader=raw.get)
        self.assertEqual(len(catalog.select()), 1)
        raw["CSV1"] += b"changed"
        with self.assertRaises(DomainError) as caught:
            catalog.get_evidence("E1")
        self.assertEqual(caught.exception.code, "SOURCE_CHANGED")
        del raw["CSV1"]
        with self.assertRaises(DomainError) as caught:
            catalog.select()
        self.assertEqual(caught.exception.code, "SOURCE_MISSING")

    def test_review_and_feature_reciprocal_scope_failures(self):
        dataset = fixture()
        dataset["reviews"][0]["text"] += "변경"
        with self.assertRaises(DomainError):
            EvidenceCatalog([dataset])
        dataset = fixture()
        dataset["evidence"][0]["feature_ids"] = ["MISSING-FEATURE"]
        with self.assertRaises(DomainError):
            EvidenceCatalog([dataset])

    def test_cross_pack_review_id_and_source_hash_ambiguity_rejected(self):
        one, two = fixture(), fixture(version="v2", suffix="2")
        two["reviews"][0]["id"] = one["reviews"][0]["id"]
        with self.assertRaises(DomainError) as caught:
            EvidenceCatalog([one, two])
        self.assertEqual(caught.exception.code, "DUPLICATE_ID")
        source = {"document_id": "CSV1", "product": one["products"][0], "document_version": "v1",
                  "source_kind": "synthetic", "sha256": "a" * 64}
        with self.assertRaises(DomainError) as caught:
            EvidenceCatalog([one], sources=[source, {**source, "document_version": "v2", "sha256": "b" * 64}])
        self.assertEqual(caught.exception.code, "SOURCE_MISMATCH")
