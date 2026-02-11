"""Tests for risk models — written before implementation (TDD)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.models import (
    AssetType,
    PortfolioSnapshot,
    Position,
    RiskAction,
    RiskDecision,
)
from src.risk.models import RiskContext, StrategyPerformance, VolatilityRegime


# -- VolatilityRegime --------------------------------------------------------


class TestVolatilityRegime:
    def test_values(self):
        assert VolatilityRegime.LOW == "low"
        assert VolatilityRegime.MEDIUM == "medium"
        assert VolatilityRegime.HIGH == "high"

    def test_is_str_enum(self):
        assert isinstance(VolatilityRegime.LOW, str)

    def test_all_members(self):
        members = {m.value for m in VolatilityRegime}
        assert members == {"low", "medium", "high"}


# -- StrategyPerformance -----------------------------------------------------


def _make_strategy_performance(**overrides) -> StrategyPerformance:
    defaults = dict(
        name="momentum",
        win_rate=0.55,
        avg_win=Decimal("150.00"),
        avg_loss=Decimal("100.00"),
        total_trades=100,
        recent_trades=20,
        recent_win_rate=0.60,
    )
    defaults.update(overrides)
    return StrategyPerformance(**defaults)


class TestStrategyPerformance:
    def test_creation(self):
        sp = _make_strategy_performance()
        assert sp.name == "momentum"
        assert sp.win_rate == 0.55
        assert sp.avg_win == Decimal("150.00")
        assert sp.avg_loss == Decimal("100.00")
        assert sp.total_trades == 100
        assert sp.recent_trades == 20
        assert sp.recent_win_rate == 0.60

    def test_defaults(self):
        sp = StrategyPerformance(
            name="test",
            win_rate=0.5,
            avg_win=Decimal("10"),
            avg_loss=Decimal("5"),
            total_trades=10,
        )
        assert sp.recent_trades == 0
        assert sp.recent_win_rate == 0.0

    def test_frozen(self):
        sp = _make_strategy_performance()
        with pytest.raises(ValidationError):
            sp.name = "other"  # type: ignore[misc]

    def test_invalid_win_rate_too_high(self):
        with pytest.raises(ValidationError, match="win_rate"):
            _make_strategy_performance(win_rate=1.5)

    def test_invalid_win_rate_too_low(self):
        with pytest.raises(ValidationError, match="win_rate"):
            _make_strategy_performance(win_rate=-0.1)

    def test_invalid_avg_win_negative(self):
        with pytest.raises(ValidationError, match="avg_win"):
            _make_strategy_performance(avg_win=Decimal("-10"))

    def test_invalid_avg_loss_negative(self):
        with pytest.raises(ValidationError, match="avg_loss"):
            _make_strategy_performance(avg_loss=Decimal("-5"))

    def test_invalid_total_trades_negative(self):
        with pytest.raises(ValidationError, match="total_trades"):
            _make_strategy_performance(total_trades=-1)

    def test_serialization_roundtrip(self):
        sp = _make_strategy_performance()
        data = sp.model_dump()
        restored = StrategyPerformance.model_validate(data)
        assert restored == sp


# -- RiskContext --------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def _make_portfolio() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("50000"),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("150"),
                current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            ),
            Position(
                symbol="BTC/USD",
                quantity=Decimal("0.5"),
                avg_entry_price=Decimal("40000"),
                current_price=Decimal("42000"),
                asset_type=AssetType.CRYPTO,
            ),
        ],
        timestamp=NOW,
    )


def _make_risk_context(**overrides) -> RiskContext:
    defaults = dict(
        regime=VolatilityRegime.MEDIUM,
        correlation_matrix={"AAPL:MSFT": 0.85, "AAPL:GOOGL": 0.72},
        strategy_stats={
            "momentum": _make_strategy_performance(),
        },
        drawdown_from_peak=0.05,
        portfolio=_make_portfolio(),
        daily_pnl=Decimal("-200.50"),
    )
    defaults.update(overrides)
    return RiskContext(**defaults)


class TestRiskContext:
    def test_creation(self):
        ctx = _make_risk_context()
        assert ctx.regime == VolatilityRegime.MEDIUM
        assert ctx.drawdown_from_peak == 0.05
        assert ctx.daily_pnl == Decimal("-200.50")
        assert "momentum" in ctx.strategy_stats
        assert ctx.portfolio.cash == Decimal("50000")

    def test_frozen(self):
        ctx = _make_risk_context()
        with pytest.raises(ValidationError):
            ctx.regime = VolatilityRegime.HIGH  # type: ignore[misc]

    def test_get_correlation_forward(self):
        ctx = _make_risk_context()
        assert ctx.get_correlation("AAPL", "MSFT") == 0.85

    def test_get_correlation_reverse(self):
        ctx = _make_risk_context()
        assert ctx.get_correlation("MSFT", "AAPL") == 0.85

    def test_get_correlation_missing_returns_zero(self):
        ctx = _make_risk_context()
        assert ctx.get_correlation("AAPL", "AMZN") == 0.0

    def test_invalid_drawdown_too_high(self):
        with pytest.raises(ValidationError, match="drawdown_from_peak"):
            _make_risk_context(drawdown_from_peak=1.5)

    def test_invalid_drawdown_negative(self):
        with pytest.raises(ValidationError, match="drawdown_from_peak"):
            _make_risk_context(drawdown_from_peak=-0.1)

    def test_serialization_roundtrip(self):
        ctx = _make_risk_context()
        data = ctx.model_dump()
        restored = RiskContext.model_validate(data)
        assert restored == ctx
        assert restored.get_correlation("AAPL", "MSFT") == 0.85


# -- RiskDecision (size_multiplier addition) ---------------------------------


class TestRiskDecisionSizeMultiplier:
    def test_with_size_multiplier(self):
        d = RiskDecision(
            action=RiskAction.RESIZE,
            reason="volatility adjustment",
            adjusted_quantity=Decimal("50"),
            size_multiplier=Decimal("0.75"),
        )
        assert d.size_multiplier == Decimal("0.75")
        assert d.is_approved

    def test_without_size_multiplier_backward_compat(self):
        d = RiskDecision(
            action=RiskAction.APPROVE,
            reason="all checks passed",
        )
        assert d.size_multiplier is None
        assert d.adjusted_quantity is None
        assert d.is_approved

    def test_veto_with_size_multiplier(self):
        d = RiskDecision(
            action=RiskAction.VETO,
            reason="too risky",
            size_multiplier=Decimal("0.0"),
        )
        assert not d.is_approved
        assert d.size_multiplier == Decimal("0.0")

    def test_serialization_roundtrip(self):
        d = RiskDecision(
            action=RiskAction.RESIZE,
            reason="adjusted",
            adjusted_quantity=Decimal("25"),
            size_multiplier=Decimal("0.5"),
        )
        data = d.model_dump()
        restored = RiskDecision.model_validate(data)
        assert restored == d
        assert restored.size_multiplier == Decimal("0.5")

    def test_serialization_roundtrip_none_multiplier(self):
        d = RiskDecision(
            action=RiskAction.APPROVE,
            reason="ok",
        )
        data = d.model_dump()
        restored = RiskDecision.model_validate(data)
        assert restored == d
        assert restored.size_multiplier is None
