from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.settings import settings


def create_app() -> FastAPI:
    application = FastAPI(title="PandaAlpha API", version="0.1.0")

    # CORS for local Next.js dev
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Routers
    application.include_router(api_router)

    return application


app = create_app()


