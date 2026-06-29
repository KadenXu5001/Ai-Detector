"""
db.py

SQLite audit log — init and write helpers.
"""

import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "audit_log.db"


def init_db() -> None:
    """Create the audit_log table if it doesn't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp          TEXT NOT NULL,
                content_id         TEXT NOT NULL,
                creator_id         TEXT,
                llm_score          REAL,
                stylometric_score  REAL,
                confidence         REAL,
                attribution        TEXT,
                status             TEXT NOT NULL DEFAULT 'classified',
                appeal_reason      TEXT,
                appealed_at        TEXT
            )
        """)
        conn.commit()


def generate_content_id() -> str:
    return str(uuid.uuid4())


def write_log_entry(
    content_id: str,
    creator_id: str | None,
    llm_score: float | None,
    confidence: float | None,
    attribution: str,
    stylometric_score: float | None = None,
    status: str = "classified",
) -> None:
    """Insert a new row into the audit log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO audit_log
                (timestamp, content_id, creator_id, llm_score,
                 stylometric_score, confidence, attribution, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, content_id, creator_id, llm_score,
             stylometric_score, confidence, attribution, status),
        )
        conn.commit()


def update_appeal(content_id: str, reason: str) -> bool:
    """
    Mark the most recent log entry for content_id as under_review.
    Returns True if a row was updated, False if content_id not found.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE audit_log
            SET status = 'under_review',
                appeal_reason = ?,
                appealed_at = ?
            WHERE content_id = ?
              AND id = (
                  SELECT id FROM audit_log
                  WHERE content_id = ?
                  ORDER BY id DESC LIMIT 1
              )
            """,
            (reason, ts, content_id, content_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def fetch_all_entries() -> list[dict]:
    """Return all audit log rows as dicts, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]
