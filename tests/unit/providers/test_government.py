"""Tests for GovernmentFeedAdapter — fetches from government data sources."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.db.models import FeedRecord
from src.providers.government import GovernmentFeedAdapter
from src.providers.protocols import NewsProvider
from src.sentiment.models import Article


def _make_feed(**overrides) -> FeedRecord:
    defaults = dict(
        name="Fed Press Releases",
        url="https://www.federalreserve.gov/feeds/press_all.xml",
        feed_type="government",
        category="markets",
        auth_type="free",
        rate_limit_rpm=60,
    )
    defaults.update(overrides)
    return FeedRecord(**defaults)


class TestGovernmentFeedAdapter:
    def test_implements_news_provider_protocol(self):
        adapter = GovernmentFeedAdapter([_make_feed()])
        assert isinstance(adapter, NewsProvider)

    def test_name(self):
        adapter = GovernmentFeedAdapter([_make_feed()])
        assert adapter.name == "government"

    def test_rate_limit(self):
        adapter = GovernmentFeedAdapter([_make_feed(rate_limit_rpm=120)])
        assert adapter.rate_limit == 120

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        adapter = GovernmentFeedAdapter([_make_feed()])
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_fetch_returns_articles_from_rss_feed(self):
        adapter = GovernmentFeedAdapter([_make_feed()])
        # Mock the RSS parsing
        with patch.object(
            adapter,
            "_fetch_rss",
            return_value=[
                Article(
                    title="Fed Rate Decision",
                    body="The Federal Reserve...",
                    source="government",
                    published_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                    related_symbols=["SPY"],
                )
            ],
        ):
            articles = await adapter.fetch_articles("SPY")
        assert len(articles) == 1
        assert articles[0].title == "Fed Rate Decision"

    @pytest.mark.asyncio
    async def test_fetch_handles_errors_gracefully(self):
        adapter = GovernmentFeedAdapter([_make_feed()])
        with patch.object(adapter, "_fetch_rss", side_effect=Exception("Timeout")):
            articles = await adapter.fetch_articles("SPY")
        assert articles == []
