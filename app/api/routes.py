from fastapi import APIRouter

from datetime import date
from typing import Optional

from fastapi import Query, Response

from app.datasource.watermark import read_watermarks
from app.datasource.readers import read_prices_and_adj, read_daily_basic
from app.metrics.core import adjust_ohlc, compute_ma, compute_vol_ann
import pandas as pd
from .watchlist_store import get_watchlist as wl_get, set_watchlist as wl_set
from .utils import normalize_ts_codes, compute_etag
from app.datasource.sqlite_meta import list_jobs

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


@router.get("/api/status")
def get_status() -> dict[str, list]:
    # 返回当前水位线与作业列表（作业留空直到接入 APScheduler）
    wms = [
        {
            "table": r.table,
            "last_dt": r.last_dt.isoformat(),
            "rowcount": r.rowcount,
            "hash": r.hash,
        }
        for r in read_watermarks()
    ]
    return {"watermarks": wms, "jobs": list_jobs()}


@router.get("/api/prices")
def get_prices(
    ts_code: str = Query(..., description="逗号分隔可多值"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    adj: str = "backward",
    include_basic: bool = False,
    response: Response = None,
) -> dict:
    ts_codes = normalize_ts_codes(ts_code)
    if not ts_codes:
        return {"error": {"code": "InvalidParam", "message": "ts_code 必填"}}
    if adj not in ("none", "forward", "backward"):
        return {"error": {"code": "InvalidParam", "message": "adj 仅支持 none|forward|backward"}}

    prices = read_prices_and_adj(ts_codes, start, end)
    if prices.empty:
        return {"adj": adj, "rows": []}
    prices = adjust_ohlc(prices, adj=adj)

    if include_basic:
        basic = read_daily_basic(ts_codes, start, end)[["ts_code", "trade_date", "turnover_rate"]]
        prices = prices.merge(basic, on=["ts_code", "trade_date"], how="left")

    prices = prices.sort_values(["ts_code", "trade_date"])  # ensure order
    def to_float(v):
        return float(v) if pd.notna(v) else None
    result_rows = []
    for rec in prices.to_dict(orient="records"):
        row = {
            "ts_code": rec["ts_code"],
            "trade_date": rec["trade_date"].isoformat() if rec.get("trade_date") else None,
            "open": to_float(rec.get("open")),
            "high": to_float(rec.get("high")),
            "low": to_float(rec.get("low")),
            "close": to_float(rec.get("close")),
            "volume": int(rec["volume"]) if rec.get("volume") is not None and pd.notna(rec.get("volume")) else None,
            "amount": to_float(rec.get("amount")),
        }
        if include_basic and "turnover_rate" in rec:
            row["turnover_rate"] = to_float(rec.get("turnover_rate"))
        result_rows.append(row)
    resp = {"adj": adj, "rows": result_rows}
    # Cache headers
    etag = compute_etag({
        "path": "/api/prices",
        "ts_code": ts_codes,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "adj": adj,
        "include_basic": include_basic,
    })
    if response is not None:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "max-age=300"
    return resp


@router.get("/api/metrics")
def get_metrics(
    ts_code: str,
    window: int = 20,
    metrics: str = "ma,vol_ann,turnover",
    start: Optional[date] = None,
    end: Optional[date] = None,
    response: Response = None,
) -> dict:
    ts_code = ts_code.strip()
    if not ts_code:
        return {"error": {"code": "InvalidParam", "message": "ts_code 必填"}}
    wanted = {m.strip() for m in metrics.split(",") if m.strip()}
    prices = read_prices_and_adj([ts_code], start, end)
    if prices.empty:
        return {"ts_code": ts_code, "rows": []}
    prices = adjust_ohlc(prices, adj="backward").sort_values("trade_date")

    out = pd.DataFrame({"trade_date": prices["trade_date"].apply(lambda d: d.isoformat())})
    if any(m.startswith("ma") for m in wanted) or "ma" in wanted:
        out[f"ma{window}"] = compute_ma(prices, window)
    if "vol_ann" in wanted:
        out["vol_ann"] = compute_vol_ann(prices, window)
    if "turnover" in wanted:
        basic = read_daily_basic([ts_code], start, end)[["trade_date", "turnover_rate"]].sort_values("trade_date")
        out = out.merge(basic.assign(trade_date=basic["trade_date"].apply(lambda d: d.isoformat())), on="trade_date", how="left")
        out.rename(columns={"turnover_rate": "turnover"}, inplace=True)

    # drop all-NaN columns except trade_date
    cols = [c for c in out.columns if c == "trade_date" or out[c].notna().any()]
    out = out[cols]
    rows = out.to_dict(orient="records")
    resp = {"ts_code": ts_code, "rows": rows}
    etag = compute_etag({
        "path": "/api/metrics",
        "ts_code": ts_code,
        "window": window,
        "metrics": sorted(list(wanted)),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    })
    if response is not None:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "max-age=300"
    return resp


@router.get("/api/watchlist")
def list_watchlist(page: int = 1, limit: int = 50) -> dict:
    return wl_get(page=page, limit=limit)


@router.post("/api/watchlist")
def update_watchlist(body: dict) -> dict:
    codes = body.get("ts_codes", [])
    if not isinstance(codes, list):
        return {"error": {"code": "InvalidParam", "message": "ts_codes 必须为数组"}}
    wl_set(codes)
    return {"ok": True}


