"""SQLite-backed job store: processing / done / failed rows, with a TTL purge."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.contracts import DoneJob

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    upload_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, job_id: str, upload_path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs (job_id, upload_path, status) VALUES (?, ?, 'processing')",
                (job_id, str(upload_path)),
            )

    def get(self, job_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def pending(self) -> list[str]:
        with self.connect() as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT job_id FROM jobs WHERE status = 'processing' ORDER BY created_at, rowid"
                )
            ]

    def created_at(self, job_id: str) -> datetime:
        row = self.get(job_id)
        if row is None:
            raise KeyError(f"Unknown job: {job_id}")
        return datetime.strptime(row["created_at"], _TIMESTAMP_FORMAT).replace(tzinfo=UTC)

    def complete(self, job_id: str, result: DoneJob) -> None:
        payload = result.model_dump_json(exclude={"job_id", "status"})
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'done', result_json = ?, error = NULL WHERE job_id = ?",
                (payload, job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', error = ?, result_json = NULL WHERE job_id = ?",
                (error, job_id),
            )

    def purge_expired(self, ttl_hours: float) -> int:
        """Delete finished rows older than `ttl_hours`. Returns the row count removed."""
        cutoff = (datetime.now(UTC) - timedelta(hours=ttl_hours)).strftime(_TIMESTAMP_FORMAT)
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM jobs WHERE status IN ('done', 'failed') AND created_at < ?",
                (cutoff,),
            )
            return cursor.rowcount
