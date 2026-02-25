"""Cross-asset strategy that detects leader-follower divergences between correlated pairs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.core.models import Signal, SignalDirection

if TYPE_CHECKING:
    from src.ml.models import FeatureVector

_DEFAULT_PAIRS: dict[str, str] = {
    "ETH/USD": "BTC/USD",
    "SOL/USD": "BTC/USD",
}


class CrossAssetStrategy:
    """Strategy that buys a follower asset when its leader is bullish but the follower lags."""

    name: str = "cross_asset"

    def __init__(
        self,
        leader_pairs: dict[str, str] | None = None,
        min_correlation: float = 0.6,
    ) -> None:
        self._pairs = leader_pairs if leader_pairs is not None else dict(_DEFAULT_PAIRS)
        self._min_correlation = min_correlation

    async def evaluate(
        self,
        symbol: str,
        features: FeatureVector,
    ) -> Signal | None:
        leader = self._pairs.get(symbol)
        if leader is None:
            return None

        leader_momentum = features.features.get("btc_momentum_lead", 0.0)
        correlation = features.features.get("btc_eth_corr_30d", 0.0)

        if abs(correlation) < self._min_correlation:
            return None

        own_sma5 = features.features.get("sma_5", 0.0)
        own_sma14 = features.features.get("sma_14", 0.0)

        if leader_momentum > 0 and own_sma5 <= own_sma14:
            confidence = min(abs(leader_momentum) * abs(correlation), 1.0)
            return Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence=confidence,
                strategy_name=self.name,
                reasoning=f"Leader {leader} bullish, {symbol} lagging",
                timestamp=datetime.now(UTC),
            )

        return None

    def required_features(self) -> list[str]:
        return ["btc_momentum_lead", "btc_eth_corr_30d", "sma_5", "sma_14"]
