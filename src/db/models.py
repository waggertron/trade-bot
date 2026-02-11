"""Pydantic models for database records."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class TradeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: str
    quantity: str
    price: str
    commission: str
    strategy: str
    paper: bool
    timestamp: datetime
    id: str = Field(default_factory=lambda: str(uuid4()))


class SignalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: str
    confidence: float = Field(ge=0, le=1)
    strategy: str
    reasoning: str
    timestamp: datetime
    id: str = Field(default_factory=lambda: str(uuid4()))


class OHLCRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    interval: str
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    source: str
