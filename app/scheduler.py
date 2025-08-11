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
from app.adapters.akshare_adapter import (
    fetch_daily_for_codes as ak_fetch_daily,
    fetch_daily_basic_for_codes as ak_fetch_basic,
    fetch_adj_factor_for_codes as ak_fetch_adj,
    fetch_daily_range_for_codes as ak_fetch_daily_range,
)
from app.datasource.parquet_io import write_parquet_atomic
from app.datasource.paths import PartitionPath
from app.datasource.watermark import WatermarkRow, upsert_watermark
from app.datasource.sqlite_meta import enqueue_fail, upsert_job_status, list_jobs
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
    # update job status snapshot (manual invocation)
    upsert_job_status("daily_job", last_run=f"{dt.isoformat()} 19:00:00", state="ok", next_run=None)


def get_jobs_status() -> list[dict[str, Any]]:
    return list_jobs()


def run_daily_range(start: date, end: date) -> None:
    """Run daily_job for each business day in [start, end].

    Does not require trade_cal permission; non-trading days will produce empty
    frames and be skipped by downstream logic.
    """
    current = start
    provider = settings.data_provider.lower()
    if provider == "akshare":
        codes = list_all_codes()
        if not codes:
            codes = [
                "000001.SZ","000002.SZ","000004.SZ","000006.SZ","000007.SZ",
                "600000.SH","600009.SH","600519.SH","601988.SH","601318.SH",
            ]
        # 批量抓区间，再按日落分区文件
        df = ak_fetch_daily_range(start, end, codes)
        if not df.empty:
            for d, g in df.groupby("trade_date"):
                part = PartitionPath("prices_daily", d)
                rows = write_parquet_atomic(g, part.tmp_file(), part.final_file())
                sha = hashlib.sha1(
                    ",".join(sorted(g["ts_code"].astype(str).tolist())).encode("utf-8")
                ).hexdigest()
                upsert_watermark(WatermarkRow(table="prices_daily", last_dt=d, rowcount=rows, hash=sha))
        # basic/adj 暂为空表（后续可补）
    else:
        current = start
        while current <= end:
            if current.weekday() < 5:
                daily_job(date=current)
            current += timedelta(days=1)


