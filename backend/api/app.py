import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.api.auth_routes import auth_router
from backend.api.saved_routes import saved_router
from backend.api.alert_routes import alert_router
from backend.api.market_routes import market_router
from backend.api.dealer_routes import dealer_router
from backend.api.dealer_dashboard import dashboard_router
from backend.api.subscription_routes import subscription_router
from backend.api.webhook_routes import webhook_router
from backend.api.web_app import web_router
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
        version="0.5.0",
        **docs_kwargs,
    )

    # CORS for Chrome extension
    # chrome-extension:// origins are exactly 32 lowercase hex chars after the ://
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
        allow_origins=["http://localhost:3000", "https://dealhawk-api.onrender.com"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )

    # Static files for dashboard CSS
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(saved_router, prefix="/api/v1")
    app.include_router(alert_router, prefix="/api/v1")
    app.include_router(market_router, prefix="/api/v1")
    app.include_router(dealer_router, prefix="/api/v1")
    app.include_router(dashboard_router)
    app.include_router(subscription_router)
    app.include_router(webhook_router)
    app.include_router(web_router)  # Registered last to avoid prefix conflicts

    @app.get("/health", tags=["health"])
    def health_check():
        return {"status": "ok", "version": "0.5.0"}

    @app.on_event("startup")
    def on_startup():
        settings.validate_production()
        if not settings.is_deployed:
            init_db()  # Deployed envs use: alembic upgrade head in Dockerfile

    return app


app = create_app()
