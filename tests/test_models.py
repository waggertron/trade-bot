from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import (
    AssetType,
    MarketTick,
    Signal,
    SignalDirection,
    Order,
    OrderSide,
    OrderType,
    Fill,
    Position,
    PortfolioSnapshot,
    ResearchReport,
    RiskDecision,
    RiskAction,
)


def test_market_tick_creation():
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150.25"),
        volume=1000,
        timestamp=datetime.now(timezone.utc),
        asset_type=AssetType.STOCK,
    )
    assert tick.symbol == "AAPL"
    assert tick.price == Decimal("150.25")
    assert tick.asset_type == AssetType.STOCK


def test_signal_creation():
    signal = Signal(
        symbol="AAPL",
        direction=SignalDirection.BUY,
        confidence=0.85,
        strategy_name="momentum",
        timestamp=datetime.now(timezone.utc),
        reasoning="Strong upward trend with volume confirmation",
    )
    assert signal.direction == SignalDirection.BUY
    assert 0.0 <= signal.confidence <= 1.0


def test_signal_confidence_clamped():
    signal = Signal(
        symbol="AAPL",
        direction=SignalDirection.BUY,
        confidence=1.5,
        strategy_name="momentum",
        timestamp=datetime.now(timezone.utc),
        reasoning="test",
    )
    assert signal.confidence == 1.0


def test_order_creation():
    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("10"),
        limit_price=Decimal("150.00"),
        asset_type=AssetType.STOCK,
    )
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT


def test_fill_creation():
    fill = Fill(
        order_id="ord-123",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150.10"),
        timestamp=datetime.now(timezone.utc),
        commission=Decimal("1.00"),
    )
    assert fill.fill_price == Decimal("150.10")


def test_position_unrealized_pnl():
    pos = Position(
        symbol="AAPL",
        quantity=Decimal("10"),
        avg_entry_price=Decimal("150.00"),
        current_price=Decimal("155.00"),
        asset_type=AssetType.STOCK,
    )
    assert pos.unrealized_pnl == Decimal("50.00")


def test_portfolio_snapshot_total_value():
    snapshot = PortfolioSnapshot(
        cash=Decimal("10000.00"),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("150.00"),
                current_price=Decimal("155.00"),
                asset_type=AssetType.STOCK,
            )
        ],
        timestamp=datetime.now(timezone.utc),
    )
    assert snapshot.total_value == Decimal("11550.00")


def test_risk_decision_veto():
    decision = RiskDecision(
        action=RiskAction.VETO,
        reason="Daily loss limit exceeded",
    )
    assert decision.action == RiskAction.VETO
    assert not decision.is_approved


def test_risk_decision_approve():
    decision = RiskDecision(
        action=RiskAction.APPROVE,
        reason="All checks passed",
    )
    assert decision.is_approved


def test_research_report_creation():
    report = ResearchReport(
        symbol="AAPL",
        summary="Strong earnings beat with raised guidance",
        sentiment_score=0.8,
        timestamp=datetime.now(timezone.utc),
        sources=["earnings_call", "sec_filing"],
    )
    assert report.sentiment_score == 0.8
    assert len(report.sources) == 2
