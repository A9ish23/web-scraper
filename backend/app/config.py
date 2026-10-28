"""
backend/app/config.py

Pydantic Settings config that reads from config.yaml (falling back to env vars).
"""

from pydantic_settings import BaseSettings
from pydantic import Field
import yaml
import os


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Scraper
    max_concurrent: int = 5
    request_timeout: float = 15.0
    retry_attempts: int = 3
    retry_backoff: float = 1.0
    rate_limit_delay: float = 1.0  # seconds between requests to same domain
    respect_robots_txt: bool = True
    user_agent: str = "WebScraper/1.0 (+https://github.com/example/scraper)"

    # Database
    db_path: str = "data/scraper.db"

    # Logging
    log_level: str = "INFO"
    log_file: str = "data/scraper.log"

    model_config = {"env_prefix": "SCRAPER_"}


def load_settings() -> Settings:
    """Load from config.yaml if exists, then overlay env vars."""
    config_path = os.environ.get("SCRAPER_CONFIG", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return Settings(**data)
    return Settings()


settings = load_settings()
