"""Canonical entities for original documents, separate from the synthetic demo manifest."""

from copy import deepcopy

from lgax_contracts import CONTRACT_VERSION, validate

from .store import EvidenceReader


class DocumentStore(EvidenceReader):
    """Read only document dataset. Never relabel public sources as synthetic reviews."""

    def __init__(self, dataset: dict):
        if dataset.get("artifact_kind") != "document_dataset":
            raise ValueError("Expected explicit document_dataset")
        self._dataset = deepcopy(dataset)
        for collection, definition in [("products", "Product"), ("reviews", "Review"),
                                       ("features", "Feature"), ("evidence", "Evidence")]:
            if not isinstance(dataset.get(collection), list):
                raise TypeError(f"Missing {collection}")
            for item in dataset[collection]:
                validate(definition, item)
            key = "model_id" if collection == "products" else "id"
            if len({item[key] for item in dataset[collection]}) != len(dataset[collection]):
                raise ValueError(f"Duplicate {collection} ID")
        self._products = {p["model_id"]: p for p in dataset["products"]}
        self._evidence = {e["id"]: e for e in dataset["evidence"]}
        self._features = {f["id"]: f for f in dataset["features"]}
        for evidence in self._evidence.values():
            if evidence["model_id"] not in self._products:
                raise ValueError("Unknown evidence model")
            product = self._products[evidence["model_id"]]
            if evidence["document_version"] != product["document_version"]:
                raise ValueError("Evidence/product version mismatch")
            if evidence["source_kind"] != product["source_kind"]:
                raise ValueError("Evidence/product source kind mismatch")
            for fid in evidence["feature_ids"]:
                feature = self._features.get(fid)
                if not feature or self._scope(feature) != self._scope(evidence):
                    raise ValueError("Cross-model/version or missing feature")
                if evidence["id"] not in feature["evidence_ids"]:
                    raise ValueError("Feature/evidence link must be reciprocal")
        for feature in self._features.values():
            if feature["model_id"] not in self._products:
                raise ValueError("Unknown feature model")
            if feature["document_version"] != self._products[feature["model_id"]]["document_version"]:
                raise ValueError("Feature/product version mismatch")
            for eid in feature["evidence_ids"]:
                evidence = self._evidence.get(eid)
                if not evidence or self._scope(feature) != self._scope(evidence):
                    raise ValueError("Cross-model/version or missing evidence")
                if feature["id"] not in evidence["feature_ids"]:
                    raise ValueError("Feature/evidence link must be reciprocal")
        for review in dataset["reviews"]:
            evidence = self._evidence.get(review["evidence_id"])
            if not evidence or evidence["source_type"] != "review":
                raise ValueError("Missing review original")
            if any(review[k] != evidence[k] for k in
                   ("model_id", "document_version", "source_kind", "source_id", "locator", "text")):
                raise ValueError("Review original mismatch")

    @staticmethod
    def _scope(item):
        return item["model_id"], item["document_version"]

    def bootstrap(self):
        # This container is NOT a DemoDataset/BootstrapResponse. Its four entity types
        # use the canonical schema; build_planning_input consumes those entities.
        return {"ok": True, "data": {**deepcopy(self._dataset), "contract_version": CONTRACT_VERSION}}
