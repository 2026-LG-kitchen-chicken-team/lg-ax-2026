"""Bounded registration of trusted original documents; canonical excerpts retain provenance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from copy import deepcopy
from pathlib import Path

from .document_store import DocumentStore
from .errors import DomainError

MAX_BYTES = 15 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DocumentRepository:
    def __init__(self, directory: Path, plan: dict, extractor_python: str):
        if plan.get("artifact_kind") != "trusted_document_plan":
            raise ValueError("Explicit trusted document plan required")
        models = [s["product"]["model_id"] for s in plan["documents"]]
        if len(set(models)) != len(models):
            raise ValueError("Use a separate dataset scope for each model document revision")
        for spec in plan["documents"]:
            if spec["product"]["document_version"] != spec["document_version"]:
                raise ValueError("Product document version mismatch")
            if spec["product"]["source_kind"] != spec["source_kind"]:
                raise ValueError("Product source kind mismatch")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "documents.sqlite"
        self.plan = deepcopy(plan)
        self.extractor_python = extractor_python
        self.specs = {spec["document_id"]: spec for spec in plan["documents"]}
        if len(self.specs) != len(plan["documents"]):
            raise ValueError("Duplicate document ID")
        for did in self.specs:
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", did):
                raise ValueError("Invalid document ID")
        self.plan_sha256 = digest(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode())
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS scope (id INTEGER PRIMARY KEY, sha TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO scope VALUES (1,?)", (self.plan_sha256,))
            if db.execute("SELECT sha FROM scope WHERE id=1").fetchone()[0] != self.plan_sha256:
                raise ValueError("Different plan/version requires a separate registration directory")
            db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, sha TEXT NOT NULL, record TEXT NOT NULL)")

    def metadata(self, did):
        with closing(sqlite3.connect(self.db)) as db, db:
            row = db.execute("SELECT record FROM documents WHERE id=?", (did,)).fetchone()
        if not row:
            raise DomainError("INVALID_DOCUMENT_ID", "등록되지 않은 문서입니다.", {})
        return json.loads(row[0])

    def original(self, did):
        record = self.metadata(did)
        try:
            data = (self.directory / (record["sha256"] + ".pdf")).read_bytes()
        except FileNotFoundError as error:
            raise DomainError("SOURCE_CHANGED", "보존한 원문을 찾을 수 없습니다.", {}) from error
        if digest(data) != record["sha256"]:
            raise DomainError("SOURCE_CHANGED", "보존한 원문 해시가 다릅니다.", {})
        return data

    def _parse(self, data):
        with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".pdf", delete=False) as f:
            f.write(data)
            source = Path(f.name)
        try:
            worker = Path(__file__).with_name("pdf_text_worker.py")
            try:
                result = subprocess.run([self.extractor_python, "-B", "-X", "utf8", str(worker), str(source)],
                                        capture_output=True, encoding="utf-8", timeout=90, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise DomainError("PARSING_UNAVAILABLE", "지정한 PDF 추출 환경을 실행할 수 없습니다.", {}) from error
            if result.returncode:
                raise DomainError("PARSING_FAILED", "텍스트 PDF 추출 실패; OCR은 수행하지 않았습니다.", {})
            return json.loads(result.stdout)
        finally:
            source.unlink(missing_ok=True)

    def upload(self, did, data):
        spec = self.specs.get(did)
        if spec is None:
            raise DomainError("INVALID_DOCUMENT_ID", "승인된 문서 범위가 아닙니다.", {})
        if not data or len(data) > MAX_BYTES or not data.startswith(b"%PDF"):
            raise DomainError("INVALID_DOCUMENT", "허용 크기의 PDF 원문이 필요합니다.", {})
        sha = digest(data)
        if sha != spec["sha256"]:
            raise DomainError("SOURCE_MISMATCH", "선택한 모델·문서 버전의 원문과 다릅니다.", {})
        with closing(sqlite3.connect(self.db)) as db, db:
            previous = db.execute("SELECT sha, record FROM documents WHERE id=?", (did,)).fetchone()
        if previous:
            if previous[0] != sha:
                raise DomainError("SOURCE_MISMATCH", "기존 문서 ID를 다른 원문으로 바꿀 수 없습니다.", {})
            self.original(did)
            return {**json.loads(previous[1]), "idempotent": True}
        parsed = self._parse(data)
        evidence, origins = [], []
        for selection in spec["selections"]:
            page = selection["page"]
            if not 1 <= page <= len(parsed["pages"]):
                raise DomainError("SOURCE_MISMATCH", "근거 페이지가 원문 범위 밖입니다.", {})
            text = parsed["pages"][page - 1]
            excerpt = selection["excerpt"]
            start = text.find(excerpt)
            if start < 0 or text.find(excerpt, start + 1) >= 0:
                raise DomainError("SOURCE_MISMATCH", "지정한 근거가 원문에서 유일하게 확인되지 않습니다.", {})
            locator = {"page": page, "section": selection["section"]}
            evidence.append({"id": selection["evidence_id"], "model_id": spec["product"]["model_id"],
                             "document_version": spec["document_version"], "source_kind": spec["source_kind"],
                             "source_type": "manual", "source_id": did, "locator": locator,
                             "text": excerpt, "feature_ids": selection["feature_ids"]})
            origins.append({"evidence_id": selection["evidence_id"], "url": spec["url"],
                            "checked_at": spec["checked_at"], "sha256": sha, "page": page,
                            "start_char": start, "end_char": start + len(excerpt),
                            "text_sha256": digest(excerpt.encode()), "document_version": spec["document_version"],
                            "source_kind": spec["source_kind"], "original_text_exact": True})
        dataset = {"artifact_kind": "document_dataset", "dataset_version": self.plan["dataset_version"],
                   "products": [spec["product"]], "reviews": [], "features": spec["features"], "evidence": evidence}
        DocumentStore(dataset)  # Validate before any persisted registration.
        record = {"document_id": did, "sha256": sha, "bytes": len(data), "product": spec["product"],
                  "document_version": spec["document_version"], "source_kind": spec["source_kind"],
                  "url": spec["url"], "checked_at": spec["checked_at"], "parser": parsed["parser"],
                  "parser_version": parsed["parser_version"], "ocr_used": False,
                  "page_count": len(parsed["pages"]), "dataset": dataset, "origins": origins,
                  "plan_sha256": self.plan_sha256, "idempotent": False}
        target = self.directory / (sha + ".pdf")
        # Immutable content-addressed original; all logical records committed together.
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as f:
                f.write(data)
                temp = Path(f.name)
            os.replace(temp, target)
        if digest(target.read_bytes()) != sha:
            raise DomainError("SOURCE_CHANGED", "원문 보존 검증에 실패했습니다.", {})
        with closing(sqlite3.connect(self.db)) as db, db:
            cursor = db.execute("INSERT OR IGNORE INTO documents VALUES (?,?,?)",
                                (did, sha, json.dumps(record, ensure_ascii=False)))
            if not cursor.rowcount:
                row = db.execute("SELECT sha,record FROM documents WHERE id=?", (did,)).fetchone()
                if row[0] != sha:
                    raise DomainError("SOURCE_MISMATCH", "문서 ID가 다른 원문에 등록됐습니다.", {})
                record = {**json.loads(row[1]), "idempotent": True}
        return record

    def store(self):
        dataset = {"artifact_kind": "document_dataset", "dataset_version": self.plan["dataset_version"],
                   "products": [], "reviews": [], "features": [], "evidence": []}
        with closing(sqlite3.connect(self.db)) as db, db:
            records = [json.loads(row[0]) for row in db.execute("SELECT record FROM documents ORDER BY id")]
        for record in records:
            for collection in ("products", "features", "evidence"):
                dataset[collection].extend(record["dataset"][collection])
        return DocumentStore(dataset)
