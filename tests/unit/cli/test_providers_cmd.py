"""Tests for tradebot providers CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestProvidersList:
    def test_list_all_shows_protocol_names(self):
        result = runner.invoke(app, ["providers", "list"])
        assert result.exit_code == 0
        assert "market_data" in result.output
        assert "news" in result.output
        assert "sentiment" in result.output
        assert "onchain" in result.output
        assert "features" in result.output
        assert "data_store" in result.output

    def test_list_by_protocol(self):
        result = runner.invoke(app, ["providers", "list", "--protocol", "market_data"])
        assert result.exit_code == 0
        assert "market_data" in result.output
        assert "mock_market" in result.output

    def test_list_unknown_protocol_exits_1(self):
        result = runner.invoke(app, ["providers", "list", "--protocol", "unknown"])
        assert result.exit_code == 1


class TestProvidersHealth:
    def test_health_with_mock(self):
        result = runner.invoke(app, ["providers", "health", "--mock"])
        assert result.exit_code == 0
        assert "healthy" in result.output
