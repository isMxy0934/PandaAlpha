"""Scheduler stubs for Phase A (A-0).

Real scheduling (APScheduler + SQLite jobstore) will be wired in Phase A-1.
This module provides placeholders to avoid coupling at import time.
"""

from __future__ import annotations

from typing import Any


def daily_job(*args: Any, **kwargs: Any) -> None:
    """Placeholder daily pipeline job to be implemented in A-1.

    Steps later: fetch -> write parquet -> update watermark.
    """


def get_jobs_status() -> list[dict[str, Any]]:
    """Return job status list for /api/status. Empty in A-0."""
    return []


