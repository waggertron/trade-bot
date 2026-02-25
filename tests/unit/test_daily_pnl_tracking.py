"""Tests for daily PnL tracking in the trading loop."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.agents.risk_manager import RiskManager
from src.core.config import RiskSettings


def test_daily_pnl_tracker_initial_state():
    """DailyPnLTracker should start with no start value."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    assert tracker.day_start_value is None


def test_daily_pnl_tracker_records_start():
    """First update should set day_start_value and compute zero PnL."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    now = datetime(2026, 2, 19, 10, 0, 0, tzinfo=UTC)
    pnl = tracker.update(Decimal("100000"), now)
    assert tracker.day_start_value == Decimal("100000")
    assert pnl == Decimal("0")


def test_daily_pnl_tracker_computes_pnl():
    """After first update, PnL is current - start."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    t1 = datetime(2026, 2, 19, 10, 0, 0, tzinfo=UTC)
    tracker.update(Decimal("100000"), t1)

    t2 = datetime(2026, 2, 19, 11, 0, 0, tzinfo=UTC)
    pnl = tracker.update(Decimal("101500"), t2)
    assert pnl == Decimal("1500")


def test_daily_pnl_tracker_negative_pnl():
    """PnL can be negative."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    t1 = datetime(2026, 2, 19, 10, 0, 0, tzinfo=UTC)
    tracker.update(Decimal("100000"), t1)

    t2 = datetime(2026, 2, 19, 12, 0, 0, tzinfo=UTC)
    pnl = tracker.update(Decimal("97000"), t2)
    assert pnl == Decimal("-3000")


def test_daily_pnl_tracker_resets_at_midnight():
    """When the date changes, day_start_value resets to current value."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    day1 = datetime(2026, 2, 19, 23, 0, 0, tzinfo=UTC)
    tracker.update(Decimal("100000"), day1)
    tracker.update(Decimal("102000"), day1)

    # Next day
    day2 = datetime(2026, 2, 20, 1, 0, 0, tzinfo=UTC)
    pnl = tracker.update(Decimal("102500"), day2)
    # Reset: new day_start_value = 102500, PnL = 0
    assert tracker.day_start_value == Decimal("102500")
    assert pnl == Decimal("0")


def test_daily_pnl_tracker_feeds_risk_manager():
    """Integration: tracker PnL is fed to risk_manager.record_daily_pnl."""
    from main import DailyPnLTracker

    tracker = DailyPnLTracker()
    risk_manager = RiskManager(RiskSettings())

    t1 = datetime(2026, 2, 19, 10, 0, 0, tzinfo=UTC)
    tracker.update(Decimal("100000"), t1)

    t2 = datetime(2026, 2, 19, 14, 0, 0, tzinfo=UTC)
    pnl = tracker.update(Decimal("97500"), t2)
    risk_manager.record_daily_pnl(pnl)

    assert risk_manager._daily_pnl == Decimal("-2500")
