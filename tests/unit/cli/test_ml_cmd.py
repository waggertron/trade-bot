"""Tests for tradebot ml CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestMLStatus:
    def test_status_shows_summary(self):
        result = runner.invoke(app, ["ml", "status"])
        assert result.exit_code == 0
        assert "ML Pipeline" in result.stdout

    def test_status_shows_store_info(self):
        result = runner.invoke(app, ["ml", "status"])
        assert "Feature Store" in result.stdout


class TestMLFeatures:
    def test_features_with_symbol(self):
        result = runner.invoke(app, ["ml", "features", "--symbol", "AAPL"])
        assert result.exit_code == 0
        assert "AAPL" in result.stdout

    def test_features_missing_symbol_fails(self):
        result = runner.invoke(app, ["ml", "features"])
        assert result.exit_code != 0
