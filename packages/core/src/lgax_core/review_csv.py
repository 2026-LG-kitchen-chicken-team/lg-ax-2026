"""Bounded upload of the existing synthetic reviews, never customer-review collection."""

import csv
import io
import json
import sqlite3
from contextlib import closing
from copy import deepcopy
from pathlib import Path

from .documents import digest
from .errors import DomainError
from .store import DemoStore

FIELDS = ("id", "model_id", "text", "source_kind", "document_version", "source_id", "row", "evidence_id")
MAX_CSV_BYTES = 1024 * 1024


def serialize_existing_reviews(dataset: dict) -> bytes:
    """Derived transport only; this does not recover a historical CSV original."""
    DemoStore(dataset)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for review in dataset["reviews"]:
        row = {k: v for k, v in review.items() if k != "locator"}
        row["row"] = review["locator"]["row"]
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


class ReviewCsvRepository:
    """Trusted server-side demo scope; uploaded rows must equal its existing reviews."""

    def __init__(self, directory: Path, dataset: dict):
        DemoStore(dataset)
        if len(dataset["reviews"]) != 36:
            raise ValueError("This transport verifies the existing 36-review scope")
        self.dataset = deepcopy(dataset)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "reviews.sqlite"
        self.source_id = dataset["reviews"][0]["source_id"]
        if any(r["source_id"] != self.source_id for r in dataset["reviews"]):
            raise ValueError("One source ID required")
        sha = digest(json.dumps(dataset, sort_keys=True, ensure_ascii=False).encode())
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS scope (id INTEGER PRIMARY KEY, sha TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO scope VALUES (1,?)", (sha,))
            if db.execute("SELECT sha FROM scope WHERE id=1").fetchone()[0] != sha:
                raise ValueError("Different demo version requires a separate directory")
            db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, record TEXT NOT NULL)")

    def _parse(self, data):
        if not data or len(data) > MAX_CSV_BYTES:
            raise DomainError("INVALID_DOCUMENT", "CSV 크기를 확인해 주세요.", {})
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
            if reader.fieldnames != list(FIELDS):
                raise ValueError("header")
            reviews = []
            for index, row in enumerate(reader, 2):
                if set(row) != set(FIELDS) or any(v is None for v in row.values()):
                    raise ValueError("columns")
                locator_row = int(row.pop("row"))
                if locator_row != index:
                    raise ValueError("row locator")
                reviews.append({**row, "locator": {"row": locator_row}})
                if len(reviews) > 36:
                    raise ValueError("scope size")
            if reviews != self.dataset["reviews"]:
                raise ValueError("existing review content/model/version/kind mismatch")
            parsed = {**deepcopy(self.dataset), "reviews": reviews}
            # Review/Evidence text and IDs are checked by the unchanged canonical demo validator.
            DemoStore(parsed)
            return parsed
        except (UnicodeError, ValueError, csv.Error) as error:
            raise DomainError("PARSING_FAILED", "기존 합성 리뷰 CSV의 형식·원문·모델·버전을 확인해 주세요.", {}) from error

    def upload(self, did, data):
        if did != self.source_id:
            raise DomainError("INVALID_DOCUMENT_ID", "승인된 합성 리뷰 자료 ID가 아닙니다.", {})
        parsed = self._parse(data)
        sha = digest(data)
        record = {"document_id": did, "sha256": sha, "source_kind": "synthetic",
                  "original_role": "derived_transport_from_existing_demo_json",
                  "review_count": len(parsed["reviews"]), "evidence_count": len(parsed["evidence"]),
                  "model_ids": [p["model_id"] for p in parsed["products"]],
                  "document_versions": sorted({r["document_version"] for r in parsed["reviews"]}),
                  "parser": "stdlib.csv", "validated_contract": "DemoDataset", "ocr_used": False}
        with closing(sqlite3.connect(self.db)) as db, db:
            previous = db.execute("SELECT record FROM documents WHERE id=?", (did,)).fetchone()
            if previous:
                if json.loads(previous[0])["sha256"] != sha:
                    raise DomainError("SOURCE_CHANGED", "변경된 CSV는 별도 자료 버전으로 등록해야 합니다.", {})
                self.original(did)
                return json.loads(previous[0])
            source = self.directory / (sha + ".csv")
            source.write_bytes(data)
            db.execute("INSERT INTO documents VALUES (?,?)", (did, json.dumps(record, ensure_ascii=False)))
        return record

    def metadata(self, did):
        with closing(sqlite3.connect(self.db)) as db:
            row = db.execute("SELECT record FROM documents WHERE id=?", (did,)).fetchone()
        if not row:
            raise DomainError("INVALID_DOCUMENT_ID", "등록되지 않은 CSV입니다.", {})
        return json.loads(row[0])

    def original(self, did):
        record = self.metadata(did)
        source = self.directory / (record["sha256"] + ".csv")
        if not source.exists() or digest(source.read_bytes()) != record["sha256"]:
            raise DomainError("SOURCE_CHANGED", "보존한 CSV 원문의 해시를 확인해 주세요.", {})
        return source.read_bytes()

    def store(self):
        from .retrieval import GroundedDemoStore
        return GroundedDemoStore(self._parse(self.original(self.source_id)))


class ReviewDocumentRepository:
    """New, explicitly approved CSV documents in a separate immutable scope.

    This does not broaden ReviewCsvRepository's frozen 36-review transport. CSV
    import and exact original checks are reused for registration and every query.
    One source ID identifies one approved model/version; separate IDs are needed
    for other model scopes. No dates, labels, review content or hashes are guessed.
    """

    def __init__(self, directory, *, products, sources, dataset_version):
        from lgax_contracts import validate
        self.products = deepcopy(products)
        self.sources = deepcopy(sources)
        self.dataset_version = dataset_version
        if not isinstance(dataset_version, str) or not dataset_version.strip() or not sources:
            raise ValueError("Explicit new-review scope required")
        for product in self.products:
            validate("Product", product)
        self.specs = {source["document_id"]: source for source in self.sources}
        if len(self.specs) != len(self.sources):
            raise ValueError("Duplicate CSV source ID")
        for source in self.sources:
            if (not isinstance(source.get("sha256"), str) or len(source["sha256"]) != 64
                    or source.get("product") not in self.products):
                raise ValueError("Approved CSV SHA and product required")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "reviews.sqlite"
        scope = {"products": self.products, "sources": self.sources, "dataset_version": dataset_version}
        self.scope_sha256 = digest(json.dumps(scope, sort_keys=True, ensure_ascii=False).encode())
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS scope (id INTEGER PRIMARY KEY, sha TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO scope VALUES (1,?)", (self.scope_sha256,))
            if db.execute("SELECT sha FROM scope WHERE id=1").fetchone()[0] != self.scope_sha256:
                raise ValueError("Different review scope requires a separate directory")
            db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, record TEXT NOT NULL)")

    def metadata(self, did):
        with closing(sqlite3.connect(self.db)) as db:
            row = db.execute("SELECT record FROM documents WHERE id=?", (did,)).fetchone()
        if row is None:
            raise DomainError("INVALID_DOCUMENT_ID", "등록되지 않은 CSV입니다.", {})
        return json.loads(row[0])

    def original(self, did):
        record = self.metadata(did)
        path = self.directory / (record["sha256"] + ".csv")
        if not path.is_file() or digest(path.read_bytes()) != record["sha256"]:
            raise DomainError("SOURCE_CHANGED", "보존 CSV 원문이 없거나 변경됐습니다.", {})
        return path.read_bytes()

    def _import(self, did, raw, **kwargs):
        from .review_import import import_review_csv
        spec = self.specs.get(did)
        if spec is None:
            raise DomainError("INVALID_DOCUMENT_ID", "승인한 CSV 자료 ID가 아닙니다.", {})
        if digest(raw) != spec["sha256"]:
            raise DomainError("SOURCE_MISMATCH", "승인 CSV 원문 SHA가 다릅니다.", {})
        return import_review_csv(raw, products=[spec["product"]], sources=[spec],
            dataset_version=self.dataset_version, **kwargs)

    def upload(self, did, data):
        from .retrieval import GroundedDocumentStore
        with closing(sqlite3.connect(self.db)) as db, db:
            # Serialize new registrations so simultaneous documents cannot both
            # pass duplicate-ID checks against an outdated document list.
            db.execute("BEGIN IMMEDIATE")
            records = [json.loads(row[0]) for row in db.execute("SELECT record FROM documents WHERE id<>?", (did,))]
            parsed = self._import(did, data,
                existing_review_ids=[r["id"] for record in records for r in record["dataset"]["reviews"]],
                existing_evidence_ids=[e["id"] for record in records for e in record["dataset"]["evidence"]])
            GroundedDocumentStore(parsed.dataset, sources=[self.specs[did]])
            record = {"document_id": did, "sha256": parsed.sha256, "dataset": parsed.dataset,
                "origins": parsed.origins, "scope_sha256": self.scope_sha256, "parser": "stdlib.csv",
                "source_kind": self.specs[did]["source_kind"], "original_role": "uploaded_review_csv",
                "review_count": len(parsed.dataset["reviews"]), "idempotent": False}
            previous = db.execute("SELECT record FROM documents WHERE id=?", (did,)).fetchone()
            if previous:
                if json.loads(previous[0])["sha256"] != parsed.sha256:
                    raise DomainError("SOURCE_CHANGED", "CSV ID를 다른 원문으로 덮어쓸 수 없습니다.", {})
                self.original(did)
                return {**json.loads(previous[0]), "idempotent": True}
            target = self.directory / (parsed.sha256 + ".csv")
            if target.exists() and target.read_bytes() != data:
                raise DomainError("SOURCE_CHANGED", "기존 보존 원문의 내용이 다릅니다.", {})
            target.write_bytes(data)
            db.execute("INSERT INTO documents VALUES (?,?)", (did, json.dumps(record, ensure_ascii=False)))
        return record

    def store(self):
        from .retrieval import GroundedDocumentStore
        with closing(sqlite3.connect(self.db)) as db:
            ids = [row[0] for row in db.execute("SELECT id FROM documents ORDER BY id")]
        dataset = {"artifact_kind": "document_dataset", "dataset_version": self.dataset_version,
                   "products": [], "reviews": [], "features": [], "evidence": []}
        products = {}
        for did in ids:
            parsed = self._import(did, self.original(did))
            for product in parsed.dataset["products"]:
                products[product["model_id"]] = product
            for collection in ("reviews", "evidence"):
                dataset[collection].extend(parsed.dataset[collection])
        dataset["products"] = list(products.values())
        return GroundedDocumentStore(dataset, sources=self.sources, source_reader=self.original)
