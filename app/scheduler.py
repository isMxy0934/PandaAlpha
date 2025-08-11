"""Scheduler stubs for Phase A (A-0).

Real scheduling (APScheduler + SQLite jobstore) will be wired in Phase A-1.
This module provides placeholders to avoid coupling at import time.
"""

from __future__ import annotations

from typing import Any
from datetime import date
import hashlib
import json

import pandas as pd
from dotenv import load_dotenv

from app.adapters.tushare_adapter import fetch_daily, fetch_adj_factor, fetch_daily_basic
from app.datasource.parquet_io import write_parquet_atomic
from app.datasource.paths import PartitionPath
from app.datasource.watermark import WatermarkRow, upsert_watermark
from app.datasource.sqlite_meta import enqueue_fail


def daily_job(*args: Any, **kwargs: Any) -> None:
    """A-1: Fetch -> Write Parquet (partitioned) -> Update watermark.

    Args can contain {"date": "YYYY-MM-DD"} for ad-hoc run.
    """
    # ensure environment from .env is loaded when invoked as a script
    load_dotenv(override=False)

    dt_param = kwargs.get("date")
    if isinstance(dt_param, date):
        dt = dt_param
    elif isinstance(dt_param, str) and dt_param:
        dt = date.fromisoformat(dt_param)
    else:
        dt = date.today()

    for fetcher in (fetch_daily, fetch_adj_factor, fetch_daily_basic):
        try:
            result = fetcher(dt)
        except Exception as e:  # record to fail_queue and continue other tables
            enqueue_fail(endpoint=fetcher.__name__, params=json.dumps({"date": dt.isoformat()}), last_error=str(e))
            continue

        if result.df.empty:
            continue

        part = PartitionPath(result.table, dt)
        rows = write_parquet_atomic(result.df, part.tmp_file(), part.final_file())

        # naive hash: sha1 of sorted ts_code
        sha = hashlib.sha1()
        if "ts_code" in result.df.columns:
            codes = ",".join(sorted(result.df["ts_code"].astype(str).tolist()))
            sha.update(codes.encode("utf-8"))
        upsert_watermark(WatermarkRow(table=result.table, last_dt=dt, rowcount=rows, hash=sha.hexdigest()))


def get_jobs_status() -> list[dict[str, Any]]:
    """Return job status list for /api/status. Empty in A-0."""
    return []


