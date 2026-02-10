import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.agents.risk_manager import RiskManager
from src.core.config import RiskSettings
from src.core.models import (
    AssetType, PortfolioSnapshot, Position, RiskAction,
    Signal, SignalDirection,
)


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
        symbol=symbol, direction=direction, confidence=confidence,
        strategy_name="test", timestamp=datetime.now(timezone.utc),
        reasoning="test signal",
    )


def make_portfolio(cash=Decimal("10000"), positions=None):
    return PortfolioSnapshot(
        cash=cash, positions=positions or [],
        timestamp=datetime.now(timezone.utc),
    )


async def test_approve_valid_trade(risk_manager):
    signal = make_signal()
    portfolio = make_portfolio()
    decision = await risk_manager.evaluate_trade(signal, portfolio)
    assert decision.is_approved


async def test_veto_max_positions_exceeded(risk_manager):
    positions = [
        Position(symbol=s, quantity=Decimal("10"), avg_entry_price=Decimal("100"),
                 current_price=Decimal("100"), asset_type=AssetType.STOCK)
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
