"""Tests for the RSS news provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.providers.configs import RSSConfig
from src.providers.protocols import NewsProvider
from src.providers.rss import RSSNewsProvider
from src.sentiment.models import Article


@pytest.fixture
def rss_config() -> RSSConfig:
    return RSSConfig(feed_urls=["https://example.com/feed.xml"])


@pytest.fixture
def provider(rss_config: RSSConfig) -> RSSNewsProvider:
    return RSSNewsProvider(rss_config)


@pytest.fixture
def mock_feed() -> dict:
    return {
        "entries": [
            {
                "title": "BTC up 10%",
                "summary": "Bitcoin rose sharply today after institutional buying.",
                "link": "https://example.com/1",
                "published_parsed": (2026, 1, 15, 12, 0, 0, 0, 0, 0),
            },
            {
                "title": "ETH staking rewards increase",
                "summary": "Ethereum staking yields hit new highs.",
                "link": "https://example.com/2",
                "published_parsed": (2026, 1, 15, 14, 30, 0, 0, 0, 0),
            },
        ],
        "bozo": False,
    }


class TestRSSNewsProvider:
    def test_creates_with_config_and_name(self, provider: RSSNewsProvider):
        assert provider.name == "rss"

    def test_implements_news_provider_protocol(self, provider: RSSNewsProvider):
        assert isinstance(provider, NewsProvider)

    def test_rate_limit_comes_from_config(self):
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"], max_articles_per_fetch=25)
        p = RSSNewsProvider(config)
        assert p.rate_limit == 25

    def test_rate_limit_default(self, provider: RSSNewsProvider):
        # Default max_articles_per_fetch is 50
        assert provider.rate_limit == 50

    async def test_health_check_returns_true(self, provider: RSSNewsProvider):
        result = await provider.health_check()
        assert result is True

    async def test_fetch_articles_parses_feed_entries(
        self, provider: RSSNewsProvider, mock_feed: dict
    ):
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)

    async def test_fetch_articles_respects_limit(
        self, provider: RSSNewsProvider, mock_feed: dict
    ):
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=1)

        assert len(articles) == 1

    async def test_articles_have_correct_source(
        self, provider: RSSNewsProvider, mock_feed: dict
    ):
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        for article in articles:
            assert article.source == "rss"

    async def test_articles_have_correct_symbol(
        self, provider: RSSNewsProvider, mock_feed: dict
    ):
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        for article in articles:
            assert article.related_symbols == ["BTC"]

    async def test_article_fields_mapped_correctly(
        self, provider: RSSNewsProvider, mock_feed: dict
    ):
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        first = articles[0]
        assert first.title == "BTC up 10%"
        assert first.body == "Bitcoin rose sharply today after institutional buying."
        assert first.url == "https://example.com/1"
        assert first.published_at == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_fetch_articles_multiple_feeds(self, mock_feed: dict):
        config = RSSConfig(
            feed_urls=["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
        )
        p = RSSNewsProvider(config)

        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await p.fetch_articles("ETH", limit=10)

        # 2 feeds * 2 entries each = 4 articles
        assert len(articles) == 4

    async def test_entries_missing_summary_use_empty_string(
        self, provider: RSSNewsProvider,
    ):
        feed = {
            "entries": [
                {
                    "title": "No summary article",
                    "link": "https://example.com/no-summary",
                    "published_parsed": (2026, 1, 15, 12, 0, 0, 0, 0, 0),
                },
            ],
            "bozo": False,
        }
        with patch("src.providers.rss.feedparser.parse", return_value=feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        assert len(articles) == 1
        assert articles[0].body == ""

    async def test_entries_missing_link_use_empty_string(
        self, provider: RSSNewsProvider,
    ):
        feed = {
            "entries": [
                {
                    "title": "No link article",
                    "summary": "Has a summary but no link.",
                    "published_parsed": (2026, 1, 15, 12, 0, 0, 0, 0, 0),
                },
            ],
            "bozo": False,
        }
        with patch("src.providers.rss.feedparser.parse", return_value=feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        assert len(articles) == 1
        assert articles[0].url == ""

    async def test_parse_time_converts_struct_time(self):
        from src.providers.rss import RSSNewsProvider

        t = (2026, 1, 15, 12, 0, 0, 0, 0, 0)
        result = RSSNewsProvider._parse_time(t)
        assert result == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_parse_time_none_returns_now(self):
        from src.providers.rss import RSSNewsProvider

        result = RSSNewsProvider._parse_time(None)
        # Should be approximately now in UTC
        assert result.tzinfo == timezone.utc
        now = datetime.now(timezone.utc)
        assert abs((now - result).total_seconds()) < 2
