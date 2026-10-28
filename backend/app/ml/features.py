"""
backend/app/ml/features.py

Turns a parsed webpage into the information an ML model needs.

    extract_features(soup, url) -> {
        "numeric": {name: float, ...},   # structural / pattern features
        "text":    "...",                # one string for TF-IDF
    }

Why two parts?
  - numeric features describe STRUCTURE (how many <p>, link density, ...)
  - text describes CONTENT (title, headings, body words)
The classifier will combine them: TF-IDF(text) + scaled numeric features.
"""

import json
import re
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# schema.org @type values we treat as strong evidence for a page type
JSONLD_GROUPS = {
    "article": {"article", "newsarticle", "blogposting", "report", "techarticle"},
    "product": {"product", "productgroup", "offer"},
    "job": {"jobposting"},
    "profile": {"person", "profilepage"},
}

# keywords that often appear in URL paths, grouped by page type
URL_KEYWORDS = {
    "product": ["product", "products", "/p/", "/dp/", "item", "shop", "store"],
    "job": ["job", "jobs", "career", "careers", "vacancy", "apply", "hiring"],
    "article": ["article", "news", "story", "post", "blog", "/20"],
    "profile": ["profile", "user", "/u/", "/in/", "people", "author"],
    "search": ["search", "results", "find", "query"],
    "forum": ["forum", "thread", "topic", "discussion", "questions", "comments"],
}

# phrases that appear in the visible text, grouped by page type
TEXT_KEYWORDS = {
    "product": ["add to cart", "buy now", "in stock", "out of stock",
                "free delivery", "add to bag", "customer reviews"],
    "job": ["apply now", "job description", "responsibilities",
            "qualifications", "salary", "full-time", "full time",
            "experience required", "apply for this job"],
    "article": ["published", "min read", "share this", "related articles",
                "written by", "updated on"],
    "profile": ["followers", "following", "connections", "about me",
                "joined", "contact me"],
    "forum": ["reply", "replies", "upvote", "posted by", "views",
              "report", "quote"],
    "search": ["results for", "sort by", "filter", "showing", "next page"],
}

CURRENCY_RE = re.compile(r"(?:₹|\$|€|£|Rs\.?|INR|USD)\s?\d[\d,]*(?:\.\d+)?")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2},? \d{4})\b",
    re.IGNORECASE,
)

STRUCTURE_TAGS = [
    "h1", "h2", "h3", "p", "a", "img", "table", "form", "button", "input",
    "select", "ul", "ol", "li", "article", "section", "nav", "aside",
    "footer", "header", "video", "iframe",
]

MAX_BODY_CHARS = 3000  # how much body text we feed to TF-IDF


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _visible_text(soup: BeautifulSoup) -> str:
    """Visible text from the semantic content area with interface noise removed."""
    clone = _content_soup(soup)
    text = clone.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def _content_soup(soup: BeautifulSoup) -> BeautifulSoup:
    clone = BeautifulSoup(str(soup.find("main") or soup.find("article") or soup.body or soup), "lxml")
    for tag in clone.find_all(["script", "style", "noscript", "template", "nav", "footer", "form", "iframe"]):
        tag.decompose()
    for tag in list(clone.find_all(True)):
        marker = " ".join([str(tag.get("id", "")), " ".join(tag.get("class", [])), str(tag.get("role", ""))])
        if re.search(r"\b(navigation|menu|sidebar|cookie|consent|popup|modal|breadcrumb|social|share|advert|promo|related|recommend|subscribe)\b", marker, re.I):
            tag.decompose()
    return clone


def _jsonld_types(soup: BeautifulSoup) -> set[str]:
    """Collect every lower-cased @type found in JSON-LD blocks."""
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                found.add(t.lower())
            elif isinstance(t, list):
                found.update(x.lower() for x in t if isinstance(x, str))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        try:
            walk(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue  # malformed JSON-LD is common; just skip it
    return found


def _meta_content(soup: BeautifulSoup, **attrs) -> str:
    tag = soup.find("meta", attrs=attrs)
    return (tag.get("content") or "").strip() if tag else ""


def _count_phrases(text_lower: str, phrases: list[str]) -> int:
    return sum(text_lower.count(p) for p in phrases)


# --------------------------------------------------------------------------
# Feature groups
# --------------------------------------------------------------------------

def _structure_features(soup: BeautifulSoup) -> dict[str, float]:
    feats = {f"n_{tag}": float(len(soup.find_all(tag))) for tag in STRUCTURE_TAGS}
    all_tags = soup.find_all(True)
    feats["n_total_tags"] = float(len(all_tags))
    feats["n_input_text"] = float(len(soup.find_all("input", type="text")))
    feats["n_input_search"] = float(len(soup.find_all("input", type="search")))
    return feats


def _text_features(soup: BeautifulSoup, text: str) -> dict[str, float]:
    text_len = len(text)
    content = _content_soup(soup)
    paragraphs = [p.get_text(" ", strip=True) for p in content.find_all("p")]
    long_paragraphs = [p for p in paragraphs if len(p) > 100]
    anchor_chars = sum(len(a.get_text(" ", strip=True)) for a in content.find_all("a"))
    n_img = len(content.find_all("img"))
    n_tags = max(len(content.find_all(True)), 1)

    return {
        "text_length": float(text_len),
        "n_words": float(len(text.split())),
        "n_paragraphs_long": float(len(long_paragraphs)),
        "avg_paragraph_len": (
            sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0.0
        ),
        "link_density": anchor_chars / text_len if text_len else 0.0,
        "image_density": n_img / (text_len / 1000) if text_len else float(n_img),
        "tag_to_text_ratio": n_tags / max(text_len, 1),
        "n_currency_mentions": float(len(CURRENCY_RE.findall(text))),
        "n_dates": float(len(DATE_RE.findall(text))),
    }


def _keyword_features(text_lower: str) -> dict[str, float]:
    return {
        f"kw_text_{group}": float(_count_phrases(text_lower, phrases))
        for group, phrases in TEXT_KEYWORDS.items()
    }


def _structured_data_features(soup: BeautifulSoup) -> dict[str, float]:
    types = _jsonld_types(soup)
    feats = {"has_jsonld": float(bool(soup.find("script", type="application/ld+json")))}
    for group, names in JSONLD_GROUPS.items():
        feats[f"jsonld_{group}"] = float(bool(types & names))

    og_type = _meta_content(soup, property="og:type").lower()
    feats["og_is_article"] = float(og_type == "article")
    feats["og_is_product"] = float("product" in og_type)
    feats["og_is_profile"] = float(og_type == "profile")
    feats["has_og_price"] = float(
        bool(soup.find("meta", attrs={"property": re.compile(r"price", re.I)}))
    )
    feats["has_article_published_time"] = float(
        bool(soup.find("meta", attrs={"property": "article:published_time"}))
    )
    feats["has_itemprop_price"] = float(bool(soup.find(attrs={"itemprop": "price"})))
    return feats


def _url_features(url: str) -> dict[str, float]:
    parsed = urlparse(url)
    path = parsed.path.lower()
    segments = [s for s in path.split("/") if s]
    feats = {
        "url_path_depth": float(len(segments)),
        "url_length": float(len(url)),
        "url_has_query": float(bool(parsed.query)),
        "url_n_query_params": float(len(parse_qs(parsed.query))),
        "url_n_digits": float(sum(c.isdigit() for c in path)),
        "url_has_year": float(bool(re.search(r"/(19|20)\d{2}/", path))),
        "url_is_root": float(path in ("", "/")),
        "url_has_search_param": float(
            any(k in parse_qs(parsed.query) for k in ("q", "query", "s", "search"))
        ),
    }
    haystack = path + "?" + parsed.query.lower()
    for group, words in URL_KEYWORDS.items():
        feats[f"kw_url_{group}"] = float(any(w in haystack for w in words))
    return feats


def _build_text_blob(soup: BeautifulSoup, url: str, text: str) -> str:
    """The single string that TF-IDF will see."""
    title = soup.title.get_text(strip=True) if soup.title else ""
    description = _meta_content(soup, name="description")
    og_type = _meta_content(soup, property="og:type")
    content = _content_soup(soup)
    headings = " ".join(
        h.get_text(" ", strip=True) for h in content.find_all(["h1", "h2", "h3"])
    )
    url_tokens = " ".join(re.split(r"[^a-zA-Z]+", urlparse(url).path))
    parts = [title, description, og_type, headings, url_tokens, text[:MAX_BODY_CHARS]]
    return " ".join(p for p in parts if p)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def extract_features(soup: BeautifulSoup, url: str) -> dict:
    """Main entry point. Returns {"numeric": {...}, "text": "..."}."""
    text = _visible_text(soup)
    text_lower = text.lower()

    numeric: dict[str, float] = {}
    numeric.update(_structure_features(soup))
    numeric.update(_text_features(soup, text))
    numeric.update(_keyword_features(text_lower))
    numeric.update(_structured_data_features(soup))
    numeric.update(_url_features(url))

    return {"numeric": numeric, "text": _build_text_blob(soup, url, text)}


# Fixed column order, so training and prediction always agree.
# (Built from an empty page; every feature function always returns all keys.)
NUMERIC_FEATURE_NAMES: list[str] = sorted(
    extract_features(BeautifulSoup("<html></html>", "html.parser"), "https://x.com")[
        "numeric"
    ].keys()
)


def to_vector(features: dict) -> list[float]:
    """Numeric features as a list in the canonical order."""
    return [features["numeric"].get(name, 0.0) for name in NUMERIC_FEATURE_NAMES]


if __name__ == "__main__":
    # Quick manual test:  python -m app.ml.features
    sample = """
    <html><head><title>iPhone 17 - Buy Now</title>
    <script type="application/ld+json">
      {"@type": "Product", "name": "iPhone 17", "offers": {"price": "79900"}}
    </script></head>
    <body><h1>iPhone 17</h1><span>₹79,900</span>
    <button>Add to Cart</button><p>The newest iPhone.</p></body></html>
    """
    soup = BeautifulSoup(sample, "html.parser")
    out = extract_features(soup, "https://shop.example.com/products/iphone-17")
    for k, v in sorted(out["numeric"].items()):
        if v:
            print(f"{k:28s} {v}")
    print("\nTEXT:", out["text"][:200])
