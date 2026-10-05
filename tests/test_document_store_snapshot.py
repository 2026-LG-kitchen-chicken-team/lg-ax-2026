"""Registered document entities must be independent of caller-owned values."""

import hashlib
import json
import re
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.document_store import DocumentStore

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class DocumentStoreSnapshotTests(unittest.TestCase):
    def dataset(self, kind):
        relative = ("data/document_datasets/lg-three-models-20261005.json" if kind == "public"
                    else "data/demo/dataset.json")
        value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        # Existing canonical entities remain unchanged; only choose this reader container.
        value["artifact_kind"] = "document_dataset"
        value.setdefault("dataset_version", "snapshot-test-container")
        if kind == "synthetic":
            versions = {p["model_id"]: p["document_version"] for p in value["products"]}
            # The demo review CSV has a different revision from its product manuals.
            # Choose unchanged manual entities for this document-version reader.
            value["evidence"] = [e for e in value["evidence"]
                                 if e["source_type"] != "review"
                                 and e["document_version"] == versions[e["model_id"]]]
            ids = {e["id"] for e in value["evidence"]}
            value["features"] = [f for f in value["features"] if set(f["evidence_ids"]) <= ids]
            value["reviews"] = []
        return value

    def observed(self, store, evidence):
        query = re.findall(r"\w+", evidence["text"])[0]
        return {
            "products": store.list_products(),
            "evidence": store.get_evidence(evidence["id"]),
            "search": store.search_evidence(query, evidence["model_id"], evidence["document_version"]),
            "bootstrap": store.bootstrap(),
            "feature_index": deepcopy(store._features),
        }

    def assert_mutation_isolated(self, kind, mutation):
        source = self.dataset(kind)
        evidence = deepcopy(source["evidence"][0])
        store = DocumentStore(source)
        expected = fingerprint(self.observed(store, evidence))
        mutation(source)
        self.assertEqual(fingerprint(self.observed(store, evidence)), expected,
                         "registered snapshot changed after caller input mutation")

    def test_original_product_fields_are_frozen(self):
        for kind in ("public", "synthetic"):
            with self.subTest(kind=kind):
                self.assert_mutation_isolated(kind, lambda d: d["products"][0].update(name="external-change"))

    def test_original_evidence_fields_and_links_are_frozen(self):
        mutations = {
            "text": lambda d: d["evidence"][0].update(text="external-change"),
            "version": lambda d: d["evidence"][0].update(document_version="external-version"),
            "model": lambda d: d["evidence"][0].update(model_id=d["products"][1]["model_id"]),
            "feature_ids": lambda d: d["evidence"][0]["feature_ids"].clear(),
            "locator": lambda d: d["evidence"][0]["locator"].update(section="external-section"),
        }
        for kind in ("public", "synthetic"):
            for label, mutation in mutations.items():
                with self.subTest(kind=kind, mutation=label):
                    self.assert_mutation_isolated(kind, mutation)

    def test_original_feature_fields_and_arrays_are_frozen(self):
        mutations = {
            "description": lambda d: d["features"][0].update(description="external-change"),
            "conditions": lambda d: d["features"][0]["conditions"].append("external-condition"),
            "evidence_ids": lambda d: d["features"][0]["evidence_ids"].clear(),
        }
        for kind in ("public", "synthetic"):
            for label, mutation in mutations.items():
                with self.subTest(kind=kind, mutation=label):
                    self.assert_mutation_isolated(kind, mutation)

    def test_caller_replacing_or_clearing_arrays_keeps_snapshot(self):
        for kind in ("public", "synthetic"):
            for collection in ("products", "features", "evidence", "reviews"):
                for replace in (False, True):
                    def mutate(d, name=collection, replace=replace):
                        if replace:
                            d[name] = []
                        else:
                            d[name].clear()
                    with self.subTest(kind=kind, collection=collection, replace=replace):
                        self.assert_mutation_isolated(kind, mutate)

    def test_nested_public_return_values_are_independent(self):
        for kind in ("public", "synthetic"):
            source = self.dataset(kind)
            store = DocumentStore(source)
            evidence = deepcopy(source["evidence"][0])
            expected = fingerprint(self.observed(store, evidence))
            outputs = self.observed(store, evidence)
            outputs["products"]["data"]["products"][0]["name"] = "external-change"
            outputs["evidence"]["data"]["evidence"]["feature_ids"].clear()
            outputs["search"]["data"]["items"][0]["locator"]["section"] = "external-section"
            outputs["bootstrap"]["data"]["features"][0]["conditions"].append("external-condition")
            with self.subTest(kind=kind):
                self.assertEqual(fingerprint(self.observed(store, evidence)), expected)

    def test_invalid_model_version_kind_and_links_still_rejected(self):
        mutations = {
            "unknown_model": lambda d: d["evidence"][0].update(model_id="unknown-model"),
            "evidence_version": lambda d: d["evidence"][0].update(document_version="wrong-version"),
            "source_kind": lambda d: d["evidence"][0].update(
                source_kind="synthetic" if d["products"][0]["source_kind"] == "public" else "public"),
            "missing_feature": lambda d: d["evidence"][0].update(feature_ids=["missing-feature"]),
            "feature_version": lambda d: d["features"][0].update(document_version="wrong-version"),
            "feature_link": lambda d: d["features"][0].update(evidence_ids=["unlinked-evidence"]),
            "duplicate_product": lambda d: d["products"].append(deepcopy(d["products"][0])),
        }
        for kind in ("public", "synthetic"):
            for label, mutate in mutations.items():
                source = self.dataset(kind)
                mutate(source)
                with self.subTest(kind=kind, invalid=label), self.assertRaises(ValueError):
                    DocumentStore(source)

    def test_review_original_link_is_preserved(self):
        original = json.loads((ROOT / "data/demo/dataset.json").read_text(encoding="utf-8"))
        review = original["reviews"][0]
        evidence = next(e for e in original["evidence"] if e["id"] == review["evidence_id"])
        product = next(p for p in original["products"] if p["model_id"] == review["model_id"])
        product["document_version"] = review["document_version"]
        source = {"artifact_kind": "document_dataset", "dataset_version": "review-scope-test",
                  "products": [product], "reviews": [review], "features": [], "evidence": [evidence]}
        DocumentStore(source)
        source["reviews"][0]["text"] = "external-change"
        with self.assertRaisesRegex(ValueError, "Review original mismatch"):
            DocumentStore(source)


if __name__ == "__main__":
    unittest.main()
