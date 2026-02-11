"""Shared data models for the trading bot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -- Enums ----------------------------------------------------------------

class AssetType(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"


class SignalDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class RiskAction(str, Enum):
    APPROVE = "approve"
    VETO = "veto"
    RESIZE = "resize"


# -- Models ---------------------------------------------------------------

class MarketTick(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    timestamp: datetime
    asset_type: AssetType
    bid: Decimal | None = None
    ask: Decimal | None = None


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    strategy_name: str
    timestamp: datetime
    reasoning: str

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    asset_type: AssetType
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    signal_id: str | None = None


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    fill_price: Decimal = Field(gt=0)
    timestamp: datetime
    commission: Decimal = Field(default=Decimal("0"), ge=0)


class Position(BaseModel):
    symbol: str
    quantity: Decimal = Field(gt=0)
    avg_entry_price: Decimal = Field(gt=0)
    current_price: Decimal = Field(gt=0)
    asset_type: AssetType
    sector: str | None = None

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.current_price - self.avg_entry_price) * self.quantity


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    cash: Decimal = Field(ge=0)
    positions: list[Position]
    timestamp: datetime

    @property
    def total_value(self) -> Decimal:
        return self.cash + sum(p.market_value for p in self.positions)


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: RiskAction
    reason: str
    adjusted_quantity: Decimal | None = None

    @property
    def is_approved(self) -> bool:
        return self.action in (RiskAction.APPROVE, RiskAction.RESIZE)


class ResearchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    summary: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    timestamp: datetime
    sources: list[str] = Field(default_factory=list)
    raw_data: dict[str, object] = Field(default_factory=dict)
