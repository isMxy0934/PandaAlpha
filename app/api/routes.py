from fastapi import APIRouter

from datetime import date
from typing import Optional

from fastapi import Query

from app.datasource.watermark import read_watermarks
from app.datasource.readers import read_prices_and_adj, read_daily_basic
from app.metrics.core import adjust_ohlc, compute_ma, compute_vol_ann

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
    return {"watermarks": wms, "jobs": []}


@router.get("/api/prices")
def get_prices(
    ts_code: str = Query(..., description="逗号分隔可多值"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    adj: str = "backward",
    include_basic: bool = False,
) -> dict:
    ts_codes = sorted({c.strip() for c in ts_code.split(",") if c.strip()})
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
    cols = ["ts_code","trade_date","open","high","low","close","volume","amount"]
    if include_basic:
        cols.append("turnover_rate")
    rows = [
        {**{k: (v.isoformat() if k == "trade_date" else (float(v) if pd.notna(v) else None)) for k, v in r.items()}}
        for r in prices[cols].to_dict(orient="records")
    ]
    return {"adj": adj, "rows": rows}


@router.get("/api/metrics")
def get_metrics(
    ts_code: str,
    window: int = 20,
    metrics: str = "ma,vol_ann,turnover",
    start: Optional[date] = None,
    end: Optional[date] = None,
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
    return {"ts_code": ts_code, "rows": rows}


