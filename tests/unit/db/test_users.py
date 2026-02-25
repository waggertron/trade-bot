"""Tests for user CRUD operations in the database."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.database import Database
from src.db.models import UserRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


class TestCreateUser:
    async def test_creates_user_and_returns_id(self, db: Database):
        user = UserRecord(email="alice@example.com", hashed_password="hashed123", name="Alice")
        user_id = await db.create_user(user)
        assert user_id == user.id

    async def test_duplicate_email_raises(self, db: Database):
        user1 = UserRecord(email="alice@example.com", hashed_password="hashed123")
        await db.create_user(user1)
        user2 = UserRecord(email="alice@example.com", hashed_password="hashed456")
        with pytest.raises(IntegrityError):
            await db.create_user(user2)


class TestGetUserByEmail:
    async def test_returns_user_when_found(self, db: Database):
        user = UserRecord(email="bob@example.com", hashed_password="hashed", name="Bob")
        await db.create_user(user)
        found = await db.get_user_by_email("bob@example.com")
        assert found is not None
        assert found.id == user.id
        assert found.email == "bob@example.com"
        assert found.name == "Bob"

    async def test_returns_none_when_not_found(self, db: Database):
        result = await db.get_user_by_email("nobody@example.com")
        assert result is None


class TestGetUserById:
    async def test_returns_user_when_found(self, db: Database):
        user = UserRecord(email="carol@example.com", hashed_password="hashed", name="Carol")
        await db.create_user(user)
        found = await db.get_user_by_id(user.id)
        assert found is not None
        assert found.email == "carol@example.com"

    async def test_returns_none_when_not_found(self, db: Database):
        result = await db.get_user_by_id("nonexistent-id")
        assert result is None


class TestUserFields:
    async def test_nullable_password_for_oauth(self, db: Database):
        user = UserRecord(email="oauth@example.com", hashed_password=None, name="OAuth User")
        await db.create_user(user)
        found = await db.get_user_by_email("oauth@example.com")
        assert found is not None
        assert found.hashed_password is None

    async def test_default_is_active_and_not_verified(self, db: Database):
        user = UserRecord(email="new@example.com", hashed_password="hashed")
        await db.create_user(user)
        found = await db.get_user_by_id(user.id)
        assert found is not None
        assert found.is_active is True
        assert found.is_verified is False
