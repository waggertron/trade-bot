"""Tests for tradebot portfolio CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestPortfolioShow:
    def test_show_exits_zero(self) -> None:
        result = runner.invoke(app, ["portfolio", "show"])
        assert result.exit_code == 0

    def test_show_contains_portfolio_header(self) -> None:
        result = runner.invoke(app, ["portfolio", "show"])
        assert result.exit_code == 0
        assert "Portfolio" in result.stdout


class TestPortfolioTrades:
    def test_trades_exits_zero(self) -> None:
        result = runner.invoke(app, ["portfolio", "trades"])
        assert result.exit_code == 0

    def test_trades_with_limit(self) -> None:
        result = runner.invoke(app, ["portfolio", "trades", "--limit", "5"])
        assert result.exit_code == 0


class TestPortfolioPnl:
    def test_pnl_exits_zero(self) -> None:
        result = runner.invoke(app, ["portfolio", "pnl"])
        assert result.exit_code == 0

    def test_pnl_with_period(self) -> None:
        result = runner.invoke(app, ["portfolio", "pnl", "--period", "7d"])
        assert result.exit_code == 0
