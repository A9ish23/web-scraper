"""
backend/app/database.py

Async SQLite database layer using aiosqlite.
All timestamps are UTC ISO-8601.
"""

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import settings

_db: aiosqlite.Connection | None = None


async def _get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

async def init_db() -> None:
    """Create tables if they do not exist."""
    db = await _get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS scrape_jobs (
            id          TEXT PRIMARY KEY,
            url         TEXT,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT,
            started_at  TEXT,
            completed_at TEXT,
            error       TEXT,
            config      JSON
        );

        CREATE TABLE IF NOT EXISTS scrape_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id       TEXT,
            url          TEXT,
            title        TEXT,
            description  TEXT,
            page_type    TEXT,
            data         JSON,
            features     JSON,
            scraped_at   TEXT,
            content_hash TEXT UNIQUE,
            FOREIGN KEY (job_id) REFERENCES scrape_jobs(id)
        );

        CREATE TABLE IF NOT EXISTS scrape_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id    TEXT,
            level     TEXT,
            message   TEXT,
            timestamp TEXT,
            FOREIGN KEY (job_id) REFERENCES scrape_jobs(id)
        );

        CREATE TABLE IF NOT EXISTS result_labels (
            result_id INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            split TEXT NOT NULL DEFAULT 'train',
            created_at TEXT NOT NULL,
            FOREIGN KEY (result_id) REFERENCES scrape_results(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS search_judgments (
            query_key TEXT NOT NULL,
            query TEXT NOT NULL,
            result_id INTEGER NOT NULL,
            relevance INTEGER NOT NULL CHECK (relevance BETWEEN 0 AND 3),
            created_at TEXT NOT NULL,
            PRIMARY KEY (query_key, result_id),
            FOREIGN KEY (result_id) REFERENCES scrape_results(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS app_migrations (
            name TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_results_job ON scrape_results(job_id);
        CREATE INDEX IF NOT EXISTS idx_results_type ON scrape_results(page_type);
        CREATE INDEX IF NOT EXISTS idx_logs_job ON scrape_logs(job_id);
    """)
    async with db.execute("PRAGMA table_info(result_labels)") as cur:
        label_columns = {row["name"] for row in await cur.fetchall()}
    if "split" not in label_columns:
        await db.execute("ALTER TABLE result_labels ADD COLUMN split TEXT NOT NULL DEFAULT 'train'")
    await db.commit()
    await _backfill_language_analysis(db)


async def _backfill_language_analysis(db: aiosqlite.Connection) -> None:
    """Add the new analysis to saved rows that already contain extracted text."""
    async with db.execute("SELECT 1 FROM app_migrations WHERE name = 'nlp_analysis_v1'") as cur:
        if await cur.fetchone():
            return
    from app.ml.nlp import analyze_text

    async with db.execute("SELECT id, title, data FROM scrape_results WHERE data IS NOT NULL") as cur:
        rows = await cur.fetchall()
    for row in rows:
        try:
            data = json.loads(row["data"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if "nlp" not in data:
            data["nlp"] = analyze_text(data.get("paragraphs", []), row["title"] or data.get("title") or "")
            await db.execute("UPDATE scrape_results SET data = ? WHERE id = ?", (json.dumps(data), row["id"]))
    await db.execute("INSERT INTO app_migrations (name, completed_at) VALUES (?, ?)",
                     ("nlp_analysis_v1", datetime.now(timezone.utc).isoformat()))
    await db.commit()


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

async def create_job(job: dict) -> None:
    db = await _get_db()
    await db.execute(
        "INSERT INTO scrape_jobs (id, url, status, created_at, config) VALUES (?, ?, ?, ?, ?)",
        (job["id"], job.get("url"), job.get("status", "pending"),
         job.get("created_at"), job.get("config")),
    )
    await db.commit()


async def get_job(job_id: str) -> dict | None:
    db = await _get_db()
    async with db.execute("SELECT * FROM scrape_jobs WHERE id = ?", (job_id,)) as cur:
        row = await cur.fetchone()
        if row is None:
            return None
        return dict(row)


async def update_job(job_id: str, updates: dict) -> None:
    db = await _get_db()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [job_id]
    await db.execute(f"UPDATE scrape_jobs SET {sets} WHERE id = ?", vals)
    await db.commit()


async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
) -> list[dict]:
    db = await _get_db()
    query = "SELECT * FROM scrape_jobs"
    params: list[Any] = []
    if status_filter:
        query += " WHERE status = ?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    async with db.execute(query, params) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def delete_job(job_id: str) -> bool:
    db = await _get_db()
    await db.execute("DELETE FROM scrape_logs WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM scrape_results WHERE job_id = ?", (job_id,))
    cur = await db.execute("DELETE FROM scrape_jobs WHERE id = ?", (job_id,))
    await db.commit()
    return cur.rowcount > 0


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

async def insert_result(result: dict) -> int | None:
    """Insert a scrape result. Silently skips duplicates (same content_hash)."""
    db = await _get_db()
    try:
        cur = await db.execute(
            """INSERT INTO scrape_results
               (job_id, url, title, description, page_type, data, features, scraped_at, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["job_id"], result["url"], result.get("title"),
             result.get("description"), result.get("page_type"),
             result.get("data"), result.get("features"),
             result.get("scraped_at"), result.get("content_hash")),
        )
        await db.commit()
        return cur.lastrowid
    except aiosqlite.IntegrityError:
        # Duplicate content_hash – skip
        return None


async def list_results(
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    sort_by: str = "scraped_at",
    sort_order: str = "desc",
    page_type_filter: str | None = None,
) -> list[dict]:
    db = await _get_db()
    allowed_sort = {"scraped_at", "title", "url", "page_type", "id"}
    if sort_by not in allowed_sort:
        sort_by = "scraped_at"
    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    query = "SELECT * FROM scrape_results WHERE 1=1"
    params: list[Any] = []

    if search:
        query += " AND (title LIKE ? OR url LIKE ? OR description LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if page_type_filter:
        query += " AND page_type = ?"
        params.append(page_type_filter)

    query += f" ORDER BY {sort_by} {order} LIMIT ? OFFSET ?"
    params += [limit, offset]

    async with db.execute(query, params) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_result(result_id: int) -> dict | None:
    db = await _get_db()
    async with db.execute("SELECT * FROM scrape_results WHERE id = ?", (result_id,)) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def save_result_label(result_id: int, label: str, split: str = "train") -> bool:
    db = await _get_db()
    async with db.execute("SELECT 1 FROM scrape_results WHERE id = ?", (result_id,)) as cur:
        if not await cur.fetchone():
            return False
    await db.execute(
        "INSERT INTO result_labels (result_id, label, split, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(result_id) DO UPDATE SET label=excluded.label, split=excluded.split, created_at=excluded.created_at",
        (result_id, label, split, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    return True


async def get_labeled_results(split: str | None = None) -> list[dict]:
    db = await _get_db()
    async with db.execute(
        "SELECT r.title, r.description, r.data, l.label, l.split FROM result_labels l "
        "JOIN scrape_results r ON r.id = l.result_id "
        + ("WHERE l.split = ? " if split else "") + "ORDER BY l.created_at",
        ((split,) if split else ()),
    ) as cur:
        records = []
        for row in await cur.fetchall():
            item = dict(row)
            try:
                data = json.loads(item.get("data") or "{}")
            except (TypeError, json.JSONDecodeError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            paragraphs = data.get("paragraphs") or []
            if not isinstance(paragraphs, list):
                paragraphs = []
            item["text"] = " ".join([item.get("title") or "", item.get("description") or "",
                                     *(paragraph for paragraph in paragraphs if isinstance(paragraph, str))])
            records.append(item)
        return records


async def save_search_judgment(query: str, result_id: int, relevance: int) -> bool:
    query_key = " ".join(query.casefold().split())
    if not query_key:
        return False
    db = await _get_db()
    async with db.execute("SELECT 1 FROM scrape_results WHERE id = ?", (result_id,)) as cur:
        if not await cur.fetchone():
            return False
    await db.execute(
        "INSERT INTO search_judgments (query_key, query, result_id, relevance, created_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(query_key, result_id) DO UPDATE SET query=excluded.query, relevance=excluded.relevance, created_at=excluded.created_at",
        (query_key, query.strip(), result_id, relevance, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    return True


async def get_search_judgments(query: str) -> list[dict]:
    query_key = " ".join(query.casefold().split())
    db = await _get_db()
    async with db.execute(
        "SELECT j.result_id, j.relevance, r.title, r.url, r.description, r.data, r.page_type, r.scraped_at, r.content_hash "
        "FROM search_judgments j JOIN scrape_results r ON r.id = j.result_id "
        "WHERE j.query_key = ? ORDER BY j.result_id",
        (query_key,),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def count_results(
    search: str | None = None,
    page_type_filter: str | None = None,
) -> int:
    db = await _get_db()
    query = "SELECT COUNT(*) FROM scrape_results WHERE 1=1"
    params: list[Any] = []
    if search:
        query += " AND (title LIKE ? OR url LIKE ? OR description LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if page_type_filter:
        query += " AND page_type = ?"
        params.append(page_type_filter)
    async with db.execute(query, params) as cur:
        row = await cur.fetchone()
        return row[0]


async def delete_results(job_id: str) -> int:
    db = await _get_db()
    cur = await db.execute("DELETE FROM scrape_results WHERE job_id = ?", (job_id,))
    await db.commit()
    return cur.rowcount


# --------------------------------------------------------------------------
# Logs
# --------------------------------------------------------------------------

async def insert_log(log: dict) -> None:
    db = await _get_db()
    await db.execute(
        "INSERT INTO scrape_logs (job_id, level, message, timestamp) VALUES (?, ?, ?, ?)",
        (log.get("job_id"), log.get("level", "INFO"), log.get("message"),
         log.get("timestamp", datetime.now(timezone.utc).isoformat())),
    )
    await db.commit()


async def list_logs(
    job_id: str | None = None,
    level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    db = await _get_db()
    query = "SELECT * FROM scrape_logs WHERE 1=1"
    params: list[Any] = []
    if job_id:
        query += " AND job_id = ?"
        params.append(job_id)
    if level:
        query += " AND level = ?"
        params.append(level.upper())
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    async with db.execute(query, params) as cur:
        return [dict(r) for r in await cur.fetchall()]


# --------------------------------------------------------------------------
# Stats & Export
# --------------------------------------------------------------------------

async def get_stats() -> dict:
    db = await _get_db()
    stats: dict[str, Any] = {}

    async with db.execute("SELECT COUNT(*) FROM scrape_jobs") as cur:
        stats["total_jobs"] = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM scrape_results") as cur:
        stats["total_results"] = (await cur.fetchone())[0]
    async with db.execute(
        "SELECT status, COUNT(*) FROM scrape_jobs GROUP BY status"
    ) as cur:
        stats["jobs_by_status"] = {r[0]: r[1] for r in await cur.fetchall()}
    async with db.execute(
        "SELECT page_type, COUNT(*) FROM scrape_results GROUP BY page_type"
    ) as cur:
        stats["results_by_type"] = {r[0]: r[1] for r in await cur.fetchall()}
    async with db.execute(
        "SELECT * FROM scrape_jobs ORDER BY created_at DESC LIMIT 5"
    ) as cur:
        stats["recent_jobs"] = [dict(r) for r in await cur.fetchall()]

    return stats


async def export_results(
    fmt: str = "json",
    search: str | None = None,
    page_type_filter: str | None = None,
) -> str:
    """Return a clean, human-readable JSON or CSV export."""
    rows = await list_results(
        limit=10000, offset=0,
        search=search, page_type_filter=page_type_filter,
    )
    export_rows = []
    for row in rows:
        try:
            data = json.loads(row.get("data") or "{}")
        except (TypeError, json.JSONDecodeError):
            data = {}
        headings = data.get("headings") or []
        paragraphs = data.get("paragraphs") or []
        links = data.get("links") or []
        images = data.get("images") or []
        page_url = row.get("url") or ""
        export_rows.append({
            "title": row.get("title") or data.get("title") or "",
            "url": page_url,
            "page_type": row.get("page_type") or "unknown",
            "description": row.get("description") or data.get("description") or "",
            "scraped_at": row.get("scraped_at") or "",
            "page_metadata": {
                "author": data.get("author"),
                "published_at": data.get("published_at"),
                "site_name": data.get("site_name"),
                "canonical_url": data.get("canonical_url"),
                "language": data.get("language"),
            },
            "classification": data.get("classification", {}),
            "language_analysis": data.get("nlp", {}),
            "content": "\n\n".join(paragraphs),
            "headings": headings,
            "links": links,
            "images": images,
            "content_summary": {
                "heading_count": len(headings),
                "paragraph_count": len(paragraphs),
                "link_count": len(links),
                "image_count": len(images),
            },
        })
    if fmt == "csv":
        output = io.StringIO(newline="")
        fields = ["title", "url", "page_type", "description", "scraped_at", "page_metadata",
                  "summary", "topics", "sentiment", "entities", "classification_confidence",
                  "classification_method", "classification_signals", "content",
                  "headings", "links", "images", "content_summary"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in export_rows:
            writer.writerow({
                **row,
                "headings": "\n".join(f"{item.get('tag', '')}: {item.get('text', '')}" for item in row["headings"]),
                "page_metadata": "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in row["page_metadata"].items() if value),
                "summary": row["language_analysis"].get("summary", ""),
                "topics": ", ".join(row["language_analysis"].get("topics", [])),
                "sentiment": row["language_analysis"].get("sentiment", {}).get("label", ""),
                "entities": "; ".join(f"{item['text']} ({item['type']})" for item in row["language_analysis"].get("entities", [])),
                "classification_confidence": row["classification"].get("confidence", ""),
                "classification_method": row["classification"].get("method", ""),
                "classification_signals": ", ".join(row["classification"].get("evidence", [])),
                "links": "\n".join(f"{item.get('text') or item.get('url', '')} — {item.get('url', '')}" for item in row["links"]),
                "images": "\n".join(f"{item.get('alt') or 'Image'} — {item.get('src', '')}" for item in row["images"]),
                "content_summary": "; ".join(f"{key.replace('_count', '').replace('_', ' ')}: {value}"
                                               for key, value in row["content_summary"].items()),
            })
        return output.getvalue()
    return json.dumps({
        "export_info": {
            "format": "web-scraper-results",
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "result_count": len(export_rows),
            "filters": {"search": search or None, "page_type": page_type_filter or None},
            "field_guide": {
                "page_type": "Page category predicted from page signals or the trained text classifier.",
                "page_metadata": "Author, publication date, site name, canonical URL and language when the page provides them.",
                "language_analysis": "Extractive summary, keyword topics, entity candidates and lexicon-based sentiment estimates.",
                "classification": "Estimated page category, model confidence and evidence signals when available.",
                "content": "Readable paragraph text collected from the main page content.",
                "headings": "Section titles with their HTML heading level.",
                "links": "Meaningful links found in the main page content.",
                "images": "Images found in the main page content, with alternative text when available.",
                "content_summary": "Counts of extracted content elements.",
            },
        },
        "results": export_rows,
    }, indent=2, ensure_ascii=False, default=str)
