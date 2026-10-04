"""
backend/app/scraper/parser.py

Turns raw HTML into a BeautifulSoup object the rest of the pipeline can use.
"""

from bs4 import BeautifulSoup


def parse_html(html_content: str) -> BeautifulSoup:
    return BeautifulSoup(html_content, "lxml")