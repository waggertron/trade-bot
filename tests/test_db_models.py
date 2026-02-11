"""Tests for Pydantic DB record models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.db.models import OHLCRecord, SignalRecord, TradeRecord


class TestTradeRecord:
    def test_creates_with_valid_data(self):
        trade = TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.25",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(timezone.utc),
        )
        assert trade.symbol == "AAPL"
        assert trade.side == "buy"
        assert trade.paper is True

    def test_has_auto_id(self):
        trade = TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.25",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(timezone.utc),
        )
        assert trade.id is not None
        assert len(trade.id) == 36  # UUID format

    def test_auto_ids_are_unique(self):
        kwargs = dict(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.25",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(timezone.utc),
        )
        t1 = TradeRecord(**kwargs)
        t2 = TradeRecord(**kwargs)
        assert t1.id != t2.id

    def test_serialization_roundtrip(self):
        trade = TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.25",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        data = trade.model_dump()
        restored = TradeRecord(**data)
        assert restored == trade
        assert restored.id == trade.id

    def test_frozen(self):
        trade = TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.25",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(ValidationError):
            trade.symbol = "MSFT"


class TestSignalRecord:
    def test_creates_with_valid_data(self):
        signal = SignalRecord(
            symbol="AAPL",
            direction="buy",
            confidence=0.85,
            strategy="momentum",
            reasoning="Strong trend",
            timestamp=datetime.now(timezone.utc),
        )
        assert signal.symbol == "AAPL"
        assert signal.confidence == 0.85

    def test_rejects_confidence_above_1(self):
        with pytest.raises(ValidationError):
            SignalRecord(
                symbol="AAPL",
                direction="buy",
                confidence=1.5,
                strategy="momentum",
                reasoning="test",
                timestamp=datetime.now(timezone.utc),
            )

    def test_rejects_confidence_below_0(self):
        with pytest.raises(ValidationError):
            SignalRecord(
                symbol="AAPL",
                direction="buy",
                confidence=-0.1,
                strategy="momentum",
                reasoning="test",
                timestamp=datetime.now(timezone.utc),
            )

    def test_accepts_boundary_confidence(self):
        s0 = SignalRecord(
            symbol="AAPL",
            direction="buy",
            confidence=0.0,
            strategy="momentum",
            reasoning="test",
            timestamp=datetime.now(timezone.utc),
        )
        s1 = SignalRecord(
            symbol="AAPL",
            direction="buy",
            confidence=1.0,
            strategy="momentum",
            reasoning="test",
            timestamp=datetime.now(timezone.utc),
        )
        assert s0.confidence == 0.0
        assert s1.confidence == 1.0

    def test_has_auto_id(self):
        signal = SignalRecord(
            symbol="AAPL",
            direction="buy",
            confidence=0.5,
            strategy="momentum",
            reasoning="test",
            timestamp=datetime.now(timezone.utc),
        )
        assert signal.id is not None
        assert len(signal.id) == 36


class TestOHLCRecord:
    def test_creates_with_valid_data(self):
        record = OHLCRecord(
            symbol="AAPL",
            interval="1d",
            timestamp=1700000000,
            open="150.00",
            high="155.00",
            low="148.00",
            close="153.00",
            volume="1000000",
            source="yfinance",
        )
        assert record.symbol == "AAPL"
        assert record.interval == "1d"
        assert record.timestamp == 1700000000
        assert record.open == "150.00"
        assert record.source == "yfinance"

    def test_frozen(self):
        record = OHLCRecord(
            symbol="AAPL",
            interval="1d",
            timestamp=1700000000,
            open="150.00",
            high="155.00",
            low="148.00",
            close="153.00",
            volume="1000000",
            source="yfinance",
        )
        with pytest.raises(ValidationError):
            record.symbol = "MSFT"

    def test_serialization_roundtrip(self):
        record = OHLCRecord(
            symbol="AAPL",
            interval="1d",
            timestamp=1700000000,
            open="150.00",
            high="155.00",
            low="148.00",
            close="153.00",
            volume="1000000",
            source="yfinance",
        )
        data = record.model_dump()
        restored = OHLCRecord(**data)
        assert restored == record
