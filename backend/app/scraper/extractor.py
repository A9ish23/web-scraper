"""
backend/app/scraper/extractor.py

Generic extraction layer: pulls title, meta description, headings,
paragraphs, links, and images out of any parsed page. This is the
"never reject an unknown page" fallback referenced in the ML plan.
"""

from bs4 import BeautifulSoup
import re


_BOILERPLATE = re.compile(
    r"\b(nav|navigation|menu|footer|sidebar|cookie|consent|popup|modal|"
    r"breadcrumb|social|share|advert|ads|promo|related|recommend|subscribe)\b", re.I,
)


def extract_page(soup: BeautifulSoup) -> dict:
    data = {
        "title": None,
        "description": None,
        "author": None,
        "published_at": None,
        "site_name": None,
        "canonical_url": None,
        "language": None,
        "headings": [],
        "paragraphs": [],
        "links": [],
        "images": [],
    }

    # Title
    if soup.title:
        data["title"] = soup.title.get_text(strip=True)

    # Meta description
    description = soup.find("meta", attrs={"name": "description"})
    if description:
        data["description"] = description.get("content")

    def meta_content(*selectors: dict) -> str | None:
        for attrs in selectors:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content", "").strip():
                return tag["content"].strip()
        return None

    data["author"] = meta_content({"name": "author"}, {"property": "article:author"})
    data["published_at"] = meta_content(
        {"property": "article:published_time"}, {"name": "datePublished"}, {"name": "publication_date"}
    )
    data["site_name"] = meta_content({"property": "og:site_name"})
    canonical = soup.find("link", rel="canonical", href=True)
    data["canonical_url"] = canonical["href"].strip() if canonical else None
    html_tag = soup.find("html")
    data["language"] = html_tag.get("lang") if html_tag else None

    # Prefer the semantic content container when present, and strip common
    # interface elements before extracting so exports focus on page content.
    content = soup.find("main") or soup.find("article") or soup.body or soup
    content = BeautifulSoup(str(content), "lxml")
    for element in content.find_all(["script", "style", "noscript", "svg", "nav", "footer", "form", "iframe"]):
        element.decompose()
    for element in list(content.find_all(True)):
        role = element.get("role", "")
        marker = " ".join([str(element.get("id", "")), " ".join(element.get("class", [])), str(role)])
        if role in {"navigation", "complementary", "contentinfo", "dialog"} or _BOILERPLATE.search(marker):
            element.decompose()

    # Headings
    for heading in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = heading.get_text(" ", strip=True)
        if text:
            data["headings"].append({
                "tag": heading.name,
                "text": text,
            })

    # Paragraphs
    seen_paragraphs = set()
    for paragraph in content.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text and text not in seen_paragraphs:
            data["paragraphs"].append(text)
            seen_paragraphs.add(text)

    # Links
    seen_links = set()
    for link in content.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        href = link["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")) or (not text and not link.find("img")):
            continue
        key = (text, href)
        if key in seen_links:
            continue
        seen_links.add(key)
        data["links"].append({
            "text": text,
            "url": href,
        })

    # Images
    for img in content.find_all("img", src=True):
        data["images"].append({
            "src": img["src"],
            "alt": img.get("alt", ""),
        })

    return data
