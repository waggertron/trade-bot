"""Tests for simulation API schema portfolio fields."""
import pytest
from pydantic import ValidationError
from src.dashboard.schemas import SimulationRequest


def test_simulation_request_defaults_backward_compat():
    """Old-style request without portfolio fields still works."""
    req = SimulationRequest(stocks=["AAPL"], initial_balance=10000)
    assert req.portfolio_mode is False
    assert req.allocation_mode == "equal_weight"
    assert req.custom_weights == {}
    assert req.rebalance_frequency == "none"
    assert req.rebalance_threshold_pct == 5.0


def test_simulation_request_portfolio_mode():
    """Portfolio mode request with custom weights."""
    req = SimulationRequest(
        stocks=["AAPL", "MSFT"],
        portfolio_mode=True,
        allocation_mode="custom",
        custom_weights={"AAPL": 0.6, "MSFT": 0.4},
        rebalance_frequency="weekly",
    )
    assert req.portfolio_mode is True
    assert req.allocation_mode == "custom"
    assert req.custom_weights == {"AAPL": 0.6, "MSFT": 0.4}
    assert req.rebalance_frequency == "weekly"


def test_simulation_request_invalid_allocation_mode():
    """Invalid allocation mode rejected."""
    with pytest.raises(ValidationError):
        SimulationRequest(stocks=["AAPL"], allocation_mode="invalid")


def test_simulation_request_invalid_rebalance_frequency():
    """Invalid rebalance frequency rejected."""
    with pytest.raises(ValidationError):
        SimulationRequest(stocks=["AAPL"], rebalance_frequency="hourly")


def test_simulation_request_threshold_bounds():
    """Threshold must be 0-100."""
    with pytest.raises(ValidationError):
        SimulationRequest(stocks=["AAPL"], rebalance_threshold_pct=101)
