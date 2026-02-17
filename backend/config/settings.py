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

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""

    # MarketCheck API
    marketcheck_api_key: str = ""
    marketcheck_base_url: str = "https://mc-api.marketcheck.com/v2"
    marketcheck_cache_ttl_hours: int = 24

    # Dealership API
    dealer_api_key_salt: str = "dealhawk-dealer-key-salt"

    # Base URL for Stripe redirect URLs (success/cancel pages)
    base_url: str = ""

    # Redis / Celery
    redis_url: str = ""
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # Email
    email_provider: str = "smtp"  # "smtp" or "sendgrid"
    sendgrid_api_key: str = ""
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from_address: str = "noreply@dealhawk.app"
    email_from_name: str = "DealHawk"

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def effective_celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url or "memory://"

    @property
    def effective_celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url or "cache+memory://"

    def validate_production(self) -> None:
        """Raise if production is using insecure defaults."""
        if self.is_production and self.jwt_secret_key == "dealhawk-dev-secret-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be changed from the default in production")
        if self.is_production and not self.stripe_secret_key:
            raise ValueError("STRIPE_SECRET_KEY must be set in production")
        if self.is_production and not self.stripe_webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET must be set in production")
        if self.is_production and not self.stripe_pro_price_id:
            raise ValueError("STRIPE_PRO_PRICE_ID must be set in production")
        if self.is_production and not self.base_url:
            raise ValueError("BASE_URL must be set in production (e.g. https://api.dealhawk.app)")
        if self.is_production and self.dealer_api_key_salt == "dealhawk-dealer-key-salt":
            raise ValueError("DEALER_API_KEY_SALT must be changed from the default in production")
        if self.is_production and not self.redis_url:
            raise ValueError("REDIS_URL must be set in production")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
