"""
Tests for app.scraper.parser
"""

from bs4 import BeautifulSoup
from app.scraper.parser import parse_html


SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
<h1>Hello World</h1>
<p>Some paragraph text.</p>
<a href="https://example.com">Link</a>
</body>
</html>
"""


def test_parse_html_returns_soup():
    result = parse_html(SAMPLE_HTML)
    assert isinstance(result, BeautifulSoup)


def test_parse_html_title():
    soup = parse_html(SAMPLE_HTML)
    assert soup.title is not None
    assert soup.title.get_text(strip=True) == "Test Page"


def test_parse_html_finds_tags():
    soup = parse_html(SAMPLE_HTML)
    assert len(soup.find_all("h1")) == 1
    assert len(soup.find_all("p")) == 1
    assert len(soup.find_all("a")) == 1


def test_parse_html_empty_input():
    soup = parse_html("")
    assert isinstance(soup, BeautifulSoup)


def test_parse_html_preserves_links():
    soup = parse_html(SAMPLE_HTML)
    link = soup.find("a")
    assert link is not None
    assert link["href"] == "https://example.com"
