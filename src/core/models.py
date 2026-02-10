from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4


class AssetType(Enum):
    STOCK = "stock"
    CRYPTO = "crypto"


class SignalDirection(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class RiskAction(Enum):
    APPROVE = "approve"
    VETO = "veto"
    RESIZE = "resize"


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    price: Decimal
    volume: int
    timestamp: datetime
    asset_type: AssetType
    bid: Decimal | None = None
    ask: Decimal | None = None


@dataclass
class Signal:
    symbol: str
    direction: SignalDirection
    confidence: float
    strategy_name: str
    timestamp: datetime
    reasoning: str
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class Order:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    asset_type: AssetType
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    signal_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    fill_price: Decimal
    timestamp: datetime
    commission: Decimal = Decimal("0")
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    asset_type: AssetType
    sector: str | None = None

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.current_price - self.avg_entry_price) * self.quantity

    @property
    def market_value(self) -> Decimal:
        return self.current_price * self.quantity


@dataclass
class PortfolioSnapshot:
    cash: Decimal
    positions: list[Position]
    timestamp: datetime

    @property
    def total_value(self) -> Decimal:
        return self.cash + sum(p.market_value for p in self.positions)


@dataclass(frozen=True)
class RiskDecision:
    action: RiskAction
    reason: str
    adjusted_quantity: Decimal | None = None

    @property
    def is_approved(self) -> bool:
        return self.action in (RiskAction.APPROVE, RiskAction.RESIZE)


@dataclass(frozen=True)
class ResearchReport:
    symbol: str
    summary: str
    sentiment_score: float
    timestamp: datetime
    sources: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
