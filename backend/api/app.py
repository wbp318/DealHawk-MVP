from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.auth_routes import auth_router
from backend.api.saved_routes import saved_router
from backend.api.alert_routes import alert_router
from backend.database.db import init_db
from backend.config.settings import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    # Disable Swagger/ReDoc in production
    docs_kwargs = {}
    if settings.is_production:
        docs_kwargs = {"docs_url": None, "redoc_url": None}

    app = FastAPI(
        title="DealHawk API",
        description="Vehicle deal scoring and negotiation intelligence",
        version="0.2.0",
        **docs_kwargs,
    )

    # CORS for Chrome extension
    # chrome-extension:// origins are exactly 32 lowercase hex chars after the ://
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(saved_router, prefix="/api/v1")
    app.include_router(alert_router, prefix="/api/v1")

    @app.on_event("startup")
    def on_startup():
        settings.validate_production()
        init_db()

    return app


app = create_app()
