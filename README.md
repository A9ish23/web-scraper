# Web Scraper

A complete web scraper with a FastAPI backend, SQLite storage, and a React UI for controlling jobs and viewing results.

## Features

- **Scrape any URL** — extracts title, description, headings, paragraphs, links, and images
- **Page classification** — automatically classifies pages as article, product, job, profile, forum, search, or other using structured data signals (JSON-LD, Open Graph), URL patterns, and text keyword analysis
- **NLP analysis** — extractive page summaries, topic keywords, entity candidates, sentiment estimates, and category evidence/confidence
- **Meaning-based search** — rank scraped pages by sentence-transformer similarity instead of exact phrase matches
- **Trainable classifier** — keep training and held-out labels separate, train a TF-IDF text classifier, and review accuracy and macro F1 on held-out pages
- **Search quality evaluation** — rate results for a query and calculate Precision@10, Recall@10, MRR@10, and nDCG@10
- **Job management** — start, stop, and delete scrape jobs with real-time progress via WebSocket
- **Results table** — search, sort, filter, and paginate through scraped data
- **Export** — download results as CSV or JSON
- **Logging** — full log trail for every scrape job, filterable by job and level
- **Settings** — configurable concurrency, timeouts, retries, rate limiting, robots.txt compliance
- **Deduplication** — content-hash based dedup prevents storing duplicate pages
- **Polite scraping** — per-domain rate limiting, robots.txt compliance, configurable delays
- **Dark/light theme** — toggle between modes, preference saved locally

## Project structure

```
web-scraper/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app with all REST endpoints + WebSocket
│   │   ├── config.py         # Pydantic Settings (reads config.yaml + env vars)
│   │   ├── database.py       # Async SQLite layer (aiosqlite)
│   │   ├── logging_config.py # Structured logging setup
│   │   ├── scraper/
│   │   │   ├── fetcher.py    # HTTP fetcher with retries, rate limiting, robots.txt
│   │   │   ├── parser.py     # BeautifulSoup HTML parser
│   │   │   ├── extractor.py  # Generic page data extraction
│   │   │   ├── engine.py     # Job orchestrator with background execution
│   │   │   └── robots.py     # Robots.txt compliance checker
│   │   ├── ml/
│   │   │   └── features.py   # ML feature extraction (~50 numeric features + text)
│   │   └── models/
│   │       └── page.py       # Pydantic request/response models
│   ├── tests/                # pytest tests for extractor, features, parser, classifier
│   ├── data/                 # SQLite database + log file (auto-created)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main app with routing and layout
│   │   ├── api.js            # API client (all backend calls + WebSocket)
│   │   ├── index.css         # Complete CSS (dark/light themes, responsive)
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx # Stats, quick scrape, recent jobs
│   │   │   ├── Jobs.jsx      # Job list with create/stop/delete
│   │   │   ├── Results.jsx   # Results table with search/sort/filter/export
│   │   │   ├── Logs.jsx      # Log viewer with auto-refresh
│   │   │   └── Settings.jsx  # Configuration editor
│   │   └── hooks/
│   │       └── useFetch.js   # Reusable data fetching hook
│   └── package.json
├── config.yaml               # Default scraper configuration
├── NOTES.md                  # Development decisions and assumptions
└── README.md                 # This file
```

## Setup

### Prerequisites
- Python 3.12+ (tested with 3.14)
- Node.js 18+ (tested with 24.18)

### Install

```bash
cd web-scraper

# Backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### Run

Start both the backend and frontend:

```bash
# Terminal 1 — Backend
cd web-scraper/backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd web-scraper/frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

The first meaning-based search downloads the `all-MiniLM-L6-v2` sentence embedding model. In each result's detail panel, add page labels to either the training or held-out evaluation set; held-out examples are never used to fit the classifier. Search-quality evaluation uses grades 0–3 for each query/result pair, with grades 2–3 counted as relevant for precision, recall, and reciprocal rank. Metrics are shown only after you add human judgments; they are not prefilled or simulated.

### Run tests

```bash
cd web-scraper/backend
python -m pytest tests/ -v
```

## Configuration

Settings are loaded from `config.yaml` (at the `web-scraper/` root), then overridden by environment variables prefixed with `SCRAPER_`. You can also edit settings live from the UI's Settings page.

| Setting | Default | Description |
|---------|---------|-------------|
| `max_concurrent` | 5 | Max parallel requests per job |
| `request_timeout` | 15.0 | HTTP request timeout in seconds |
| `retry_attempts` | 3 | Number of retries on failure |
| `retry_backoff` | 1.0 | Base backoff delay between retries |
| `rate_limit_delay` | 1.0 | Min seconds between requests to same domain |
| `respect_robots_txt` | true | Check robots.txt before scraping |
| `user_agent` | WebScraper/1.0 | User-Agent header for requests |
| `db_path` | data/scraper.db | SQLite database file path |
| `log_level` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `log_file` | data/scraper.log | Log file path |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/jobs` | Start scrape job (`{urls: [...]}`) |
| GET | `/api/jobs` | List jobs (pagination + status filter) |
| GET | `/api/jobs/{id}` | Job details |
| POST | `/api/jobs/{id}/stop` | Stop running job |
| DELETE | `/api/jobs/{id}` | Delete job + results |
| GET | `/api/results` | List results (search, sort, filter, paginate) |
| POST | `/api/results/{id}/label` | Save a corrected category for training |
| POST | `/api/results/{id}/search-judgment` | Save a 0–3 human relevance rating for a query |
| POST | `/api/ml/train` | Train and evaluate the text classifier from corrected labels |
| GET | `/api/ml/status` | Check model and labeled-example status |
| GET | `/api/ml/search-evaluation?query=...` | Measure ranking quality against human relevance ratings |
| GET | `/api/results/{id}` | Single result detail |
| GET | `/api/results/export/{csv\|json}` | Export results |
| GET | `/api/logs` | List logs (filter by job, level) |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/settings` | Current configuration |
| PUT | `/api/settings` | Update configuration |
| WS | `/ws` | Real-time job progress updates |
