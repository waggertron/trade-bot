"""Tests for wiring OnChainFeatureProvider with mock/real fallback."""

from __future__ import annotations

import pytest

from src.core.config import Settings
from src.providers.mock import MockOnChainProvider
from src.providers.onchain_features import OnChainFeatureProvider


def test_build_onchain_provider_mock_true():
    """When use_mocks.onchain=True, uses MockOnChainProvider."""
    from main import build_onchain_provider

    settings = Settings.for_testing(use_mocks={"onchain": True})
    provider = build_onchain_provider(settings)
    assert isinstance(provider, OnChainFeatureProvider)
    assert isinstance(provider._provider, MockOnChainProvider)


def test_build_onchain_provider_mock_false():
    """When use_mocks.onchain=False, uses BlockchairProvider."""
    from main import build_onchain_provider
    from src.providers.blockchair import BlockchairProvider

    settings = Settings.for_testing(use_mocks={"onchain": False})
    provider = build_onchain_provider(settings)
    assert isinstance(provider, OnChainFeatureProvider)
    assert isinstance(provider._provider, BlockchairProvider)


@pytest.mark.asyncio
async def test_onchain_feature_provider_with_mock():
    """OnChainFeatureProvider with MockOnChainProvider returns features."""
    mock_provider = MockOnChainProvider()
    onchain = OnChainFeatureProvider(mock_provider)
    features = await onchain.compute("BTC/USD")
    assert "exchange_inflow_ratio" in features
    assert "active_addresses_trend" in features
