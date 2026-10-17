"""SQLite snapshots; one canonical JSON record per run ID, no duplicate tables."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


class RunRepository:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, snapshot TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as connection:
            with connection:
                yield connection

    def put(self, run_id, snapshot):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute("INSERT INTO runs (id, updated_at, snapshot) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,snapshot=excluded.snapshot",
                               (run_id, now, json.dumps(snapshot, ensure_ascii=False)))
        return {"id": run_id, "updatedAt": now}

    def list(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT id,updated_at FROM runs ORDER BY updated_at DESC LIMIT 100").fetchall()
        return [{"id": rid, "updatedAt": updated} for rid, updated in rows]

    def get(self, run_id):
        with self.connect() as connection:
            row = connection.execute("SELECT snapshot FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None
