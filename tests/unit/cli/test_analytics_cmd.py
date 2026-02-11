"""Tests for tradebot analytics CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestAnalyticsStatus:
    def test_analytics_status(self):
        result = runner.invoke(app, ["analytics", "status"])
        assert result.exit_code == 0
        assert "Analytics Module" in result.stdout
        assert "Ready" in result.stdout

    def test_analytics_status_lists_analyzers(self):
        result = runner.invoke(app, ["analytics", "status"])
        assert result.exit_code == 0
        assert "StrategyAttribution" in result.stdout
        assert "MonteCarloSimulator" in result.stdout


class TestAnalyticsAttribution:
    def test_analytics_attribution(self):
        result = runner.invoke(app, ["analytics", "attribution"])
        assert result.exit_code == 0
        assert "Strategy Attribution" in result.stdout

    def test_analytics_attribution_mentions_strategies(self):
        result = runner.invoke(app, ["analytics", "attribution"])
        assert result.exit_code == 0
        assert "momentum" in result.stdout
        assert "ml_ensemble" in result.stdout
