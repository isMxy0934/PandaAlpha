from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


DATA_DIR = Path("data")
PARQUET_DIR = DATA_DIR / "parquet"
META_SQLITE = DATA_DIR / "meta.sqlite"
WATERMARK_PARQUET = DATA_DIR / "watermark.parquet"


@dataclass(frozen=True)
class PartitionPath:
    table: str
    dt: date

    def dir(self) -> Path:
        return PARQUET_DIR / self.table / f"year={self.dt.year:04d}" / f"month={self.dt.month:02d}" / f"day={self.dt.day:02d}"

    def file_pattern(self) -> str:
        return str(self.dir() / "part-*.parquet")

    def tmp_file(self) -> Path:
        return self.dir() / "part-0000.parquet.tmp"

    def final_file(self) -> Path:
        return self.dir() / "part-0000.parquet"


