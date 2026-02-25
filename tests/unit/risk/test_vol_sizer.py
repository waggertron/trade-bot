"""Tests for VolTargetedPositionSizer."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.core.models import (
    AssetType,
    PortfolioSnapshot,
    Position,
    Signal,
    SignalDirection,
)
from src.risk.models import RiskContext, VolatilityRegime
from src.risk.protocols import PositionSizer
from src.risk.vol_sizer import VolTargetedPositionSizer

NOW = datetime.now(UTC)


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


def _make_risk_context(
    portfolio: PortfolioSnapshot,
    regime: VolatilityRegime = VolatilityRegime.MEDIUM,
) -> RiskContext:
    return RiskContext(
        regime=regime,
        correlation_matrix={},
        strategy_stats={},
        drawdown_from_peak=0.0,
        portfolio=portfolio,
        daily_pnl=Decimal("0"),
    )


# -- Tests --------------------------------------------------------------------


class TestVolTargetedPositionSizer:
    def test_is_instance_of_protocol(self):
        """VolTargetedPositionSizer should satisfy the PositionSizer protocol."""
        sizer = VolTargetedPositionSizer()
        assert isinstance(sizer, PositionSizer)

    def test_name_property(self):
        """name property should return 'vol_targeted'."""
        sizer = VolTargetedPositionSizer()
        assert sizer.name == "vol_targeted"

    @pytest.mark.asyncio
    async def test_low_regime_full_base_size(self):
        """LOW regime -> multiplier 1.0 -> full 1% of portfolio.

        base_size = 10000 * 0.01 = 100
        regime_multiplier = 1.0
        size = 100 * 1.0 = 100
        """
        sizer = VolTargetedPositionSizer(target_vol_contribution=0.01)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.LOW)
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_medium_regime_75_percent(self):
        """MEDIUM regime -> multiplier 0.75 -> 75% of base size.

        base_size = 10000 * 0.01 = 100
        regime_multiplier = 0.75
        size = 100 * 0.75 = 75
        """
        sizer = VolTargetedPositionSizer(target_vol_contribution=0.01)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.MEDIUM)
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("75")

    @pytest.mark.asyncio
    async def test_high_regime_50_percent(self):
        """HIGH regime -> multiplier 0.5 -> 50% of base size.

        base_size = 10000 * 0.01 = 100
        regime_multiplier = 0.5
        size = 100 * 0.5 = 50
        """
        sizer = VolTargetedPositionSizer(target_vol_contribution=0.01)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.HIGH)
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("50")

    @pytest.mark.asyncio
    async def test_result_capped_at_cash(self):
        """Size should not exceed available cash."""
        position = Position(
            symbol="AAPL",
            quantity=Decimal("100"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("150"),
            asset_type=AssetType.STOCK,
        )
        # total_value = 10 + 15000 = 15010; base = 15010 * 0.01 = 150.10
        # LOW regime -> 150.10 * 1.0 = 150.10 -> capped at 10
        portfolio = _make_portfolio(cash=Decimal("10"), positions=[position])
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.LOW)
        signal = _make_signal()

        sizer = VolTargetedPositionSizer(target_vol_contribution=0.01)
        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("10")

    @pytest.mark.asyncio
    async def test_custom_target_vol_contribution(self):
        """Custom target_vol_contribution=0.02 -> 2% base size.

        base_size = 10000 * 0.02 = 200
        LOW regime -> 200 * 1.0 = 200
        """
        sizer = VolTargetedPositionSizer(target_vol_contribution=0.02)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.LOW)
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("200")

    @pytest.mark.asyncio
    async def test_custom_target_with_high_regime(self):
        """Custom target_vol_contribution=0.02 with HIGH regime.

        base_size = 10000 * 0.02 = 200
        HIGH regime -> 200 * 0.5 = 100
        """
        sizer = VolTargetedPositionSizer(target_vol_contribution=0.02)
        portfolio = _make_portfolio(cash=Decimal("10000"))
        risk_ctx = _make_risk_context(portfolio, VolatilityRegime.HIGH)
        signal = _make_signal()

        result = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert result == Decimal("100")
