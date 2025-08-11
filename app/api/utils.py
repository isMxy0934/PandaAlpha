from __future__ import annotations

import hashlib
import json
from typing import Iterable

from app.datasource.watermark import read_watermarks


def compute_data_snapshot_id() -> str:
    wms = read_watermarks()
    payload = [
        {"table": w.table, "last_dt": w.last_dt.isoformat(), "rowcount": w.rowcount, "hash": w.hash}
        for w in sorted(wms, key=lambda x: x.table)
    ]
    s = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def normalize_ts_codes(value: str) -> list[str]:
    return sorted({c.strip() for c in value.split(",") if c.strip()})


def compute_etag(normalized_query: dict) -> str:
    snapshot = compute_data_snapshot_id()
    nq = json.dumps(normalized_query, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1((snapshot + nq).encode("utf-8")).hexdigest()


