"""Tests for tradebot news CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestNewsStatus:
    def test_status_exits_zero(self):
        result = runner.invoke(app, ["news", "status"])
        assert result.exit_code == 0

    def test_status_contains_providers(self):
        result = runner.invoke(app, ["news", "status"])
        assert result.exit_code == 0
        assert "RSS" in result.output
        assert "Reddit" in result.output
        assert "NewsAPI" in result.output
        assert "Mock" in result.output


class TestNewsFeeds:
    def test_feeds_exits_zero(self):
        result = runner.invoke(app, ["news", "feeds"])
        assert result.exit_code == 0
