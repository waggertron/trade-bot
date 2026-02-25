"""Tests for AnalyticsReporter: generate formatted multi-section text reports."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.analytics.attribution import StrategyAttribution
from src.analytics.models import AttributedFill
from src.analytics.monte_carlo import MonteCarloSimulator
from src.analytics.reporter import AnalyticsReporter
from src.core.models import Fill, OrderSide

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fill(
    symbol: str = "BTC/USD",
    side: OrderSide = OrderSide.BUY,
    price: float = 100.0,
    qty: float = 1.0,
) -> Fill:
    return Fill(
        order_id="test",
        symbol=symbol,
        side=side,
        quantity=Decimal(str(qty)),
        fill_price=Decimal(str(price)),
        timestamp=datetime.now(UTC),
    )


def make_attributed(
    fill: Fill,
    strategy: str = "momentum",
    regime: str = "medium",
) -> AttributedFill:
    return AttributedFill(fill=fill, strategy=strategy, regime=regime)


def _sample_fills() -> list[AttributedFill]:
    """Two strategies, each with one completed trade."""
    return [
        # momentum: buy 100, sell 130 -> +30
        make_attributed(make_fill(side=OrderSide.BUY, price=100.0), strategy="momentum"),
        make_attributed(make_fill(side=OrderSide.SELL, price=130.0), strategy="momentum"),
        # ml_ensemble: buy 200, sell 190 -> -10
        make_attributed(make_fill(side=OrderSide.BUY, price=200.0), strategy="ml_ensemble"),
        make_attributed(make_fill(side=OrderSide.SELL, price=190.0), strategy="ml_ensemble"),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyticsReporter:
    """Tests for AnalyticsReporter.generate_report()."""

    def setup_method(self) -> None:
        attribution = StrategyAttribution()
        simulator = MonteCarloSimulator(n_simulations=10, seed=42)
        self.reporter = AnalyticsReporter(attribution=attribution, simulator=simulator)

    # -- test_report_contains_total_pnl ------------------------------------

    def test_report_contains_total_pnl(self) -> None:
        fills = _sample_fills()
        report = self.reporter.generate_report(fills, initial_cash=10_000.0)
        assert "Total P&L" in report
        # momentum +30, ml_ensemble -10 = +20 total
        assert "$20.00" in report

    # -- test_report_contains_strategy_names --------------------------------

    def test_report_contains_strategy_names(self) -> None:
        fills = _sample_fills()
        report = self.reporter.generate_report(fills, initial_cash=10_000.0)
        assert "momentum" in report
        assert "ml_ensemble" in report

    # -- test_report_contains_monte_carlo -----------------------------------

    def test_report_contains_monte_carlo(self) -> None:
        fills = _sample_fills()
        report = self.reporter.generate_report(fills, initial_cash=10_000.0)
        assert "MONTE CARLO" in report

    # -- test_report_contains_percentile ------------------------------------

    def test_report_contains_percentile(self) -> None:
        fills = _sample_fills()
        report = self.reporter.generate_report(fills, initial_cash=10_000.0)
        assert "Percentile:" in report

    # -- test_empty_fills ---------------------------------------------------

    def test_empty_fills(self) -> None:
        report = self.reporter.generate_report([], initial_cash=10_000.0)
        assert "Total P&L" in report
        assert "$0.00" in report
        # Should not error out
        assert "ANALYTICS REPORT" in report

    # -- test_report_return_type --------------------------------------------

    def test_report_return_type(self) -> None:
        fills = _sample_fills()
        report = self.reporter.generate_report(fills, initial_cash=10_000.0)
        assert isinstance(report, str)
