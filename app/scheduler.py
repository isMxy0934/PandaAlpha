"""Scheduler stubs for Phase A (A-0).

Real scheduling (APScheduler + SQLite jobstore) will be wired in Phase A-1.
This module provides placeholders to avoid coupling at import time.
"""

from __future__ import annotations

from typing import Any
from datetime import date, timedelta
import hashlib
import json

import pandas as pd
from dotenv import load_dotenv

from app.settings import settings
from app.adapters.tushare_adapter import fetch_daily as ts_fetch_daily, fetch_adj_factor as ts_fetch_adj, fetch_daily_basic as ts_fetch_basic
from app.adapters.akshare_adapter import fetch_daily_for_codes as ak_fetch_daily, fetch_daily_basic_for_codes as ak_fetch_basic, fetch_adj_factor_for_codes as ak_fetch_adj
from app.datasource.parquet_io import write_parquet_atomic
from app.datasource.paths import PartitionPath
from app.datasource.watermark import WatermarkRow, upsert_watermark
from app.datasource.sqlite_meta import enqueue_fail
from app.api.watchlist_store import list_all_codes


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

    provider = settings.data_provider.lower()
    if provider == "tushare":
        fetchers = (lambda d: ts_fetch_daily(d), lambda d: ts_fetch_adj(d), lambda d: ts_fetch_basic(d))
    else:
        # akshare: fetch per watchlist codes; fallback到 Top 部分代码为空则跳过
        codes = list_all_codes()
        if not codes:
            # 默认抓取沪深各 5 支示例，便于首次跑通（可在 watchlist 设置）
            codes = [
                "000001.SZ","000002.SZ","000004.SZ","000006.SZ","000007.SZ",
                "600000.SH","600009.SH","600519.SH","601988.SH","601318.SH",
            ]
        fetchers = (
            lambda d: ak_fetch_daily(d, codes),
            lambda d: ak_fetch_adj(d, codes),
            lambda d: ak_fetch_basic(d, codes),
        )

    for fetcher in fetchers:
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


def run_daily_range(start: date, end: date) -> None:
    """Run daily_job for each business day in [start, end].

    Does not require trade_cal permission; non-trading days will produce empty
    frames and be skipped by downstream logic.
    """
    current = start
    while current <= end:
        # quick weekday filter (Mon-Fri)
        if current.weekday() < 5:
            daily_job(date=current)
        current += timedelta(days=1)


