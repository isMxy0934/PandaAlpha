from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import tushare as ts
except Exception:  # pragma: no cover - optional at dev time
    ts = None  # type: ignore


class RateLimitedError(Exception):
    pass


@dataclass
class FetchResult:
    table: str
    trade_date: date
    df: pd.DataFrame


def _ensure_ts() -> Any:
    if ts is None:
        raise RuntimeError("tushare not installed")
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN not set in environment")
    ts.set_token(token)
    return ts.pro_api()


def fetch_trade_cal(start: date, end: date) -> pd.DataFrame:
    pro = _ensure_ts()
    df = pd.DataFrame(
        pro.trade_cal(start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), is_open="1")
    )
    if df.empty:
        return df
    df["cal_date"] = pd.to_datetime(df["cal_date"], format="%Y%m%d").dt.date
    return df[["cal_date", "is_open"]]


@retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=8), stop=stop_after_attempt(5), reraise=True)
def fetch_daily(trade_date: date) -> FetchResult:
    pro = _ensure_ts()
    ds = trade_date.strftime("%Y%m%d")
    try:
        raw = pro.daily(trade_date=ds)
    except Exception as e:  # tushare raises generic Exception
        # Rough heuristic for rate limit
        msg = str(e).lower()
        if "exceed" in msg or "too many" in msg or "rate" in msg:
            raise RateLimitedError(msg)
        raise

    df = pd.DataFrame(raw)
    if df.empty:
        return FetchResult("prices_daily", trade_date, df)

    # Normalize schema per requirement.md
    df = df.rename(
        columns={
            "ts_code": "ts_code",
            "trade_date": "trade_date",
            "open": "open_raw",
            "high": "high_raw",
            "low": "low_raw",
            "close": "close_raw",
            "pre_close": "pre_close",
            "vol": "volume",
            "amount": "amount",
        }
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
    # TuShare: vol=手, amount=千元 → 转换到 规范：股 & 元
    if "volume" in df.columns:
        df["volume"] = (pd.to_numeric(df["volume"], errors="coerce").fillna(0) * 100).astype("int64")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0) * 1000.0
    return FetchResult("prices_daily", trade_date, df[[
        "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount"
    ]])


@retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=8), stop=stop_after_attempt(5), reraise=True)
def fetch_adj_factor(trade_date: date) -> FetchResult:
    pro = _ensure_ts()
    ds = trade_date.strftime("%Y%m%d")
    raw = pro.adj_factor(trade_date=ds)
    df = pd.DataFrame(raw)
    if df.empty:
        return FetchResult("adj_factor", trade_date, df)
    df = df.rename(columns={"ts_code": "ts_code", "trade_date": "trade_date", "adj_factor": "adj_factor"})
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
    return FetchResult("adj_factor", trade_date, df[["ts_code", "trade_date", "adj_factor"]])


@retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=8), stop=stop_after_attempt(5), reraise=True)
def fetch_daily_basic(trade_date: date) -> FetchResult:
    pro = _ensure_ts()
    ds = trade_date.strftime("%Y%m%d")
    raw = pro.daily_basic(trade_date=ds, fields="ts_code,trade_date,turnover_rate,pe,pe_ttm,pb,ps,total_mv,circ_mv")
    df = pd.DataFrame(raw)
    if df.empty:
        return FetchResult("daily_basic", trade_date, df)
    df = df.rename(columns={"trade_date": "trade_date"})
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
    return FetchResult(
        "daily_basic",
        trade_date,
        df[["ts_code", "trade_date", "turnover_rate", "pe", "pe_ttm", "pb", "ps", "total_mv", "circ_mv"]],
    )


