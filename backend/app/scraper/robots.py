"""
backend/app/scraper/robots.py

Async robots.txt checker with per-origin caching.
"""

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

_cache: dict[str, RobotFileParser] = {}
_lock = asyncio.Lock()


async def can_fetch(url: str, user_agent: str) -> bool:
    """Check whether *user_agent* is allowed to fetch *url* per robots.txt."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async with _lock:
        if robots_url not in _cache:
            rp = RobotFileParser()
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(robots_url)
                    rp.parse(resp.text.splitlines())
            except Exception:
                rp.parse([])  # Allow all if can't fetch robots.txt
            _cache[robots_url] = rp

    return _cache[robots_url].can_fetch(user_agent, url)
