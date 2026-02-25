"""Tests for password strength validation in registration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.dashboard.schemas import RegisterRequest


class TestPasswordValidation:
    def test_rejects_short_password(self):
        with pytest.raises(ValidationError, match="password"):
            RegisterRequest(email="a@b.com", password="Ab1!abc")

    def test_rejects_no_uppercase(self):
        with pytest.raises(ValidationError, match="password"):
            RegisterRequest(email="a@b.com", password="alllower1!")

    def test_rejects_no_lowercase(self):
        with pytest.raises(ValidationError, match="password"):
            RegisterRequest(email="a@b.com", password="ALLUPPER1!")

    def test_rejects_no_digit(self):
        with pytest.raises(ValidationError, match="password"):
            RegisterRequest(email="a@b.com", password="NoDigitHere!")

    def test_accepts_strong_password(self):
        req = RegisterRequest(email="a@b.com", password="Strong1!")
        assert req.password == "Strong1!"

    def test_accepts_long_password(self):
        req = RegisterRequest(email="a@b.com", password="VeryLong1Password!")
        assert len(req.password) > 8
