"""Weighted consensus resolver for combining multiple strategy signals."""

from __future__ import annotations

from collections import defaultdict

from src.core.models import Signal, SignalDirection
from src.risk.models import RiskContext


class WeightedConsensus:
    """Resolve multiple strategy signals into a single actionable signal.

    Combines signals by weighting each signal's confidence with:
    - A per-strategy config weight
    - An accuracy weight derived from recent win rate (via RiskContext)
    - A regime multiplier that adjusts weight based on volatility regime

    Signals are grouped by direction.  The direction with the highest total
    weighted score wins, and the individual signal with the highest weighted
    score in that direction is returned -- provided the total exceeds the
    minimum consensus threshold.
    """

    def __init__(
        self,
        strategy_weights: dict[str, float] | None = None,
        regime_multipliers: dict[tuple[str, str], float] | None = None,
        min_consensus_score: float = 0.3,
    ) -> None:
        self._strategy_weights = strategy_weights or {}
        self._regime_multipliers = regime_multipliers or {}
        self._min_consensus_score = min_consensus_score

    async def resolve(
        self,
        signals: list[Signal],
        risk_context: RiskContext | None = None,
    ) -> Signal | None:
        """Resolve a list of signals into a single consensus signal.

        Returns ``None`` when there are no actionable signals, or the total
        weighted score for the winning direction falls below the minimum
        consensus threshold.
        """
        # 1. Filter out HOLD signals
        actionable = [s for s in signals if s.direction != SignalDirection.HOLD]

        # 2. If no actionable signals, return None
        if not actionable:
            return None

        # 3. Score each signal
        direction_scores: dict[SignalDirection, float] = defaultdict(float)
        best_signal: dict[SignalDirection, tuple[float, Signal]] = {}

        for signal in actionable:
            config_weight = self._strategy_weights.get(signal.strategy_name, 1.0)

            if risk_context is not None:
                stats = risk_context.strategy_stats.get(signal.strategy_name)
                if stats and stats.recent_trades >= 10:
                    accuracy_weight = stats.recent_win_rate
                else:
                    accuracy_weight = 0.5
                regime_weight = self._regime_multipliers.get(
                    (signal.strategy_name, risk_context.regime.value),
                    1.0,
                )
            else:
                accuracy_weight = 0.5
                regime_weight = 1.0

            weighted_score = (
                signal.confidence * config_weight * accuracy_weight * regime_weight
            )

            direction_scores[signal.direction] += weighted_score

            current_best = best_signal.get(signal.direction)
            if current_best is None or weighted_score > current_best[0]:
                best_signal[signal.direction] = (weighted_score, signal)

        # 4. If direction_scores is empty, return None
        if not direction_scores:
            return None

        # 5. Find the winning direction
        best_direction = max(direction_scores, key=direction_scores.get)  # type: ignore[arg-type]

        # 6. Check minimum consensus threshold
        if direction_scores[best_direction] < self._min_consensus_score:
            return None

        # 7. Return the best signal for that direction
        return best_signal[best_direction][1]
