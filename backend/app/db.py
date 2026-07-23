"""SQLite persistence for analysis log entries."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "space_analyser.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                metrics TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts)")
        conn.commit()
    finally:
        conn.close()


def insert_log(session_id: str, ts: str, metrics: dict[str, float]) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO logs (session_id, ts, metrics) VALUES (?, ?, ?)",
            (session_id, ts, json.dumps(metrics)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch_logs(limit: int = 100, offset: int = 0, session_id: Optional[str] = None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        if session_id:
            rows = conn.execute(
                "SELECT id, session_id, ts, metrics FROM logs WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, session_id, ts, metrics FROM logs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "ts": row["ts"],
                    "metrics": json.loads(row["metrics"]),
                }
            )
        return result
    finally:
        conn.close()


def fetch_sessions() -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT session_id, COUNT(*) as count, MIN(ts) as started_at, MAX(ts) as ended_at
            FROM logs GROUP BY session_id ORDER BY started_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def export_csv(session_id: Optional[str] = None) -> str:
    logs = fetch_logs(limit=1_000_000, offset=0, session_id=session_id)
    logs.reverse()
    buf = io.StringIO()
    if not logs:
        return ""
    metric_keys = sorted(logs[0]["metrics"].keys())
    writer = csv.writer(buf)
    writer.writerow(["id", "session_id", "ts", *metric_keys])
    for log in logs:
        writer.writerow([log["id"], log["session_id"], log["ts"], *[log["metrics"].get(k, "") for k in metric_keys]])
    return buf.getvalue()
