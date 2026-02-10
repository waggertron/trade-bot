from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import (
    AssetType, Fill, MarketTick, Order, OrderSide, OrderType,
    PortfolioSnapshot, Position, ResearchReport, RiskAction, RiskDecision,
    Signal, SignalDirection,
)
from src.core.protocols import (
    ExecutionAgent, MarketDataAgent, PortfolioAgent,
    ResearchAgent, RiskManagerAgent, StrategyAgent,
)


class MockStrategy:
    name = "mock"

    async def evaluate(self, symbol, market_data, research=None):
        return Signal(
            symbol=symbol,
            direction=SignalDirection.BUY,
            confidence=0.9,
            strategy_name=self.name,
            timestamp=datetime.now(timezone.utc),
            reasoning="mock signal",
        )


class MockRiskManager:
    async def evaluate_trade(self, signal, portfolio):
        return RiskDecision(action=RiskAction.APPROVE, reason="all clear")

    async def check_portfolio_health(self, portfolio):
        return []


async def test_mock_satisfies_strategy_protocol():
    mock = MockStrategy()
    assert isinstance(mock, StrategyAgent)
    tick = MarketTick(
        symbol="AAPL", price=Decimal("150"), volume=100,
        timestamp=datetime.now(timezone.utc), asset_type=AssetType.STOCK,
    )
    signal = await mock.evaluate("AAPL", [tick])
    assert signal is not None
    assert signal.direction == SignalDirection.BUY


async def test_mock_satisfies_risk_manager_protocol():
    mock = MockRiskManager()
    assert isinstance(mock, RiskManagerAgent)
    snapshot = PortfolioSnapshot(
        cash=Decimal("10000"), positions=[], timestamp=datetime.now(timezone.utc),
    )
    signal = Signal(
        symbol="AAPL", direction=SignalDirection.BUY, confidence=0.9,
        strategy_name="test", timestamp=datetime.now(timezone.utc), reasoning="test",
    )
    decision = await mock.evaluate_trade(signal, snapshot)
    assert decision.is_approved
