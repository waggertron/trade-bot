"""Tests for user_settings CRUD operations."""

from __future__ import annotations

import pytest

from src.db.database import Database
from src.db.models import UserRecord, UserSettingsRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user(db: Database):
    record = UserRecord(email="settings@example.com", hashed_password="h", name="User")
    await db.create_user(record)
    return record


class TestGetUserSettings:
    async def test_returns_none_when_no_settings(self, db: Database, user: UserRecord):
        result = await db.get_user_settings(user.id)
        assert result is None

    async def test_returns_settings_after_creation(self, db: Database, user: UserRecord):
        settings = UserSettingsRecord(user_id=user.id, mode="paper")
        await db.save_user_settings(settings)
        result = await db.get_user_settings(user.id)
        assert result is not None
        assert result.user_id == user.id
        assert result.mode == "paper"


class TestSaveUserSettings:
    async def test_creates_new_settings(self, db: Database, user: UserRecord):
        settings = UserSettingsRecord(
            user_id=user.id, mode="paper", risk_preset="moderate",
            symbols_config='{"stocks": ["AAPL"], "crypto": ["BTC/USD"]}',
            strategy_weights='{"momentum": 0.5}',
        )
        sid = await db.save_user_settings(settings)
        assert sid == settings.id

    async def test_duplicate_user_raises(self, db: Database, user: UserRecord):
        s1 = UserSettingsRecord(user_id=user.id)
        await db.save_user_settings(s1)
        s2 = UserSettingsRecord(user_id=user.id)
        with pytest.raises(Exception):
            await db.save_user_settings(s2)


class TestUpdateUserSettings:
    async def test_updates_mode(self, db: Database, user: UserRecord):
        settings = UserSettingsRecord(user_id=user.id, mode="paper")
        await db.save_user_settings(settings)
        await db.update_user_settings(user.id, mode="live")
        result = await db.get_user_settings(user.id)
        assert result is not None
        assert result.mode == "live"

    async def test_updates_symbols_config(self, db: Database, user: UserRecord):
        settings = UserSettingsRecord(user_id=user.id)
        await db.save_user_settings(settings)
        new_config = '{"stocks": ["MSFT"], "crypto": []}'
        await db.update_user_settings(user.id, symbols_config=new_config)
        result = await db.get_user_settings(user.id)
        assert result is not None
        assert result.symbols_config == new_config
