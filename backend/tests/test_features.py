"""
Tests for app.ml.features and the rule-based classifier in engine.
"""

from bs4 import BeautifulSoup
from app.ml.features import extract_features, NUMERIC_FEATURE_NAMES, to_vector
from app.scraper.engine import _classify_page


# --------------------------------------------------------------------------
# Feature extraction tests
# --------------------------------------------------------------------------

PRODUCT_HTML = """
<html><head><title>iPhone 17 - Buy Now</title>
<script type="application/ld+json">
  {"@type": "Product", "name": "iPhone 17", "offers": {"price": "79900"}}
</script>
<meta property="og:type" content="product">
</head>
<body><h1>iPhone 17</h1><span>$799</span>
<button>Add to Cart</button><p>The newest iPhone.</p></body></html>
"""

ARTICLE_HTML = """
<html><head><title>Breaking News</title>
<meta property="og:type" content="article">
<meta property="article:published_time" content="2024-01-01">
</head>
<body><article><h1>Breaking News Story</h1>
<p>Published on January 1. This is a long article about current events.</p>
<p>Related articles below.</p>
</article></body></html>
"""

JOB_HTML = """
<html><head><title>Software Engineer at Acme</title>
<script type="application/ld+json">
  {"@type": "JobPosting", "title": "Software Engineer"}
</script>
</head>
<body><h1>Software Engineer</h1>
<p>Job description and responsibilities.</p>
<p>Qualifications: 3+ years experience required.</p>
<button>Apply Now</button></body></html>
"""

PLAIN_HTML = """
<html><head><title>Welcome</title></head>
<body><h1>Welcome to our site</h1><p>Nothing special here.</p></body></html>
"""


def test_features_returns_expected_structure():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://shop.example.com/products/iphone")
    assert "numeric" in feats
    assert "text" in feats
    assert isinstance(feats["numeric"], dict)
    assert isinstance(feats["text"], str)


def test_features_numeric_keys_are_consistent():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://example.com/p/1")
    for name in NUMERIC_FEATURE_NAMES:
        assert name in feats["numeric"], f"Missing feature: {name}"


def test_to_vector_length():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://example.com")
    vec = to_vector(feats)
    assert len(vec) == len(NUMERIC_FEATURE_NAMES)
    assert all(isinstance(v, float) for v in vec)


def test_product_features_detected():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://shop.example.com/products/iphone")
    n = feats["numeric"]
    assert n.get("jsonld_product") == 1.0
    assert n.get("has_jsonld") == 1.0


def test_article_features_detected():
    soup = BeautifulSoup(ARTICLE_HTML, "lxml")
    feats = extract_features(soup, "https://news.example.com/article/123")
    n = feats["numeric"]
    assert n.get("og_is_article") == 1.0
    assert n.get("has_article_published_time") == 1.0


def test_text_blob_not_empty():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://example.com")
    assert len(feats["text"]) > 10


# --------------------------------------------------------------------------
# Classifier tests
# --------------------------------------------------------------------------

def test_classify_product():
    soup = BeautifulSoup(PRODUCT_HTML, "lxml")
    feats = extract_features(soup, "https://shop.example.com/products/iphone")
    assert _classify_page(feats) == "product"


def test_classify_article():
    soup = BeautifulSoup(ARTICLE_HTML, "lxml")
    feats = extract_features(soup, "https://news.example.com/article/123")
    assert _classify_page(feats) == "article"


def test_classify_job():
    soup = BeautifulSoup(JOB_HTML, "lxml")
    feats = extract_features(soup, "https://careers.example.com/job/456")
    assert _classify_page(feats) == "job"


def test_classify_other():
    soup = BeautifulSoup(PLAIN_HTML, "lxml")
    feats = extract_features(soup, "https://example.com")
    assert _classify_page(feats) == "other"


def test_classify_url_fallback_product():
    """When there's no structured data, URL keywords should kick in."""
    feats = {"numeric": {"kw_url_product": 1.0}}
    assert _classify_page(feats) == "product"


def test_classify_url_fallback_forum():
    feats = {"numeric": {"kw_url_forum": 1.0}}
    assert _classify_page(feats) == "forum"


def test_classify_text_fallback():
    """When only text keywords fire, highest score wins."""
    feats = {"numeric": {"kw_text_article": 3.0, "kw_text_product": 1.0}}
    assert _classify_page(feats) == "article"
