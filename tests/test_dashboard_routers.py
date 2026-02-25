# tests/test_dashboard_routers.py
"""Integration tests for all dashboard router modules."""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.dashboard.dependencies import require_user
from src.dashboard.routers import backtest as backtest_router
from src.core.config import RiskSettings, Settings
from src.core.models import (
    AssetType, Fill, Order, OrderSide, OrderType, PortfolioSnapshot, Position,
)
from src.db.models import OHLCRecord, SignalRecord, TradeRecord, UserRecord

_test_user = UserRecord(email="test@example.com", hashed_password="h", name="Test", is_verified=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state():
    """Reset shared state + backtest in-memory store between tests.

    Must mutate the existing object (not replace it) because routers
    bind to it via ``from src.dashboard.dependencies import state``.
    """
    _clear_state()
    backtest_router._backtest_runs.clear()
    yield
    _clear_state()
    backtest_router._backtest_runs.clear()


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
                symbol="AAPL", quantity=Decimal("10"),
                avg_entry_price=Decimal("150"), current_price=Decimal("155"),
                asset_type=AssetType.STOCK,
            )
        ],
        timestamp=datetime.now(timezone.utc),
    )
    portfolio.get_positions.return_value = [
        Position(
            symbol="AAPL", quantity=Decimal("10"),
            avg_entry_price=Decimal("150"), current_price=Decimal("155"),
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
            symbol="AAPL", side="buy", quantity="10", price="150",
            commission="1", strategy="momentum", paper=True,
            timestamp=datetime.now(timezone.utc),
        )
    ]
    db.list_signals.return_value = [
        SignalRecord(
            symbol="AAPL", direction="buy", confidence=0.8,
            strategy="momentum", reasoning="uptrend",
            timestamp=datetime.now(timezone.utc),
        )
    ]
    db.get_trade.return_value = None
    db.query_ohlc_bars.return_value = []
    db.save_trade = AsyncMock()
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
    executor.cancel_order.return_value = True
    executor.submit_order.return_value = Fill(
        order_id="order-1", symbol="AAPL", side=OrderSide.BUY,
        quantity=Decimal("10"), fill_price=Decimal("150"),
        timestamp=datetime.now(timezone.utc),
    )
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
            name="momentum", enabled=True, weight=0.4,
            description="Momentum strategy",
            __class__=type("MomentumStrategy", (), {}),
        ),
        SimpleNamespace(
            name="mean_reversion", enabled=False, weight=0.6,
            description="Mean reversion strategy",
            __class__=type("MeanReversionStrategy", (), {}),
        ),
    ]


@pytest.fixture
async def client(
    mock_portfolio, mock_db, mock_orchestrator, mock_executor,
    mock_risk_manager, mock_event_bus, mock_settings, mock_strategies,
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


@pytest.fixture
async def client_minimal():
    """Client with no dependencies — tests 503/fallback paths."""
    app = create_app()
    app.dependency_overrides[require_user] = lambda: _test_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ===========================================================================
# Portfolio Router
# ===========================================================================


class TestPortfolioRouter:
    async def test_get_portfolio_snapshot(self, client):
        resp = await client.get("/api/portfolio/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash"] == "50000"
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "AAPL"

    async def test_get_portfolio_none(self, client_minimal):
        resp = await client_minimal.get("/api/portfolio/")
        assert resp.status_code == 200
        assert resp.json()["error"] == "Portfolio not available"

    async def test_get_positions(self, client):
        resp = await client.get("/api/portfolio/positions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    async def test_get_positions_none(self, client_minimal):
        resp = await client_minimal.get("/api/portfolio/positions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_pnl(self, client):
        resp = await client.get("/api/portfolio/pnl")
        assert resp.status_code == 200
        data = resp.json()
        assert "realized_pnl" in data
        assert "unrealized_pnl" in data
        assert "win_rate" in data

    async def test_get_equity_curve(self, client):
        resp = await client.get("/api/portfolio/equity-curve")
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert len(data["points"]) >= 1

    async def test_get_equity_curve_none(self, client_minimal):
        resp = await client_minimal.get("/api/portfolio/equity-curve")
        assert resp.status_code == 200
        assert resp.json()["points"] == []

    async def test_get_allocation(self, client):
        resp = await client.get("/api/portfolio/allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_type" in data
        assert "cash_pct" in data

    async def test_get_allocation_none(self, client_minimal):
        resp = await client_minimal.get("/api/portfolio/allocation")
        assert resp.status_code == 200
        assert resp.json()["cash_pct"] == 100


# ===========================================================================
# Trading Router
# ===========================================================================


class TestTradingRouter:
    async def test_place_order(self, client):
        resp = await client.post("/api/trading/order", json={
            "symbol": "AAPL", "side": "buy", "quantity": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "fill" in data
        assert data["fill"]["symbol"] == "AAPL"

    async def test_place_order_503_no_executor(self, client_minimal):
        resp = await client_minimal.post("/api/trading/order", json={
            "symbol": "AAPL", "side": "buy", "quantity": 10,
        })
        assert resp.status_code == 503

    async def test_get_orders(self, client):
        resp = await client.get("/api/trading/orders")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_cancel_order(self, client):
        resp = await client.delete("/api/trading/orders/abc")
        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True

    async def test_cancel_all(self, client):
        resp = await client.post("/api/trading/cancel-all")
        assert resp.status_code == 200
        assert resp.json()["cancelled_count"] == 0

    async def test_get_prices(self, client):
        resp = await client.get("/api/trading/prices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["AAPL"] == "150"

    async def test_get_prices_none(self, client_minimal):
        resp = await client_minimal.get("/api/trading/prices")
        assert resp.status_code == 200
        assert resp.json() == {}


# ===========================================================================
# Trades Router
# ===========================================================================


class TestTradesRouter:
    async def test_list_trades(self, client):
        resp = await client.get("/api/trades/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    async def test_list_trades_no_db(self, client_minimal):
        resp = await client_minimal.get("/api/trades/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_trade_not_found(self, client):
        resp = await client.get("/api/trades/nonexistent")
        assert resp.status_code == 404

    async def test_get_trade_no_db(self, client_minimal):
        resp = await client_minimal.get("/api/trades/some-id")
        assert resp.status_code == 503


# ===========================================================================
# Signals Router
# ===========================================================================


class TestSignalsRouter:
    async def test_list_signals(self, client):
        resp = await client.get("/api/signals/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    async def test_list_signals_no_db(self, client_minimal):
        resp = await client_minimal.get("/api/signals/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_latest_signals(self, client):
        resp = await client.get("/api/signals/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_latest_signals_dedup(self, client, mock_db):
        """Two signals for same strategy+symbol -> only one latest."""
        mock_db.list_signals.return_value = [
            SignalRecord(
                symbol="AAPL", direction="buy", confidence=0.9,
                strategy="momentum", reasoning="strong",
                timestamp=datetime.now(timezone.utc),
            ),
            SignalRecord(
                symbol="AAPL", direction="sell", confidence=0.5,
                strategy="momentum", reasoning="weak",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        resp = await client.get("/api/signals/latest")
        data = resp.json()
        assert len(data) == 1


# ===========================================================================
# Strategies Router
# ===========================================================================


class TestStrategiesRouter:
    async def test_list_strategies(self, client):
        resp = await client.get("/api/strategies/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {s["name"] for s in data}
        assert "momentum" in names

    async def test_strategy_status(self, client):
        resp = await client.get("/api/strategies/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["enabled"] == 1

    async def test_get_strategy_found(self, client):
        resp = await client.get("/api/strategies/momentum")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "momentum"

    async def test_get_strategy_not_found(self, client):
        resp = await client.get("/api/strategies/nonexistent")
        assert resp.status_code == 404

    async def test_update_weight(self, client):
        resp = await client.put("/api/strategies/momentum/weight", json={"weight": 0.7})
        assert resp.status_code == 200
        assert resp.json()["weight"] == 0.7

    async def test_update_weight_not_found(self, client):
        resp = await client.put("/api/strategies/nonexistent/weight", json={"weight": 0.5})
        assert resp.status_code == 404

    async def test_update_enabled(self, client):
        resp = await client.put("/api/strategies/momentum/enabled", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    async def test_get_strategy_signals(self, client):
        resp = await client.get("/api/strategies/momentum/signals")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_strategy_performance(self, client):
        resp = await client.get("/api/strategies/momentum/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "momentum"
        assert "total_trades" in data

    async def test_get_consensus(self, client):
        resp = await client.get("/api/strategies/consensus")
        assert resp.status_code == 200
        data = resp.json()
        assert "symbols" in data


# ===========================================================================
# Analytics Router
# ===========================================================================


class TestAnalyticsRouter:
    async def test_get_drawdown_empty_fills(self, client):
        resp = await client.get("/api/analytics/drawdown")
        assert resp.status_code == 200
        assert resp.json()["points"] == []

    async def test_get_drawdown_none_portfolio(self, client_minimal):
        resp = await client_minimal.get("/api/analytics/drawdown")
        assert resp.status_code == 200
        assert resp.json()["points"] == []

    async def test_get_correlation_no_bars(self, client):
        resp = await client.get("/api/analytics/correlation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbols"] == []
        assert data["matrix"] == []

    async def test_get_monte_carlo_empty(self, client):
        resp = await client.get("/api/analytics/monte-carlo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_simulations"] == 0


# ===========================================================================
# Risk Router
# ===========================================================================


class TestRiskRouter:
    async def test_get_risk_status(self, client):
        resp = await client.get("/api/risk/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "max_position_pct" in data
        assert data["max_position_pct"] == 2.0

    async def test_get_risk_status_none(self, client_minimal):
        resp = await client_minimal.get("/api/risk/status")
        assert resp.status_code == 200
        assert resp.json()["error"] == "Risk manager not available"

    async def test_update_settings_partial(self, client):
        resp = await client.put("/api/risk/settings", json={"max_position_pct": 5.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["max_position_pct"] == 5.0

    async def test_update_settings_no_changes(self, client):
        resp = await client.put("/api/risk/settings", json={})
        assert resp.status_code == 200
        assert resp.json()["message"] == "No changes"

    async def test_update_settings_503(self, client_minimal):
        resp = await client_minimal.put("/api/risk/settings", json={"max_position_pct": 5.0})
        assert resp.status_code == 503

    async def test_apply_preset(self, client):
        resp = await client.put("/api/risk/preset", json={"level": "aggressive"})
        assert resp.status_code == 200
        data = resp.json()
        assert "aggressive" in data["message"]
        assert data["settings"]["max_position_pct"] == 5.0

    async def test_apply_preset_503(self, client_minimal):
        resp = await client_minimal.put("/api/risk/preset", json={"level": "conservative"})
        assert resp.status_code == 503

    async def test_get_presets(self, client):
        resp = await client.get("/api/risk/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "conservative" in data
        assert "aggressive" in data

    async def test_get_regime(self, client):
        resp = await client.get("/api/risk/regime")
        assert resp.status_code == 200
        assert resp.json()["regime"] == "medium"

    async def test_get_drawdown_status(self, client):
        resp = await client.get("/api/risk/drawdown")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_pct" in data
        assert "positions_used" in data

    async def test_get_circuit_breaker(self, client):
        resp = await client.get("/api/risk/circuit-breaker")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tripped"] is False

    async def test_reset_circuit_breaker(self, client):
        resp = await client.post("/api/risk/circuit-breaker/reset")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Circuit breaker reset"

    async def test_reset_circuit_breaker_503(self, client_minimal):
        resp = await client_minimal.post("/api/risk/circuit-breaker/reset")
        assert resp.status_code == 503

    async def test_get_risk_decisions(self, client):
        resp = await client.get("/api/risk/decisions")
        assert resp.status_code == 200
        assert resp.json() == []


# ===========================================================================
# Backtest Router
# ===========================================================================


class TestBacktestRouter:
    async def test_run_backtest(self, client):
        resp = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["status"] in ("running", "completed", "failed")

    async def test_list_runs_empty(self, client):
        resp = await client.get("/api/backtest/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_runs_after_create(self, client):
        await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        resp = await client.get("/api/backtest/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_get_run_not_found(self, client):
        resp = await client.get("/api/backtest/runs/nonexistent")
        assert resp.status_code == 404

    async def test_get_run_after_create(self, client):
        create_resp = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        run_id = create_resp.json()["id"]
        resp = await client.get(f"/api/backtest/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id


# ===========================================================================
# News Router
# ===========================================================================


class TestNewsRouter:
    async def test_news_status(self, client):
        resp = await client.get("/api/news/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is True
        assert data["providers"] == []

    async def test_news_feeds(self, client):
        resp = await client.get("/api/news/feeds")
        assert resp.status_code == 200
        assert resp.json()["feeds"] == []

    async def test_news_articles(self, client):
        resp = await client.get("/api/news/articles")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_sentiment_aggregate(self, client):
        resp = await client.get("/api/sentiment/aggregate")
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_sentiment_trend(self, client):
        resp = await client.get("/api/sentiment/trend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "BTC/USD"
        assert data["points"] == []


# ===========================================================================
# ML Router
# ===========================================================================


class TestMLRouter:
    async def test_feature_catalog(self, client):
        resp = await client.get("/api/features/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "technical" in data
        assert "sentiment" in data
        assert len(data["technical"]) > 0

    async def test_feature_status(self, client):
        resp = await client.get("/api/features/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    async def test_list_models(self, client):
        resp = await client.get("/api/ml/models")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_model_importance(self, client):
        resp = await client.get("/api/ml/models/xgb_btc/importance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "xgb_btc"
        assert data["features"] == []

    async def test_trigger_training(self, client):
        resp = await client.post("/api/ml/train")
        assert resp.status_code == 200
        assert resp.json()["status"] == "training_started"

    async def test_get_predictions(self, client):
        resp = await client.get("/api/ml/predictions")
        assert resp.status_code == 200
        assert resp.json() == {}


# ===========================================================================
# Config Router
# ===========================================================================


class TestConfigRouter:
    async def test_get_config(self, client):
        resp = await client.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "paper"

    async def test_get_config_none(self, client_minimal):
        resp = await client_minimal.get("/api/config/")
        assert resp.status_code == 200
        assert resp.json()["error"] == "Settings not available"

    async def test_get_mode(self, client):
        resp = await client.get("/api/config/mode")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "paper"

    async def test_set_mode(self, client):
        resp = await client.put("/api/config/mode", json={"mode": "live"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    async def test_set_mode_503(self, client_minimal):
        resp = await client_minimal.put("/api/config/mode", json={"mode": "live"})
        assert resp.status_code == 503

    async def test_get_symbols(self, client):
        resp = await client.get("/api/config/symbols")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data
        assert "crypto" in data

    async def test_update_symbols(self, client):
        resp = await client.put("/api/config/symbols", json={
            "stocks": ["AAPL", "GOOG"], "crypto": ["BTC/USD"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["stocks"] == ["AAPL", "GOOG"]
        assert data["crypto"] == ["BTC/USD"]

    async def test_update_symbols_503(self, client_minimal):
        resp = await client_minimal.put("/api/config/symbols", json={
            "stocks": ["AAPL"],
        })
        assert resp.status_code == 503


# ===========================================================================
# Market Router
# ===========================================================================


class TestMarketRouter:
    async def test_get_ohlc(self, client):
        resp = await client.get("/api/market/ohlc/AAPL")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_ohlc_no_db(self, client_minimal):
        resp = await client_minimal.get("/api/market/ohlc/AAPL")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_prices(self, client):
        resp = await client.get("/api/market/prices")
        assert resp.status_code == 200
        assert resp.json()["AAPL"] == "150"

    async def test_get_prices_none(self, client_minimal):
        resp = await client_minimal.get("/api/market/prices")
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_get_sparklines_no_bars(self, client):
        resp = await client.get("/api/market/sparklines")
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_get_sparklines_with_data(self, client, mock_db):
        mock_db.query_ohlc_bars.return_value = [
            OHLCRecord(
                symbol="AAPL", interval="1h", timestamp=1700000000 + i * 3600,
                open="150", high="155", low="149", close=str(150 + i),
                volume="1000", source="test",
            )
            for i in range(5)
        ]
        resp = await client.get("/api/market/sparklines?points=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "AAPL" in data
        assert len(data["AAPL"]["prices"]) == 5


# ===========================================================================
# WebSocket broadcast function
# ===========================================================================


class TestWebSocketBroadcast:
    async def test_broadcast_sends_to_clients(self):
        from src.dashboard.routers.websocket import broadcast, _clients

        mock_ws = AsyncMock()
        _clients.add(mock_ws)
        try:
            await broadcast("test_event", {"key": "value"})
            mock_ws.send_text.assert_called_once()
            import json
            sent = json.loads(mock_ws.send_text.call_args[0][0])
            assert sent["type"] == "test_event"
            assert sent["data"]["key"] == "value"
        finally:
            _clients.clear()

    async def test_broadcast_removes_disconnected(self):
        from src.dashboard.routers.websocket import broadcast, _clients

        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_text.side_effect = Exception("disconnected")

        _clients.add(good_ws)
        _clients.add(bad_ws)
        try:
            await broadcast("test", {"data": 1})
            good_ws.send_text.assert_called_once()
            assert bad_ws not in _clients
        finally:
            _clients.clear()
