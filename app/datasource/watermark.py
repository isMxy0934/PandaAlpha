from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .paths import WATERMARK_PARQUET


@dataclass
class WatermarkRow:
    table: str
    last_dt: date
    rowcount: int
    hash: str


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_watermarks() -> list[WatermarkRow]:
    if not WATERMARK_PARQUET.exists():
        return []
    table = pq.read_table(WATERMARK_PARQUET)
    df = table.to_pandas()
    rows: list[WatermarkRow] = []
    for _, r in df.iterrows():
        rows.append(
            WatermarkRow(
                table=str(r["table"]),
                last_dt=pd.to_datetime(r["last_dt"]).date(),
                rowcount=int(r["rowcount"]),
                hash=str(r["hash"]),
            )
        )
    return rows


def upsert_watermark(row: WatermarkRow) -> None:
    existing = read_watermarks()
    by_table = {r.table: r for r in existing}
    by_table[row.table] = row
    df = pd.DataFrame(
        [
            {
                "table": r.table,
                "last_dt": pd.Timestamp(r.last_dt),
                "rowcount": r.rowcount,
                "hash": r.hash,
            }
            for r in by_table.values()
        ]
    )
    _ensure_parent(WATERMARK_PARQUET)
    pq.write_table(pa.Table.from_pandas(df), WATERMARK_PARQUET)


