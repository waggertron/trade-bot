"""Tests for ProviderRegistry."""

from __future__ import annotations

import pytest

from src.providers.mock import (
    MockDataStore,
    MockFeatureProvider,
    MockMarketDataProvider,
    MockNewsProvider,
    MockOnChainProvider,
    MockSentimentAnalyzer,
)
from src.providers.protocols import (
    DataStore,
    FeatureProvider,
    MarketDataProvider,
    NewsProvider,
    OnChainProvider,
    SentimentAnalyzer,
)
from src.providers.registry import ProviderRegistry


class TestRegisterAndGet:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        mock_market = MockMarketDataProvider()
        registry.register(MarketDataProvider, mock_market)
        assert registry.get(MarketDataProvider) is mock_market

    def test_get_unregistered_raises_key_error(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="No provider registered"):
            registry.get(MarketDataProvider)

    def test_register_rejects_non_conforming(self):
        registry = ProviderRegistry()

        class NotAProvider:
            pass

        with pytest.raises(TypeError, match="does not implement"):
            registry.register(MarketDataProvider, NotAProvider())


class TestForTesting:
    def test_for_testing_creates_all_mocks(self):
        registry = ProviderRegistry.for_testing()
        assert isinstance(registry.get(MarketDataProvider), MockMarketDataProvider)
        assert isinstance(registry.get(NewsProvider), MockNewsProvider)
        assert isinstance(registry.get(SentimentAnalyzer), MockSentimentAnalyzer)
        assert isinstance(registry.get(OnChainProvider), MockOnChainProvider)
        assert isinstance(registry.get(FeatureProvider), MockFeatureProvider)
        assert isinstance(registry.get(DataStore), MockDataStore)

    def test_for_testing_allows_overrides(self):
        custom_market = MockMarketDataProvider()
        custom_market.set_price("BTC", __import__("decimal").Decimal("99999"))

        registry = ProviderRegistry.for_testing(
            overrides={MarketDataProvider: custom_market}
        )
        assert registry.get(MarketDataProvider) is custom_market
        # Other mocks still present
        assert isinstance(registry.get(NewsProvider), MockNewsProvider)


class TestAllAndHas:
    def test_all_returns_registered(self):
        registry = ProviderRegistry.for_testing()
        items = list(registry.all())
        names = [name for name, _ in items]
        assert "MarketDataProvider" in names
        assert "NewsProvider" in names
        assert "SentimentAnalyzer" in names
        assert "OnChainProvider" in names
        assert "FeatureProvider" in names
        assert "DataStore" in names
        assert len(items) == 6

    def test_has_true_and_false(self):
        registry = ProviderRegistry()
        assert registry.has(MarketDataProvider) is False
        registry.register(MarketDataProvider, MockMarketDataProvider())
        assert registry.has(MarketDataProvider) is True
        assert registry.has(NewsProvider) is False
