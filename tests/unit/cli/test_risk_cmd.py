"""Tests for tradebot risk CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestRiskStatus:
    def test_risk_status(self):
        result = runner.invoke(app, ["risk", "status"])
        assert result.exit_code == 0
        assert "max_position_pct" in result.stdout
        assert "daily_loss_limit_pct" in result.stdout

    def test_risk_status_contains_all_fields(self):
        result = runner.invoke(app, ["risk", "status"])
        assert result.exit_code == 0
        assert "max_open_positions" in result.stdout
        assert "stop_loss_pct" in result.stdout
        assert "max_correlation" in result.stdout


class TestRiskLimits:
    def test_risk_limits_default(self):
        result = runner.invoke(app, ["risk", "limits"])
        assert result.exit_code == 0
        # Default is medium regime
        assert "max_position_pct" in result.stdout
        assert "8" in result.stdout  # max_open_positions for MEDIUM
        assert "3.0" in result.stdout  # daily_loss_limit_pct for MEDIUM

    def test_risk_limits_high(self):
        result = runner.invoke(app, ["risk", "limits", "--regime", "high"])
        assert result.exit_code == 0
        assert "4" in result.stdout  # max_open_positions: 4
        assert "2.0" in result.stdout  # daily_loss_limit_pct: 2.0

    def test_risk_limits_low(self):
        result = runner.invoke(app, ["risk", "limits", "--regime", "low"])
        assert result.exit_code == 0
        assert "12" in result.stdout  # max_open_positions: 12
        assert "4.0" in result.stdout  # daily_loss_limit_pct: 4.0
