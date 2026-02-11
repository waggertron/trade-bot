import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.providers.mock import MockNewsProvider, MockSentimentAnalyzer
from src.providers.configs import MockNewsConfig, MockSentimentConfig
from src.sentiment.pipeline import SentimentPipeline
from src.sentiment.bridge import SentimentBridge
from src.agents.strategies.sentiment import SentimentStrategy
from src.core.models import MarketTick, AssetType


class TestSentimentE2E:
    """Full integration: news -> buffer -> score -> aggregate -> bridge -> strategy signal."""

    @pytest.fixture
    def positive_pipeline(self):
        canned = [
            {
                "title": "Bitcoin surges past $100k",
                "body": "BTC hit new all-time high today as institutional demand grows.",
                "source": "rss",
                "url": "https://example.com/1",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["BTC"],
            },
            {
                "title": "Crypto market bullish",
                "body": "Analysts predict continued growth in crypto markets.",
                "source": "rss",
                "url": "https://example.com/2",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["BTC"],
            },
        ]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.8, default_magnitude=0.9))
        return SentimentPipeline(news_providers=[news], analyzer=analyzer)

    @pytest.mark.asyncio
    async def test_pipeline_to_strategy_buy_signal(self, positive_pipeline):
        """Full flow: positive sentiment -> BUY signal."""
        # Run pipeline cycle
        scores = await positive_pipeline.run_cycle(symbols=["BTC"])
        assert scores["BTC"] > 0.5

        # Bridge to research reports
        bridge = SentimentBridge(aggregator=positive_pipeline.aggregator)
        reports = bridge.to_research_reports(["BTC"])
        assert len(reports) >= 1
        assert reports[0].sentiment_score > 0.5

        # Feed to strategy
        strategy = SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)
        tick = MarketTick(
            symbol="BTC",
            price=Decimal("100000"),
            volume=1000,
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        signal = await strategy.evaluate("BTC", [tick], research=reports)
        assert signal is not None
        assert signal.direction.value == "buy"

    @pytest.mark.asyncio
    async def test_negative_sentiment_generates_sell(self):
        """Negative sentiment -> SELL signal."""
        canned = [{
            "title": "Crypto crash imminent",
            "body": "Markets plummet as regulation fears grow.",
            "source": "rss",
            "url": "https://example.com/crash",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "related_symbols": ["BTC"],
        }]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=-0.8, default_magnitude=0.9))
        pipeline = SentimentPipeline(news_providers=[news], analyzer=analyzer)

        await pipeline.run_cycle(symbols=["BTC"])
        bridge = SentimentBridge(aggregator=pipeline.aggregator)
        reports = bridge.to_research_reports(["BTC"])

        strategy = SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)
        tick = MarketTick(
            symbol="BTC",
            price=Decimal("100000"),
            volume=1000,
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        signal = await strategy.evaluate("BTC", [tick], research=reports)
        assert signal is not None
        assert signal.direction.value == "sell"

    @pytest.mark.asyncio
    async def test_neutral_sentiment_no_signal(self):
        """Neutral sentiment -> no signal."""
        canned = [{
            "title": "Market update",
            "body": "Markets were mixed today.",
            "source": "rss",
            "url": "https://example.com/neutral",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "related_symbols": ["BTC"],
        }]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.1, default_magnitude=0.5))
        pipeline = SentimentPipeline(news_providers=[news], analyzer=analyzer)

        await pipeline.run_cycle(symbols=["BTC"])
        bridge = SentimentBridge(aggregator=pipeline.aggregator)
        reports = bridge.to_research_reports(["BTC"])

        strategy = SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)
        tick = MarketTick(
            symbol="BTC",
            price=Decimal("100000"),
            volume=1000,
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        signal = await strategy.evaluate("BTC", [tick], research=reports)
        assert signal is None  # neutral sentiment = no signal

    @pytest.mark.asyncio
    async def test_store_persistence(self, positive_pipeline):
        """After a cycle, store should have articles and scores."""
        await positive_pipeline.run_cycle(symbols=["BTC"])
        assert positive_pipeline.store.article_count() >= 1
        assert positive_pipeline.store.score_count() >= 1

    @pytest.mark.asyncio
    async def test_multiple_symbols(self):
        """Pipeline handles multiple symbols correctly."""
        canned = [
            {
                "title": "BTC news",
                "body": "BTC article.",
                "source": "rss",
                "url": "https://example.com/btc",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["BTC"],
            },
            {
                "title": "ETH news",
                "body": "ETH article.",
                "source": "rss",
                "url": "https://example.com/eth",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["ETH"],
            },
        ]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.7, default_magnitude=0.8))
        pipeline = SentimentPipeline(news_providers=[news], analyzer=analyzer)

        scores = await pipeline.run_cycle(symbols=["BTC", "ETH"])
        assert "BTC" in scores
        assert "ETH" in scores
        assert scores["BTC"] > 0
        assert scores["ETH"] > 0
