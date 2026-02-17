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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
