"""On-chain feature computation from blockchain metrics."""

from __future__ import annotations

from typing import Any


class OnChainFeatureProvider:
    """Computes trading features from on-chain blockchain metrics."""

    def __init__(self, onchain_provider: object) -> None:
        self._provider = onchain_provider
        self._history: dict[str, list[dict[str, Any]]] = {}  # symbol -> list of metric snapshots

    @property
    def name(self) -> str:
        return "onchain"

    async def compute(self, symbol: str) -> dict[str, float]:
        """Compute on-chain features for a symbol.

        symbol: "BTC", "ETH", etc. (also accepts "BTC/USD" -- the suffix is stripped).
        Returns dict with feature_name -> float:
        - exchange_inflow_ratio: proxy from tx count relative to history
        - active_addresses_trend: change vs historical average
        - onchain_tx_count: raw transaction count
        - onchain_avg_tx_value: average transaction value
        """
        # Strip "/USD" or similar suffix
        base_symbol = symbol.split("/")[0] if "/" in symbol else symbol

        metrics = await self._provider.get_metrics(base_symbol)

        if "error" in metrics:
            return {
                "exchange_inflow_ratio": 0.5,
                "active_addresses_trend": 0.0,
                "onchain_tx_count": 0.0,
            }

        # Track history for trend computation
        if base_symbol not in self._history:
            self._history[base_symbol] = []
        self._history[base_symbol].append(metrics)
        # Keep last 30 snapshots
        if len(self._history[base_symbol]) > 30:
            self._history[base_symbol] = self._history[base_symbol][-30:]

        history = self._history[base_symbol]

        # Compute features
        tx_count = float(metrics.get("transaction_count", 0))
        active_addrs = float(metrics.get("active_addresses", 0))
        avg_tx_val = float(metrics.get("average_transaction_value", 0))

        # Exchange inflow ratio: normalize tx count (0-1 scale, relative to max seen)
        max_tx = max(float(h.get("transaction_count", 1)) for h in history)
        exchange_inflow_ratio = tx_count / max_tx if max_tx > 0 else 0.5

        # Active addresses trend: current vs average
        avg_active = sum(float(h.get("active_addresses", 0)) for h in history) / len(history)
        active_addresses_trend = (active_addrs - avg_active) / avg_active if avg_active > 0 else 0.0

        return {
            "exchange_inflow_ratio": round(exchange_inflow_ratio, 4),
            "active_addresses_trend": round(active_addresses_trend, 4),
            "onchain_tx_count": tx_count,
            "onchain_avg_tx_value": avg_tx_val,
        }
