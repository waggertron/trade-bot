"""Tests for tradebot strategies CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestStrategiesList:
    def test_list_exits_zero(self):
        result = runner.invoke(app, ["strategies", "list"])
        assert result.exit_code == 0

    def test_list_contains_momentum(self):
        result = runner.invoke(app, ["strategies", "list"])
        assert "momentum" in result.stdout

    def test_list_contains_ml_ensemble(self):
        result = runner.invoke(app, ["strategies", "list"])
        assert "ml_ensemble" in result.stdout


class TestStrategiesStatus:
    def test_status_exits_zero(self):
        result = runner.invoke(app, ["strategies", "status"])
        assert result.exit_code == 0
