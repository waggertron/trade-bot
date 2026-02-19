"""Tests for feed, article, and sentiment_score DB tables + CRUD methods."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db.database import Database
from src.db.models import ArticleRecord, FeedRecord, SentimentScoreRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


def _make_feed(**overrides) -> FeedRecord:
    defaults = dict(
        name="CNBC Top News",
        url="https://search.cnbc.com/rs/search/combinedcms/view.xml",
        feed_type="rss",
        category="markets",
        auth_type="free",
        rate_limit_rpm=60,
        enabled=True,
    )
    defaults.update(overrides)
    return FeedRecord(**defaults)


def _make_article(feed_id: str | None = None, **overrides) -> ArticleRecord:
    defaults = dict(
        content_hash="abc123",
        title="Test Article",
        body="Some body text",
        source="rss",
        url="https://example.com/article",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc),
        feed_id=feed_id,
        symbols=["AAPL"],
    )
    defaults.update(overrides)
    return ArticleRecord(**defaults)


def _make_score(article_id: str, **overrides) -> SentimentScoreRecord:
    defaults = dict(
        article_id=article_id,
        score=0.5,
        magnitude=0.8,
        reasoning="Bullish tone",
        analyzer="ollama:llama3.2",
    )
    defaults.update(overrides)
    return SentimentScoreRecord(**defaults)


# -- Feed CRUD ----------------------------------------------------------------


class TestFeedCRUD:
    @pytest.mark.asyncio
    async def test_save_and_list_feeds(self, db):
        feed = _make_feed()
        await db.save_feed(feed)
        feeds = await db.list_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "CNBC Top News"
        assert feeds[0].feed_type == "rss"

    @pytest.mark.asyncio
    async def test_list_feeds_filters_by_enabled(self, db):
        await db.save_feed(_make_feed(name="Active", url="https://a.com", enabled=True))
        await db.save_feed(_make_feed(name="Disabled", url="https://b.com", enabled=False))
        enabled = await db.list_feeds(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "Active"

    @pytest.mark.asyncio
    async def test_list_feeds_filters_by_feed_type(self, db):
        await db.save_feed(_make_feed(name="RSS", url="https://a.com", feed_type="rss"))
        await db.save_feed(_make_feed(name="API", url="https://b.com", feed_type="json_api"))
        rss_feeds = await db.list_feeds(feed_type="rss")
        assert len(rss_feeds) == 1
        assert rss_feeds[0].name == "RSS"

    @pytest.mark.asyncio
    async def test_seed_feeds_bulk_insert(self, db):
        records = [
            _make_feed(name=f"Feed {i}", url=f"https://feed{i}.com")
            for i in range(5)
        ]
        await db.seed_feeds(records)
        feeds = await db.list_feeds()
        assert len(feeds) == 5

    @pytest.mark.asyncio
    async def test_seed_feeds_ignores_duplicates(self, db):
        feed = _make_feed()
        await db.seed_feeds([feed])
        await db.seed_feeds([feed])  # Same URL — should be ignored
        feeds = await db.list_feeds()
        assert len(feeds) == 1

    @pytest.mark.asyncio
    async def test_count_feeds(self, db):
        assert await db.count_feeds() == 0
        await db.save_feed(_make_feed())
        assert await db.count_feeds() == 1


# -- Article CRUD -------------------------------------------------------------


class TestArticleCRUD:
    @pytest.mark.asyncio
    async def test_save_article_returns_id(self, db):
        article = _make_article()
        article_id = await db.save_article(article)
        assert article_id == article.id

    @pytest.mark.asyncio
    async def test_save_article_deduplicates_by_content_hash(self, db):
        a1 = _make_article(content_hash="same_hash", title="First")
        a2 = _make_article(content_hash="same_hash", title="Second")
        await db.save_article(a1)
        result = await db.save_article(a2)
        assert result is None  # Duplicate — not inserted

    @pytest.mark.asyncio
    async def test_save_article_stores_symbols(self, db):
        article = _make_article(symbols=["AAPL", "MSFT"])
        await db.save_article(article)
        articles = await db.get_articles_for_symbol("AAPL")
        assert len(articles) == 1
        assert articles[0].title == "Test Article"

    @pytest.mark.asyncio
    async def test_get_articles_for_symbol_filters_correctly(self, db):
        await db.save_article(_make_article(content_hash="h1", symbols=["AAPL"]))
        await db.save_article(_make_article(content_hash="h2", symbols=["MSFT"]))
        aapl_articles = await db.get_articles_for_symbol("AAPL")
        assert len(aapl_articles) == 1


# -- Sentiment Score CRUD -----------------------------------------------------


class TestSentimentScoreCRUD:
    @pytest.mark.asyncio
    async def test_save_and_check_score(self, db):
        article = _make_article()
        await db.save_article(article)
        score = _make_score(article.id)
        await db.save_score(score)
        assert await db.has_score(article.id, "ollama:llama3.2") is True
        assert await db.has_score(article.id, "finbert") is False

    @pytest.mark.asyncio
    async def test_unique_constraint_article_analyzer(self, db):
        article = _make_article()
        await db.save_article(article)
        score = _make_score(article.id)
        await db.save_score(score)
        # Same article + analyzer combo should be ignored, not error
        await db.save_score(score)

    @pytest.mark.asyncio
    async def test_load_recent_scores(self, db):
        article = _make_article()
        await db.save_article(article)
        score = _make_score(article.id)
        await db.save_score(score)
        scores = await db.load_recent_scores(hours=48)
        assert len(scores) == 1
        assert scores[0].score == 0.5
        assert scores[0].article_id == article.id

    @pytest.mark.asyncio
    async def test_get_unscored_articles(self, db):
        a1 = _make_article(content_hash="h1", symbols=["AAPL"])
        a2 = _make_article(content_hash="h2", symbols=["AAPL"])
        await db.save_article(a1)
        await db.save_article(a2)
        # Score only a1
        await db.save_score(_make_score(a1.id))
        unscored = await db.get_unscored_articles("AAPL", "ollama:llama3.2")
        assert len(unscored) == 1
        assert unscored[0].id == a2.id
