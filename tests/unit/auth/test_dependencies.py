"""Tests for FastAPI auth dependencies."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.auth.dependencies import get_current_user
from src.auth.tokens import create_access_token
from src.db.database import Database
from src.db.models import UserRecord

TEST_SECRET = "test-secret-key-for-testing-only"


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user(db: Database):
    record = UserRecord(
        email="test@example.com",
        hashed_password="hashed",
        name="Test",
    )
    await db.create_user(record)
    return record


class TestGetCurrentUser:
    async def test_valid_token_returns_user(self, db: Database, user: UserRecord):
        token = create_access_token(user_id=user.id, secret=TEST_SECRET)
        result = await get_current_user(
            token=token,
            db=db,
            secret=TEST_SECRET,
        )
        assert result.id == user.id
        assert result.email == "test@example.com"

    async def test_invalid_token_raises_401(self, db: Database):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="bad-token",
                db=db,
                secret=TEST_SECRET,
            )
        assert exc_info.value.status_code == 401

    async def test_nonexistent_user_raises_401(self, db: Database):
        token = create_access_token(user_id="ghost", secret=TEST_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=token,
                db=db,
                secret=TEST_SECRET,
            )
        assert exc_info.value.status_code == 401

    async def test_refresh_token_rejected(self, db: Database, user: UserRecord):
        from src.auth.tokens import create_refresh_token

        token = create_refresh_token(user_id=user.id, secret=TEST_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=token,
                db=db,
                secret=TEST_SECRET,
            )
        assert exc_info.value.status_code == 401

    async def test_inactive_user_raises_403(self, db: Database):
        inactive = UserRecord(
            email="inactive@example.com",
            hashed_password="hashed",
            name="Inactive",
            is_active=False,
        )
        await db.create_user(inactive)
        token = create_access_token(user_id=inactive.id, secret=TEST_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=token,
                db=db,
                secret=TEST_SECRET,
            )
        assert exc_info.value.status_code == 403
        assert "deactivated" in exc_info.value.detail.lower()
