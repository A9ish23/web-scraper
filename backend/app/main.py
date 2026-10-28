"""
backend/app/main.py

Complete REST API for the web scraper with WebSocket support.
"""

import logging
import json
import os
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import (
    init_db, list_jobs, get_job, delete_job,
    list_results, get_result, count_results, export_results,
    list_logs, get_stats, save_result_label, get_labeled_results,
    save_search_judgment, get_search_judgments,
)
from app.logging_config import setup_logging
from app.models.page import (
    ScrapeRequest, SettingsUpdate,
    HealthResponse, StatsResponse,
)
from app.scraper.engine import start_scrape_job, stop_scrape_job, ws_subscribers
from app.ml.nlp import rank_semantically, evaluate_search_ranking
from app.ml.classifier import train_classifier, model_status

logger = logging.getLogger("scraper")

app = FastAPI(
    title="Web Scraper API",
    version="1.0.0",
    description="Production-ready web scraping backend with ML classification",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    setup_logging()
    logger.info("Initializing database...")
    await init_db()
    logger.info("Web Scraper API ready")


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

@app.post("/api/jobs")
async def create_job_endpoint(req: ScrapeRequest):
    job_id = await start_scrape_job(req.urls, req.config)
    return {"job_id": job_id, "status": "pending", "message": f"Scrape job started for {len(req.urls)} URL(s)"}


@app.get("/api/jobs")
async def list_jobs_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
):
    jobs = await list_jobs(limit=limit, offset=offset, status_filter=status)
    return {"jobs": jobs, "limit": limit, "offset": offset}


@app.get("/api/jobs/{job_id}")
async def get_job_endpoint(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/stop")
async def stop_job_endpoint(job_id: str):
    stopped = await stop_scrape_job(job_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Job not found or already finished")
    return {"message": f"Job {job_id} stop signal sent"}


@app.delete("/api/jobs/{job_id}")
async def delete_job_endpoint(job_id: str):
    deleted = await delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": f"Job {job_id} and associated data deleted"}


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@app.get("/api/results")
async def list_results_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    sort_by: str = Query("scraped_at"),
    sort_order: str = Query("desc"),
    page_type: str | None = Query(None),
    semantic: bool = Query(False),
):
    if semantic and search:
        candidates = await list_results(limit=10000, offset=0, page_type_filter=page_type)
        try:
            ranked = await run_in_threadpool(rank_semantically, candidates, search)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        total = len(ranked)
        return {"results": ranked[offset:offset + limit], "total": total, "limit": limit, "offset": offset}
    results = await list_results(
        limit=limit, offset=offset, search=search,
        sort_by=sort_by, sort_order=sort_order,
        page_type_filter=page_type,
    )
    total = await count_results(search=search, page_type_filter=page_type)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@app.post("/api/results/{result_id}/label")
async def label_result_endpoint(result_id: int, payload: dict):
    label = str(payload.get("label", "")).strip().lower()
    split = str(payload.get("split", "train")).strip().lower()
    allowed = {"article", "product", "job", "profile", "forum", "search", "other"}
    if label not in allowed:
        raise HTTPException(status_code=422, detail=f"Choose one of: {', '.join(sorted(allowed))}")
    if split not in {"train", "evaluation"}:
        raise HTTPException(status_code=422, detail="Split must be 'train' or 'evaluation'")
    if not await save_result_label(result_id, label, split):
        raise HTTPException(status_code=404, detail="Result not found")
    return {"result_id": result_id, "label": label, "split": split, "message": "Label saved to the selected dataset split."}


@app.post("/api/results/{result_id}/search-judgment")
async def search_judgment_endpoint(result_id: int, payload: dict):
    query = str(payload.get("query", "")).strip()
    relevance = payload.get("relevance")
    if not query:
        raise HTTPException(status_code=422, detail="A search query is required")
    if not isinstance(relevance, int) or relevance not in range(4):
        raise HTTPException(status_code=422, detail="Relevance must be an integer from 0 to 3")
    if not await save_search_judgment(query, result_id, relevance):
        raise HTTPException(status_code=404, detail="Result not found")
    return {"result_id": result_id, "query": query, "relevance": relevance}


@app.post("/api/ml/train")
async def train_classifier_endpoint():
    records = await get_labeled_results("train")
    evaluation_records = await get_labeled_results("evaluation")
    try:
        outcome = await run_in_threadpool(train_classifier, records, evaluation_records)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Model training requires scikit-learn and joblib. Install backend requirements and restart the API.") from exc
    return {**outcome, "model": model_status()}


@app.get("/api/ml/status")
async def ml_status_endpoint():
    records = await get_labeled_results()
    counts = {}
    for record in records:
        split_counts = counts.setdefault(record["split"], {})
        split_counts[record["label"]] = split_counts.get(record["label"], 0) + 1
    return {**model_status(), "labeled_examples": len(records), "label_counts": counts}


@app.get("/api/ml/search-evaluation")
async def search_evaluation_endpoint(query: str = Query(..., min_length=1)):
    judgments = await get_search_judgments(query)
    if not judgments:
        return {"measured": False, "query": query, "message": "Rate search results for this exact query before calculating metrics."}
    candidates = await list_results(limit=10000, offset=0)
    try:
        ranked = await run_in_threadpool(rank_semantically, candidates, query)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"measured": True, "query": query, **evaluate_search_ranking(ranked, judgments, k=10)}


@app.get("/api/results/export/{fmt}")
async def export_results_endpoint(
    fmt: str,
    search: str | None = Query(None),
    page_type: str | None = Query(None),
):
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")
    data = await export_results(fmt=fmt, search=search, page_type_filter=page_type)
    if fmt == "csv":
        return PlainTextResponse(data, media_type="text/csv", headers={
            "Content-Disposition": "attachment; filename=results.csv"
        })
    return JSONResponse(content=json.loads(data), headers={
        "Content-Disposition": "attachment; filename=results.json"
    })


@app.get("/api/results/{result_id}")
async def get_result_endpoint(result_id: int):
    result = await get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


# --------------------------------------------------------------------------
# Logs
# --------------------------------------------------------------------------

@app.get("/api/logs")
async def list_logs_endpoint(
    job_id: str | None = Query(None),
    level: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    logs = await list_logs(job_id=job_id, level=level, limit=limit, offset=offset)
    return {"logs": logs, "limit": limit, "offset": offset}


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------

@app.get("/api/stats", response_model=StatsResponse)
async def stats_endpoint():
    return await get_stats()


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    return settings.model_dump()


@app.put("/api/settings")
async def update_settings(updates: SettingsUpdate):
    # Load current config
    config_path = os.environ.get("SCRAPER_CONFIG", "config.yaml")
    current: dict = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            current = yaml.safe_load(f) or {}

    # Apply non-None updates
    changed = updates.model_dump(exclude_none=True)
    current.update(changed)

    # Save to YAML
    with open(config_path, "w") as f:
        yaml.dump(current, f, default_flow_style=False)

    # Apply to in-memory settings
    for k, v in changed.items():
        if hasattr(settings, k):
            object.__setattr__(settings, k, v)

    return {"message": "Settings updated. Some changes may require restart.", "settings": settings.model_dump()}


# --------------------------------------------------------------------------
# WebSocket
# --------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_subscribers.add(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_subscribers.discard(websocket)


# --------------------------------------------------------------------------
# Serve built React frontend (catch-all — must be LAST)
# --------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _setup_static() -> None:
    """Mount the built React app if the dist/ folder exists."""
    if _FRONTEND_DIST.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # Serve index.html for all non-API paths so React Router works
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

        logger.info("Serving React UI from %s", _FRONTEND_DIST)


_setup_static()
