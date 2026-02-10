from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class TradeRecord:
    symbol: str
    side: str
    quantity: str
    price: str
    commission: str
    strategy: str
    paper: bool
    timestamp: datetime
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class SignalRecord:
    symbol: str
    direction: str
    confidence: float
    strategy: str
    reasoning: str
    timestamp: datetime
    id: str = field(default_factory=lambda: str(uuid4()))
