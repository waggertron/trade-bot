"""Pydantic request/response schemas for the dashboard API."""

from __future__ import annotations

import re

from pydantic import Field, field_validator

from src.core.base import StrictBase


def _validate_password_strength(password: str) -> str:
    """Validate password meets minimum complexity requirements."""
    if len(password) < 8:
        msg = "Password must be at least 8 characters"
        raise ValueError(msg)
    if not re.search(r"[A-Z]", password):
        msg = "Password must contain at least one uppercase letter"
        raise ValueError(msg)
    if not re.search(r"[a-z]", password):
        msg = "Password must contain at least one lowercase letter"
        raise ValueError(msg)
    if not re.search(r"\d", password):
        msg = "Password must contain at least one digit"
        raise ValueError(msg)
    return password


# -- Auth ---------------------------------------------------------------------


class RegisterRequest(StrictBase):
    email: str
    password: str = Field(min_length=8)
    name: str = ""

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(StrictBase):
    email: str
    password: str


class RefreshRequest(StrictBase):
    refresh_token: str


class UpdateProfileRequest(StrictBase):
    name: str | None = None
    password: str | None = Field(default=None, min_length=8)

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_password_strength(v)
        return v


# -- Trading ------------------------------------------------------------------


class PlaceOrderRequest(StrictBase):
    symbol: str
    side: str = Field(pattern=r"^(buy|sell)$")
    order_type: str = Field(default="market", pattern=r"^(market|limit)$")
    quantity: float = Field(gt=0)
    limit_price: float | None = None


class OrderResponse(StrictBase):
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: str
    limit_price: str | None = None
    status: str = "open"


# -- Risk ---------------------------------------------------------------------


class RiskSettingsUpdate(StrictBase):
    max_position_pct: float | None = None
    max_sector_exposure_pct: float | None = None
    daily_loss_limit_pct: float | None = None
    weekly_drawdown_limit_pct: float | None = None
    max_open_positions: int | None = None
    stop_loss_pct: float | None = None
    trailing_stop_enabled: bool | None = None
    trailing_stop_pct: float | None = None
    max_correlation: float | None = None


class RiskPresetRequest(StrictBase):
    level: str = Field(pattern=r"^(conservative|moderate|aggressive|very_aggressive)$")


# -- Strategies ---------------------------------------------------------------


class UpdateWeightRequest(StrictBase):
    weight: float = Field(ge=0, le=1.0)


class UpdateEnabledRequest(StrictBase):
    enabled: bool


# -- Config -------------------------------------------------------------------


class UpdateModeRequest(StrictBase):
    mode: str = Field(pattern=r"^(paper|live)$")


class UpdateSymbolsRequest(StrictBase):
    stocks: list[str] = Field(default_factory=list)
    crypto: list[str] = Field(default_factory=list)


# -- Backtest -----------------------------------------------------------------


class BacktestRequest(StrictBase):
    start_date: str
    end_date: str
    strategies: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    initial_capital: float = 100000.0


# -- Simulation ---------------------------------------------------------------


class SimulationRequest(StrictBase):
    stocks: list[str] = Field(
        default_factory=lambda: [
            "SPY",
            "QQQ",
            "DIA",
            "IWM",
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "META",
            "TSLA",
            "XLF",
            "XLK",
            "XLE",
            "XLV",
            "XLI",
        ]
    )
    initial_balance: float = Field(default=10_000.0, gt=0)
    train_days: int = Field(default=60, gt=0)
    test_days: int = Field(default=30, gt=0)
    risk_levels: list[str] = Field(
        default_factory=lambda: [
            "conservative",
            "moderate",
            "aggressive",
            "very_aggressive",
        ]
    )
    mc_simulations: int = Field(default=1000, gt=0)
    mc_seed: int | None = Field(default=None, description="Monte Carlo random seed")
    max_position_pct: float | None = Field(
        default=None,
        ge=0.1,
        le=100.0,
        description="Override max position size %",
    )
    # Portfolio simulation fields
    portfolio_mode: bool = False
    allocation_mode: str = Field(default="equal_weight", pattern=r"^(equal_weight|custom)$")
    custom_weights: dict[str, float] = Field(default_factory=dict)
    rebalance_frequency: str = Field(default="none", pattern=r"^(none|daily|weekly|monthly)$")
    rebalance_threshold_pct: float = Field(default=5.0, ge=0.0, le=100.0)
