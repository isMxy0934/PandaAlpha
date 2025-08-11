from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


@router.get("/api/status")
def get_status() -> dict[str, list]:
    # A-0: 返回空水位线与作业列表，占位
    return {"watermarks": [], "jobs": []}


