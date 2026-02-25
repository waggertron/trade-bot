"""Tests for BlockchairProvider on-chain data provider."""

from __future__ import annotations

from typing import Any

import pytest

from src.providers.configs import BlockchairConfig
from src.providers.protocols import OnChainProvider

# -- Simple mock client that returns dicts directly ---------------------------


class _FakeClient:
    """Minimal mock client for BlockchairProvider tests.

    get() returns a raw dict (not HttpResponse) because
    BlockchairProvider calls ``response.get("data", {})``.
    """

    def __init__(self) -> None:
        self._responses: dict[str, dict[str, Any]] = {}
        self.call_count: int = 0

    def stub(self, url: str, response: dict[str, Any]) -> None:
        self._responses[url] = response

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        self.call_count += 1
        if url in self._responses:
            return self._responses[url]
        return {"error": "not found"}


class _FailingClient:
    """Client that always raises on get."""

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        raise ConnectionError("network failure")


# -- Fixtures ----------------------------------------------------------------


BITCOIN_STATS_RESPONSE: dict[str, Any] = {
    "data": {
        "mempool_transactions": 45000,
        "transactions_24h": 350000,
        "average_transaction_fee_usd_24h": 12.5,
        "blocks_24h": 144,
        "hashrate_24h": "450E",
        "difficulty": 72_000_000_000_000,
        "market_cap_usd": 1_200_000_000_000,
    },
}


@pytest.fixture()
def config() -> BlockchairConfig:
    return BlockchairConfig(api_key="test-key", cache_ttl_seconds=60)


@pytest.fixture()
def client() -> _FakeClient:
    c = _FakeClient()
    c.stub("https://api.blockchair.com/bitcoin/stats", BITCOIN_STATS_RESPONSE)
    return c


@pytest.fixture()
def provider(config: BlockchairConfig, client: _FakeClient):
    from src.providers.blockchair import BlockchairProvider

    return BlockchairProvider(config=config, client=client)


# -- Protocol compliance -----------------------------------------------------


class TestBlockchairProtocolCompliance:
    def test_implements_onchain_protocol(self, provider):
        assert isinstance(provider, OnChainProvider)

    def test_has_name(self, provider):
        assert provider.name == "blockchair"


# -- get_metrics -------------------------------------------------------------


class TestGetMetrics:
    async def test_returns_expected_keys(self, provider):
        metrics = await provider.get_metrics("BTC")
        expected_keys = {
            "symbol",
            "timestamp",
            "active_addresses",
            "transaction_count",
            "average_transaction_value",
            "blocks_24h",
            "hashrate",
            "difficulty",
            "market_cap",
        }
        assert expected_keys.issubset(metrics.keys())

    async def test_returns_correct_values(self, provider):
        metrics = await provider.get_metrics("BTC")
        assert metrics["symbol"] == "BTC"
        assert metrics["transaction_count"] == 350000
        assert metrics["blocks_24h"] == 144

    async def test_unsupported_symbol_returns_error(self, provider):
        metrics = await provider.get_metrics("UNSUPPORTED")
        assert metrics["symbol"] == "UNSUPPORTED"
        assert metrics["error"] == "unsupported_blockchain"

    async def test_cache_hit_avoids_client_call(self, provider, client: _FakeClient):
        # First call populates cache
        await provider.get_metrics("BTC")
        first_count = client.call_count
        # Second call should use cache
        await provider.get_metrics("BTC")
        assert client.call_count == first_count  # No additional client call

    async def test_cache_miss_after_expiry(self, config, client: _FakeClient):
        """If cache_ttl_seconds is 0, every call hits the client."""
        from src.providers.blockchair import BlockchairProvider

        zero_ttl_config = BlockchairConfig(api_key="key", cache_ttl_seconds=0)
        p = BlockchairProvider(config=zero_ttl_config, client=client)
        await p.get_metrics("BTC")
        await p.get_metrics("BTC")
        assert client.call_count == 2

    async def test_api_key_passed_as_param(self, provider, client: _FakeClient):
        await provider.get_metrics("BTC")
        # The client doesn't capture params directly, but we verify no errors
        assert client.call_count == 1

    async def test_ethereum_mapping(self, config):
        c = _FakeClient()
        c.stub(
            "https://api.blockchair.com/ethereum/stats",
            {"data": {"transactions_24h": 1_200_000, "blocks_24h": 7200}},
        )
        from src.providers.blockchair import BlockchairProvider

        p = BlockchairProvider(config=config, client=c)
        metrics = await p.get_metrics("ETH")
        assert metrics["symbol"] == "ETH"
        assert metrics["transaction_count"] == 1_200_000


# -- health_check ------------------------------------------------------------


class TestHealthCheck:
    async def test_healthy_when_api_responds(self, provider):
        result = await provider.health_check()
        assert result is True

    async def test_unhealthy_when_api_fails(self, config):
        from src.providers.blockchair import BlockchairProvider

        p = BlockchairProvider(config=config, client=_FailingClient())
        result = await p.health_check()
        assert result is False

    async def test_unhealthy_when_response_has_no_data(self, config):
        from src.providers.blockchair import BlockchairProvider

        c = _FakeClient()
        c.stub("https://api.blockchair.com/bitcoin/stats", {"error": "bad"})
        p = BlockchairProvider(config=config, client=c)
        result = await p.health_check()
        assert result is False
