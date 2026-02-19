"""Pydantic config models for all provider subsystems."""

from __future__ import annotations

from pydantic import ConfigDict, Field, SecretStr

from src.core.base import StrictBase


# -- Shared -------------------------------------------------------------------


class RateLimit(StrictBase):
    model_config = ConfigDict(frozen=True)

    requests_per_minute: int = Field(gt=0)


# -- Market Data --------------------------------------------------------------


class MarketDataConfig(StrictBase):
    model_config = ConfigDict(frozen=True)

    timeout: float = Field(10.0, gt=0)


class KrakenMarketConfig(MarketDataConfig):
    base_url: str = "https://api.kraken.com"
    api_key: str = ""
    api_secret: str = ""


class BinanceMarketConfig(MarketDataConfig):
    base_url: str = "https://api.binance.us"


class YFinanceMarketConfig(MarketDataConfig):
    pass


class MockMarketConfig(MarketDataConfig):
    should_fail: bool = False
    default_prices: dict[str, str] = Field(default_factory=dict)
    latency_ms: int = Field(0, ge=0)


# -- News ---------------------------------------------------------------------


class NewsProviderConfig(StrictBase):
    model_config = ConfigDict(frozen=True)

    fetch_interval_seconds: int = Field(300, ge=1)
    max_articles_per_fetch: int = Field(50, ge=1)


class RSSConfig(NewsProviderConfig):
    feed_urls: list[str] = Field(min_length=1)


class RedditConfig(NewsProviderConfig):
    subreddits: list[str] = Field(
        default=["wallstreetbets", "cryptocurrency"],
    )
    client_id: str = ""
    client_secret: str = ""


class NewsAPIConfig(NewsProviderConfig):
    api_key: str = ""
    base_url: str = "https://newsapi.org/v2"


class MockNewsConfig(NewsProviderConfig):
    should_fail: bool = False
    canned_articles: list[dict] = Field(default_factory=list)
    latency_ms: int = 0


# -- Sentiment ----------------------------------------------------------------


class SentimentConfig(StrictBase):
    model_config = ConfigDict(frozen=True)


class OllamaSentimentConfig(SentimentConfig):
    model: str = "llama3.2"
    base_url: str = "http://127.0.0.1:11434"
    timeout: float = 120.0


class FinBERTSentimentConfig(SentimentConfig):
    model_name: str = "ProsusAI/finbert"
    device: str = "cpu"


class ClaudeSentimentConfig(SentimentConfig):
    api_key: SecretStr = SecretStr("")
    model: str = "claude-sonnet-4-5-20250929"


class MockSentimentConfig(SentimentConfig):
    default_score: float = 0.0
    default_magnitude: float = 0.5
    should_fail: bool = False


# -- On-Chain -----------------------------------------------------------------


class OnChainConfig(StrictBase):
    model_config = ConfigDict(frozen=True)


class BlockchairConfig(OnChainConfig):
    base_url: str = "https://api.blockchair.com"
    api_key: str = ""
    timeout_seconds: int = 10
    cache_ttl_seconds: int = 300


class MockOnChainConfig(OnChainConfig):
    should_fail: bool = False


# -- Features -----------------------------------------------------------------


class FeatureConfig(StrictBase):
    model_config = ConfigDict(frozen=True)


class TechnicalFeatureConfig(FeatureConfig):
    indicators: list[str] = Field(
        default=["sma", "rsi", "macd", "bbands", "atr"],
    )


class MockFeatureConfig(FeatureConfig):
    default_features: dict[str, float] = Field(default_factory=dict)
