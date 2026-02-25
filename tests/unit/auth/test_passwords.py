"""Tests for password hashing and verification."""

from __future__ import annotations

from src.auth.passwords import hash_password, verify_password


class TestHashPassword:
    def test_returns_bcrypt_hash(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"
        assert hashed.startswith("$2b$")

    def test_different_calls_produce_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False
