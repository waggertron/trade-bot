"""Tests for user-scoped database operations — multi-tenant data isolation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.db.database import Database
from src.db.models import SignalRecord, TradeRecord, UserRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user_a(db: Database):
    record = UserRecord(email="alice@example.com", hashed_password="h", name="Alice")
    await db.create_user(record)
    return record


@pytest.fixture
async def user_b(db: Database):
    record = UserRecord(email="bob@example.com", hashed_password="h", name="Bob")
    await db.create_user(record)
    return record


def _make_trade(user_id: str, symbol: str = "AAPL", strategy: str = "momentum") -> TradeRecord:
    return TradeRecord(
        symbol=symbol,
        side="buy",
        quantity="10",
        price="100",
        commission="1",
        strategy=strategy,
        paper=True,
        timestamp=datetime.now(UTC),
        user_id=user_id,
    )


def _make_signal(user_id: str, symbol: str = "AAPL") -> SignalRecord:
    return SignalRecord(
        symbol=symbol,
        direction="buy",
        confidence=0.8,
        strategy="momentum",
        reasoning="test",
        timestamp=datetime.now(UTC),
        user_id=user_id,
    )


class TestSaveTradeWithUser:
    async def test_stores_user_id(self, db: Database, user_a: UserRecord):
        trade = _make_trade(user_a.id)
        tid = await db.save_trade(trade)
        retrieved = await db.get_trade(tid)
        assert retrieved is not None
        assert retrieved.user_id == user_a.id


class TestListTradesScoped:
    async def test_lists_only_own_trades(
        self,
        db: Database,
        user_a: UserRecord,
        user_b: UserRecord,
    ):
        await db.save_trade(_make_trade(user_a.id, symbol="AAPL"))
        await db.save_trade(_make_trade(user_a.id, symbol="MSFT"))
        await db.save_trade(_make_trade(user_b.id, symbol="GOOGL"))
        alice_trades = await db.list_trades(user_id=user_a.id)
        assert len(alice_trades) == 2
        assert all(t.user_id == user_a.id for t in alice_trades)

    async def test_user_b_sees_only_own(self, db: Database, user_a: UserRecord, user_b: UserRecord):
        await db.save_trade(_make_trade(user_a.id))
        await db.save_trade(_make_trade(user_b.id))
        bob_trades = await db.list_trades(user_id=user_b.id)
        assert len(bob_trades) == 1
        assert bob_trades[0].user_id == user_b.id

    async def test_strategy_filter_combined_with_user(
        self,
        db: Database,
        user_a: UserRecord,
        user_b: UserRecord,
    ):
        await db.save_trade(_make_trade(user_a.id, strategy="momentum"))
        await db.save_trade(_make_trade(user_a.id, strategy="sentiment"))
        await db.save_trade(_make_trade(user_b.id, strategy="momentum"))
        result = await db.list_trades(user_id=user_a.id, strategy="momentum")
        assert len(result) == 1

    async def test_no_user_id_returns_all(
        self,
        db: Database,
        user_a: UserRecord,
        user_b: UserRecord,
    ):
        """Backward compat: omitting user_id returns all trades."""
        await db.save_trade(_make_trade(user_a.id))
        await db.save_trade(_make_trade(user_b.id))
        all_trades = await db.list_trades()
        assert len(all_trades) == 2


class TestSaveSignalWithUser:
    async def test_stores_user_id(self, db: Database, user_a: UserRecord):
        sig = _make_signal(user_a.id)
        await db.save_signal(sig)
        # Verify via list
        signals = await db.list_signals(user_id=user_a.id)
        assert len(signals) == 1
        assert signals[0].user_id == user_a.id


class TestListSignalsScoped:
    async def test_lists_only_own_signals(
        self,
        db: Database,
        user_a: UserRecord,
        user_b: UserRecord,
    ):
        await db.save_signal(_make_signal(user_a.id, symbol="AAPL"))
        await db.save_signal(_make_signal(user_a.id, symbol="MSFT"))
        await db.save_signal(_make_signal(user_b.id, symbol="GOOGL"))
        alice_signals = await db.list_signals(user_id=user_a.id)
        assert len(alice_signals) == 2
        assert all(s.user_id == user_a.id for s in alice_signals)

    async def test_no_user_id_returns_all(
        self,
        db: Database,
        user_a: UserRecord,
        user_b: UserRecord,
    ):
        """Backward compat: omitting user_id returns all signals."""
        await db.save_signal(_make_signal(user_a.id))
        await db.save_signal(_make_signal(user_b.id))
        all_signals = await db.list_signals()
        assert len(all_signals) == 2
