"""Tests for email verification token creation and verification."""

from __future__ import annotations

from datetime import UTC

from src.auth.tokens import create_verification_token, decode_token


class TestVerificationTokens:
    def test_create_verification_token(self):
        token = create_verification_token(user_id="user-123", secret="test-secret")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_verification_token(self):
        token = create_verification_token(user_id="user-123", secret="test-secret")
        payload = decode_token(token, secret="test-secret")
        assert payload["sub"] == "user-123"
        assert payload["type"] == "verification"

    def test_verification_token_expires_in_24h(self):
        from datetime import datetime

        token = create_verification_token(user_id="user-123", secret="test-secret")
        payload = decode_token(token, secret="test-secret")
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        iat = datetime.fromtimestamp(payload["iat"], tz=UTC)
        delta = exp - iat
        # Should be 24 hours
        assert 23 * 3600 <= delta.total_seconds() <= 25 * 3600
