from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

import pandas as pd

try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None  # type: ignore


@dataclass
class FetchResult:
    table: str
    trade_date: date
    df: pd.DataFrame


def _ensure_ak() -> None:
    if ak is None:
        raise RuntimeError("akshare not installed")


def ts_code_to_ak_symbol(ts_code: str) -> str:
    # 000001.SZ -> sz000001; 600000.SH -> sh600000
    code, ex = ts_code.split(".")
    return ("sz" if ex.upper() == "SZ" else "sh") + code


def _normalize_ak_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize akshare daily df to have columns: trade_date, open_raw, high_raw, low_raw, close_raw, volume, amount.

    Accepts both Chinese/English column names and date in index or column.
    """
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    # If date in index, promote to column
    if df.index.name in ("date", "日期"):
        df = df.reset_index()

    # Standardize date column to 'trade_date'
    if "日期" in df.columns:
        df.rename(columns={"日期": "trade_date"}, inplace=True)
    elif "date" in df.columns:
        df.rename(columns={"date": "trade_date"}, inplace=True)

    # Standardize OHLCV/amount
    rename_map = {
        "开盘": "open_raw",
        "最高": "high_raw",
        "最低": "low_raw",
        "收盘": "close_raw",
        "成交量": "volume",
        "成交额": "amount",
        # English fallbacks
        "open": "open_raw",
        "high": "high_raw",
        "low": "low_raw",
        "close": "close_raw",
        "volume": "volume",
        "amount": "amount",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Ensure date type
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    else:
        # No recognizable date; return empty
        return pd.DataFrame()

    # Coerce numeric
    for c in ("open_raw", "high_raw", "low_raw", "close_raw", "amount"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")

    return df[[c for c in ["trade_date", "open_raw", "high_raw", "low_raw", "close_raw", "volume", "amount"] if c in df.columns]]


def fetch_daily_for_codes(trade_date: date, ts_codes: List[str]) -> FetchResult:
    """Fetch daily OHLCV/amount for given codes on a specific date using AkShare.

    Note: We request per-symbol within [date,date] to avoid full-history download.
    """
    _ensure_ak()
    frames: List[pd.DataFrame] = []
    start = end = trade_date.strftime("%Y%m%d")
    for code in ts_codes:
        symbol = ts_code_to_ak_symbol(code)
        try:
            raw = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="")
        except Exception:
            continue
        df = _normalize_ak_df(raw)
        if df is None or df.empty:
            continue
        out = pd.DataFrame(
            {
                "ts_code": code,
                "trade_date": df["trade_date"],
                "open_raw": df.get("open_raw"),
                "high_raw": df.get("high_raw"),
                "low_raw": df.get("low_raw"),
                "close_raw": df.get("close_raw"),
                # 未提供 pre_close，置为 NaN（后续可通过历史补充）
                "pre_close": pd.NA,
                # 成交量/额单位由数据源决定，后续可做单位校准；此处保持数值
                "volume": df.get("volume"),
                "amount": df.get("amount"),
            }
        )
        frames.append(out)
    if not frames:
        return FetchResult("prices_daily", trade_date, pd.DataFrame(columns=[
            "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount"
        ]))
    res = pd.concat(frames, ignore_index=True)
    return FetchResult("prices_daily", trade_date, res)


def fetch_daily_range_for_codes(start: date, end: date, ts_codes: List[str]) -> pd.DataFrame:
    """Fetch OHLCV for codes within [start, end] using AkShare, return normalized DataFrame.

    Columns: ts_code, trade_date, open_raw, high_raw, low_raw, close_raw, pre_close, volume, amount
    """
    _ensure_ak()
    frames: List[pd.DataFrame] = []
    s = start.strftime("%Y%m%d")
    e = end.strftime("%Y%m%d")
    for code in ts_codes:
        symbol = ts_code_to_ak_symbol(code)
        try:
            raw = ak.stock_zh_a_daily(symbol=symbol, start_date=s, end_date=e, adjust="")
        except Exception:
            continue
        df = _normalize_ak_df(raw)
        if df is None or df.empty:
            continue
        out = pd.DataFrame(
            {
                "ts_code": code,
                "trade_date": df["trade_date"],
                "open_raw": df.get("open_raw"),
                "high_raw": df.get("high_raw"),
                "low_raw": df.get("low_raw"),
                "close_raw": df.get("close_raw"),
                "pre_close": pd.NA,
                "volume": df.get("volume"),
                "amount": df.get("amount"),
            }
        )
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=[
            "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount"
        ])
    return pd.concat(frames, ignore_index=True)

def fetch_daily_basic_for_codes(trade_date: date, ts_codes: List[str]) -> FetchResult:
    """Fetch daily_basic minimal fields using ak.stock_zh_a_hist to get turnover rate.

    AkShare stock_zh_a_hist(symbol, period="daily", start_date, end_date, adjust="") returns
    columns 包含 换手率. 我们取单日 trade_date 的记录。
    """
    _ensure_ak()
    frames: List[pd.DataFrame] = []
    s = e = trade_date.strftime("%Y%m%d")
    for code in ts_codes:
        symbol = ts_code_to_ak_symbol(code)
        try:
            raw = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=s, end_date=e, adjust="")
        except Exception:
            continue
        if raw is None or raw.empty:
            continue
        df = raw.copy()
        # normalize date
        if "日期" in df.columns:
            df.rename(columns={"日期": "trade_date"}, inplace=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        # turnover rate column names across versions: "换手率" or "换手率(%)"
        tr_col = "换手率" if "换手率" in df.columns else ("换手率(%)" if "换手率(%)" in df.columns else None)
        if tr_col is None:
            continue
        out = pd.DataFrame(
            {
                "ts_code": code,
                "trade_date": df["trade_date"],
                # AkShare turnover is in percent; convert to % number consistent with spec
                "turnover_rate": pd.to_numeric(df[tr_col], errors="coerce").astype(float),
                # placeholders for valuation fields
                "pe": pd.NA,
                "pe_ttm": pd.NA,
                "pb": pd.NA,
                "ps": pd.NA,
                "total_mv": pd.NA,
                "circ_mv": pd.NA,
            }
        )
        frames.append(out)
    cols = ["ts_code", "trade_date", "turnover_rate", "pe", "pe_ttm", "pb", "ps", "total_mv", "circ_mv"]
    if not frames:
        return FetchResult("daily_basic", trade_date, pd.DataFrame(columns=cols))
    return FetchResult("daily_basic", trade_date, pd.concat(frames, ignore_index=True)[cols])


def fetch_adj_factor_for_codes(trade_date: date, ts_codes: List[str]) -> FetchResult:
    """AkShare adj factor fallback: not provided here (Phase A), return empty."""
    return FetchResult("adj_factor", trade_date, pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor"]))


