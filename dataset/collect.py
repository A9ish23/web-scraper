"""
dataset/collect.py

Fetches a list of URLs, saves each page's raw HTML to dataset/raw/,
and appends a row to dataset/labels.csv.

Usage:
    python collect.py --label product --domain amazon.in \
        https://www.amazon.in/dp/XXXXXXX https://www.amazon.in/dp/YYYYYYY

    python collect.py --label job --urls-file jobs.txt

    # jobs.txt: one URL per line, optionally "url,domain" if you want to
    # override the auto-detected domain.

Re-running is safe: a URL already present in labels.csv is skipped, so you
can build the dataset incrementally across many sessions.
"""

import argparse
import asyncio
import csv
from fileinput import filename
import hashlib
import html
import sys
from pathlib import Path
from urllib.parse import urlparse


# --- reuse the project's own fetcher instead of a bare `requests.get` -----
# This keeps behavior (headers, timeouts, retries) identical to what the
# live /scrape endpoint actually sees.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.scraper.fetcher import fetch_page  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
LABELS_CSV = HERE / "labels.csv"
CSV_FIELDS = ["filename", "url", "label", "domain"]


def slugify_filename(url: str) -> str:
    """Stable, filesystem-safe filename for a URL: <domain>__<hash>.html"""
    domain = urlparse(url).netloc.replace(":", "_")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{domain}__{digest}.html"


def load_existing_urls() -> set[str]:
    if not LABELS_CSV.exists():
        return set()
    with LABELS_CSV.open(newline="", encoding="utf-8") as f:
        return {row["url"] for row in csv.DictReader(f)}


def append_row(row: dict) -> None:
    is_new = not LABELS_CSV.exists()
    with LABELS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


async def collect_one(url: str, label: str, domain_override: str | None,
                       seen: set[str]) -> str:
    if url in seen:
        return f"SKIP  (already have) {url}"

    try:
        html = await fetch_page(url)
    except Exception as exc:  # noqa: BLE001 - we want to log and continue
        return f"FAIL  ({exc!r}) {url}"

    if not html or len(html) < 200:
        return f"FAIL  (empty/too short) {url}"

    filename = slugify_filename(url)

    label_dir = RAW_DIR / label
    label_dir.mkdir(parents=True, exist_ok=True)

    (label_dir / filename).write_text(html, encoding="utf-8")

    domain = domain_override or urlparse(url).netloc
    append_row({
    "filename": filename,
    "url": url,
    "label": label,
    "domain": domain
})
    seen.add(url)
    return f"OK    [{label:10s}] {url}"


async def run(urls: list[str], label: str, domain_override: str | None) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seen = load_existing_urls()

    # Fetch a few pages concurrently, but don't hammer servers.
    sem = asyncio.Semaphore(5)

    async def bounded(url: str) -> str:
        async with sem:
            return await collect_one(url, label, domain_override, seen)

    results = await asyncio.gather(*(bounded(u) for u in urls))
    for r in results:
        print(r)

    ok = sum(r.startswith("OK") for r in results)
    print(f"\n{ok}/{len(urls)} pages saved. Total dataset rows: "
          f"{len(load_existing_urls())}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("urls", nargs="*", help="Page URLs to fetch")
    p.add_argument("--urls-file", type=Path,
                    help="Text file, one URL per line (optionally 'url,domain')")
    p.add_argument("--label", required=True,
                    help="Page type label, e.g. article, product, job, other")
    p.add_argument("--domain", default=None,
                    help="Override the domain recorded in labels.csv for every URL")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    urls = list(args.urls)

    if args.urls_file:
        for line in args.urls_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line.split(",")[0].strip())

    if not urls:
        print("No URLs given. Pass them directly or via --urls-file.")
        return

    asyncio.run(run(urls, args.label, args.domain))


if __name__ == "__main__":
    main()