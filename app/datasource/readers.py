from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

import pandas as pd
import pyarrow.dataset as ds

from .paths import PARQUET_DIR


def _dataset(table: str) -> ds.Dataset:
    return ds.dataset(str(PARQUET_DIR / table), format="parquet", partitioning="hive")


def _filter_date_range(start: Optional[date], end: Optional[date]):
    filters = []
    if start is not None:
        filters.append(("trade_date", ">=", pd.Timestamp(start).date()))
    if end is not None:
        filters.append(("trade_date", "<=", pd.Timestamp(end).date()))
    return filters if filters else None


def read_prices_and_adj(
    ts_codes: Optional[list[str]],
    start: Optional[date],
    end: Optional[date],
) -> pd.DataFrame:
    try:
        prices_ds = _dataset("prices_daily")
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount","adj_factor"
        ])
    filters = _filter_date_range(start, end)
    table = prices_ds.to_table(filter=filters, columns=[
        "ts_code","trade_date","open_raw","high_raw","low_raw","close_raw","pre_close","volume","amount"
    ])
    prices = table.to_pandas()
    if ts_codes:
        prices = prices[prices["ts_code"].isin(ts_codes)]

    try:
        adj_ds = _dataset("adj_factor")
        adj_table = adj_ds.to_table(filter=filters, columns=["ts_code","trade_date","adj_factor"])
        adj = adj_table.to_pandas()
    except Exception:
        # dataset may not exist yet
        adj = pd.DataFrame(columns=["ts_code","trade_date","adj_factor"])

    if not adj.empty:
        prices = prices.merge(adj, on=["ts_code","trade_date"], how="left")
    else:
        prices["adj_factor"] = pd.NA

    return prices


def read_daily_basic(
    ts_codes: Optional[list[str]],
    start: Optional[date],
    end: Optional[date],
) -> pd.DataFrame:
    try:
        basic_ds = _dataset("daily_basic")
    except Exception:
        return pd.DataFrame(columns=["ts_code","trade_date","turnover_rate","pe","pe_ttm","pb","ps","total_mv","circ_mv"])
    filters = _filter_date_range(start, end)
    table = basic_ds.to_table(filter=filters)
    df = table.to_pandas()
    if ts_codes:
        df = df[df["ts_code"].isin(ts_codes)]
    return df


