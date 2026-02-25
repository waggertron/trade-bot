"""Tests for OAuth account linking and lookup."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.database import Database
from src.db.models import OAuthAccountRecord, UserRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user(db: Database):
    record = UserRecord(email="oauth@example.com", name="OAuth User")
    await db.create_user(record)
    return record


class TestLinkOAuthAccount:
    async def test_links_account_and_returns_id(self, db: Database, user: UserRecord):
        account = OAuthAccountRecord(
            user_id=user.id,
            provider="google",
            provider_user_id="g-12345",
            email="oauth@gmail.com",
        )
        account_id = await db.link_oauth_account(account)
        assert account_id == account.id

    async def test_duplicate_provider_user_raises(self, db: Database, user: UserRecord):
        acct1 = OAuthAccountRecord(
            user_id=user.id,
            provider="google",
            provider_user_id="g-12345",
            email="oauth@gmail.com",
        )
        await db.link_oauth_account(acct1)
        acct2 = OAuthAccountRecord(
            user_id=user.id,
            provider="google",
            provider_user_id="g-12345",
            email="other@gmail.com",
        )
        with pytest.raises(IntegrityError):
            await db.link_oauth_account(acct2)

    async def test_same_user_different_providers(self, db: Database, user: UserRecord):
        google = OAuthAccountRecord(
            user_id=user.id,
            provider="google",
            provider_user_id="g-123",
            email="u@gmail.com",
        )
        github = OAuthAccountRecord(
            user_id=user.id,
            provider="github",
            provider_user_id="gh-456",
            email="u@github.com",
        )
        await db.link_oauth_account(google)
        await db.link_oauth_account(github)
        # Both should exist
        found_g = await db.get_user_by_oauth("google", "g-123")
        found_gh = await db.get_user_by_oauth("github", "gh-456")
        assert found_g is not None
        assert found_gh is not None
        assert found_g.id == found_gh.id == user.id


class TestGetUserByOAuth:
    async def test_returns_user_when_linked(self, db: Database, user: UserRecord):
        account = OAuthAccountRecord(
            user_id=user.id,
            provider="github",
            provider_user_id="gh-789",
            email="oauth@github.com",
        )
        await db.link_oauth_account(account)
        found = await db.get_user_by_oauth("github", "gh-789")
        assert found is not None
        assert found.id == user.id
        assert found.email == "oauth@example.com"

    async def test_returns_none_when_not_found(self, db: Database):
        result = await db.get_user_by_oauth("google", "nonexistent")
        assert result is None
