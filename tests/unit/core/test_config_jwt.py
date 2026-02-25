"""Tests for JWT secret validation at startup."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import AuthSettings


class TestJWTSecretValidation:
    def test_rejects_empty_jwt_secret(self):
        with pytest.raises(ValidationError, match="jwt_secret_key"):
            AuthSettings(jwt_secret_key="")

    def test_rejects_short_jwt_secret(self):
        with pytest.raises(ValidationError, match="jwt_secret_key"):
            AuthSettings(jwt_secret_key="too-short")

    def test_accepts_valid_jwt_secret(self):
        secret = "a" * 32
        settings = AuthSettings(jwt_secret_key=secret)
        assert settings.jwt_secret_key == secret

    def test_accepts_long_jwt_secret(self):
        secret = "x" * 64
        settings = AuthSettings(jwt_secret_key=secret)
        assert settings.jwt_secret_key == secret

    def test_rejects_31_char_secret(self):
        with pytest.raises(ValidationError, match="jwt_secret_key"):
            AuthSettings(jwt_secret_key="a" * 31)
