"""Tests for DB-backed SentimentPipeline — fetch, dedup, score, warm-up."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db.database import Database
from src.db.models import ArticleRecord, FeedRecord, SentimentScoreRecord
from src.providers.configs import MockNewsConfig, MockSentimentConfig
from src.providers.mock import MockNewsProvider, MockSentimentAnalyzer
from src.sentiment.models import Article
from src.sentiment.pipeline import SentimentPipeline


CANNED_ARTICLES = [
    Article(
        title="BTC surges past $100k",
        body="Bitcoin broke records today...",
        source="rss",
        url="https://example.com/1",
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        related_symbols=["BTC"],
    ),
]


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


class _FakeFeedManager:
    """A test double for FeedManager that returns canned articles."""

    def __init__(self, articles: list[Article] | None = None):
        self._articles = articles if articles is not None else CANNED_ARTICLES
        self.feeds: list = []
        self.feeds_by_type: dict = {}

    async def fetch_all(self, symbols: list[str]) -> list[Article]:
        return self._articles

    async def has_feeds(self) -> bool:
        return True

    async def load_feeds(self) -> None:
        pass


def _make_pipeline(db, articles=None, score=0.7):
    analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=score))
    feed_manager = _FakeFeedManager(articles)
    return SentimentPipeline(
        feed_manager=feed_manager,
        analyzer=analyzer,
        db=db,
    )


class TestFetchSavesToDB:
    @pytest.mark.asyncio
    async def test_fetch_returns_new_count(self, db):
        pipeline = _make_pipeline(db)
        count = await pipeline.fetch(["BTC"])
        assert count == 1

    @pytest.mark.asyncio
    async def test_fetch_deduplicates_by_content_hash(self, db):
        pipeline = _make_pipeline(db)
        first = await pipeline.fetch(["BTC"])
        second = await pipeline.fetch(["BTC"])
        assert first == 1
        assert second == 0

    @pytest.mark.asyncio
    async def test_fetch_stores_article_in_db(self, db):
        pipeline = _make_pipeline(db)
        await pipeline.fetch(["BTC"])
        articles = await db.get_articles_for_symbol("BTC")
        assert len(articles) == 1
        assert articles[0].title == "BTC surges past $100k"


class TestScoreUsesDB:
    @pytest.mark.asyncio
    async def test_score_returns_count(self, db):
        pipeline = _make_pipeline(db)
        await pipeline.fetch(["BTC"])
        scored = await pipeline.score(["BTC"])
        assert scored == 1

    @pytest.mark.asyncio
    async def test_score_persists_to_db(self, db):
        pipeline = _make_pipeline(db)
        await pipeline.fetch(["BTC"])
        await pipeline.score(["BTC"])
        scores = await db.load_recent_scores(hours=48)
        assert len(scores) == 1
        assert scores[0].score == 0.7

    @pytest.mark.asyncio
    async def test_score_skips_already_scored(self, db):
        pipeline = _make_pipeline(db)
        await pipeline.fetch(["BTC"])
        first = await pipeline.score(["BTC"])
        second = await pipeline.score(["BTC"])
        assert first == 1
        assert second == 0  # Already scored, not re-scored

    @pytest.mark.asyncio
    async def test_score_feeds_aggregator(self, db):
        pipeline = _make_pipeline(db, score=0.7)
        await pipeline.fetch(["BTC"])
        await pipeline.score(["BTC"])
        sentiment = pipeline.get_sentiment("BTC")
        assert sentiment != 0.0


class TestWarmUp:
    @pytest.mark.asyncio
    async def test_warm_up_loads_scores_into_aggregator(self, db):
        # Pre-seed a score in the DB
        article = ArticleRecord(
            content_hash="warmup_hash",
            title="Old article",
            source="rss",
            published_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            symbols=["BTC"],
        )
        await db.save_article(article)
        await db.save_score(SentimentScoreRecord(
            article_id=article.id,
            score=0.8,
            magnitude=0.9,
            analyzer="mock",
            reasoning="Warm-up test",
        ))

        pipeline = _make_pipeline(db)
        await pipeline.warm_up(["BTC"], hours=48)
        sentiment = pipeline.get_sentiment("BTC")
        assert sentiment != 0.0


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_run_cycle_returns_sentiment_dict(self, db):
        pipeline = _make_pipeline(db, score=0.7)
        result = await pipeline.run_cycle(["BTC"])
        assert isinstance(result, dict)
        assert "BTC" in result
        assert result["BTC"] != 0.0

    @pytest.mark.asyncio
    async def test_run_cycle_no_articles(self, db):
        pipeline = _make_pipeline(db, articles=[])
        result = await pipeline.run_cycle(["BTC"])
        assert result["BTC"] == 0.0
