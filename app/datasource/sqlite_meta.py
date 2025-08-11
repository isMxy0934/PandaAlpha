from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .paths import META_SQLITE


def _ensure_conn() -> sqlite3.Connection:
    META_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(META_SQLITE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fail_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            params TEXT NOT NULL,
            retries INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def enqueue_fail(endpoint: str, params: str, last_error: str) -> None:
    conn = _ensure_conn()
    with conn:
        conn.execute(
            "INSERT INTO fail_queue(endpoint, params, last_error) VALUES (?,?,?)",
            (endpoint, params, last_error),
        )


def list_fail(limit: int = 50) -> list[dict[str, Any]]:
    conn = _ensure_conn()
    cur = conn.execute("SELECT id, endpoint, params, retries, last_error, created_at FROM fail_queue ORDER BY id DESC LIMIT ?", (limit,))
    rows = [
        {
            "id": r[0],
            "endpoint": r[1],
            "params": r[2],
            "retries": r[3],
            "last_error": r[4],
            "created_at": r[5],
        }
        for r in cur.fetchall()
    ]
    return rows


