"""Tests for tradebot backtest CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestBacktestStatus:
    def test_status_exits_zero(self):
        result = runner.invoke(app, ["backtest", "status"])
        assert result.exit_code == 0

    def test_status_contains_analyzers(self):
        result = runner.invoke(app, ["backtest", "status"])
        assert "StrategyAttribution" in result.stdout
        assert "MonteCarloSimulator" in result.stdout


class TestBacktestExample:
    def test_example_exits_zero(self):
        result = runner.invoke(app, ["backtest", "example"])
        assert result.exit_code == 0

    def test_example_contains_report(self):
        result = runner.invoke(app, ["backtest", "example"])
        assert "P&L" in result.stdout or "Strategy" in result.stdout
