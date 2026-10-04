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
        return DemoStore(self._parse(self.original(self.source_id)))
