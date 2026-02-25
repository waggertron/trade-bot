"""Tests for the email verification API endpoint."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.auth.tokens import create_verification_token
from src.core.config import AuthSettings, Settings
from src.dashboard.app import create_app
from src.dashboard.dependencies import require_user
from src.db.models import UserRecord

JWT_SECRET = "test-secret-key-for-verification!!"


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_user_settings.return_value = None
    return db


@pytest.fixture
def unverified_user():
    return UserRecord(
        id="user-1",
        email="test@example.com",
        hashed_password="h",
        name="Test",
        is_verified=False,
    )


@pytest.fixture
def verified_user():
    return UserRecord(
        id="user-2",
        email="verified@example.com",
        hashed_password="h",
        name="Verified",
        is_verified=True,
    )


@pytest.fixture
def settings():
    return Settings(auth=AuthSettings(jwt_secret_key=JWT_SECRET))


@pytest.fixture
def client(mock_db, settings, unverified_user):
    app = create_app(db=mock_db, settings=settings)
    app.dependency_overrides[require_user] = lambda: unverified_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestVerifyEndpoint:
    def test_verify_with_valid_token(self, client, mock_db, unverified_user):
        mock_db.get_user_by_id.return_value = unverified_user
        mock_db.update_user.return_value = None

        token = create_verification_token(user_id=unverified_user.id, secret=JWT_SECRET)
        resp = client.get(f"/api/auth/verify/{token}")

        assert resp.status_code == 200
        assert resp.json()["verified"] is True
        mock_db.update_user.assert_called_once_with(unverified_user.id, is_verified=True)

    def test_verify_with_invalid_token(self, client):
        resp = client.get("/api/auth/verify/bad-token")
        assert resp.status_code == 400

    def test_verify_with_nonexistent_user(self, client, mock_db):
        mock_db.get_user_by_id.return_value = None

        token = create_verification_token(user_id="ghost", secret=JWT_SECRET)
        resp = client.get(f"/api/auth/verify/{token}")

        assert resp.status_code == 404


class TestTradingRequiresVerification:
    def test_unverified_user_blocked_from_placing_orders(self, mock_db, settings, unverified_user):
        """Unverified users should get 403 on trading order endpoint."""
        mock_executor = AsyncMock()
        mock_portfolio = AsyncMock()
        app = create_app(
            db=mock_db,
            settings=settings,
            executor=mock_executor,
            portfolio_manager=mock_portfolio,
        )
        app.dependency_overrides[require_user] = lambda: unverified_user
        with TestClient(app) as c:
            resp = c.post(
                "/api/trading/order",
                json={
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": "1",
                },
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 403
        assert "verified" in resp.json()["detail"].lower()

    def test_verified_user_can_place_orders(self, mock_db, settings, verified_user):
        """Verified users should be able to trade."""
        from datetime import datetime
        from decimal import Decimal

        from src.core.models import Fill, OrderSide

        mock_executor = AsyncMock()
        mock_executor.submit_order.return_value = Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            fill_price=Decimal("50000"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        mock_portfolio = AsyncMock()
        app = create_app(
            db=mock_db,
            settings=settings,
            executor=mock_executor,
            portfolio_manager=mock_portfolio,
        )
        app.dependency_overrides[require_user] = lambda: verified_user
        with TestClient(app) as c:
            resp = c.post(
                "/api/trading/order",
                json={
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": "1",
                },
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 200
