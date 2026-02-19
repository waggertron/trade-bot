"""Tests for FeedManager — loads feeds from DB and fans out to adapters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db.database import Database
from src.db.models import FeedRecord
from src.feeds.manager import FeedManager
from src.sentiment.models import Article


def _make_feed(**overrides) -> FeedRecord:
    defaults = dict(
        name="Test Feed",
        url="https://example.com/feed",
        feed_type="rss",
        category="markets",
        auth_type="free",
        rate_limit_rpm=60,
        enabled=True,
    )
    defaults.update(overrides)
    return FeedRecord(**defaults)


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


class TestFeedManagerLoadFeeds:
    @pytest.mark.asyncio
    async def test_load_feeds_from_db(self, db):
        await db.save_feed(_make_feed(name="F1", url="https://a.com"))
        await db.save_feed(_make_feed(name="F2", url="https://b.com"))
        mgr = FeedManager(db)
        await mgr.load_feeds()
        assert len(mgr.feeds) == 2

    @pytest.mark.asyncio
    async def test_load_feeds_only_enabled(self, db):
        await db.save_feed(_make_feed(name="Active", url="https://a.com", enabled=True))
        await db.save_feed(_make_feed(name="Disabled", url="https://b.com", enabled=False))
        mgr = FeedManager(db)
        await mgr.load_feeds()
        assert len(mgr.feeds) == 1
        assert mgr.feeds[0].name == "Active"

    @pytest.mark.asyncio
    async def test_has_feeds_returns_false_when_empty(self, db):
        mgr = FeedManager(db)
        assert await mgr.has_feeds() is False

    @pytest.mark.asyncio
    async def test_has_feeds_returns_true_after_seed(self, db):
        await db.save_feed(_make_feed())
        mgr = FeedManager(db)
        assert await mgr.has_feeds() is True

    @pytest.mark.asyncio
    async def test_feeds_grouped_by_type(self, db):
        await db.save_feed(_make_feed(name="RSS1", url="https://a.com", feed_type="rss"))
        await db.save_feed(_make_feed(name="API1", url="https://b.com", feed_type="json_api"))
        await db.save_feed(_make_feed(name="GOV1", url="https://c.com", feed_type="government"))
        mgr = FeedManager(db)
        await mgr.load_feeds()
        grouped = mgr.feeds_by_type
        assert "rss" in grouped
        assert "json_api" in grouped
        assert "government" in grouped
