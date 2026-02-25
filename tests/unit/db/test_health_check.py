"""Tests for Database.check_health method."""

from __future__ import annotations

import pytest

from src.db.database import Database


class TestDatabaseHealthCheck:
    async def test_check_health_on_valid_db(self, tmp_path):
        db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
        await db.initialize()

        result = await db.check_health()

        assert result is True
        await db.close()

    async def test_check_health_returns_true(self, tmp_path):
        db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test2.db'}")
        await db.initialize()

        # Should return True for valid database
        result = await db.check_health()
        assert result is True

        await db.close()
