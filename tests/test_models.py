from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.models import (
    AssetType,
    Fill,
    MarketTick,
    Order,
    OrderSide,
    OrderType,
    PortfolioSnapshot,
    Position,
    ResearchReport,
    RiskAction,
    RiskDecision,
    Signal,
    SignalDirection,
)

# -- Existing tests (preserved) -------------------------------------------


def test_market_tick_creation():
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150.25"),
        volume=1000,
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
        sources=["earnings_call", "sec_filing"],
    )
    assert report.sentiment_score == 0.8
    assert len(report.sources) == 2


# -- New validation tests --------------------------------------------------


class TestMarketTickValidation:
    def test_rejects_negative_price(self):
        with pytest.raises(ValidationError):
            MarketTick(
                symbol="BTC/USD",
                price=Decimal("-1"),
                volume=100,
                timestamp=datetime.now(UTC),
                asset_type=AssetType.CRYPTO,
            )

    def test_rejects_negative_volume(self):
        with pytest.raises(ValidationError):
            MarketTick(
                symbol="BTC/USD",
                price=Decimal("50000"),
                volume=-1,
                timestamp=datetime.now(UTC),
                asset_type=AssetType.CRYPTO,
            )

    def test_frozen(self):
        tick = MarketTick(
            symbol="BTC/USD",
            price=Decimal("50000"),
            volume=100,
            timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )
        with pytest.raises(ValidationError):
            tick.price = Decimal("60000")

    def test_serialization_roundtrip(self):
        tick = MarketTick(
            symbol="BTC/USD",
            price=Decimal("50000"),
            volume=100,
            timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )
        data = tick.model_dump()
        restored = MarketTick.model_validate(data)
        assert restored == tick


class TestSignalValidation:
    def test_clamps_confidence_above_one(self):
        sig = Signal(
            symbol="BTC/USD",
            direction=SignalDirection.BUY,
            confidence=1.5,
            strategy_name="test",
            timestamp=datetime.now(UTC),
            reasoning="test",
        )
        assert sig.confidence == 1.0

    def test_clamps_confidence_below_zero(self):
        sig = Signal(
            symbol="BTC/USD",
            direction=SignalDirection.BUY,
            confidence=-0.5,
            strategy_name="test",
            timestamp=datetime.now(UTC),
            reasoning="test",
        )
        assert sig.confidence == 0.0

    def test_auto_generates_id(self):
        sig = Signal(
            symbol="BTC/USD",
            direction=SignalDirection.BUY,
            confidence=0.8,
            strategy_name="test",
            timestamp=datetime.now(UTC),
            reasoning="test",
        )
        assert sig.id is not None
        assert len(sig.id) > 0


class TestPositionProperties:
    def test_market_value(self):
        pos = Position(
            symbol="BTC/USD",
            quantity=Decimal("2"),
            avg_entry_price=Decimal("50000"),
            current_price=Decimal("55000"),
            asset_type=AssetType.CRYPTO,
        )
        assert pos.market_value == Decimal("110000")

    def test_unrealized_pnl(self):
        pos = Position(
            symbol="BTC/USD",
            quantity=Decimal("2"),
            avg_entry_price=Decimal("50000"),
            current_price=Decimal("55000"),
            asset_type=AssetType.CRYPTO,
        )
        assert pos.unrealized_pnl == Decimal("10000")


class TestPortfolioSnapshotProperties:
    def test_total_value(self):
        snap = PortfolioSnapshot(
            cash=Decimal("10000"),
            positions=[
                Position(
                    symbol="BTC/USD",
                    quantity=Decimal("1"),
                    avg_entry_price=Decimal("50000"),
                    current_price=Decimal("55000"),
                    asset_type=AssetType.CRYPTO,
                )
            ],
            timestamp=datetime.now(UTC),
        )
        assert snap.total_value == Decimal("65000")


class TestRiskDecisionProperties:
    def test_approve_is_approved(self):
        d = RiskDecision(action=RiskAction.APPROVE, reason="ok")
        assert d.is_approved is True

    def test_veto_is_not_approved(self):
        d = RiskDecision(action=RiskAction.VETO, reason="too risky")
        assert d.is_approved is False

    def test_resize_is_approved(self):
        d = RiskDecision(
            action=RiskAction.RESIZE,
            reason="reducing",
            adjusted_quantity=Decimal("5"),
        )
        assert d.is_approved is True


# -- Missing validation tests (code review fixes) --------------------------


class TestMarketTickZeroPrice:
    def test_rejects_zero_price(self):
        with pytest.raises(ValidationError):
            MarketTick(
                symbol="BTC/USD",
                price=Decimal("0"),
                volume=100,
                timestamp=datetime.now(UTC),
                asset_type=AssetType.CRYPTO,
            )


class TestOrderQuantityValidation:
    def test_rejects_zero_quantity(self):
        with pytest.raises(ValidationError):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("0"),
                asset_type=AssetType.STOCK,
            )

    def test_rejects_negative_quantity(self):
        with pytest.raises(ValidationError):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("-5"),
                asset_type=AssetType.STOCK,
            )


class TestFillValidation:
    def test_rejects_zero_quantity(self):
        with pytest.raises(ValidationError):
            Fill(
                order_id="ord-1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("0"),
                fill_price=Decimal("150"),
                timestamp=datetime.now(UTC),
                commission=Decimal("1"),
            )

    def test_rejects_negative_quantity(self):
        with pytest.raises(ValidationError):
            Fill(
                order_id="ord-1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("-10"),
                fill_price=Decimal("150"),
                timestamp=datetime.now(UTC),
                commission=Decimal("1"),
            )

    def test_rejects_zero_fill_price(self):
        with pytest.raises(ValidationError):
            Fill(
                order_id="ord-1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("10"),
                fill_price=Decimal("0"),
                timestamp=datetime.now(UTC),
                commission=Decimal("1"),
            )

    def test_rejects_negative_fill_price(self):
        with pytest.raises(ValidationError):
            Fill(
                order_id="ord-1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("10"),
                fill_price=Decimal("-50"),
                timestamp=datetime.now(UTC),
                commission=Decimal("1"),
            )

    def test_rejects_negative_commission(self):
        with pytest.raises(ValidationError):
            Fill(
                order_id="ord-1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("10"),
                fill_price=Decimal("150"),
                timestamp=datetime.now(UTC),
                commission=Decimal("-1"),
            )


class TestResearchReportSentimentValidation:
    def test_rejects_sentiment_above_one(self):
        with pytest.raises(ValidationError):
            ResearchReport(
                symbol="AAPL",
                summary="test",
                sentiment_score=1.5,
                timestamp=datetime.now(UTC),
            )

    def test_rejects_sentiment_below_negative_one(self):
        with pytest.raises(ValidationError):
            ResearchReport(
                symbol="AAPL",
                summary="test",
                sentiment_score=-1.5,
                timestamp=datetime.now(UTC),
            )


class TestPortfolioSnapshotCashValidation:
    def test_rejects_negative_cash(self):
        with pytest.raises(ValidationError):
            PortfolioSnapshot(
                cash=Decimal("-100"),
                positions=[],
                timestamp=datetime.now(UTC),
            )
