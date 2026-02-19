"""Tests for simulation CLI command."""
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.simulation_cmd import app

runner = CliRunner()


def test_simulation_run_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "balance" in result.output.lower()


def test_simulation_run_defaults():
    """Smoke test: ensure the command can be invoked (mocking the engine)."""
    mock_report = {
        "id": "test123",
        "status": "completed",
        "config": {"stocks": ["AAPL"], "initial_balance": 10000.0, "train_days": 60, "test_days": 30, "risk_levels": ["moderate"], "mc_simulations": 50},
        "risk_level_results": {},
        "recommendation": {"optimal_risk_level": "moderate", "reasoning": "test", "suggested_weights": {}, "confidence": 0.5},
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch("src.cli.simulation_cmd._run_simulation", return_value=mock_report):
        result = runner.invoke(app, [
            "run",
            "--stocks", "AAPL",
            "--balance", "10000",
            "--train-days", "60",
            "--test-days", "30",
            "--mc-sims", "50",
        ])
        assert result.exit_code == 0
