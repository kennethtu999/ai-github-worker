import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_db_parent() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    ensure_db_parent()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              event_id TEXT,
              repo TEXT,
              issue_number INTEGER,
              pr_number INTEGER,
              task_type TEXT,
              mode TEXT,
              status TEXT,
              payload_json TEXT,
              created_at TEXT,
              started_at TEXT,
              finished_at TEXT,
              result_json TEXT
            );

            CREATE TABLE IF NOT EXISTS processed_events (
              event_id TEXT PRIMARY KEY,
              received_at TEXT
            );
            """
        )
        conn.commit()


def is_event_processed(event_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT event_id FROM processed_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return row is not None


def mark_event_processed(event_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, received_at) VALUES (?, ?)",
            (event_id, now_iso()),
        )
        conn.commit()


def enqueue_job(job: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, event_id, repo, issue_number, pr_number,
              task_type, mode, status, payload_json,
              created_at, started_at, finished_at, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"],
                job.get("event_id"),
                job.get("repo"),
                job.get("issue_number"),
                job.get("pr_number"),
                job.get("task_type"),
                job.get("mode"),
                "queued",
                json.dumps(job.get("payload", {}), ensure_ascii=False),
                now_iso(),
                None,
                None,
                None,
            ),
        )
        conn.commit()


def claim_next_queued_job() -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
            (now_iso(), row["id"]),
        )
        conn.commit()
        return _row_to_job_dict(row)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return _row_to_job_dict(row)


def update_job_status(job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, finished_at = ?, result_json = ? WHERE id = ?",
            (
                status,
                now_iso(),
                json.dumps(result or {}, ensure_ascii=False),
                job_id,
            ),
        )
        conn.commit()


def _row_to_job_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "event_id": row["event_id"],
        "repo": row["repo"],
        "issue_number": row["issue_number"],
        "pr_number": row["pr_number"],
        "task_type": row["task_type"],
        "mode": row["mode"],
        "status": row["status"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "result": json.loads(row["result_json"] or "{}"),
    }
