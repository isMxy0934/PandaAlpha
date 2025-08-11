from __future__ import annotations

from math import sqrt
from typing import Iterable, Optional

import pandas as pd


def adjust_ohlc(df: pd.DataFrame, adj: str = "backward") -> pd.DataFrame:
    """Adjust raw OHLC using adj_factor.

    - none: return raw
    - backward: normalize adj_factor to last available date per ts_code
    - forward: normalize to first available date per ts_code
    """
    out = df.copy()
    if adj == "none":
        out["open"] = out["open_raw"]
        out["high"] = out["high_raw"]
        out["low"] = out["low_raw"]
        out["close"] = out["close_raw"]
        return out

    if "adj_factor" not in out.columns or out["adj_factor"].isna().all():
        # no factors available; fall back to raw
        return adjust_ohlc(out, adj="none")

    def _normalize(group: pd.DataFrame) -> pd.DataFrame:
        g = group.sort_values("trade_date").copy()
        if adj == "backward":
            base = g["adj_factor"].ffill().bfill().iloc[-1]
        else:  # forward
            base = g["adj_factor"].ffill().bfill().iloc[0]
        scale = g["adj_factor"].ffill().bfill() / base
        for col_raw, col_adj in [
            ("open_raw", "open"),
            ("high_raw", "high"),
            ("low_raw", "low"),
            ("close_raw", "close"),
        ]:
            g[col_adj] = g[col_raw] * scale
        return g

    out = out.groupby("ts_code", group_keys=False).apply(_normalize)
    return out


def compute_ma(df: pd.DataFrame, window: int) -> pd.Series:
    return df["close"].rolling(window=window, min_periods=window).mean().rename(f"ma{window}")


def compute_vol_ann(df: pd.DataFrame, window: int) -> pd.Series:
    close = df["close"].astype(float)
    ret = close.pct_change()
    vol = ret.rolling(window=window, min_periods=window).std() * sqrt(252)
    return vol.rename("vol_ann")


