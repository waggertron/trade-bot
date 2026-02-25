"""End-to-end integration tests for the full risk management pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

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
from src.risk.fixed_sizer import FixedPositionSizer
from src.risk.kelly_sizer import KellyPositionSizer
from src.risk.models import RiskContext, StrategyPerformance, VolatilityRegime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_portfolio(
    cash: Decimal = Decimal("50000"),
    positions: list[Position] | None = None,
    ts: datetime | None = None,
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=cash,
        positions=positions or [],
        timestamp=ts or datetime(2025, 6, 1, 12, 0, 0),
    )


def _make_signal(
    symbol: str = "AAPL",
    direction: SignalDirection = SignalDirection.BUY,
    strategy: str = "momentum",
    confidence: float = 0.75,
    ts: datetime | None = None,
) -> Signal:
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strategy_name=strategy,
        timestamp=ts or datetime(2025, 6, 1, 12, 0, 0),
        reasoning="Test signal",
    )


def _make_risk_context(
    regime: VolatilityRegime = VolatilityRegime.MEDIUM,
    correlations: dict[str, float] | None = None,
    strategy_stats: dict[str, StrategyPerformance] | None = None,
    drawdown: float = 0.0,
    portfolio: PortfolioSnapshot | None = None,
    daily_pnl: Decimal = Decimal("0"),
) -> RiskContext:
    port = portfolio or _make_portfolio()
    return RiskContext(
        regime=regime,
        correlation_matrix=correlations or {},
        strategy_stats=strategy_stats or {},
        drawdown_from_peak=drawdown,
        portfolio=port,
        daily_pnl=daily_pnl,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestRiskPipelineE2E:
    """Full integration: risk manager + sizers + circuit breaker working together."""

    async def test_full_risk_pipeline_approve(self):
        """Happy path: moderate settings, MEDIUM regime, approved trade with valid size."""
        settings = RiskSettings(
            max_position_pct=2.0,
            daily_loss_limit_pct=3.0,
            max_open_positions=10,
            max_correlation=0.7,
        )
        sizer = FixedPositionSizer(position_pct=2.0)
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)

        positions = [
            Position(
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("150"),
                current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            ),
            Position(
                symbol="GOOG",
                quantity=Decimal("5"),
                avg_entry_price=Decimal("2700"),
                current_price=Decimal("2750"),
                asset_type=AssetType.STOCK,
            ),
        ]
        portfolio = _make_portfolio(cash=Decimal("50000"), positions=positions)

        risk_ctx = _make_risk_context(
            regime=VolatilityRegime.MEDIUM,
            correlations={},
            strategy_stats={
                "momentum": StrategyPerformance(
                    name="momentum",
                    win_rate=0.55,
                    avg_win=Decimal("150"),
                    avg_loss=Decimal("100"),
                    total_trades=40,
                ),
            },
            portfolio=portfolio,
        )

        rm = RiskManager(settings=settings, position_sizer=sizer, circuit_breaker=breaker)

        # Update circuit breaker with current portfolio value so it has a peak
        now = datetime(2025, 6, 1, 12, 0, 0)
        rm.update_circuit_breaker(portfolio.total_value, now)

        signal = _make_signal(symbol="MSFT", ts=now)

        decision = await rm.evaluate_trade(signal, portfolio, risk_ctx)
        assert decision.action == RiskAction.APPROVE, f"Expected APPROVE, got {decision}"
        assert decision.reason == "All risk checks passed"

        # Compute position size via sizer
        size = await sizer.compute_size(signal, portfolio, risk_ctx)
        assert size > 0
        expected = portfolio.total_value * Decimal("0.02")
        assert size == min(expected, portfolio.cash)

    async def test_regime_aware_limits_tighten_in_high_vol(self):
        """HIGH regime tightens daily loss limit; LOW regime loosens it."""
        settings = RiskSettings(
            daily_loss_limit_pct=3.0,
            max_open_positions=10,
            max_correlation=0.7,
        )
        portfolio = _make_portfolio(cash=Decimal("100000"))
        signal = _make_signal()

        rm = RiskManager(settings=settings)

        # Daily PnL at -2.5% of 100_000 = -2500
        rm.record_daily_pnl(Decimal("-2500"))

        # --- HIGH regime: effective daily_loss_limit_pct = 2.0% ---
        # 2.5% >= 2.0% -> should VETO
        high_ctx = _make_risk_context(
            regime=VolatilityRegime.HIGH,
            portfolio=portfolio,
            daily_pnl=Decimal("-2500"),
        )

        decision_high = await rm.evaluate_trade(signal, portfolio, high_ctx)
        assert decision_high.action == RiskAction.VETO, (
            f"Expected VETO in HIGH regime, got {decision_high}"
        )
        assert "Daily loss limit exceeded" in decision_high.reason

        # --- LOW regime: effective daily_loss_limit_pct = 4.0% ---
        # 2.5% < 4.0% -> should APPROVE
        low_ctx = _make_risk_context(
            regime=VolatilityRegime.LOW,
            portfolio=portfolio,
            daily_pnl=Decimal("-2500"),
        )

        decision_low = await rm.evaluate_trade(signal, portfolio, low_ctx)
        assert decision_low.action == RiskAction.APPROVE, (
            f"Expected APPROVE in LOW regime, got {decision_low}"
        )

    async def test_correlation_blocks_correlated_trade(self):
        """High correlation between existing position and new signal triggers VETO."""
        settings = RiskSettings(
            max_correlation=0.7,
            daily_loss_limit_pct=5.0,
            max_open_positions=10,
        )

        btc_position = Position(
            symbol="BTC/USD",
            quantity=Decimal("1"),
            avg_entry_price=Decimal("60000"),
            current_price=Decimal("62000"),
            asset_type=AssetType.CRYPTO,
        )
        portfolio = _make_portfolio(
            cash=Decimal("50000"),
            positions=[btc_position],
        )

        # Correlation of 0.85 between BTC/USD and ETH/USD exceeds 0.7 limit
        risk_ctx = _make_risk_context(
            regime=VolatilityRegime.MEDIUM,
            correlations={"BTC/USD:ETH/USD": 0.85},
            portfolio=portfolio,
        )

        rm = RiskManager(settings=settings)
        signal = _make_signal(symbol="ETH/USD")

        decision = await rm.evaluate_trade(signal, portfolio, risk_ctx)
        assert decision.action == RiskAction.VETO, (
            f"Expected VETO for correlated trade, got {decision}"
        )
        assert "correlation" in decision.reason.lower()
        assert "BTC/USD" in decision.reason

    async def test_circuit_breaker_halts_and_recovers(self):
        """Circuit breaker trips on drawdown, holds during cooldown, recovers after."""
        breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=1.0)

        t0 = datetime(2025, 6, 1, 10, 0, 0)

        # Set the peak value
        breaker.update(Decimal("10000"), t0)
        assert breaker.peak_value == Decimal("10000")

        # Portfolio drops to 8800 -> 12% drawdown -> should trip
        t1 = t0 + timedelta(minutes=30)
        assert breaker.is_tripped(Decimal("8800"), t1) is True
        assert breaker.is_in_cooldown is True

        # Wire it into RiskManager and verify VETO
        settings = RiskSettings(daily_loss_limit_pct=5.0, max_open_positions=10)
        rm = RiskManager(settings=settings, circuit_breaker=breaker)

        portfolio = _make_portfolio(cash=Decimal("8800"))
        signal = _make_signal(ts=t1)

        decision = await rm.evaluate_trade(signal, portfolio)
        assert decision.action == RiskAction.VETO
        assert "circuit breaker" in decision.reason.lower()

        # Still in cooldown 30 minutes later
        t2 = t1 + timedelta(minutes=30)
        assert breaker.is_tripped(Decimal("8800"), t2) is True

        # Advance past cooldown (1 hour after trip)
        t3 = t1 + timedelta(hours=1, seconds=1)
        assert breaker.is_tripped(Decimal("8800"), t3) is False
        assert breaker.is_in_cooldown is False

    async def test_kelly_sizer_with_strategy_stats(self):
        """Kelly sizer computes a reasonable position size from strategy performance."""
        portfolio = _make_portfolio(cash=Decimal("100000"))

        stats = StrategyPerformance(
            name="momentum",
            win_rate=0.6,
            avg_win=Decimal("200"),
            avg_loss=Decimal("100"),
            total_trades=50,
        )

        risk_ctx = _make_risk_context(
            regime=VolatilityRegime.MEDIUM,
            strategy_stats={"momentum": stats},
            portfolio=portfolio,
        )

        kelly_sizer = KellyPositionSizer(kelly_multiplier=0.5)
        signal = _make_signal(strategy="momentum")

        size = await kelly_sizer.compute_size(signal, portfolio, risk_ctx)

        # Kelly fraction: (0.6*2 - 0.4)/2 = 0.4, half-kelly = 0.2, capped at 5%
        # So effective fraction = 5% of total_value = 5000
        assert size > Decimal("0"), f"Expected positive size, got {size}"
        max_allowed = portfolio.total_value * Decimal("0.05")
        assert size <= max_allowed, f"Kelly size {size} exceeds 5% cap of {max_allowed}"
        assert size <= portfolio.cash, "Size must not exceed available cash"

        # With these stats, Kelly should produce a non-trivial allocation
        # (much more than the 1% fallback)
        fallback = portfolio.total_value * Decimal("0.01")
        assert size >= fallback, f"Kelly size {size} should be at least the 1% fallback {fallback}"
