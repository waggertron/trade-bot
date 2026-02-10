# tests/test_dashboard.py
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from src.dashboard.app import create_app
from src.core.models import PortfolioSnapshot, Position, AssetType
from src.db.models import TradeRecord


@pytest.fixture
def mock_portfolio():
    portfolio = AsyncMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        cash=Decimal("50000"),
        positions=[
            Position(
                symbol="AAPL", quantity=Decimal("10"),
                avg_entry_price=Decimal("150"), current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            )
        ],
        timestamp=datetime.now(timezone.utc),
    )
    portfolio.get_pnl.return_value = 50.0
    return portfolio


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.list_trades.return_value = [
        TradeRecord(
            symbol="AAPL", side="buy", quantity="10", price="150",
            commission="1", strategy="momentum", paper=True,
            timestamp=datetime.now(timezone.utc),
        )
    ]
    db.list_signals.return_value = []
    return db


@pytest.fixture
async def client(mock_portfolio, mock_db):
    app = create_app(portfolio=mock_portfolio, db=mock_db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_portfolio_endpoint(client):
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "cash" in data
    assert "positions" in data


async def test_trades_endpoint(client):
    resp = await client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
