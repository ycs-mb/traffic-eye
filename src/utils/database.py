"""SQLite database layer with WAL mode for crash-safe writes."""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS violations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    confidence REAL NOT NULL,
    plate_text TEXT,
    plate_confidence REAL DEFAULT 0.0,
    gps_lat REAL,
    gps_lon REAL,
    gps_heading REAL,
    gps_speed_kmh REAL,
    gps_address TEXT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    consecutive_frames INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_hash TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cloud_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    response_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS email_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_violations_status ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp);
CREATE INDEX IF NOT EXISTS idx_evidence_violation ON evidence_files(violation_id);
CREATE INDEX IF NOT EXISTS idx_cloud_queue_status ON cloud_queue(status);
CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status);
"""


class Database:
    """Thread-safe SQLite database with WAL mode."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        logger.info("Database initialized at %s (WAL mode)", self._db_path)

    @contextmanager
    def transaction(self):
        """Context manager for thread-safe transactions."""
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- Violations ---

    def insert_violation(
        self,
        violation_id: str,
        violation_type: str,
        confidence: float,
        plate_text: Optional[str] = None,
        plate_confidence: float = 0.0,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
        gps_heading: Optional[float] = None,
        gps_speed_kmh: Optional[float] = None,
        gps_address: Optional[str] = None,
        timestamp: Optional[str] = None,
        consecutive_frames: int = 0,
    ) -> str:
        now = self._now_iso()
        ts = timestamp or now
        with self.transaction() as cur:
            cur.execute(
                """INSERT INTO violations
                (id, type, confidence, plate_text, plate_confidence,
                 gps_lat, gps_lon, gps_heading, gps_speed_kmh, gps_address,
                 timestamp, status, consecutive_frames, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (violation_id, violation_type, confidence, plate_text,
                 plate_confidence, gps_lat, gps_lon, gps_heading,
                 gps_speed_kmh, gps_address, ts, consecutive_frames, now, now),
            )
        return violation_id

    def get_violation(self, violation_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM violations WHERE id = ?", (violation_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def update_violation_status(self, violation_id: str, status: str) -> None:
        with self.transaction() as cur:
            cur.execute(
                "UPDATE violations SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now_iso(), violation_id),
            )

    def get_violations_by_status(self, status: str) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM violations WHERE status = ? ORDER BY timestamp DESC",
                (status,),
            )
            return [dict(row) for row in cur.fetchall()]

    def delete_old_violations(self, before_timestamp: str) -> int:
        with self.transaction() as cur:
            # Only delete violations that are not pending
            cur.execute(
                """DELETE FROM violations
                WHERE timestamp < ? AND status NOT IN ('pending', 'processing')""",
                (before_timestamp,),
            )
            return cur.rowcount

    # --- Evidence Files ---

    def insert_evidence_file(
        self,
        violation_id: str,
        file_path: str,
        file_type: str,
        file_size: int = 0,
        file_hash: Optional[str] = None,
    ) -> int:
        with self.transaction() as cur:
            cur.execute(
                """INSERT INTO evidence_files
                (violation_id, file_path, file_type, file_size, file_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (violation_id, file_path, file_type, file_size, file_hash,
                 self._now_iso()),
            )
            return cur.lastrowid

    def get_evidence_files(self, violation_id: str) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM evidence_files WHERE violation_id = ?",
                (violation_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    # --- Cloud Queue ---

    def enqueue_cloud(self, violation_id: str) -> int:
        now = self._now_iso()
        with self.transaction() as cur:
            cur.execute(
                """INSERT INTO cloud_queue
                (violation_id, status, created_at, updated_at)
                VALUES (?, 'pending', ?, ?)""",
                (violation_id, now, now),
            )
            return cur.lastrowid

    def get_pending_cloud(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT * FROM cloud_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def update_cloud_status(
        self,
        queue_id: int,
        status: str,
        response_json: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = self._now_iso()
        with self.transaction() as cur:
            cur.execute(
                """UPDATE cloud_queue
                SET status = ?, attempts = attempts + 1,
                    last_attempt_at = ?, response_json = ?,
                    error_message = ?, updated_at = ?
                WHERE id = ?""",
                (status, now, response_json, error_message, now, queue_id),
            )

    # --- Email Queue ---

    def enqueue_email(self, violation_id: str) -> int:
        now = self._now_iso()
        with self.transaction() as cur:
            cur.execute(
                """INSERT INTO email_queue
                (violation_id, status, created_at, updated_at)
                VALUES (?, 'pending', ?, ?)""",
                (violation_id, now, now),
            )
            return cur.lastrowid

    def get_pending_emails(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT * FROM email_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def update_email_status(
        self,
        queue_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        now = self._now_iso()
        with self.transaction() as cur:
            cur.execute(
                """UPDATE email_queue
                SET status = ?, attempts = attempts + 1,
                    last_attempt_at = ?, error_message = ?,
                    updated_at = ?
                WHERE id = ?""",
                (status, now, error_message, now, queue_id),
            )
