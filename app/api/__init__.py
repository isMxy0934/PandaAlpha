from fastapi import APIRouter

from .routes import router as base_router

router = APIRouter()
router.include_router(base_router)

__all__ = ["router"]


