"""Tests for KellyPositionSizer."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import (
    AssetType,
    PortfolioSnapshot,
    Position,
    Signal,
    SignalDirection,
)
from src.risk.kelly_sizer import KellyPositionSizer
from src.risk.models import RiskContext, StrategyPerformance, VolatilityRegime
from src.risk.protocols import PositionSizer

NOW = datetime.now(timezone.utc)


# -- Helpers ------------------------------------------------------------------


def _make_portfolio(
    cash: Decimal = Decimal("10000"),
    positions: list[Position] | None = None,
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=cash,
        positions=positions or [],
        timestamp=NOW,
    )


def _make_signal(strategy_name: str = "momentum") -> Signal:
    return Signal(
        symbol="AAPL",
        direction=SignalDirection.BUY,
        confidence=0.85,
        strategy_name=strategy_name,
        timestamp=NOW,
        reasoning="test signal",
    )


def _make_risk_context(
    portfolio: PortfolioSnapshot,
    strategy_stats: dict[str, StrategyPerformance] | None = None,
) -> RiskContext:
    return RiskContext(
        regime=VolatilityRegime.MEDIUM,
        correlation_matrix={},
        strategy_stats=strategy_stats or {},
        drawdown_from_peak=0.0,
        portfolio=portfolio,
        daily_pnl=Decimal("0"),
    )


def _make_strategy_stats(
    name: str = "momentum",
    win_rate: float = 0.6,
    avg_win: Decimal = Decimal("200"),
    avg_loss: Decimal = Decimal("100"),
    total_trades: int = 50,
) -> StrategyPerformance:
    return StrategyPerformance(
        name=name,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        total_trades=total_trades,
    )


# -- Tests --------------------------------------------------------------------


class TestKellyPositionSizer:
    def test_is_instance_of_protocol(self):
        """KellyPositionSizer should satisfy the PositionSizer protocol."""
        sizer = KellyPositionSizer()
        assert isinstance(sizer, PositionSizer)

    def test_name_property(self):
        """name property should return 'kelly'."""
        sizer = KellyPositionSizer()
        assert sizer.name == "kelly"

    @pytest.mark.asyncio
    async def test_good_stats_computes_proper_kelly_fraction(self):
        """With good stats (win_rate=0.6, avg_win=200, avg_loss=100, total_trades=50).

        payoff_ratio = 200 / 100 = 2.0
        win_prob = 0.6
        loss_prob = 0.4
        kelly = (0.6 * 2.0 - 0.4) / 2.0 = (1.2 - 0.4) / 2.0 = 0.8 / 2.0 = 0.4
        half_kelly (multiplier=0.5) = 0.4 * 0.5 = 0.2 -> capped at 0.05
        size = 10000 * 0.05 = 500
        """
        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats()
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        # Kelly fraction 0.4 * 0.5 = 0.2, capped at 0.05 -> 10000 * 0.05 = 500
        assert result == Decimal("10000") * Decimal("0.05")

    @pytest.mark.asyncio
    async def test_moderate_stats_uncapped(self):
        """With moderate stats that yield kelly fraction below 5% cap.

        win_rate=0.55, avg_win=120, avg_loss=100, total_trades=30
        payoff_ratio = 120 / 100 = 1.2
        kelly = (0.55 * 1.2 - 0.45) / 1.2 = (0.66 - 0.45) / 1.2 = 0.21 / 1.2 = 0.175
        half_kelly = 0.175 * 0.5 = 0.0875 -> capped at 0.05
        """
        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(
            win_rate=0.55,
            avg_win=Decimal("120"),
            avg_loss=Decimal("100"),
            total_trades=30,
        )
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        # 0.0875 capped at 0.05 -> 500
        assert result == Decimal("10000") * Decimal("0.05")

    @pytest.mark.asyncio
    async def test_small_kelly_fraction_not_capped(self):
        """Stats that yield a kelly fraction below 5%, not capped.

        win_rate=0.52, avg_win=105, avg_loss=100, total_trades=25
        payoff_ratio = 105 / 100 = 1.05
        kelly = (0.52 * 1.05 - 0.48) / 1.05 = (0.546 - 0.48) / 1.05 = 0.066 / 1.05 ~ 0.06285...
        half_kelly = 0.06285... * 0.5 ~ 0.031428...
        This is < 0.05, so not capped.
        size = 10000 * 0.031428... ~ 314.28...
        """
        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(
            win_rate=0.52,
            avg_win=Decimal("105"),
            avg_loss=Decimal("100"),
            total_trades=25,
        )
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        # Compute expected: kelly fraction should be < 5% and > 0
        assert Decimal("0") < result < Decimal("500")
        # More precise check:
        # payoff_ratio = 1.05, win_prob = 0.52, loss_prob = 0.48
        # kelly = (0.52 * 1.05 - 0.48) / 1.05
        payoff = Decimal("105") / Decimal("100")
        win_prob = Decimal("0.52")
        loss_prob = Decimal("1") - win_prob
        kelly_raw = (win_prob * payoff - loss_prob) / payoff
        half_kelly = kelly_raw * Decimal("0.5")
        expected = Decimal("10000") * half_kelly
        assert result == expected

    @pytest.mark.asyncio
    async def test_insufficient_data_fallback(self):
        """With total_trades=5 (< 20) -> fallback to 1% of portfolio."""
        sizer = KellyPositionSizer()
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(total_trades=5)
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        # 1% of 10000 = 100
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_no_strategy_stats_fallback(self):
        """With no strategy stats -> fallback to 1% of portfolio."""
        sizer = KellyPositionSizer()
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, {})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_avg_loss_zero_fallback(self):
        """With avg_loss=0 -> fallback to 1% of portfolio."""
        sizer = KellyPositionSizer()
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(avg_loss=Decimal("0"), total_trades=50)
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_kelly_fraction_capped_at_5_percent(self):
        """Kelly fraction should be capped at 5% max.

        With very good stats, raw kelly can be large.
        win_rate=0.8, avg_win=500, avg_loss=50, total_trades=100
        payoff_ratio = 500 / 50 = 10
        kelly = (0.8 * 10 - 0.2) / 10 = (8 - 0.2) / 10 = 7.8 / 10 = 0.78
        half_kelly = 0.78 * 0.5 = 0.39 -> capped at 0.05
        size = 10000 * 0.05 = 500
        """
        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(
            win_rate=0.8,
            avg_win=Decimal("500"),
            avg_loss=Decimal("50"),
            total_trades=100,
        )
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("500")  # 5% of 10000

    @pytest.mark.asyncio
    async def test_result_capped_at_available_cash(self):
        """Size should not exceed available cash."""
        position = Position(
            symbol="AAPL",
            quantity=Decimal("66"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("150"),
            asset_type=AssetType.STOCK,
        )
        # total_value = 50 + 66*150 = 9950; 5% of 9950 = 497.5; but cash=50
        portfolio = _make_portfolio(cash=Decimal("50"), positions=[position])
        stats = _make_strategy_stats()  # good stats -> will hit 5% cap
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("50")  # capped at cash

    @pytest.mark.asyncio
    async def test_negative_kelly_returns_zero(self):
        """A bad strategy with negative Kelly should return 0.

        win_rate=0.3, avg_win=100, avg_loss=150, total_trades=50
        payoff_ratio = 100 / 150 = 0.6667
        kelly = (0.3 * 0.6667 - 0.7) / 0.6667 = (0.2 - 0.7) / 0.6667 = -0.5 / 0.6667 < 0
        -> max(0, negative) = 0
        """
        sizer = KellyPositionSizer(kelly_multiplier=0.5)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        stats = _make_strategy_stats(
            win_rate=0.3,
            avg_win=Decimal("100"),
            avg_loss=Decimal("150"),
            total_trades=50,
        )
        risk_ctx = _make_risk_context(portfolio, {"momentum": stats})
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_fallback_capped_at_cash(self):
        """Fallback (1% of total_value) should also be capped at cash."""
        position = Position(
            symbol="AAPL",
            quantity=Decimal("66"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("150"),
            asset_type=AssetType.STOCK,
        )
        # total_value = 5 + 9900 = 9905; 1% = 99.05; cash = 5
        portfolio = _make_portfolio(cash=Decimal("5"), positions=[position])
        risk_ctx = _make_risk_context(portfolio, {})
        signal = _make_signal()

        sizer = KellyPositionSizer()
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("5")  # capped at cash
