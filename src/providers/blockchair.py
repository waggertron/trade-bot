"""Blockchair on-chain data provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.providers.configs import BlockchairConfig

# Asset symbol to blockchain name mapping
BLOCKCHAIN_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BCH": "bitcoin-cash",
    "LTC": "litecoin",
    "DOGE": "dogecoin",
}


class BlockchairProvider:
    """Fetches blockchain metrics from the Blockchair API."""

    def __init__(self, config: BlockchairConfig, client: object) -> None:
        self._config = config
        self._client = client  # HttpClient protocol (get returns dict)
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}  # symbol -> (timestamp, data)

    @property
    def name(self) -> str:
        return "blockchair"

    async def get_metrics(self, symbol: str) -> dict[str, Any]:
        """Fetch on-chain metrics for a cryptocurrency.

        symbol: "BTC", "ETH", etc. (not "BTC/USD")
        Returns dict with: active_addresses, transaction_count,
        average_transaction_value, blocks_24h, etc.
        """
        import time

        # Check cache
        now = time.time()
        if symbol in self._cache:
            cached_ts, cached_data = self._cache[symbol]
            if now - cached_ts < self._config.cache_ttl_seconds:
                return cached_data

        blockchain = BLOCKCHAIN_MAP.get(symbol)
        if blockchain is None:
            return {"symbol": symbol, "error": "unsupported_blockchain"}

        url = f"{self._config.base_url}/{blockchain}/stats"
        params: dict[str, str] = {}
        if self._config.api_key:
            params["key"] = self._config.api_key

        response = await self._client.get(url, params=params)

        # Parse response
        data = response.get("data", {})
        metrics: dict[str, Any] = {
            "symbol": symbol,
            "timestamp": int(now),
            "active_addresses": data.get("mempool_transactions", 0),
            "transaction_count": data.get("transactions_24h", 0),
            "average_transaction_value": data.get("average_transaction_fee_usd_24h", 0.0),
            "blocks_24h": data.get("blocks_24h", 0),
            "hashrate": data.get("hashrate_24h", "0"),
            "difficulty": data.get("difficulty", 0),
            "market_cap": data.get("market_cap_usd", 0),
        }

        # Cache it
        self._cache[symbol] = (now, metrics)
        return metrics

    async def health_check(self) -> bool:
        """Check API connectivity."""
        try:
            response = await self._client.get(f"{self._config.base_url}/bitcoin/stats")
            return isinstance(response, dict) and "data" in response
        except Exception:
            return False
