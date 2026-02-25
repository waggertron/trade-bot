# tests/test_dashboard.py
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import RiskSettings, Settings
from src.core.models import AssetType, PortfolioSnapshot, Position
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.dashboard.dependencies import require_user
from src.db.models import TradeRecord, UserRecord

_test_user = UserRecord(
    email="test@example.com",
    hashed_password="h",
    name="Test",
    is_verified=True,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset the shared dashboard state between tests.

    Must mutate the existing object (not replace it) because routers
    bind to it via ``from src.dashboard.dependencies import state``.
    """
    _clear_state()
    yield
    _clear_state()


def _clear_state():
    s = dependencies.state
    s.portfolio = None
    s.db = None
    s.orchestrator = None
    s.executor = None
    s.risk_manager = None
    s.event_bus = None
    s.settings = None
    s.strategies = []


@pytest.fixture
def mock_portfolio():
    portfolio = AsyncMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        cash=Decimal("50000"),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("150"),
                current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            )
        ],
        timestamp=datetime.now(UTC),
    )
    portfolio.get_positions.return_value = [
        Position(
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_entry_price=Decimal("150"),
            current_price=Decimal("155"),
            asset_type=AssetType.STOCK,
        )
    ]
    portfolio.get_pnl.return_value = 50.0
    portfolio._fills = []
    portfolio._cash = Decimal("100000")
    portfolio._realized_pnl = []
    return portfolio


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.list_trades.return_value = [
        TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150",
            commission="1",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(UTC),
        )
    ]
    db.list_signals.return_value = []
    db.get_trade.return_value = None
    db.query_ohlc_bars.return_value = []
    db.get_user_settings.return_value = None
    return db


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.is_paused = False
    return orch


@pytest.fixture
def mock_executor():
    executor = AsyncMock()
    executor._open_orders = {}
    executor._current_prices = {"AAPL": Decimal("150")}
    executor.cancel_all.return_value = 0
    return executor


@pytest.fixture
def mock_risk_manager():
    rm = MagicMock()
    rm._settings = RiskSettings()
    rm._daily_pnl = Decimal("0")
    rm._circuit_breaker = None
    return rm


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.get_history.return_value = []
    return bus


@pytest.fixture
def mock_settings():
    return Settings.for_testing()


@pytest.fixture
def mock_strategies():
    return [
        SimpleNamespace(
            name="momentum",
            enabled=True,
            weight=0.4,
            description="Momentum strategy",
            __class__=type("MomentumStrategy", (), {}),
        ),
    ]


@pytest.fixture
async def client(
    mock_portfolio,
    mock_db,
    mock_orchestrator,
    mock_executor,
    mock_risk_manager,
    mock_event_bus,
    mock_settings,
    mock_strategies,
):
    app = create_app(
        portfolio_manager=mock_portfolio,
        db=mock_db,
        orchestrator=mock_orchestrator,
        executor=mock_executor,
        risk_manager=mock_risk_manager,
        event_bus=mock_event_bus,
        settings=mock_settings,
        strategy_list=mock_strategies,
    )
    app.dependency_overrides[require_user] = lambda: _test_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# -- System endpoints --


async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_pause_endpoint(client):
    resp = await client.post("/api/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


async def test_resume_endpoint(client):
    resp = await client.post("/api/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"


async def test_system_status_endpoint(client):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "paper"
    assert data["is_paused"] is False
    assert "uptime_seconds" in data
    assert data["strategies_count"] == 1


# -- Portfolio endpoint (preserved from original) --


async def test_portfolio_endpoint(client):
    resp = await client.get("/api/portfolio/")
    assert resp.status_code == 200
    data = resp.json()
    assert "cash" in data
    assert "positions" in data


# -- Trades endpoint (preserved from original) --


async def test_trades_endpoint(client):
    resp = await client.get("/api/trades/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
