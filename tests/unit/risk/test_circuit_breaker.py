"""Tests for DrawdownCircuitBreaker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.risk.circuit_breaker import DrawdownCircuitBreaker

NOW = datetime.now(UTC)


class TestDrawdownCircuitBreaker:
    def test_not_tripped_initially(self):
        """New breaker with reasonable value should not be tripped."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
        assert breaker.is_tripped(Decimal("10000"), NOW) is False

    def test_update_tracks_peak(self):
        """update() should track the highest portfolio value seen."""
        breaker = DrawdownCircuitBreaker()
        breaker.update(Decimal("100"), NOW)
        breaker.update(Decimal("120"), NOW)
        breaker.update(Decimal("110"), NOW)
        assert breaker.peak_value == Decimal("120")

    def test_trips_on_drawdown(self):
        """11% drawdown from peak of 10000 should trip a 10% threshold breaker."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0)
        breaker.update(Decimal("10000"), NOW)
        # 8900 is 11% below peak of 10000
        assert breaker.is_tripped(Decimal("8900"), NOW) is True

    def test_not_tripped_within_threshold(self):
        """8% drawdown should NOT trip a 10% threshold breaker."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0)
        breaker.update(Decimal("10000"), NOW)
        # 9200 is 8% below peak of 10000
        assert breaker.is_tripped(Decimal("9200"), NOW) is False

    def test_remains_tripped_during_cooldown(self):
        """Once tripped, breaker stays tripped during cooldown period."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
        breaker.update(Decimal("10000"), NOW)
        # Trip the breaker
        assert breaker.is_tripped(Decimal("8900"), NOW) is True
        # 1 hour later, still within 24-hour cooldown
        one_hour_later = NOW + timedelta(hours=1)
        assert breaker.is_tripped(Decimal("8900"), one_hour_later) is True

    def test_resets_after_cooldown_expires(self):
        """After cooldown expires, breaker should reset and return False."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
        breaker.update(Decimal("10000"), NOW)
        # Trip the breaker
        assert breaker.is_tripped(Decimal("8900"), NOW) is True
        # 25 hours later, cooldown has expired
        after_cooldown = NOW + timedelta(hours=25)
        assert breaker.is_tripped(Decimal("8900"), after_cooldown) is False

    def test_manual_reset(self):
        """reset() should clear tripped state and peak value."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0)
        breaker.update(Decimal("10000"), NOW)
        # Trip the breaker
        assert breaker.is_tripped(Decimal("8900"), NOW) is True
        # Manual reset
        breaker.reset()
        assert breaker.is_tripped(Decimal("8900"), NOW) is False
        assert breaker.peak_value == Decimal("0")

    def test_handles_zero_peak(self):
        """With zero peak (never updated), is_tripped should return False."""
        breaker = DrawdownCircuitBreaker()
        assert breaker.is_tripped(Decimal("5000"), NOW) is False
        assert breaker.is_tripped(Decimal("0"), NOW) is False

    def test_sequential_updates_track_peak(self):
        """Peak should only increase, never decrease across sequential updates."""
        breaker = DrawdownCircuitBreaker()
        values = [
            Decimal("100"),
            Decimal("150"),
            Decimal("130"),
            Decimal("200"),
            Decimal("180"),
            Decimal("190"),
        ]
        expected_peaks = [
            Decimal("100"),
            Decimal("150"),
            Decimal("150"),
            Decimal("200"),
            Decimal("200"),
            Decimal("200"),
        ]
        for value, expected_peak in zip(values, expected_peaks, strict=False):
            breaker.update(value, NOW)
            assert breaker.peak_value == expected_peak

    def test_is_in_cooldown_property(self):
        """is_in_cooldown should reflect current cooldown state."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0)
        # Not tripped -> not in cooldown
        assert breaker.is_in_cooldown is False
        # Trip it
        breaker.update(Decimal("10000"), NOW)
        breaker.is_tripped(Decimal("8900"), NOW)
        # Now in cooldown
        assert breaker.is_in_cooldown is True

    def test_peak_value_property(self):
        """peak_value property should return the current peak."""
        breaker = DrawdownCircuitBreaker()
        assert breaker.peak_value == Decimal("0")
        breaker.update(Decimal("500"), NOW)
        assert breaker.peak_value == Decimal("500")
        breaker.update(Decimal("750"), NOW)
        assert breaker.peak_value == Decimal("750")
        breaker.update(Decimal("600"), NOW)
        assert breaker.peak_value == Decimal("750")
