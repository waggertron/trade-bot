"""Tests for SentimentPipeline — orchestration of fetch/score/aggregate cycle."""

from __future__ import annotations

import pytest

from src.providers.configs import MockNewsConfig, MockSentimentConfig
from src.providers.mock import MockNewsProvider, MockSentimentAnalyzer
from src.sentiment.pipeline import SentimentPipeline


# -- Fixtures -----------------------------------------------------------------

CANNED_ARTICLES = [
    {
        "title": "BTC surges past $100k",
        "body": "Bitcoin broke records today...",
        "source": "rss",
        "url": "https://example.com/1",
        "published_at": "2026-01-15T00:00:00+00:00",
        "related_symbols": ["BTC"],
    },
]


def _make_pipeline(
    canned: list[dict] | None = None,
    score: float = 0.7,
) -> SentimentPipeline:
    articles = canned if canned is not None else CANNED_ARTICLES
    news = MockNewsProvider(MockNewsConfig(canned_articles=articles))
    analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=score))
    return SentimentPipeline(news_providers=[news], analyzer=analyzer)


# -- Fetch populates buffer ---------------------------------------------------


class TestFetchPopulatesBuffer:
    @pytest.mark.asyncio
    async def test_fetch_returns_new_count(self):
        pipeline = _make_pipeline()
        count = await pipeline.fetch(["BTC"])
        assert count == 1

    @pytest.mark.asyncio
    async def test_fetch_populates_buffer(self):
        pipeline = _make_pipeline()
        await pipeline.fetch(["BTC"])
        assert pipeline.buffer.pending_count("BTC") == 1

    @pytest.mark.asyncio
    async def test_fetch_multiple_symbols(self):
        canned = [
            {
                "title": "BTC surges",
                "body": "Bitcoin up",
                "source": "rss",
                "url": "https://example.com/1",
                "published_at": "2026-01-15T00:00:00+00:00",
                "related_symbols": ["BTC"],
            },
            {
                "title": "ETH rallies",
                "body": "Ethereum up",
                "source": "rss",
                "url": "https://example.com/2",
                "published_at": "2026-01-15T01:00:00+00:00",
                "related_symbols": ["ETH"],
            },
        ]
        pipeline = _make_pipeline(canned=canned)
        count = await pipeline.fetch(["BTC", "ETH"])
        # Each symbol fetch returns both articles, but dedup means each unique
        # article is ingested once. 2 unique articles total.
        assert count == 2

    @pytest.mark.asyncio
    async def test_fetch_deduplicates(self):
        pipeline = _make_pipeline()
        first = await pipeline.fetch(["BTC"])
        second = await pipeline.fetch(["BTC"])
        assert first == 1
        assert second == 0  # duplicate, not re-ingested


# -- Score processes buffered articles ----------------------------------------


class TestScoreProcessesBuffer:
    @pytest.mark.asyncio
    async def test_score_returns_count(self):
        pipeline = _make_pipeline()
        await pipeline.fetch(["BTC"])
        scored = await pipeline.score(["BTC"])
        assert scored == 1

    @pytest.mark.asyncio
    async def test_score_drains_buffer(self):
        pipeline = _make_pipeline()
        await pipeline.fetch(["BTC"])
        await pipeline.score(["BTC"])
        assert pipeline.buffer.pending_count("BTC") == 0

    @pytest.mark.asyncio
    async def test_score_no_articles_returns_zero(self):
        pipeline = _make_pipeline()
        scored = await pipeline.score(["BTC"])
        assert scored == 0

    @pytest.mark.asyncio
    async def test_score_defaults_to_buffer_symbols(self):
        pipeline = _make_pipeline()
        await pipeline.fetch(["BTC"])
        scored = await pipeline.score()  # no symbols arg -> use buffer.symbols()
        assert scored == 1


# -- get_sentiment returns aggregated score -----------------------------------


class TestGetSentiment:
    @pytest.mark.asyncio
    async def test_get_sentiment_after_cycle(self):
        pipeline = _make_pipeline(score=0.7)
        await pipeline.fetch(["BTC"])
        await pipeline.score(["BTC"])
        sentiment = pipeline.get_sentiment("BTC")
        assert sentiment != 0.0
        assert isinstance(sentiment, float)

    def test_get_sentiment_no_data(self):
        pipeline = _make_pipeline()
        sentiment = pipeline.get_sentiment("BTC")
        assert sentiment == 0.0


# -- run_cycle end-to-end -----------------------------------------------------


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_run_cycle_returns_sentiment_dict(self):
        pipeline = _make_pipeline(score=0.7)
        result = await pipeline.run_cycle(["BTC"])
        assert isinstance(result, dict)
        assert "BTC" in result
        assert result["BTC"] != 0.0

    @pytest.mark.asyncio
    async def test_run_cycle_no_articles_returns_zero(self):
        pipeline = _make_pipeline(canned=[])
        result = await pipeline.run_cycle(["BTC"])
        assert result["BTC"] == 0.0


# -- Store has articles after cycle -------------------------------------------


class TestStoreAfterCycle:
    @pytest.mark.asyncio
    async def test_store_has_articles_after_cycle(self):
        pipeline = _make_pipeline()
        await pipeline.run_cycle(["BTC"])
        assert pipeline.store.article_count() >= 1

    @pytest.mark.asyncio
    async def test_store_has_scores_after_cycle(self):
        pipeline = _make_pipeline()
        await pipeline.run_cycle(["BTC"])
        assert pipeline.store.score_count() >= 1
