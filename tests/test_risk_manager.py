from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.agents.risk_manager import RiskManager
from src.core.config import RiskSettings
from src.core.models import (
    AssetType,
    PortfolioSnapshot,
    Position,
    RiskAction,
    Signal,
    SignalDirection,
)
from src.risk.circuit_breaker import DrawdownCircuitBreaker
from src.risk.models import RiskContext, StrategyPerformance, VolatilityRegime


@pytest.fixture
def risk_settings():
    return RiskSettings(
        max_position_pct=2.0,
        daily_loss_limit_pct=3.0,
        max_open_positions=3,
        stop_loss_pct=5.0,
    )


@pytest.fixture
def risk_manager(risk_settings):
    return RiskManager(risk_settings)


def make_signal(symbol="AAPL", direction=SignalDirection.BUY, confidence=0.9):
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strategy_name="test",
        timestamp=datetime.now(UTC),
        reasoning="test signal",
    )


def make_portfolio(cash=Decimal("10000"), positions=None):
    return PortfolioSnapshot(
        cash=cash,
        positions=positions or [],
        timestamp=datetime.now(UTC),
    )


async def test_approve_valid_trade(risk_manager):
    signal = make_signal()
    portfolio = make_portfolio()
    decision = await risk_manager.evaluate_trade(signal, portfolio)
    assert decision.is_approved


async def test_veto_max_positions_exceeded(risk_manager):
    positions = [
        Position(
            symbol=s,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            current_price=Decimal("100"),
            asset_type=AssetType.STOCK,
        )
        for s in ["AAPL", "MSFT", "GOOGL"]
    ]
    portfolio = make_portfolio(positions=positions)
    signal = make_signal(symbol="AMZN")
    decision = await risk_manager.evaluate_trade(signal, portfolio)
    assert decision.action == RiskAction.VETO
    assert "max open positions" in decision.reason.lower()


async def test_veto_daily_loss_limit(risk_manager):
    risk_manager.record_daily_pnl(Decimal("-350"))  # -3.5% on 10k
    portfolio = make_portfolio()
    signal = make_signal()
    decision = await risk_manager.evaluate_trade(signal, portfolio)
    assert decision.action == RiskAction.VETO
    assert "daily loss" in decision.reason.lower()


async def test_approve_within_daily_loss(risk_manager):
    risk_manager.record_daily_pnl(Decimal("-100"))  # -1% on 10k
    portfolio = make_portfolio()
    signal = make_signal()
    decision = await risk_manager.evaluate_trade(signal, portfolio)
    assert decision.is_approved


async def test_check_portfolio_health_empty(risk_manager):
    portfolio = make_portfolio()
    warnings = await risk_manager.check_portfolio_health(portfolio)
    assert warnings == []


async def test_check_portfolio_health_near_limit(risk_manager):
    risk_manager.record_daily_pnl(Decimal("-250"))  # -2.5% on 10k, near 3% limit
    portfolio = make_portfolio()
    warnings = await risk_manager.check_portfolio_health(portfolio)
    assert any("daily loss" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# New tests for enhanced RiskManager (Task 5)
# ---------------------------------------------------------------------------


def _make_risk_context(
    regime: VolatilityRegime = VolatilityRegime.MEDIUM,
    correlation_matrix: dict[str, float] | None = None,
    portfolio: PortfolioSnapshot | None = None,
    daily_pnl: Decimal = Decimal("0"),
) -> RiskContext:
    """Helper to build a RiskContext for tests."""
    if portfolio is None:
        portfolio = make_portfolio()
    return RiskContext(
        regime=regime,
        correlation_matrix=correlation_matrix or {},
        strategy_stats={
            "test": StrategyPerformance(
                name="test",
                win_rate=0.6,
                avg_win=Decimal("100"),
                avg_loss=Decimal("50"),
                total_trades=20,
            ),
        },
        drawdown_from_peak=0.0,
        portfolio=portfolio,
        daily_pnl=daily_pnl,
    )


async def test_circuit_breaker_veto(risk_settings):
    """Circuit breaker tripped -> VETO."""
    cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0, cooldown_hours=24.0)
    now = datetime.now(UTC)
    # Set peak, then trigger drawdown
    cb.update(Decimal("10000"), now)
    rm = RiskManager(risk_settings, circuit_breaker=cb)

    # Portfolio value dropped below threshold (peak 10000, now 9000 = 10% drop > 5%)
    portfolio = make_portfolio(cash=Decimal("9000"))
    signal = make_signal()
    decision = await rm.evaluate_trade(signal, portfolio)
    assert decision.action == RiskAction.VETO
    assert "circuit breaker" in decision.reason.lower()


async def test_regime_adjusted_daily_loss_limit(risk_settings):
    """HIGH regime lowers daily loss limit to 2%, so -2.5% exceeds it even though static is 3%."""
    rm = RiskManager(risk_settings)
    rm.record_daily_pnl(Decimal("-250"))  # -2.5% on 10k portfolio

    portfolio = make_portfolio()
    risk_context = _make_risk_context(regime=VolatilityRegime.HIGH, portfolio=portfolio)
    signal = make_signal()

    decision = await rm.evaluate_trade(signal, portfolio, risk_context=risk_context)
    assert decision.action == RiskAction.VETO
    assert "daily loss" in decision.reason.lower()


async def test_regime_adjusted_max_positions(risk_settings):
    """HIGH regime limits to 4 positions. With 4 filled and a new symbol -> VETO."""
    positions = [
        Position(
            symbol=s,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            current_price=Decimal("100"),
            asset_type=AssetType.STOCK,
        )
        for s in ["AAPL", "MSFT", "GOOGL", "TSLA"]
    ]
    portfolio = make_portfolio(positions=positions)
    risk_context = _make_risk_context(regime=VolatilityRegime.HIGH, portfolio=portfolio)

    # Static limit is 3 so this would be vetoed anyway; use a higher static limit
    settings = RiskSettings(
        max_position_pct=2.0,
        daily_loss_limit_pct=3.0,
        max_open_positions=10,
        stop_loss_pct=5.0,
    )
    rm = RiskManager(settings)
    signal = make_signal(symbol="AMZN")

    decision = await rm.evaluate_trade(signal, portfolio, risk_context=risk_context)
    assert decision.action == RiskAction.VETO
    assert "max open positions" in decision.reason.lower()


async def test_correlation_veto(risk_settings):
    """Correlation between signal symbol and existing position > max_correlation -> VETO."""
    positions = [
        Position(
            symbol="MSFT",
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            current_price=Decimal("100"),
            asset_type=AssetType.STOCK,
        ),
    ]
    portfolio = make_portfolio(positions=positions)
    # max_correlation defaults to 0.7; set correlation to 0.85
    risk_context = _make_risk_context(
        correlation_matrix={"AAPL:MSFT": 0.85},
        portfolio=portfolio,
    )
    rm = RiskManager(risk_settings)
    signal = make_signal(symbol="AAPL")

    decision = await rm.evaluate_trade(signal, portfolio, risk_context=risk_context)
    assert decision.action == RiskAction.VETO
    assert "correlation" in decision.reason.lower()


async def test_correlation_resize(risk_settings):
    """Correlation between max_correlation*0.7 and max_correlation -> RESIZE with multiplier."""
    positions = [
        Position(
            symbol="MSFT",
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            current_price=Decimal("100"),
            asset_type=AssetType.STOCK,
        ),
    ]
    portfolio = make_portfolio(positions=positions)
    # max_correlation=0.7, threshold for resize = 0.7 * 0.7 = 0.49
    # Use correlation 0.6, which is between 0.49 and 0.7
    risk_context = _make_risk_context(
        correlation_matrix={"AAPL:MSFT": 0.6},
        portfolio=portfolio,
    )
    rm = RiskManager(risk_settings)
    signal = make_signal(symbol="AAPL")

    decision = await rm.evaluate_trade(signal, portfolio, risk_context=risk_context)
    assert decision.action == RiskAction.RESIZE
    assert decision.size_multiplier is not None
    # multiplier = 1 - abs(corr) / max_corr = 1 - 0.6/0.7 ≈ 0.143
    expected = Decimal(str(1 - 0.6 / 0.7))
    assert abs(decision.size_multiplier - expected) < Decimal("0.01")


async def test_no_risk_context_uses_static_limits(risk_settings):
    """Without risk_context, static settings limits apply (same as existing behavior)."""
    rm = RiskManager(risk_settings)
    rm.record_daily_pnl(Decimal("-250"))  # -2.5% on 10k, below static 3% limit

    portfolio = make_portfolio()
    signal = make_signal()

    # No risk_context → uses static 3% limit → 2.5% is under → APPROVE
    decision = await rm.evaluate_trade(signal, portfolio)
    assert decision.is_approved


async def test_update_circuit_breaker(risk_settings):
    """update_circuit_breaker tracks peak value."""
    cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0, cooldown_hours=24.0)
    rm = RiskManager(risk_settings, circuit_breaker=cb)
    now = datetime.now(UTC)

    rm.update_circuit_breaker(Decimal("10000"), now)
    assert cb.peak_value == Decimal("10000")

    rm.update_circuit_breaker(Decimal("11000"), now)
    assert cb.peak_value == Decimal("11000")


async def test_circuit_breaker_none_no_error(risk_settings):
    """update_circuit_breaker with no circuit breaker set raises no error."""
    rm = RiskManager(risk_settings)  # no circuit_breaker
    now = datetime.now(UTC)
    rm.update_circuit_breaker(Decimal("10000"), now)  # should not raise
