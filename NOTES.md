# Scraper Project — Development Notes

## Project Understanding

### What this scraper targets
A general-purpose web scraper that fetches any URL, extracts structured page data (title, description, headings, paragraphs, links, images), and classifies pages by type (article, product, job, profile, forum, search, other) using feature extraction and heuristics.

### What data it collects
- **Page metadata**: title, meta description, Open Graph tags
- **Content**: headings (h1–h6), paragraphs, links, images
- **ML features**: ~50 numeric features (structural counts, text stats, keyword matches, JSON-LD signals, URL patterns) plus a TF-IDF text blob
- **Classification**: page type label derived from structured data, URL patterns, and text keyword signals

### How it runs
- FastAPI backend with async HTTP fetching via httpx
- BeautifulSoup + lxml for HTML parsing
- SQLite database for persistence via aiosqlite
- React frontend with Vite for the web UI
- WebSocket for real-time job progress updates

### What was finished (original)
- HTTP fetcher with browser-like User-Agent, timeout, redirects
- HTML parser (BS4 + lxml)
- Generic page extractor (title, description, headings, paragraphs, links, images)
- Comprehensive ML feature extraction (structure, text, keywords, JSON-LD, URL features)
- Dataset collector with deduplication and CSV label tracking
- ~80 labeled pages across 4 categories (article, product, job, other)

### What was broken or missing (original)
- No error handling, retries, or rate limiting in the fetcher
- No robots.txt compliance
- No database — results were not persisted
- No configuration system — everything hardcoded
- Empty placeholder files: `classifier.py`, `train.py`, `page.py`
- No logging system
- No UI whatsoever
- No tests
- `python` command not on PATH (only available via venv)

### Bug fixed
- `ws_subscribers` in `engine.py` caused `UnboundLocalError` because the compound assignment `ws_subscribers -= dead` made Python treat it as a local variable. Fixed by adding `global ws_subscribers` declaration.

## Decisions Made

1. **Database**: SQLite via aiosqlite. Lightweight, zero-config, fits a single-user scraper tool. No need for PostgreSQL overhead.

2. **Classifier**: Rule-based heuristic using the existing feature extraction (JSON-LD, OG tags, URL keywords, text keywords). The ML pipeline (train.py, classifier.py) was scaffolded for a future sklearn model but has no training data pipeline yet — the rule-based approach works well enough with the structured signals already extracted.

3. **Config**: YAML config file (`config.yaml`) with Pydantic Settings. Environment variable overrides supported (prefix `SCRAPER_`).

4. **UI framework**: React + Vite with vanilla CSS. No Tailwind, no component library. Hand-written styles for a deliberate, tool-like aesthetic.

5. **Deduplication**: SHA-256 hash of extracted content. Same content from different scrape runs won't create duplicate rows.

6. **Real-time updates**: WebSocket connection from UI to backend for live job progress.

7. **Export**: CSV and JSON export of results with optional filters.

8. **Retry strategy**: Exponential backoff (base * 2^attempt) with configurable attempts and base delay.

9. **Rate limiting**: Per-domain asyncio.Lock with configurable delay between requests.

## UI Visual Direction

Dense, data-first layout inspired by Linear and terminal dashboards. Monochrome neutral base (gray-900 to gray-50) with a single teal accent (#0D9488) for actions and active states. Type pairing: system sans-serif (-apple-system, "Segoe UI") for interface labels at 13px; JetBrains Mono / monospace for data values, URLs, and code. 4px/8px spacing grid throughout. Flat surfaces with 1px solid borders (no shadows, no gradients, no rounded corners beyond 3px). Dark mode as default with a light mode toggle. Keyboard-navigable with visible focus rings.

## Known Limitations

- No JavaScript rendering — sites that require JS (SPAs) won't return useful content. Would need Playwright/Puppeteer for that.
- Rule-based classifier, not ML-trained. Accuracy depends on pages having structured data or recognizable URL/text patterns.
- Single-machine, single-process. Not designed for distributed crawling.
- No proxy rotation support (could be added via config).
- No authentication on the UI — suitable for local use only.
- Rate limiting is per-domain but not persisted across restarts.
- The existing `dataset/collect.py` tool is separate from the main scraper pipeline — it was used for building training data. The main app uses its own pipeline.
