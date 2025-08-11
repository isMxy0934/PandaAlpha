from __future__ import annotations

import json
from datetime import date
from typing import Dict, List

import pandas as pd
import requests

from app.datasource.readers import read_prices_and_adj
from app.metrics.core import adjust_ohlc, compute_ma, compute_vol_ann


API_BASE = "http://127.0.0.1:8000"


def compute_local(ts_code: str, start: date, end: date, window: int = 20) -> pd.DataFrame:
    prices = read_prices_and_adj([ts_code], start, end)
    if prices.empty:
        return pd.DataFrame(columns=["trade_date", "ma", "vol_ann"]).assign(ts_code=ts_code)
    prices = adjust_ohlc(prices, adj="backward").sort_values("trade_date")
    out = pd.DataFrame({"trade_date": prices["trade_date"]})
    out["ma"] = compute_ma(prices, window)
    out["vol_ann"] = compute_vol_ann(prices, window)
    out["ts_code"] = ts_code
    return out


def fetch_api_metrics(ts_code: str, start: date, end: date, window: int = 20) -> pd.DataFrame:
    url = f"{API_BASE}/api/metrics"
    params = {
        "ts_code": ts_code,
        "window": window,
        "metrics": "ma,vol_ann,turnover",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    rows = data.get("rows", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["trade_date", "ma", "vol_ann"]).assign(ts_code=ts_code)
    # API 字段名：ma20
    ma_col = f"ma{window}"
    if ma_col not in df.columns:
        df[ma_col] = pd.NA
    return pd.DataFrame({
        "ts_code": ts_code,
        "trade_date": pd.to_datetime(df["trade_date"]).dt.date,
        "ma": pd.to_numeric(df[ma_col], errors="coerce"),
        "vol_ann": pd.to_numeric(df.get("vol_ann", pd.NA), errors="coerce"),
    })


def compare_series(local: pd.Series, remote: pd.Series) -> float:
    joined = pd.concat([local.rename("l"), remote.rename("r")], axis=1).dropna()
    if joined.empty:
        return float("nan")
    return float((joined["l"] - joined["r"]).abs().max())


def run(ts_codes: List[str], start: date, end: date, window: int = 20) -> None:
    summary: List[Dict] = []
    for ts in ts_codes:
        loc = compute_local(ts, start, end, window)
        api = fetch_api_metrics(ts, start, end, window)
        loc = loc.set_index("trade_date")
        api = api.set_index("trade_date")
        max_ma = compare_series(loc["ma"], api["ma"]) if not loc.empty and not api.empty else float("nan")
        max_vol = compare_series(loc["vol_ann"], api["vol_ann"]) if not loc.empty and not api.empty else float("nan")
        summary.append({"ts_code": ts, "max_abs_diff_ma": max_ma, "max_abs_diff_vol_ann": max_vol})
    print(json.dumps({"window": window, "start": start.isoformat(), "end": end.isoformat(), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run([
        "600519.SH",
        "600000.SH",
        "000001.SZ",
    ], start=date(2025, 6, 10), end=date(2025, 8, 8), window=20)


