"""Tests for tradebot sentiment CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestSentimentStatus:
    def test_status_shows_summary(self):
        result = runner.invoke(app, ["sentiment", "status"])
        assert result.exit_code == 0
        assert "Sentiment Pipeline" in result.stdout

    def test_status_shows_config_details(self):
        result = runner.invoke(app, ["sentiment", "status"])
        assert "Enabled" in result.stdout
        assert "Analyzer" in result.stdout
        assert "ollama" in result.stdout

    def test_status_shows_feeds_info(self):
        result = runner.invoke(app, ["sentiment", "status"])
        assert "Feeds" in result.stdout

    def test_status_shows_interval(self):
        result = runner.invoke(app, ["sentiment", "status"])
        assert "Interval" in result.stdout


class TestSentimentScores:
    def test_scores_with_symbol(self):
        result = runner.invoke(app, ["sentiment", "scores", "--symbol", "BTC"])
        assert result.exit_code == 0
        assert "BTC" in result.stdout

    def test_scores_missing_symbol_fails(self):
        result = runner.invoke(app, ["sentiment", "scores"])
        assert result.exit_code != 0  # missing required --symbol
