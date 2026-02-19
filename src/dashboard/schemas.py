"""Pydantic request/response schemas for the dashboard API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# -- Trading ------------------------------------------------------------------

class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str = Field(pattern=r"^(buy|sell)$")
    order_type: str = Field(default="market", pattern=r"^(market|limit)$")
    quantity: float = Field(gt=0)
    limit_price: float | None = None


class OrderResponse(BaseModel):
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: str
    limit_price: str | None = None
    status: str = "open"


# -- Risk ---------------------------------------------------------------------

class RiskSettingsUpdate(BaseModel):
    max_position_pct: float | None = None
    max_sector_exposure_pct: float | None = None
    daily_loss_limit_pct: float | None = None
    weekly_drawdown_limit_pct: float | None = None
    max_open_positions: int | None = None
    stop_loss_pct: float | None = None
    trailing_stop_enabled: bool | None = None
    trailing_stop_pct: float | None = None
    max_correlation: float | None = None


class RiskPresetRequest(BaseModel):
    level: str = Field(pattern=r"^(conservative|moderate|aggressive|very_aggressive)$")


# -- Strategies ---------------------------------------------------------------

class UpdateWeightRequest(BaseModel):
    weight: float = Field(ge=0, le=1.0)


class UpdateEnabledRequest(BaseModel):
    enabled: bool


# -- Config -------------------------------------------------------------------

class UpdateModeRequest(BaseModel):
    mode: str = Field(pattern=r"^(paper|live)$")


class UpdateSymbolsRequest(BaseModel):
    stocks: list[str] = Field(default_factory=list)
    crypto: list[str] = Field(default_factory=list)


# -- Backtest -----------------------------------------------------------------

class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    strategies: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    initial_capital: float = 100000.0


# -- Simulation ---------------------------------------------------------------

class SimulationRequest(BaseModel):
    stocks: list[str] = Field(default_factory=lambda: [
        "SPY", "QQQ", "DIA", "IWM",
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "XLF", "XLK", "XLE", "XLV", "XLI",
    ])
    initial_balance: float = Field(default=10_000.0, gt=0)
    train_days: int = Field(default=60, gt=0)
    test_days: int = Field(default=30, gt=0)
    risk_levels: list[str] = Field(default_factory=lambda: [
        "conservative", "moderate", "aggressive", "very_aggressive",
    ])
    mc_simulations: int = Field(default=1000, gt=0)
