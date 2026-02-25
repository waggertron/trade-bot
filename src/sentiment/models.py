"""Shared Pydantic models for the sentiment analysis pipeline.

Article   - represents a news article fetched from any provider.
SentimentResult - represents the scored sentiment output for a piece of text.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ConfigDict, Field

from src.core.base import StrictBase


class Article(StrictBase):
    """A news article fetched from any news provider.

    * ``id`` is auto-generated (uuid4 hex).
    * ``content_hash`` is auto-computed from ``title + body[:200]``
      so that duplicate content can be detected cheaply.
    * The model is frozen (immutable after creation).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    body: str = ""
    source: str
    url: str = ""
    published_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    related_symbols: list[str]
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        h = hashlib.sha256((self.title + self.body[:200]).encode()).hexdigest()
        object.__setattr__(self, "content_hash", h)


class SentimentResult(StrictBase):
    """Scored sentiment output for a piece of text.

    * ``score`` ranges from -1 (very bearish) to +1 (very bullish).
    * ``magnitude`` ranges from 0 (low confidence) to 1 (high confidence).
    * The model is frozen (immutable after creation).
    """

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=-1, le=1)
    magnitude: float = Field(ge=0, le=1)
    timestamp: datetime
    reasoning: str | None = None
    article_id: str | None = None
    analyzer: str | None = None
