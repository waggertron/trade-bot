"""Tests for OnChainFeatureProvider."""
from __future__ import annotations

from typing import Any

import pytest


# -- Minimal stub provider that returns dicts --------------------------------


class _StubOnChainProvider:
    """Returns canned metrics for testing OnChainFeatureProvider."""

    def __init__(self, metrics: dict[str, dict[str, Any]]) -> None:
        self._metrics = metrics

    @property
    def name(self) -> str:
        return "stub_onchain"

    async def get_metrics(self, symbol: str) -> dict[str, Any]:
        return dict(self._metrics.get(symbol, {"symbol": symbol, "error": "unknown"}))

    async def health_check(self) -> bool:
        return True


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture()
def btc_metrics() -> dict[str, Any]:
    return {
        "symbol": "BTC",
        "timestamp": 1700000000,
        "active_addresses": 1_000_000,
        "transaction_count": 500_000,
        "average_transaction_value": 25000.0,
        "blocks_24h": 144,
    }


@pytest.fixture()
def stub_provider(btc_metrics: dict[str, Any]) -> _StubOnChainProvider:
    return _StubOnChainProvider(metrics={"BTC": btc_metrics})


@pytest.fixture()
def feature_provider(stub_provider: _StubOnChainProvider):
    from src.providers.onchain_features import OnChainFeatureProvider

    return OnChainFeatureProvider(onchain_provider=stub_provider)


# -- compute returns expected features ---------------------------------------


class TestComputeBasic:
    async def test_returns_expected_keys(self, feature_provider):
        features = await feature_provider.compute("BTC")
        expected = {
            "exchange_inflow_ratio",
            "active_addresses_trend",
            "onchain_tx_count",
            "onchain_avg_tx_value",
        }
        assert expected == set(features.keys())

    async def test_all_values_are_floats(self, feature_provider):
        features = await feature_provider.compute("BTC")
        for key, value in features.items():
            assert isinstance(value, float), f"{key} is {type(value)}, expected float"

    async def test_tx_count_matches_metric(self, feature_provider, btc_metrics):
        features = await feature_provider.compute("BTC")
        assert features["onchain_tx_count"] == float(btc_metrics["transaction_count"])

    async def test_avg_tx_value_matches_metric(self, feature_provider, btc_metrics):
        features = await feature_provider.compute("BTC")
        assert features["onchain_avg_tx_value"] == float(
            btc_metrics["average_transaction_value"]
        )


# -- Error handling ----------------------------------------------------------


class TestComputeErrors:
    async def test_handles_error_metrics(self):
        """Unknown symbol yields safe default features."""
        from src.providers.onchain_features import OnChainFeatureProvider

        stub = _StubOnChainProvider(metrics={})  # no data at all
        fp = OnChainFeatureProvider(onchain_provider=stub)
        features = await fp.compute("UNKNOWN")
        assert features["exchange_inflow_ratio"] == 0.5
        assert features["active_addresses_trend"] == 0.0
        assert features["onchain_tx_count"] == 0.0


# -- Symbol stripping --------------------------------------------------------


class TestSymbolStripping:
    async def test_strips_slash_usd(self, stub_provider):
        """'BTC/USD' should be stripped to 'BTC'."""
        from src.providers.onchain_features import OnChainFeatureProvider

        fp = OnChainFeatureProvider(onchain_provider=stub_provider)
        features = await fp.compute("BTC/USD")
        # Should still find BTC metrics
        assert features["onchain_tx_count"] == 500_000.0

    async def test_plain_symbol_works(self, feature_provider):
        features = await feature_provider.compute("BTC")
        assert features["onchain_tx_count"] == 500_000.0


# -- Trend computation with history ------------------------------------------


class TestTrendComputation:
    async def test_first_call_trend_is_zero(self, feature_provider):
        """With only one data point, trend should be 0."""
        features = await feature_provider.compute("BTC")
        assert features["active_addresses_trend"] == 0.0

    async def test_increasing_addresses_positive_trend(self):
        """When addresses grow, trend should be positive."""
        from src.providers.onchain_features import OnChainFeatureProvider

        # First snapshot: 1_000_000 addresses
        metrics_v1 = {
            "BTC": {
                "symbol": "BTC",
                "timestamp": 1700000000,
                "active_addresses": 1_000_000,
                "transaction_count": 500_000,
                "average_transaction_value": 25000.0,
                "blocks_24h": 144,
            },
        }
        stub = _StubOnChainProvider(metrics=metrics_v1)
        fp = OnChainFeatureProvider(onchain_provider=stub)
        await fp.compute("BTC")

        # Second snapshot: 1_500_000 addresses (50% increase)
        stub._metrics["BTC"]["active_addresses"] = 1_500_000
        features = await fp.compute("BTC")
        # Average of 1M and 1.5M = 1.25M; trend = (1.5M - 1.25M) / 1.25M = 0.2
        assert features["active_addresses_trend"] > 0

    async def test_exchange_inflow_ratio_scales(self):
        """Inflow ratio should be 1.0 at maximum transaction count."""
        from src.providers.onchain_features import OnChainFeatureProvider

        metrics = {
            "BTC": {
                "symbol": "BTC",
                "timestamp": 1700000000,
                "active_addresses": 1_000_000,
                "transaction_count": 500_000,
                "average_transaction_value": 25000.0,
                "blocks_24h": 144,
            },
        }
        stub = _StubOnChainProvider(metrics=metrics)
        fp = OnChainFeatureProvider(onchain_provider=stub)
        features = await fp.compute("BTC")
        # Only one data point: max == current, so ratio = 1.0
        assert features["exchange_inflow_ratio"] == 1.0

    async def test_history_capped_at_30(self):
        """Internal history list should not exceed 30 entries."""
        from src.providers.onchain_features import OnChainFeatureProvider

        metrics = {
            "BTC": {
                "symbol": "BTC",
                "timestamp": 1700000000,
                "active_addresses": 1_000_000,
                "transaction_count": 500_000,
                "average_transaction_value": 25000.0,
                "blocks_24h": 144,
            },
        }
        stub = _StubOnChainProvider(metrics=metrics)
        fp = OnChainFeatureProvider(onchain_provider=stub)
        for _ in range(40):
            await fp.compute("BTC")
        assert len(fp._history["BTC"]) == 30
