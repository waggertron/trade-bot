# tests/test_schemas.py
"""Tests for all Pydantic schemas in src/dashboard/schemas.py."""

import pytest
from pydantic import ValidationError

from src.dashboard.schemas import (
    BacktestRequest,
    OrderResponse,
    PlaceOrderRequest,
    RiskPresetRequest,
    RiskSettingsUpdate,
    UpdateEnabledRequest,
    UpdateModeRequest,
    UpdateSymbolsRequest,
    UpdateWeightRequest,
)

# -- PlaceOrderRequest -------------------------------------------------------


class TestPlaceOrderRequest:
    def test_valid_buy(self):
        req = PlaceOrderRequest(symbol="AAPL", side="buy", quantity=10.0)
        assert req.side == "buy"
        assert req.order_type == "market"
        assert req.limit_price is None

    def test_valid_sell(self):
        req = PlaceOrderRequest(symbol="AAPL", side="sell", quantity=5.0)
        assert req.side == "sell"

    def test_invalid_side_rejects(self):
        with pytest.raises(ValidationError):
            PlaceOrderRequest(symbol="AAPL", side="short", quantity=10.0)

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            PlaceOrderRequest(symbol="AAPL", side="buy", quantity=0)

    def test_negative_quantity_rejects(self):
        with pytest.raises(ValidationError):
            PlaceOrderRequest(symbol="AAPL", side="buy", quantity=-5.0)

    def test_limit_price_optional(self):
        req = PlaceOrderRequest(
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=10.0,
            limit_price=150.0,
        )
        assert req.limit_price == 150.0

    def test_market_order_type(self):
        req = PlaceOrderRequest(symbol="AAPL", side="buy", quantity=1.0, order_type="market")
        assert req.order_type == "market"

    def test_limit_order_type(self):
        req = PlaceOrderRequest(symbol="AAPL", side="buy", quantity=1.0, order_type="limit")
        assert req.order_type == "limit"

    def test_invalid_order_type_rejects(self):
        with pytest.raises(ValidationError):
            PlaceOrderRequest(symbol="AAPL", side="buy", quantity=1.0, order_type="stop")


# -- OrderResponse -----------------------------------------------------------


class TestOrderResponse:
    def test_creation(self):
        resp = OrderResponse(
            id="abc",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity="10",
        )
        assert resp.id == "abc"
        assert resp.status == "open"

    def test_status_default_open(self):
        resp = OrderResponse(id="x", symbol="X", side="sell", order_type="limit", quantity="5")
        assert resp.status == "open"


# -- RiskSettingsUpdate ------------------------------------------------------


class TestRiskSettingsUpdate:
    def test_all_none_valid(self):
        update = RiskSettingsUpdate()
        assert update.max_position_pct is None
        assert update.daily_loss_limit_pct is None

    def test_individual_field_update(self):
        update = RiskSettingsUpdate(max_position_pct=5.0)
        assert update.max_position_pct == 5.0
        assert update.max_open_positions is None


# -- RiskPresetRequest -------------------------------------------------------


class TestRiskPresetRequest:
    @pytest.mark.parametrize("level", ["conservative", "moderate", "aggressive", "very_aggressive"])
    def test_valid_levels(self, level):
        req = RiskPresetRequest(level=level)
        assert req.level == level

    def test_invalid_level_rejects(self):
        with pytest.raises(ValidationError):
            RiskPresetRequest(level="yolo")


# -- UpdateWeightRequest -----------------------------------------------------


class TestUpdateWeightRequest:
    def test_zero_valid(self):
        req = UpdateWeightRequest(weight=0.0)
        assert req.weight == 0.0

    def test_one_valid(self):
        req = UpdateWeightRequest(weight=1.0)
        assert req.weight == 1.0

    def test_negative_rejects(self):
        with pytest.raises(ValidationError):
            UpdateWeightRequest(weight=-0.1)

    def test_above_one_rejects(self):
        with pytest.raises(ValidationError):
            UpdateWeightRequest(weight=1.1)


# -- UpdateEnabledRequest ----------------------------------------------------


class TestUpdateEnabledRequest:
    def test_true(self):
        req = UpdateEnabledRequest(enabled=True)
        assert req.enabled is True

    def test_false(self):
        req = UpdateEnabledRequest(enabled=False)
        assert req.enabled is False


# -- UpdateModeRequest -------------------------------------------------------


class TestUpdateModeRequest:
    def test_paper_valid(self):
        req = UpdateModeRequest(mode="paper")
        assert req.mode == "paper"

    def test_live_valid(self):
        req = UpdateModeRequest(mode="live")
        assert req.mode == "live"

    def test_invalid_rejects(self):
        with pytest.raises(ValidationError):
            UpdateModeRequest(mode="demo")


# -- UpdateSymbolsRequest ----------------------------------------------------


class TestUpdateSymbolsRequest:
    def test_empty_lists_default(self):
        req = UpdateSymbolsRequest()
        assert req.stocks == []
        assert req.crypto == []

    def test_populated_lists(self):
        req = UpdateSymbolsRequest(stocks=["AAPL", "GOOG"], crypto=["BTC/USD"])
        assert req.stocks == ["AAPL", "GOOG"]
        assert req.crypto == ["BTC/USD"]


# -- BacktestRequest ---------------------------------------------------------


class TestBacktestRequest:
    def test_valid_config(self):
        req = BacktestRequest(start_date="2024-01-01", end_date="2024-06-30")
        assert req.start_date == "2024-01-01"
        assert req.strategies == []
        assert req.symbols == []

    def test_default_initial_capital(self):
        req = BacktestRequest(start_date="2024-01-01", end_date="2024-06-30")
        assert req.initial_capital == 100000.0

    def test_custom_initial_capital(self):
        req = BacktestRequest(
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=50000.0,
        )
        assert req.initial_capital == 50000.0
