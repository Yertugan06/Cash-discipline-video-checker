import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.models import AnalysisResult


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, upload_path TEXT NOT NULL,
                    debug INTEGER NOT NULL, status TEXT NOT NULL,
                    result_json TEXT, error TEXT,
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

    def create(self, job_id: str, upload_path: Path, debug: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs (job_id, upload_path, debug, status) "
                "VALUES (?, ?, ?, 'processing')",
                (job_id, str(upload_path), int(debug)),
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

    def complete(self, job_id: str, result: AnalysisResult) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'done', result_json = ?, error = NULL WHERE job_id = ?",
                (result.model_dump_json(), job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', error = ?, result_json = NULL WHERE job_id = ?",
                (error, job_id),
            )
