from __future__ import annotations

import sqlite3
from typing import Any, List, Tuple

from app.datasource.paths import META_SQLITE


def _conn() -> sqlite3.Connection:
    META_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(META_SQLITE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            ts_codes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    return conn


def get_watchlist(page: int, limit: int) -> dict[str, Any]:
    conn = _conn()
    cur = conn.execute("SELECT ts_codes FROM watchlist WHERE id=1")
    row = cur.fetchone()
    all_codes: List[str] = []
    if row and row[0]:
        all_codes = [c for c in row[0].split(",") if c]
    total = len(all_codes)
    start = max(0, (page - 1) * limit)
    end = min(total, start + limit)
    items = all_codes[start:end]
    return {"page": page, "limit": limit, "total": total, "items": items}


def set_watchlist(codes: list[str]) -> None:
    dedup_sorted = ",".join(sorted({c.strip() for c in codes if c.strip()}))
    conn = _conn()
    with conn:
        # upsert single row id=1
        conn.execute("INSERT INTO watchlist(id, ts_codes) VALUES(1, ?) ON CONFLICT(id) DO UPDATE SET ts_codes=excluded.ts_codes", (dedup_sorted,))


def list_all_codes() -> list[str]:
    conn = _conn()
    cur = conn.execute("SELECT ts_codes FROM watchlist WHERE id=1")
    row = cur.fetchone()
    if not row or not row[0]:
        return []
    return [c for c in row[0].split(",") if c]


