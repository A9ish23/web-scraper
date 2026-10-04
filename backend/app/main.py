from fastapi import FastAPI
from app.scraper.fetcher import fetch_page
from app.scraper.parser import parse_html
from app.scraper.extractor import extract_page
from app.ml.features import extract_features

app = FastAPI()


@app.get("/scrape")
async def scrape(url: str):
    html = await fetch_page(url)
    soup = parse_html(html)
    data = extract_page(soup)
    return {
        "url": url,
        "data": data
    }


@app.get("/features")
async def features(url: str):
    html = await fetch_page(url)
    soup = parse_html(html)
    return extract_features(soup, url)