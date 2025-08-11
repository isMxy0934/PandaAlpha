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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            last_run TIMESTAMP,
            state TEXT,
            next_run TIMESTAMP
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


def upsert_job_status(job_id: str, last_run: str | None, state: str | None, next_run: str | None) -> None:
    conn = _ensure_conn()
    with conn:
        conn.execute(
            "INSERT INTO jobs(id,last_run,state,next_run) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_run=excluded.last_run, state=excluded.state, next_run=excluded.next_run",
            (job_id, last_run, state, next_run),
        )


def list_jobs() -> list[dict[str, Any]]:
    conn = _ensure_conn()
    cur = conn.execute("SELECT id,last_run,state,next_run FROM jobs ORDER BY id")
    return [
        {"id": r[0], "last_run": r[1], "state": r[2], "next_run": r[3]}
        for r in cur.fetchall()
    ]


