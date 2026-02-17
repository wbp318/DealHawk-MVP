from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dealhawk.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # NHTSA VIN decoder (free, no key needed)
    nhtsa_base_url: str = "https://vpic.nhtsa.dot.gov/api"

    # CORS - allow Chrome extension
    cors_origins: list[str] = ["chrome-extension://*", "http://localhost:3000"]

    # JWT Authentication
    jwt_secret_key: str = "dealhawk-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_production(self) -> None:
        """Raise if production is using insecure defaults."""
        if self.is_production and self.jwt_secret_key == "dealhawk-dev-secret-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be changed from the default in production")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
