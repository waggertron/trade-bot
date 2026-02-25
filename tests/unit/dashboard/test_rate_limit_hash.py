"""Tests for deterministic rate limiter key generation."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.dashboard.rate_limit import RateLimitMiddleware


class TestRateLimitKeyDeterminism:
    def test_same_token_produces_same_key(self):
        """The same auth header must produce the same rate limit key every time."""
        mw = RateLimitMiddleware(app=MagicMock())

        req = MagicMock()
        req.headers = {"authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test-token"}
        req.client = MagicMock(host="127.0.0.1")

        key1 = mw._get_key(req)
        key2 = mw._get_key(req)
        assert key1 == key2

    def test_key_is_hex_digest_not_python_hash(self):
        """Key should use a hex digest, not Python's non-deterministic hash()."""
        mw = RateLimitMiddleware(app=MagicMock())

        req = MagicMock()
        req.headers = {"authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test-token"}
        req.client = MagicMock(host="127.0.0.1")

        key = mw._get_key(req)
        # Should be "user:<64-char hex digest>" not "user:<integer>"
        assert key.startswith("user:")
        hex_part = key.removeprefix("user:")
        # SHA-256 hex digest is exactly 64 chars
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_different_tokens_produce_different_keys(self):
        mw = RateLimitMiddleware(app=MagicMock())

        req1 = MagicMock()
        req1.headers = {"authorization": "Bearer token-aaa"}
        req1.client = MagicMock(host="127.0.0.1")

        req2 = MagicMock()
        req2.headers = {"authorization": "Bearer token-bbb"}
        req2.client = MagicMock(host="127.0.0.1")

        assert mw._get_key(req1) != mw._get_key(req2)

    def test_no_auth_falls_back_to_ip(self):
        mw = RateLimitMiddleware(app=MagicMock())

        req = MagicMock()
        req.headers = {}
        req.client = MagicMock(host="10.0.0.1")

        key = mw._get_key(req)
        assert key == "ip:10.0.0.1"
