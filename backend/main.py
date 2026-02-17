"""DealHawk API entry point."""

import uvicorn
from backend.config.settings import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
