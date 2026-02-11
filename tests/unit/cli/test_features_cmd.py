"""Tests for tradebot features CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestFeaturesList:
    def test_list_exits_zero(self):
        result = runner.invoke(app, ["features", "list"])
        assert result.exit_code == 0

    def test_list_contains_technical(self):
        result = runner.invoke(app, ["features", "list"])
        assert result.exit_code == 0
        assert "sma_5" in result.output
        assert "rsi_14" in result.output
        assert "macd_signal" in result.output

    def test_list_contains_sentiment(self):
        result = runner.invoke(app, ["features", "list"])
        assert result.exit_code == 0
        assert "sentiment_avg_6h" in result.output
        assert "sentiment_avg_24h" in result.output
        assert "article_volume_ratio" in result.output


class TestFeaturesStatus:
    def test_status_exits_zero(self):
        result = runner.invoke(app, ["features", "status"])
        assert result.exit_code == 0
