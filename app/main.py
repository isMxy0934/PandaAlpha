from fastapi import FastAPI

from app.api import router as api_router
from app.settings import settings


def create_app() -> FastAPI:
    application = FastAPI(title="PandaAlpha API", version="0.1.0")

    # Routers
    application.include_router(api_router)

    return application


app = create_app()


