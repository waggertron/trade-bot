"""Pydantic models for database records."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ConfigDict, Field

from src.core.base import StrictBase


class UserRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    email: str
    hashed_password: str | None = None
    name: str = ""
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))


class OAuthAccountRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    user_id: str
    provider: str  # google, github
    provider_user_id: str
    email: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))


class UserSettingsRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    user_id: str
    mode: str = "paper"
    risk_preset: str = ""
    symbols_config: str = ""
    strategy_weights: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))


class TradeRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: str
    quantity: str
    price: str
    commission: str
    strategy: str
    paper: bool
    timestamp: datetime
    user_id: str | None = None
    id: str = Field(default_factory=lambda: str(uuid4()))


class SignalRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: str
    confidence: float = Field(ge=0, le=1)
    strategy: str
    reasoning: str
    timestamp: datetime
    user_id: str | None = None
    id: str = Field(default_factory=lambda: str(uuid4()))


class OHLCRecord(StrictBase):
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


class FeedRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    name: str
    url: str
    feed_type: str  # rss, json_api, government
    category: str  # markets, politics, technology, etc.
    auth_type: str = "free"  # free, api_key
    rate_limit_rpm: int = 60
    enabled: bool = True
    last_fetched_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))


class ArticleRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    content_hash: str
    title: str
    body: str = ""
    source: str
    url: str = ""
    published_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    feed_id: str | None = None
    symbols: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))


class SentimentScoreRecord(StrictBase):
    model_config = ConfigDict(frozen=True)

    article_id: str
    score: float
    magnitude: float
    reasoning: str | None = None
    analyzer: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(default_factory=lambda: str(uuid4()))
