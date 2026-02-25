"""Tests for JWT token revocation via jti claim and blacklist."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.auth.dependencies import get_current_user
from src.auth.tokens import create_access_token, decode_token
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
        email="revoke@example.com",
        hashed_password="hashed",
        name="Revoke Test",
    )
    await db.create_user(record)
    return record


class TestTokenJtiClaim:
    def test_access_token_contains_jti(self):
        token = create_access_token(user_id="user1", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0

    def test_each_token_has_unique_jti(self):
        t1 = create_access_token(user_id="user1", secret=TEST_SECRET)
        t2 = create_access_token(user_id="user1", secret=TEST_SECRET)
        p1 = decode_token(t1, secret=TEST_SECRET)
        p2 = decode_token(t2, secret=TEST_SECRET)
        assert p1["jti"] != p2["jti"]


class TestTokenRevocationDB:
    async def test_revoke_and_check(self, db: Database):
        token = create_access_token(user_id="user1", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        jti = payload["jti"]

        assert await db.is_token_revoked(jti) is False
        await db.revoke_token(jti)
        assert await db.is_token_revoked(jti) is True

    async def test_unrevoked_token_not_found(self, db: Database):
        assert await db.is_token_revoked("nonexistent-jti") is False


class TestRevokedTokenRejected:
    async def test_revoked_access_token_raises_401(
        self, db: Database, user: UserRecord
    ):
        token = create_access_token(user_id=user.id, secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)

        # Revoke the token
        await db.revoke_token(payload["jti"])

        # get_current_user should reject it
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=token,
                db=db,
                secret=TEST_SECRET,
            )
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()
