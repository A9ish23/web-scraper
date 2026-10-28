"""
backend/app/scraper/fetcher.py

Fetches raw HTML for a URL. Async, with a browser-like User-Agent
(many sites block requests that don't send one) and basic error handling.

Enhanced with: retry with exponential backoff, per-domain rate limiting,
and robots.txt compliance.
"""

import asyncio
import logging
import time
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.scraper.robots import can_fetch

logger = logging.getLogger("scraper.fetcher")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Per-domain rate limiting
_domain_locks: dict[str, asyncio.Lock] = {}
_domain_last_request: dict[str, float] = {}


async def _rate_limit(domain: str) -> None:
    """Wait if needed to respect rate limiting for a domain."""
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()

    async with _domain_locks[domain]:
        last = _domain_last_request.get(domain, 0)
        elapsed = time.monotonic() - last
        delay = settings.rate_limit_delay
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        _domain_last_request[domain] = time.monotonic()


async def fetch_page(url: str) -> str:
    """
    Fetch a URL and return its raw HTML as a string.

    Includes:
    - Robots.txt compliance (configurable)
    - Per-domain rate limiting
    - Retry with exponential backoff
    - Configurable timeout

    Raises httpx.HTTPStatusError on 4xx/5xx responses,
    and httpx.RequestError on connection/timeout problems.
    """
    # Check robots.txt
    if settings.respect_robots_txt:
        allowed = await can_fetch(url, settings.user_agent)
        if not allowed:
            raise PermissionError(f"Blocked by robots.txt: {url}")

    domain = urlparse(url).netloc
    await _rate_limit(domain)

    last_error = None
    for attempt in range(settings.retry_attempts):
        try:
            async with httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=settings.request_timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc
            if attempt < settings.retry_attempts - 1:
                wait = settings.retry_backoff * (2 ** attempt)
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                    attempt + 1, settings.retry_attempts, url, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("All %d attempts failed for %s: %s",
                             settings.retry_attempts, url, exc)

    raise last_error
