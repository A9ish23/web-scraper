"""
Tests for app.scraper.extractor
"""

from bs4 import BeautifulSoup
from app.scraper.extractor import extract_page


SAMPLE_HTML = """
<html>
<head>
    <title>My Product Page</title>
    <meta name="description" content="A great product description.">
</head>
<body>
    <h1>Product Title</h1>
    <h2>Features</h2>
    <p>This is a long paragraph about the product.</p>
    <p>Another paragraph.</p>
    <a href="https://example.com/buy">Buy Now</a>
    <a href="/about">About</a>
    <img src="/images/product.jpg" alt="Product Image">
    <img src="/images/thumb.jpg" alt="">
</body>
</html>
"""


def test_extract_page_returns_dict():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert isinstance(data, dict)


def test_extract_title():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert data["title"] == "My Product Page"


def test_extract_description():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert data["description"] == "A great product description."


def test_extract_headings():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert len(data["headings"]) == 2
    assert data["headings"][0]["tag"] == "h1"
    assert data["headings"][0]["text"] == "Product Title"
    assert data["headings"][1]["tag"] == "h2"


def test_extract_paragraphs():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert len(data["paragraphs"]) == 2
    assert "product" in data["paragraphs"][0].lower()


def test_extract_links():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert len(data["links"]) == 2
    urls = [l["url"] for l in data["links"]]
    assert "https://example.com/buy" in urls


def test_extract_images():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    data = extract_page(soup)
    assert len(data["images"]) == 2
    assert data["images"][0]["src"] == "/images/product.jpg"
    assert data["images"][0]["alt"] == "Product Image"


def test_extract_empty_page():
    soup = BeautifulSoup("<html><body></body></html>", "lxml")
    data = extract_page(soup)
    assert data["title"] is None
    assert data["description"] is None
    assert data["headings"] == []
    assert data["paragraphs"] == []
    assert data["links"] == []
    assert data["images"] == []
