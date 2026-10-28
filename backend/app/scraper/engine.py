"""
backend/app/scraper/engine.py

Core scrape orchestrator – starts background jobs, tracks progress,
supports cancellation, and broadcasts real-time updates via WebSocket.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.database import create_job, update_job, insert_result, insert_log, get_job
from app.scraper.fetcher import fetch_page
from app.scraper.parser import parse_html
from app.scraper.extractor import extract_page
from app.ml.features import extract_features
from app.ml.nlp import analyze_text
from app.ml.classifier import predict_page

logger = logging.getLogger("scraper")

# Track active jobs so we can cancel them
_active_jobs: dict[str, asyncio.Event] = {}

# WebSocket subscribers (filled in by main.py)
ws_subscribers: set = set()


async def _broadcast(message: dict) -> None:
    """Send a JSON message to every connected WebSocket client."""
    global ws_subscribers
    if not ws_subscribers:
        return
    payload = json.dumps(message, default=str)
    dead: set = set()
    for ws in ws_subscribers:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    ws_subscribers -= dead


async def start_scrape_job(urls: list[str], config: dict | None = None) -> str:
    """Create a new job and start scraping in the background. Returns job_id."""
    job_id = str(uuid.uuid4())[:8]
    cancel_event = asyncio.Event()
    _active_jobs[job_id] = cancel_event

    job = {
        "id": job_id,
        "url": ", ".join(urls[:3]) + ("..." if len(urls) > 3 else ""),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": json.dumps(config or {}),
    }
    await create_job(job)

    # Run in background
    asyncio.create_task(_run_job(job_id, urls, cancel_event, config or {}))
    return job_id


async def stop_scrape_job(job_id: str) -> bool:
    """Signal a running job to stop. Returns True if the job existed."""
    if job_id in _active_jobs:
        _active_jobs[job_id].set()
        return True
    return False


async def _run_job(
    job_id: str,
    urls: list[str],
    cancel: asyncio.Event,
    config: dict,
) -> None:
    await update_job(job_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    await insert_log({"job_id": job_id, "level": "INFO",
                       "message": f"Starting scrape of {len(urls)} URLs"})
    await _broadcast({"type": "job_update", "job_id": job_id,
                       "status": "running", "total": len(urls),
                       "completed": 0, "failed": 0})

    sem = asyncio.Semaphore(config.get("max_concurrent", settings.max_concurrent))
    completed = 0
    failed = 0

    async def scrape_one(url: str) -> None:
        nonlocal completed, failed
        if cancel.is_set():
            return
        async with sem:
            if cancel.is_set():
                return
            try:
                html = await fetch_page(url)
                soup = parse_html(html)
                data = extract_page(soup)
                features = extract_features(soup, url)
                page_type = _classify_page(features)
                evidence = [name for name, value in features.get("numeric", {}).items()
                            if value and (name.startswith(("jsonld_", "og_is_", "kw_url_", "kw_text_")))]
                confidence = min(0.99, 0.50 + 0.12 * len(evidence)) if page_type != "other" else 0.35
                data["nlp"] = analyze_text(data.get("paragraphs", []), data.get("title") or "")
                classification = {
                    "label": page_type,
                    "confidence": round(confidence, 2),
                    "method": "rule-based estimate",
                    "evidence": evidence[:8],
                }
                page_text = " ".join([data.get("title") or "", data.get("description") or "", *data.get("paragraphs", [])])
                trained_prediction = predict_page(page_text)
                if trained_prediction:
                    classification = trained_prediction
                    page_type = trained_prediction["label"]
                data["classification"] = classification

                content_hash = hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()[:16]

                result = {
                    "job_id": job_id,
                    "url": url,
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "page_type": page_type,
                    "data": json.dumps(data),
                    "features": json.dumps(features),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "content_hash": content_hash,
                }
                await insert_result(result)
                completed += 1
                await insert_log({"job_id": job_id, "level": "INFO",
                                   "message": f"Scraped: {url}"})
            except Exception as e:
                failed += 1
                logger.warning("Failed %s: %s", url, e)
                await insert_log({"job_id": job_id, "level": "ERROR",
                                   "message": f"Failed {url}: {str(e)}"})

            await _broadcast({
                "type": "job_progress", "job_id": job_id,
                "total": len(urls), "completed": completed, "failed": failed,
            })

    tasks = [scrape_one(url) for url in urls]
    await asyncio.gather(*tasks, return_exceptions=True)

    status = "cancelled" if cancel.is_set() else "completed"
    await update_job(job_id, {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    await insert_log({"job_id": job_id, "level": "INFO",
                       "message": f"Job {status}. {completed} ok, {failed} failed."})
    await _broadcast({"type": "job_update", "job_id": job_id,
                       "status": status, "completed": completed, "failed": failed})
    _active_jobs.pop(job_id, None)


# --------------------------------------------------------------------------
# Rule-based classifier
# --------------------------------------------------------------------------

def _classify_page(features: dict) -> str:
    """Simple rule-based classifier using the feature data."""
    n = features.get("numeric", {})

    # Use structured data signals first
    if n.get("jsonld_product") or n.get("og_is_product") or n.get("has_itemprop_price"):
        return "product"
    if n.get("jsonld_article") or n.get("og_is_article") or n.get("has_article_published_time"):
        return "article"
    if n.get("jsonld_job"):
        return "job"
    if n.get("jsonld_profile") or n.get("og_is_profile"):
        return "profile"

    # Fall back to URL keywords
    if n.get("kw_url_product"):
        return "product"
    if n.get("kw_url_article"):
        return "article"
    if n.get("kw_url_job"):
        return "job"
    if n.get("kw_url_search"):
        return "search"
    if n.get("kw_url_forum"):
        return "forum"

    # Fall back to text keywords
    scores: dict[str, float] = {}
    for key in ["product", "article", "job", "forum", "search"]:
        scores[key] = n.get(f"kw_text_{key}", 0)
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return "other"
