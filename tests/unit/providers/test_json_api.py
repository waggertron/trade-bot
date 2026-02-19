"""Tests for JSONAPIAdapter — fetches articles from JSON API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.db.models import FeedRecord
from src.providers.json_api import JSONAPIAdapter
from src.providers.protocols import NewsProvider
from src.sentiment.models import Article


def _make_feed(**overrides) -> FeedRecord:
    defaults = dict(
        name="Finnhub",
        url="https://finnhub.io/api/v1/news?category=general&token=KEY",
        feed_type="json_api",
        category="markets",
        auth_type="api_key",
        rate_limit_rpm=60,
    )
    defaults.update(overrides)
    return FeedRecord(**defaults)


class TestJSONAPIAdapter:
    def test_implements_news_provider_protocol(self):
        adapter = JSONAPIAdapter([_make_feed()])
        assert isinstance(adapter, NewsProvider)

    def test_name(self):
        adapter = JSONAPIAdapter([_make_feed()])
        assert adapter.name == "json_api"

    def test_rate_limit(self):
        adapter = JSONAPIAdapter([_make_feed(rate_limit_rpm=60)])
        assert adapter.rate_limit == 60

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        adapter = JSONAPIAdapter([_make_feed()])
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_fetch_returns_articles(self):
        feed = _make_feed(
            name="HN API",
            url="https://hacker-news.firebaseio.com/v0/topstories.json",
            auth_type="free",
        )
        adapter = JSONAPIAdapter([feed])

        mock_response = AsyncMock()
        mock_response.json.return_value = [
            {
                "title": "Test Article",
                "url": "https://example.com",
                "time": 1700000000,
            }
        ]
        mock_response.raise_for_status = AsyncMock()

        with patch.object(adapter, "_fetch_url", return_value=[
            {"title": "Test Article", "url": "https://example.com", "time": 1700000000}
        ]):
            articles = await adapter.fetch_articles("AAPL")

        assert len(articles) >= 1
        assert all(isinstance(a, Article) for a in articles)

    @pytest.mark.asyncio
    async def test_fetch_handles_errors_gracefully(self):
        adapter = JSONAPIAdapter([_make_feed()])
        with patch.object(adapter, "_fetch_url", side_effect=Exception("Connection failed")):
            articles = await adapter.fetch_articles("AAPL")
        assert articles == []
