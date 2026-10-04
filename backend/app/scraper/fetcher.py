"""
backend/app/scraper/fetcher.py

Fetches raw HTML for a URL. Async, with a browser-like User-Agent
(many sites block requests that don't send one) and basic error handling.
"""

import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 15.0  # seconds


async def fetch_page(url: str) -> str:
    """
    Fetch a URL and return its raw HTML as a string.
    Raises httpx.HTTPStatusError on 4xx/5xx responses,
    and httpx.RequestError on connection/timeout problems.
    """
    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text