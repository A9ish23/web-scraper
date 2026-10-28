"""
backend/app/models/page.py

Pydantic models for request / response validation.
"""

from pydantic import BaseModel, Field
from typing import Any


# --------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="List of URLs to scrape")
    config: dict[str, Any] | None = Field(None, description="Per-job config overrides")


class SettingsUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    max_concurrent: int | None = None
    request_timeout: float | None = None
    retry_attempts: int | None = None
    retry_backoff: float | None = None
    rate_limit_delay: float | None = None
    respect_robots_txt: bool | None = None
    user_agent: str | None = None
    db_path: str | None = None
    log_level: str | None = None
    log_file: str | None = None


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------

class JobResponse(BaseModel):
    id: str
    url: str | None = None
    status: str
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    config: str | None = None


class ResultResponse(BaseModel):
    id: int
    job_id: str | None = None
    url: str | None = None
    title: str | None = None
    description: str | None = None
    page_type: str | None = None
    data: str | None = None
    features: str | None = None
    scraped_at: str | None = None
    content_hash: str | None = None


class LogEntry(BaseModel):
    id: int
    job_id: str | None = None
    level: str | None = None
    message: str | None = None
    timestamp: str | None = None


class StatsResponse(BaseModel):
    total_jobs: int = 0
    total_results: int = 0
    jobs_by_status: dict[str, int] = {}
    results_by_type: dict[str, int] = {}
    recent_jobs: list[dict[str, Any]] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
