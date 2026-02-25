"""Tests for SentimentScoringProcessor."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.db.database import Database
from src.db.models import ArticleRecord
from src.processing.processors.sentiment import SentimentScoringProcessor
from src.processing.protocols import Processor
from src.providers.configs import MockSentimentConfig
from src.providers.mock import MockSentimentAnalyzer
from src.sentiment.aggregator import SentimentAggregator


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


def _make_article(content_hash: str = "h1", symbol: str = "BTC") -> ArticleRecord:
    return ArticleRecord(
        content_hash=content_hash,
        title="BTC hits new high",
        body="Bitcoin surged today...",
        source="rss",
        published_at=datetime(2026, 1, 15, tzinfo=UTC),
        symbols=[symbol],
    )


class TestSentimentScoringProcessorProtocol:
    def test_satisfies_processor_protocol(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.5))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)
        assert isinstance(proc, Processor)

    def test_name(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.5))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)
        assert proc.name == "sentiment_scoring"


class TestSentimentScoringProcessorBehavior:
    @pytest.mark.asyncio
    async def test_scores_article_and_saves_to_db(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.7))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)

        article = _make_article()
        await db.save_article(article)
        await proc.process(article)

        assert await db.has_score(article.id, analyzer.name) is True

    @pytest.mark.asyncio
    async def test_score_value_matches_analyzer(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.8))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)

        article = _make_article()
        await db.save_article(article)
        await proc.process(article)

        scores = await db.load_recent_scores(hours=48)
        assert len(scores) == 1
        assert scores[0].score == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_skips_already_scored_article(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.5))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)

        article = _make_article()
        await db.save_article(article)
        await proc.process(article)  # First time
        await proc.process(article)  # Should be skipped

        scores = await db.load_recent_scores(hours=48)
        assert len(scores) == 1  # Only one score, not two

    @pytest.mark.asyncio
    async def test_feeds_aggregator_when_provided(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.6))
        aggregator = SentimentAggregator()
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db, aggregator=aggregator)

        article = _make_article(symbol="BTC")
        await db.save_article(article)
        await proc.process(article)

        from datetime import datetime

        score = aggregator.aggregate("BTC", datetime.now(UTC))
        assert score != 0.0

    @pytest.mark.asyncio
    async def test_works_without_aggregator(self, db):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.5))
        proc = SentimentScoringProcessor(analyzer=analyzer, db=db)  # no aggregator

        article = _make_article()
        await db.save_article(article)
        await proc.process(article)  # Should not raise

        assert await db.has_score(article.id, analyzer.name) is True
