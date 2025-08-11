from fastapi import APIRouter

from app.datasource.watermark import read_watermarks

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


