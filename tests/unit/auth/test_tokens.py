"""Tests for JWT token creation and verification."""

from __future__ import annotations

import pytest

from src.auth.tokens import create_access_token, create_refresh_token, decode_token

TEST_SECRET = "test-secret-key-for-testing-only"


class TestCreateAccessToken:
    def test_returns_string_token(self):
        token = create_access_token(user_id="user123", secret=TEST_SECRET)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_user_id(self):
        token = create_access_token(user_id="user123", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        assert payload["sub"] == "user123"

    def test_token_has_type_access(self):
        token = create_access_token(user_id="user123", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        assert payload["type"] == "access"


class TestCreateRefreshToken:
    def test_returns_string_token(self):
        token = create_refresh_token(user_id="user123", secret=TEST_SECRET)
        assert isinstance(token, str)

    def test_token_has_type_refresh(self):
        token = create_refresh_token(user_id="user123", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        assert payload["type"] == "refresh"


class TestDecodeToken:
    def test_valid_token_returns_payload(self):
        token = create_access_token(user_id="user123", secret=TEST_SECRET)
        payload = decode_token(token, secret=TEST_SECRET)
        assert payload["sub"] == "user123"

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("invalid.token.here", secret=TEST_SECRET)

    def test_wrong_secret_raises(self):
        token = create_access_token(user_id="user123", secret=TEST_SECRET)
        with pytest.raises(Exception):
            decode_token(token, secret="wrong-secret")

    def test_expired_token_raises(self):
        token = create_access_token(
            user_id="user123", secret=TEST_SECRET, expire_minutes=-1,
        )
        with pytest.raises(Exception):
            decode_token(token, secret=TEST_SECRET)
