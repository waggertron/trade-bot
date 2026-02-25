from datetime import UTC, datetime
from decimal import Decimal

from src.core.models import AssetType, Fill, OrderSide, PortfolioSnapshot, Position
from src.discord_bot.bot import TradeBot, format_portfolio_status, format_trade_alert


def test_format_trade_alert():
    fill = Fill(
        order_id="ord-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150.25"),
        timestamp=datetime.now(UTC),
        commission=Decimal("1.00"),
    )
    msg = format_trade_alert(fill, strategy="momentum", reasoning="Strong trend")
    assert "AAPL" in msg
    assert "BUY" in msg
    assert "150.25" in msg
    assert "momentum" in msg


def test_format_portfolio_status():
    snapshot = PortfolioSnapshot(
        cash=Decimal("50000"),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("150"),
                current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            ),
        ],
        timestamp=datetime.now(UTC),
    )
    msg = format_portfolio_status(snapshot)
    assert "AAPL" in msg
    assert "50000" in msg or "50,000" in msg


def test_trade_bot_constructs():
    bot = TradeBot(token="fake-token", channel_id=123)
    assert bot is not None
