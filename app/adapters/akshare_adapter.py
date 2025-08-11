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
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="")
        except Exception:
            continue
        if df is None or df.empty:
            continue
        # Normalize columns to spec
        # AkShare columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额
        m = {
            "日期": "trade_date",
            "开盘": "open_raw",
            "最高": "high_raw",
            "最低": "low_raw",
            "收盘": "close_raw",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns=m)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        out = pd.DataFrame(
            {
                "ts_code": code,
                "trade_date": df["trade_date"],
                "open_raw": pd.to_numeric(df["open_raw"], errors="coerce"),
                "high_raw": pd.to_numeric(df["high_raw"], errors="coerce"),
                "low_raw": pd.to_numeric(df["low_raw"], errors="coerce"),
                "close_raw": pd.to_numeric(df["close_raw"], errors="coerce"),
                # 未提供 pre_close，置为 NaN（后续可通过历史补充）
                "pre_close": pd.NA,
                # 成交量/额单位由数据源决定，后续可做单位校准；此处保持数值
                "volume": pd.to_numeric(df["volume"], errors="coerce").astype("Int64"),
                "amount": pd.to_numeric(df["amount"], errors="coerce"),
            }
        )
        frames.append(out)
    if not frames:
        return FetchResult("prices_daily", trade_date, pd.DataFrame(columns=[
            "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount"
        ]))
    res = pd.concat(frames, ignore_index=True)
    return FetchResult("prices_daily", trade_date, res)


def fetch_daily_basic_for_codes(trade_date: date, ts_codes: List[str]) -> FetchResult:
    """Placeholder for turnover/valuation via AkShare.

    Many endpoints require per-symbol queries; for Phase A, we only return
    empty turnover placeholders. Can be extended in later phases.
    """
    cols = ["ts_code", "trade_date", "turnover_rate", "pe", "pe_ttm", "pb", "ps", "total_mv", "circ_mv"]
    return FetchResult("daily_basic", trade_date, pd.DataFrame(columns=cols))


def fetch_adj_factor_for_codes(trade_date: date, ts_codes: List[str]) -> FetchResult:
    """AkShare adj factor fallback: not provided here (Phase A), return empty."""
    return FetchResult("adj_factor", trade_date, pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor"]))


