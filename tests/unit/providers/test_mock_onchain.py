"""Tests for MockOnChainProvider (enhanced version)."""

from __future__ import annotations

import pytest

from src.providers.mock import MockOnChainProvider
from src.providers.protocols import OnChainProvider

# -- Protocol compliance -----------------------------------------------------


class TestMockOnChainProtocol:
    def test_implements_onchain_protocol(self):
        assert isinstance(MockOnChainProvider(), OnChainProvider)

    def test_has_name(self):
        assert MockOnChainProvider().name == "mock_onchain"


# -- Canned metrics ----------------------------------------------------------


class TestCannedMetrics:
    async def test_returns_btc_metrics(self):
        provider = MockOnChainProvider()
        metrics = await provider.get_metrics("BTC")
        assert metrics["symbol"] == "BTC"
        assert metrics["active_addresses"] == 1_000_000
        assert metrics["transaction_count"] == 500_000

    async def test_returns_eth_metrics(self):
        provider = MockOnChainProvider()
        metrics = await provider.get_metrics("ETH")
        assert metrics["symbol"] == "ETH"
        assert metrics["active_addresses"] == 500_000
        assert metrics["transaction_count"] == 1_200_000

    async def test_unknown_symbol_returns_error(self):
        provider = MockOnChainProvider()
        metrics = await provider.get_metrics("DOGE")
        assert metrics["symbol"] == "DOGE"
        assert metrics["error"] == "unknown"

    async def test_custom_metrics_override_defaults(self):
        custom = {
            "BTC": {
                "symbol": "BTC",
                "timestamp": 99,
                "active_addresses": 42,
                "transaction_count": 7,
            },
        }
        provider = MockOnChainProvider(metrics=custom)
        metrics = await provider.get_metrics("BTC")
        assert metrics["active_addresses"] == 42
        assert metrics["transaction_count"] == 7


# -- call_count tracking ----------------------------------------------------


class TestCallCount:
    async def test_starts_at_zero(self):
        provider = MockOnChainProvider()
        assert provider.call_count == 0

    async def test_increments_on_each_call(self):
        provider = MockOnChainProvider()
        await provider.get_metrics("BTC")
        await provider.get_metrics("ETH")
        await provider.get_metrics("BTC")
        assert provider.call_count == 3


# -- Failure mode ------------------------------------------------------------


class TestFailureMode:
    async def test_should_fail_raises_connection_error(self):
        provider = MockOnChainProvider(should_fail=True)
        with pytest.raises(ConnectionError, match="Mock on-chain provider failure"):
            await provider.get_metrics("BTC")

    async def test_should_fail_increments_call_count(self):
        provider = MockOnChainProvider(should_fail=True)
        with pytest.raises(ConnectionError):
            await provider.get_metrics("BTC")
        assert provider.call_count == 1


# -- health_check ------------------------------------------------------------


class TestHealthCheck:
    async def test_healthy_by_default(self):
        provider = MockOnChainProvider()
        assert await provider.health_check() is True

    async def test_unhealthy_when_should_fail(self):
        provider = MockOnChainProvider(should_fail=True)
        assert await provider.health_check() is False
