from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_parquet_atomic(df: pd.DataFrame, dest_tmp: Path, dest_final: Path) -> int:
    """Write DataFrame to dest_tmp then atomically rename to dest_final.

    Returns
    -------
    int
        Number of rows written.
    """
    _ensure_parent(dest_tmp)

    table = pa.Table.from_pandas(df)
    pq.write_table(
        table,
        dest_tmp,
        compression="zstd",
        use_dictionary=True,
        data_page_size=1024 * 1024,
        write_statistics=True,
    )

    # Atomic rename
    dest_tmp.replace(dest_final) if dest_final.exists() else dest_tmp.rename(dest_final)

    return len(df)


