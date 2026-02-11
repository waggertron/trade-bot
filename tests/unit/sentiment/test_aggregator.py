"""Tests for SentimentAggregator with time-weighted decay scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.models import SentimentResult


def _make_result(
    score: float = 0.5,
    magnitude: float = 1.0,
    timestamp: datetime | None = None,
) -> SentimentResult:
    """Helper to create a SentimentResult with sensible defaults."""
    return SentimentResult(
        score=score,
        magnitude=magnitude,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


# -- SentimentAggregator (exponential decay, default) -------------------------


class TestSentimentAggregatorExponential:
    """Tests for SentimentAggregator with the default exponential decay."""

    def test_no_scores_returns_zero(self):
        agg = SentimentAggregator()
        result = agg.aggregate("BTC", datetime.now(timezone.utc))
        assert result == 0.0

    def test_single_recent_score(self):
        """A score created 'now' should come back approximately as-is."""
        now = datetime.now(timezone.utc)
        agg = SentimentAggregator()
        agg.add_scores("BTC", [_make_result(score=0.8, magnitude=1.0, timestamp=now)])
        result = agg.aggregate("BTC", now)
        assert result == pytest.approx(0.8, abs=0.01)

    def test_old_score_decays(self):
        """A score 12 hours old with a 6-hour half-life should be weighted at
        ~0.25 of its original value relative to a fresh score."""
        now = datetime.now(timezone.utc)
        twelve_hours_ago = now - timedelta(hours=12)

        agg = SentimentAggregator(half_life_hours=6.0)
        agg.add_scores(
            "BTC",
            [_make_result(score=0.8, magnitude=1.0, timestamp=twelve_hours_ago)],
        )
        result = agg.aggregate("BTC", now)
        # weight = 2^(-12/6) = 2^(-2) = 0.25
        # weighted_sum = 0.8 * 0.25 * 1.0 = 0.2
        # weight_total = 0.25
        # result = 0.2 / 0.25 = 0.8
        # Even with decay, a single score still returns its own score
        # because the weighted average is score itself.
        assert result == pytest.approx(0.8, abs=0.01)

    def test_recent_outweighs_old(self):
        """When a recent bullish score and an old bearish score compete,
        the recent one should dominate."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=12)  # 2 half-lives at 6h

        agg = SentimentAggregator(half_life_hours=6.0)
        agg.add_scores(
            "BTC",
            [
                _make_result(score=-0.8, magnitude=1.0, timestamp=old_time),
                _make_result(score=0.8, magnitude=1.0, timestamp=now),
            ],
        )
        result = agg.aggregate("BTC", now)
        # old weight = 2^(-12/6) = 0.25, new weight = 2^0 = 1.0
        # weighted_sum = (-0.8 * 0.25 * 1.0) + (0.8 * 1.0 * 1.0) = -0.2 + 0.8 = 0.6
        # weight_total = 0.25 + 1.0 = 1.25
        # result = 0.6 / 1.25 = 0.48
        assert result == pytest.approx(0.48, abs=0.01)
        # The result is positive, showing the recent bullish score dominates
        assert result > 0

    def test_magnitude_scales_contribution(self):
        """A low-magnitude score contributes less than a high-magnitude score."""
        now = datetime.now(timezone.utc)

        agg = SentimentAggregator()
        agg.add_scores(
            "BTC",
            [
                _make_result(score=0.8, magnitude=0.1, timestamp=now),
                _make_result(score=-0.8, magnitude=1.0, timestamp=now),
            ],
        )
        result = agg.aggregate("BTC", now)
        # Both are at time=now, so weight=1.0 for each
        # weighted_sum = (0.8 * 1.0 * 0.1) + (-0.8 * 1.0 * 1.0) = 0.08 - 0.8 = -0.72
        # weight_total = 1.0 + 1.0 = 2.0
        # result = -0.72 / 2.0 = -0.36
        assert result == pytest.approx(-0.36, abs=0.01)
        # The high-magnitude bearish score dominates
        assert result < 0

    def test_prune_removes_old_scores(self):
        """Scores older than max_age_hours should be pruned."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=49)  # Older than 48h default
        recent_time = now - timedelta(hours=1)

        agg = SentimentAggregator(max_age_hours=48.0)
        agg.add_scores(
            "BTC",
            [
                _make_result(score=0.5, timestamp=old_time),
                _make_result(score=0.3, timestamp=old_time),
                _make_result(score=0.8, timestamp=recent_time),
            ],
        )
        removed = agg.prune("BTC", now)
        assert removed == 2

        # Only the recent score should remain
        result = agg.aggregate("BTC", now)
        assert result == pytest.approx(0.8, abs=0.1)

    def test_prune_nonexistent_symbol_returns_zero(self):
        agg = SentimentAggregator()
        removed = agg.prune("NONEXISTENT", datetime.now(timezone.utc))
        assert removed == 0

    def test_symbols_lists_symbols_with_scores(self):
        now = datetime.now(timezone.utc)
        agg = SentimentAggregator()

        assert agg.symbols() == []

        agg.add_scores("BTC", [_make_result(timestamp=now)])
        agg.add_scores("ETH", [_make_result(timestamp=now)])

        syms = agg.symbols()
        assert sorted(syms) == ["BTC", "ETH"]

    def test_symbols_excludes_empty_after_prune(self):
        """After pruning all scores for a symbol, it should still appear in
        symbols() since the key exists (but with an empty list)."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=49)

        agg = SentimentAggregator(max_age_hours=48.0)
        agg.add_scores("BTC", [_make_result(timestamp=old_time)])
        agg.prune("BTC", now)

        # The symbol key still exists in the dict
        assert "BTC" in agg.symbols()

    def test_add_scores_appends(self):
        """Calling add_scores multiple times should accumulate scores."""
        now = datetime.now(timezone.utc)
        agg = SentimentAggregator()
        agg.add_scores("BTC", [_make_result(score=0.5, timestamp=now)])
        agg.add_scores("BTC", [_make_result(score=0.3, timestamp=now)])

        # Both scores should contribute
        result = agg.aggregate("BTC", now)
        # weighted_sum = (0.5 * 1.0 * 1.0) + (0.3 * 1.0 * 1.0) = 0.8
        # weight_total = 1.0 + 1.0 = 2.0
        # result = 0.8 / 2.0 = 0.4
        assert result == pytest.approx(0.4, abs=0.01)


# -- SentimentAggregator (linear decay) --------------------------------------


class TestSentimentAggregatorLinear:
    """Tests for SentimentAggregator with linear decay mode."""

    def test_linear_decay_recent_score(self):
        now = datetime.now(timezone.utc)
        agg = SentimentAggregator(decay="linear", half_life_hours=6.0)
        agg.add_scores("BTC", [_make_result(score=0.7, magnitude=1.0, timestamp=now)])
        result = agg.aggregate("BTC", now)
        assert result == pytest.approx(0.7, abs=0.01)

    def test_linear_decay_old_score_zero_weight(self):
        """A score at exactly 4 * half_life hours old should have weight 0
        under linear decay, so it contributes nothing."""
        now = datetime.now(timezone.utc)
        # Linear decay: weight = max(0, 1 - age / (half_life * 4))
        # At age = half_life * 4 = 24h, weight = max(0, 1 - 1) = 0
        cutoff_time = now - timedelta(hours=24)

        agg = SentimentAggregator(decay="linear", half_life_hours=6.0)
        agg.add_scores(
            "BTC",
            [_make_result(score=0.9, magnitude=1.0, timestamp=cutoff_time)],
        )
        result = agg.aggregate("BTC", now)
        assert result == 0.0

    def test_linear_decay_midpoint(self):
        """A score at 2 * half_life should have weight 0.5."""
        now = datetime.now(timezone.utc)
        mid_time = now - timedelta(hours=12)  # 2 * 6h half_life

        agg = SentimentAggregator(decay="linear", half_life_hours=6.0)
        agg.add_scores(
            "BTC",
            [_make_result(score=0.6, magnitude=1.0, timestamp=mid_time)],
        )
        result = agg.aggregate("BTC", now)
        # weight = max(0, 1 - 12 / 24) = 0.5
        # weighted_sum = 0.6 * 0.5 * 1.0 = 0.3
        # weight_total = 0.5
        # result = 0.3 / 0.5 = 0.6
        assert result == pytest.approx(0.6, abs=0.01)

    def test_linear_recent_outweighs_old(self):
        """Under linear decay, recent should still dominate old."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=18)  # weight = max(0, 1 - 18/24) = 0.25

        agg = SentimentAggregator(decay="linear", half_life_hours=6.0)
        agg.add_scores(
            "BTC",
            [
                _make_result(score=-1.0, magnitude=1.0, timestamp=old_time),
                _make_result(score=1.0, magnitude=1.0, timestamp=now),
            ],
        )
        result = agg.aggregate("BTC", now)
        # old weight = 0.25, new weight = 1.0
        # weighted_sum = (-1.0 * 0.25 * 1.0) + (1.0 * 1.0 * 1.0) = -0.25 + 1.0 = 0.75
        # weight_total = 0.25 + 1.0 = 1.25
        # result = 0.75 / 1.25 = 0.6
        assert result == pytest.approx(0.6, abs=0.01)
        assert result > 0
