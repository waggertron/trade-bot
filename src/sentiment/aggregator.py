"""SentimentAggregator — combine per-article scores into a single rolling
score per symbol using time-weighted decay.

Supports exponential and linear decay modes.  Recent articles are weighted
more heavily so the aggregate reflects the *current* sentiment landscape.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from src.sentiment.models import SentimentResult


class SentimentAggregator:
    """Aggregates per-article sentiment scores into a rolling score per symbol.

    Parameters
    ----------
    decay:
        Decay mode — ``"exponential"`` (default) or ``"linear"``.
    half_life_hours:
        Controls how quickly older scores lose influence.
        * Exponential: ``weight = 2 ** (-age / half_life)``
        * Linear: ``weight = max(0, 1 - age / (half_life * 4))``
    max_age_hours:
        Scores older than this are eligible for pruning.
    """

    def __init__(
        self,
        decay: str = "exponential",
        half_life_hours: float = 6.0,
        max_age_hours: float = 48.0,
    ) -> None:
        self._decay = decay
        self._half_life = timedelta(hours=half_life_hours)
        self._max_age = timedelta(hours=max_age_hours)
        self._scores: dict[str, list[SentimentResult]] = defaultdict(list)

    # -- public API -----------------------------------------------------------

    def add_scores(self, symbol: str, scores: list[SentimentResult]) -> None:
        """Append *scores* to the rolling buffer for *symbol*."""
        self._scores[symbol].extend(scores)

    def aggregate(self, symbol: str, now: datetime) -> float:
        """Compute the time-weighted average sentiment for *symbol*.

        Each score contributes ``score * weight * magnitude`` to the
        weighted sum, while ``weight`` alone is added to the weight total.
        Returns ``weighted_sum / weight_total`` if weight_total > 0,
        otherwise ``0.0``.
        """
        results = self._scores.get(symbol)
        if not results:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for result in results:
            age = now - result.timestamp
            weight = self._compute_weight(age)
            if weight <= 0:
                continue
            weighted_sum += result.score * weight * result.magnitude
            weight_total += weight

        if weight_total <= 0:
            return 0.0
        return weighted_sum / weight_total

    def prune(self, symbol: str, now: datetime) -> int:
        """Remove scores older than *max_age* for *symbol*.

        Returns the number of scores removed.
        """
        results = self._scores.get(symbol)
        if not results:
            return 0

        original_count = len(results)
        self._scores[symbol] = [
            r for r in results if (now - r.timestamp) <= self._max_age
        ]
        return original_count - len(self._scores[symbol])

    def symbols(self) -> list[str]:
        """Return a list of symbols that have scores (including empty lists)."""
        return list(self._scores.keys())

    # -- internals ------------------------------------------------------------

    def _compute_weight(self, age: timedelta) -> float:
        """Return the decay weight for a given *age*."""
        age_hours = age.total_seconds() / 3600.0
        half_life_hours = self._half_life.total_seconds() / 3600.0

        if self._decay == "linear":
            return max(0.0, 1.0 - age_hours / (half_life_hours * 4))

        # exponential (default)
        return 2.0 ** (-age_hours / half_life_hours)
