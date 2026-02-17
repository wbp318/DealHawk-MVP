from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.database.db import init_db
from backend.config.settings import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DealHawk API",
        description="Vehicle deal scoring and negotiation intelligence",
        version="0.1.0",
    )

    # CORS for Chrome extension
    # chrome-extension:// origins are exactly 32 lowercase hex chars after the ://
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.on_event("startup")
    def on_startup():
        init_db()

    return app


app = create_app()
