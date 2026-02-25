"""Tests for wiring ProviderRegistry into main.py."""

from __future__ import annotations

from src.core.config import Settings
from src.providers.protocols import (
    FeatureProvider,
    NewsProvider,
    OnChainProvider,
    SentimentAnalyzer,
)
from src.providers.registry import ProviderRegistry


def test_build_registry_returns_registry():
    """build_registry should return a ProviderRegistry with providers registered."""
    from main import build_registry

    settings = Settings.for_testing()
    # Build mock providers to pass in
    from src.providers.mock import (
        MockFeatureProvider,
        MockNewsProvider,
        MockOnChainProvider,
        MockSentimentAnalyzer,
    )

    registry = build_registry(
        settings,
        news_provider=MockNewsProvider(),
        sentiment_analyzer=MockSentimentAnalyzer(),
        onchain_provider=MockOnChainProvider(),
        feature_provider=MockFeatureProvider(),
    )
    assert isinstance(registry, ProviderRegistry)
    assert registry.has(NewsProvider)
    assert registry.has(SentimentAnalyzer)
    assert registry.has(OnChainProvider)
    assert registry.has(FeatureProvider)


def test_build_registry_providers_accessible():
    """Registered providers should be accessible via get()."""
    from main import build_registry
    from src.providers.mock import (
        MockFeatureProvider,
        MockNewsProvider,
        MockOnChainProvider,
        MockSentimentAnalyzer,
    )

    settings = Settings.for_testing()
    news = MockNewsProvider()
    registry = build_registry(
        settings,
        news_provider=news,
        sentiment_analyzer=MockSentimentAnalyzer(),
        onchain_provider=MockOnChainProvider(),
        feature_provider=MockFeatureProvider(),
    )
    assert registry.get(NewsProvider) is news
