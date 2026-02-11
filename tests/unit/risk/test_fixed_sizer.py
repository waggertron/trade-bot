"""Tests for FixedPositionSizer."""

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
from src.risk.fixed_sizer import FixedPositionSizer
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


def _make_signal() -> Signal:
    return Signal(
        symbol="AAPL",
        direction=SignalDirection.BUY,
        confidence=0.85,
        strategy_name="momentum",
        timestamp=NOW,
        reasoning="test signal",
    )


def _make_risk_context(portfolio: PortfolioSnapshot) -> RiskContext:
    return RiskContext(
        regime=VolatilityRegime.MEDIUM,
        correlation_matrix={},
        strategy_stats={},
        drawdown_from_peak=0.0,
        portfolio=portfolio,
        daily_pnl=Decimal("0"),
    )


# -- Tests --------------------------------------------------------------------


class TestFixedPositionSizer:
    def test_is_instance_of_protocol(self):
        """FixedPositionSizer should satisfy the PositionSizer protocol."""
        sizer = FixedPositionSizer()
        assert isinstance(sizer, PositionSizer)

    def test_name_property(self):
        """name property should return 'fixed'."""
        sizer = FixedPositionSizer()
        assert sizer.name == "fixed"

    @pytest.mark.asyncio
    async def test_computes_correct_size(self):
        """2% of 10000 = 200."""
        sizer = FixedPositionSizer(position_pct=2.0)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        signal = _make_signal()
        risk_ctx = _make_risk_context(portfolio)

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("200")

    @pytest.mark.asyncio
    async def test_caps_at_available_cash(self):
        """Portfolio value 10000 but cash only 100 -> returns 100."""
        position = Position(
            symbol="AAPL",
            quantity=Decimal("66"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("150"),
            asset_type=AssetType.STOCK,
        )
        portfolio = _make_portfolio(
            cash=Decimal("100"),
            positions=[position],
        )
        # total_value = 100 + 66*150 = 10000; 2% of 10000 = 200; but cash=100
        signal = _make_signal()
        risk_ctx = _make_risk_context(portfolio)

        sizer = FixedPositionSizer(position_pct=2.0)
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_zero_portfolio_value(self):
        """Zero portfolio value -> returns 0."""
        portfolio = _make_portfolio(cash=Decimal("0"), positions=[])
        signal = _make_signal()
        risk_ctx = _make_risk_context(portfolio)

        sizer = FixedPositionSizer()
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_zero_cash(self):
        """Zero cash -> returns 0 even if portfolio has positions."""
        position = Position(
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("150"),
            asset_type=AssetType.STOCK,
        )
        portfolio = _make_portfolio(cash=Decimal("0"), positions=[position])
        signal = _make_signal()
        risk_ctx = _make_risk_context(portfolio)

        sizer = FixedPositionSizer()
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_custom_position_pct(self):
        """5% of 10000 = 500."""
        sizer = FixedPositionSizer(position_pct=5.0)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        signal = _make_signal()
        risk_ctx = _make_risk_context(portfolio)

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("500")
