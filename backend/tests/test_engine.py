"""Tests for the rule-based classifier in app.scraper.engine"""

from app.scraper.engine import _classify_page


def test_classify_product_by_jsonld():
    features = {"numeric": {"jsonld_product": 1.0, "og_is_product": 0, "has_itemprop_price": 0}}
    assert _classify_page(features) == "product"


def test_classify_article_by_og():
    features = {"numeric": {"og_is_article": 1.0, "jsonld_article": 0, "has_article_published_time": 0,
                             "jsonld_product": 0, "og_is_product": 0, "has_itemprop_price": 0}}
    assert _classify_page(features) == "article"


def test_classify_job_by_jsonld():
    features = {"numeric": {"jsonld_job": 1.0,
                             "jsonld_product": 0, "og_is_product": 0, "has_itemprop_price": 0,
                             "jsonld_article": 0, "og_is_article": 0, "has_article_published_time": 0}}
    assert _classify_page(features) == "job"


def test_classify_by_url_keyword():
    features = {"numeric": {"kw_url_product": 1.0,
                             "jsonld_product": 0, "og_is_product": 0, "has_itemprop_price": 0,
                             "jsonld_article": 0, "og_is_article": 0, "has_article_published_time": 0,
                             "jsonld_job": 0, "jsonld_profile": 0, "og_is_profile": 0}}
    assert _classify_page(features) == "product"


def test_classify_fallback_to_other():
    features = {"numeric": {
        "jsonld_product": 0, "og_is_product": 0, "has_itemprop_price": 0,
        "jsonld_article": 0, "og_is_article": 0, "has_article_published_time": 0,
        "jsonld_job": 0, "jsonld_profile": 0, "og_is_profile": 0,
        "kw_url_product": 0, "kw_url_article": 0, "kw_url_job": 0,
        "kw_url_search": 0, "kw_url_forum": 0,
        "kw_text_product": 0, "kw_text_article": 0, "kw_text_job": 0,
        "kw_text_forum": 0, "kw_text_search": 0,
    }}
    assert _classify_page(features) == "other"


def test_classify_by_text_keywords():
    features = {"numeric": {
        "jsonld_product": 0, "og_is_product": 0, "has_itemprop_price": 0,
        "jsonld_article": 0, "og_is_article": 0, "has_article_published_time": 0,
        "jsonld_job": 0, "jsonld_profile": 0, "og_is_profile": 0,
        "kw_url_product": 0, "kw_url_article": 0, "kw_url_job": 0,
        "kw_url_search": 0, "kw_url_forum": 0,
        "kw_text_product": 5, "kw_text_article": 1, "kw_text_job": 0,
        "kw_text_forum": 0, "kw_text_search": 0,
    }}
    assert _classify_page(features) == "product"
