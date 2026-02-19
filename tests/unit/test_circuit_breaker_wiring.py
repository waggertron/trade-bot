"""Tests for wiring DrawdownCircuitBreaker into RiskManager via main.py."""

from __future__ import annotations

from decimal import Decimal

from src.core.config import Settings
from src.risk.circuit_breaker import DrawdownCircuitBreaker


def test_build_circuit_breaker_uses_risk_settings():
    """build_circuit_breaker creates a breaker from risk settings."""
    from main import build_circuit_breaker

    settings = Settings.for_testing(risk={"weekly_drawdown_limit_pct": 8.0})
    breaker = build_circuit_breaker(settings)
    assert isinstance(breaker, DrawdownCircuitBreaker)
    # The max_drawdown should be 8% (from weekly_drawdown_limit_pct)
    assert breaker._max_drawdown == 0.08


def test_build_circuit_breaker_default_cooldown():
    """Default cooldown should be 24 hours."""
    from main import build_circuit_breaker

    settings = Settings.for_testing()
    breaker = build_circuit_breaker(settings)
    assert breaker._cooldown.total_seconds() == 24 * 3600


def test_risk_manager_constructed_with_circuit_breaker():
    """build_risk_manager should wire a circuit breaker into RiskManager."""
    from main import build_risk_manager

    settings = Settings.for_testing()
    risk_manager = build_risk_manager(settings)
    assert risk_manager._circuit_breaker is not None
    assert isinstance(risk_manager._circuit_breaker, DrawdownCircuitBreaker)
