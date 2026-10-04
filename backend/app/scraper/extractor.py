"""
backend/app/scraper/extractor.py

Generic extraction layer: pulls title, meta description, headings,
paragraphs, links, and images out of any parsed page. This is the
"never reject an unknown page" fallback referenced in the ML plan.
"""

from bs4 import BeautifulSoup


def extract_page(soup: BeautifulSoup) -> dict:
    data = {
        "title": None,
        "description": None,
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

    # Headings
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = heading.get_text(" ", strip=True)
        if text:
            data["headings"].append({
                "tag": heading.name,
                "text": text,
            })

    # Paragraphs
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text:
            data["paragraphs"].append(text)

    # Links
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        data["links"].append({
            "text": text,
            "url": link["href"],
        })

    # Images
    for img in soup.find_all("img", src=True):
        data["images"].append({
            "src": img["src"],
            "alt": img.get("alt", ""),
        })

    return data