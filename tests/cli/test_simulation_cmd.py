"""Tests for simulation CLI command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.simulation_cmd import app

runner = CliRunner()


def test_simulation_run_help(monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "balance" in result.output.lower()


def test_simulation_run_help_shows_portfolio_flags(monkeypatch):
    """Help text should include the new portfolio-mode flags."""
    # Rich truncates long option names in narrow terminals (e.g. --portfo…).
    # Force a wide terminal so the full names are printed.
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--portfolio" in result.output
    assert "--weights" in result.output
    assert "--rebalance" in result.output


def _mock_report(*, portfolio_mode: bool = False, config_extras: dict | None = None) -> dict:
    """Build a minimal mock report dict."""
    config = {
        "stocks": ["AAPL"],
        "initial_balance": 10000.0,
        "train_days": 60,
        "test_days": 30,
        "risk_levels": ["moderate"],
        "mc_simulations": 50,
        "portfolio_mode": portfolio_mode,
    }
    if config_extras:
        config.update(config_extras)
    return {
        "id": "test123",
        "status": "completed",
        "config": config,
        "risk_level_results": {},
        "recommendation": {
            "optimal_risk_level": "moderate",
            "reasoning": "test",
            "suggested_weights": {},
            "confidence": 0.5,
        },
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }


def test_simulation_run_defaults():
    """Smoke test: ensure the command can be invoked (mocking the engine)."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--balance",
                "10000",
                "--train-days",
                "60",
                "--test-days",
                "30",
                "--mc-sims",
                "50",
            ],
        )
        assert result.exit_code == 0


def test_run_passes_portfolio_flags_to_run_simulation():
    """--portfolio, --weights, --rebalance should be forwarded to _run_simulation."""
    with patch(
        "src.cli.simulation_cmd._run_simulation",
        return_value=_mock_report(portfolio_mode=True),
    ) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--stocks",
                "MSFT",
                "--balance",
                "20000",
                "--train-days",
                "60",
                "--test-days",
                "30",
                "--mc-sims",
                "50",
                "--portfolio",
                "--weights",
                '{"AAPL":0.6,"MSFT":0.4}',
                "--rebalance",
                "weekly",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_fn.assert_called_once()
        _, _kwargs = mock_fn.call_args
        # Positional args are first 6, then portfolio-specific kwargs
        args = mock_fn.call_args
        # Check portfolio-related kwargs were passed
        assert args.kwargs.get("portfolio_mode") is True or args.args[6] is True
        # Check allocation_weights was parsed from JSON
        alloc = args.kwargs.get("allocation_weights") or args.args[7]
        assert alloc == {"AAPL": 0.6, "MSFT": 0.4}
        # Check rebalance frequency
        rebal = args.kwargs.get("rebalance_freq") or args.args[8]
        assert rebal == "weekly"


def test_run_portfolio_mode_status_message():
    """When --portfolio is set, the output should include a portfolio mode message."""
    with patch(
        "src.cli.simulation_cmd._run_simulation",
        return_value=_mock_report(portfolio_mode=True),
    ):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--portfolio",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Portfolio Mode" in result.output


def test_run_simulation_creates_config_with_portfolio_fields():
    """_run_simulation should create a SimulationConfig with portfolio fields."""
    from unittest.mock import MagicMock

    mock_engine_cls = MagicMock()
    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report(portfolio_mode=True)
    mock_engine_cls.return_value.run.return_value = mock_report

    with (
        patch("src.simulation.engine.SimulationEngine", mock_engine_cls),
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        # asyncio.run should call the coroutine; simulate that
        mock_asyncio.run.side_effect = lambda coro: mock_report

        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL", "MSFT"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            portfolio_mode=True,
            allocation_weights={"AAPL": 0.5, "MSFT": 0.5},
            rebalance_freq="monthly",
        )

        # asyncio.run was called; check the config passed to SimulationEngine
        # Since the import is local, we need to check what asyncio.run received
        # The config is constructed before SimulationEngine, so let's verify
        # by checking the mock_asyncio.run call and the report return
        mock_asyncio.run.assert_called_once()


def test_run_simulation_config_construction():
    """Verify _run_simulation constructs SimulationConfig with correct portfolio fields."""
    from unittest.mock import MagicMock

    # We can test the config construction by patching _run_simulation more directly.
    # Since SimulationEngine is imported locally, let's test by capturing the config
    # object created. We'll mock the entire engine path.
    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report(portfolio_mode=True)

    with (
        patch("src.simulation.engine.SimulationEngine") as mock_engine_cls,
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        mock_engine_cls.return_value.run.return_value = mock_report
        mock_asyncio.run.side_effect = lambda coro: mock_report

        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL", "MSFT"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            portfolio_mode=True,
            allocation_weights={"AAPL": 0.5, "MSFT": 0.5},
            rebalance_freq="monthly",
        )

        # The SimulationEngine was constructed with a config inside _run_simulation
        # Since it's a local import, we patched at source. Check if it was called.
        mock_engine_cls.assert_called_once()
        config_arg = mock_engine_cls.call_args[0][0]
        assert config_arg.portfolio_mode is True
        assert config_arg.allocation.mode == "custom"
        assert config_arg.allocation.weights == {"AAPL": 0.5, "MSFT": 0.5}
        assert config_arg.rebalance.frequency == "monthly"


def test_run_simulation_equal_weight_when_no_custom_weights():
    """_run_simulation should default to equal_weight when no weights given."""
    from unittest.mock import MagicMock

    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report(portfolio_mode=True)

    with (
        patch("src.simulation.engine.SimulationEngine") as mock_engine_cls,
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        mock_engine_cls.return_value.run.return_value = mock_report
        mock_asyncio.run.side_effect = lambda coro: mock_report

        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL", "MSFT"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            portfolio_mode=True,
            allocation_weights=None,
            rebalance_freq="none",
        )

        config_arg = mock_engine_cls.call_args[0][0]
        assert config_arg.allocation.mode == "equal_weight"
        assert config_arg.allocation.weights == {}
        assert config_arg.rebalance.frequency == "none"


def test_print_report_with_portfolio_metrics():
    """_print_report should display portfolio metrics when present."""
    report = _mock_report(
        portfolio_mode=True,
        config_extras={
            "allocation": {"mode": "equal_weight", "weights": {}},
        },
    )
    report["risk_level_results"] = {
        "moderate": {
            "risk_level": "moderate",
            "stock_results": [
                {
                    "symbol": "AAPL",
                    "initial_balance": 5000.0,
                    "final_value": 5500.0,
                    "total_pnl": 500.0,
                    "return_pct": 10.0,
                    "max_drawdown": 5.0,
                    "sharpe_ratio": 1.2,
                    "total_trades": 10,
                    "winning_trades": 6,
                    "losing_trades": 4,
                    "win_rate": 0.6,
                    "equity_curve": [5000, 5100, 5200, 5300, 5500],
                },
                {
                    "symbol": "MSFT",
                    "initial_balance": 5000.0,
                    "final_value": 5300.0,
                    "total_pnl": 300.0,
                    "return_pct": 6.0,
                    "max_drawdown": 3.0,
                    "sharpe_ratio": 0.9,
                    "total_trades": 8,
                    "winning_trades": 5,
                    "losing_trades": 3,
                    "win_rate": 0.625,
                    "equity_curve": [5000, 5050, 5100, 5200, 5300],
                },
            ],
            "monte_carlo_projections": [],
            "strategy_assessments": [],
            "total_return_pct": 8.0,
            "avg_sharpe": 1.05,
            "avg_max_drawdown": 4.0,
            "total_trades": 18,
            "portfolio_metrics": {
                "initial_balance": 10000.0,
                "final_value": 10800.0,
                "total_return_pct": 8.0,
                "max_drawdown": 4.5,
                "sharpe_ratio": 1.1,
                "sortino_ratio": 1.5,
                "calmar_ratio": 1.78,
                "total_trades": 18,
                "equity_curve": [10000, 10150, 10300, 10500, 10800],
                "daily_returns": [0.015, 0.0148, 0.0194, 0.0286],
                "rebalance_dates": [],
            },
            "portfolio_monte_carlo": {
                "median_final": 11000.0,
                "p5_final": 9500.0,
                "p95_final": 12500.0,
                "median_return_pct": 10.0,
                "p5_return_pct": -5.0,
                "p95_return_pct": 25.0,
                "worst_drawdown_p95": 8.5,
                "n_paths": 1000,
                "correlation_matrix": [[1.0, 0.65], [0.65, 1.0]],
            },
        }
    }

    from src.cli.simulation_cmd import _print_report

    # This should not raise; we verify it runs without error
    _print_report(report)


def test_simulation_run_help_shows_seed_and_rebalance_threshold_flags(monkeypatch):
    """Help text should include --seed and --rebalance-threshold flags."""
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--seed" in result.output
    assert "--rebalance-threshold" in result.output


def test_run_passes_seed_and_rebalance_threshold_to_run_simulation():
    """--seed and --rebalance-threshold should be forwarded to _run_simulation."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--balance",
                "10000",
                "--train-days",
                "60",
                "--test-days",
                "30",
                "--mc-sims",
                "50",
                "--seed",
                "42",
                "--rebalance-threshold",
                "3.5",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_fn.assert_called_once()
        args = mock_fn.call_args
        assert args.kwargs.get("seed") == 42
        assert args.kwargs.get("rebalance_threshold") == 3.5


def test_run_seed_default_is_none():
    """When --seed is not specified, seed should default to None."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
            ],
        )
        assert result.exit_code == 0, result.output
        args = mock_fn.call_args
        assert args.kwargs.get("seed") is None


def test_run_rebalance_threshold_default_is_5():
    """When --rebalance-threshold is not specified, it should default to 5.0."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
            ],
        )
        assert result.exit_code == 0, result.output
        args = mock_fn.call_args
        assert args.kwargs.get("rebalance_threshold") == 5.0


def test_run_shows_seed_in_status_display():
    """When --seed is specified, the output should show the seed value."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--seed",
                "42",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Seed: 42" in result.output


def test_run_does_not_show_seed_when_not_specified():
    """When --seed is not specified, the output should not show a seed line."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Seed:" not in result.output


def test_run_simulation_passes_threshold_pct_to_rebalance_config():
    """_run_simulation should pass threshold_pct to RebalanceConfig."""
    from unittest.mock import MagicMock

    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report()

    with (
        patch("src.simulation.engine.SimulationEngine") as mock_engine_cls,
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        mock_engine_cls.return_value.run.return_value = mock_report
        mock_asyncio.run.side_effect = lambda coro: mock_report

        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            rebalance_threshold=3.5,
        )

        config_arg = mock_engine_cls.call_args[0][0]
        assert config_arg.rebalance.threshold_pct == 3.5


def test_run_simulation_passes_mc_seed_to_simulation_config():
    """_run_simulation should pass mc_seed to SimulationConfig."""
    from unittest.mock import MagicMock

    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report()

    with (
        patch("src.simulation.engine.SimulationEngine") as mock_engine_cls,
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        mock_engine_cls.return_value.run.return_value = mock_report
        mock_asyncio.run.side_effect = lambda coro: mock_report

        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            seed=42,
            use_cache=False,
        )

        config_arg = mock_engine_cls.call_args[0][0]
        assert config_arg.mc_seed == 42


# ---------------------------------------------------------------------------
# --charts flag tests
# ---------------------------------------------------------------------------


def _mock_report_with_stocks(*, num_stocks: int = 2) -> dict:
    """Build a mock report with per-stock results and equity curves for chart tests."""
    stock_results = []
    for i in range(num_stocks):
        sym = f"STK{i}"
        stock_results.append(
            {
                "symbol": sym,
                "initial_balance": 5000.0,
                "final_value": 5500.0,
                "total_pnl": 500.0,
                "return_pct": 10.0,
                "max_drawdown": 5.0,
                "sharpe_ratio": 1.2,
                "total_trades": 10,
                "winning_trades": 6,
                "losing_trades": 4,
                "win_rate": 0.6,
                "equity_curve": [5000, 5100, 5200, 5300, 5500],
            }
        )

    report = _mock_report()
    report["risk_level_results"] = {
        "moderate": {
            "risk_level": "moderate",
            "stock_results": stock_results,
            "monte_carlo_projections": [],
            "strategy_assessments": [],
            "total_return_pct": 10.0,
            "avg_sharpe": 1.2,
            "avg_max_drawdown": 5.0,
            "total_trades": 20,
            "portfolio_metrics": None,
            "portfolio_monte_carlo": None,
        },
    }
    return report


def test_run_help_shows_charts_flag(monkeypatch):
    """Help text should include the --charts flag."""
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--charts" in result.output


def test_charts_none_skips_all_charts():
    """--charts none should produce compact output: no charts, no per-stock tables."""
    report = _mock_report_with_stocks()
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "none"])
    assert result.exit_code == 0, result.output
    # No chart-related content
    assert "Equity Curve" not in result.output
    assert "Charts" not in result.output
    # Per-stock detail tables should be skipped
    assert "Per-Stock Details" not in result.output
    assert "Per-Stock Results" not in result.output
    # Portfolio metrics should still show
    assert "Risk Level Comparison" in result.output


def test_charts_summary_skips_per_stock_equity_curves():
    """--charts summary should skip per-stock equity curves but show summary charts."""
    report = _mock_report_with_stocks(num_stocks=3)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "summary"])
    assert result.exit_code == 0, result.output
    # Per-stock equity curves should NOT appear
    assert "STK0 Equity Curve" not in result.output
    assert "STK1 Equity Curve" not in result.output
    # Summary chart section should still appear
    assert "Charts" in result.output


def test_charts_full_includes_per_stock_equity_curves():
    """--charts full should include per-stock equity curves."""
    report = _mock_report_with_stocks(num_stocks=2)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "full"])
    assert result.exit_code == 0, result.output
    # Per-stock equity curves should appear
    assert "STK0 Equity Curve" in result.output
    assert "STK1 Equity Curve" in result.output


def test_charts_default_is_summary():
    """When --charts is not specified, it should default to summary (no per-stock curves)."""
    report = _mock_report_with_stocks(num_stocks=2)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0"])
    assert result.exit_code == 0, result.output
    # Per-stock equity curves should NOT appear (summary mode)
    assert "STK0 Equity Curve" not in result.output


# ---------------------------------------------------------------------------
# Engine progress callback wiring tests
# ---------------------------------------------------------------------------


def test_run_simulation_passes_progress_cb_to_engine():
    """_run_simulation should pass progress_cb to SimulationEngine when provided."""
    from unittest.mock import MagicMock

    mock_report = MagicMock()
    mock_report.model_dump.return_value = _mock_report()

    with (
        patch("src.simulation.engine.SimulationEngine") as mock_engine_cls,
        patch("src.cli.simulation_cmd.asyncio") as mock_asyncio,
    ):
        mock_engine_cls.return_value.run.return_value = mock_report
        mock_asyncio.run.side_effect = lambda coro: mock_report

        cb = MagicMock()
        from src.cli.simulation_cmd import _run_simulation

        _run_simulation(
            stocks=["AAPL"],
            balance=10000.0,
            train_days=60,
            test_days=30,
            risk_levels=[],
            mc_sims=100,
            progress_cb=cb,
        )

        mock_engine_cls.assert_called_once()
        _, kwargs = mock_engine_cls.call_args
        assert kwargs.get("progress_cb") is cb


# ---------------------------------------------------------------------------
# Chart rendering progress bar tests
# ---------------------------------------------------------------------------


def test_charts_full_shows_rendering_progress():
    """--charts full should show a chart rendering progress indicator."""
    report = _mock_report_with_stocks(num_stocks=3)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "full"])
    assert result.exit_code == 0, result.output
    assert "Rendering charts" in result.output


def test_charts_summary_no_rendering_progress():
    """--charts summary should NOT show chart rendering progress."""
    report = _mock_report_with_stocks(num_stocks=3)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "summary"])
    assert result.exit_code == 0, result.output
    assert "Rendering charts" not in result.output


def test_charts_none_no_rendering_progress():
    """--charts none should NOT show chart rendering progress."""
    report = _mock_report_with_stocks(num_stocks=3)
    with patch("src.cli.simulation_cmd._run_simulation", return_value=report):
        result = runner.invoke(app, ["run", "--stocks", "STK0", "--charts", "none"])
    assert result.exit_code == 0, result.output
    assert "Rendering charts" not in result.output


# ---------------------------------------------------------------------------
# Multi-rebalance CLI tests
# ---------------------------------------------------------------------------


def test_single_rebalance_backward_compatible():
    """--rebalance none still works as a single value (backward compatible)."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--rebalance",
                "none",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_fn.assert_called_once()
        args = mock_fn.call_args
        assert args.kwargs.get("rebalance_freq") == "none"


def test_multiple_rebalance_values_accepted():
    """--rebalance none --rebalance monthly should parse as two values."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--rebalance",
                "none",
                "--rebalance",
                "monthly",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        # Should be called twice — once per rebalance mode
        assert mock_fn.call_count == 2
        rebal_freqs = [c.kwargs["rebalance_freq"] for c in mock_fn.call_args_list]
        assert "none" in rebal_freqs
        assert "monthly" in rebal_freqs


def _mock_report_with_recommendation(
    *,
    optimal_risk: str = "moderate",
    return_pct: float = 10.0,
    sharpe: float = 1.5,
    max_dd: float = 5.0,
) -> dict:
    """Build a mock report with a recommendation and risk level results."""
    report = _mock_report()
    report["risk_level_results"] = {
        optimal_risk: {
            "risk_level": optimal_risk,
            "stock_results": [],
            "monte_carlo_projections": [],
            "strategy_assessments": [],
            "total_return_pct": return_pct,
            "avg_sharpe": sharpe,
            "avg_max_drawdown": max_dd,
            "total_trades": 10,
            "portfolio_metrics": None,
            "portfolio_monte_carlo": None,
        },
    }
    report["recommendation"] = {
        "optimal_risk_level": optimal_risk,
        "reasoning": "test",
        "suggested_weights": {},
        "confidence": 0.8,
    }
    return report


def test_multiple_rebalance_prints_comparison_table():
    """When multiple rebalance modes are given, output should include a comparison table."""
    report_none = _mock_report_with_recommendation(return_pct=10.0, sharpe=1.5, max_dd=5.0)
    report_monthly = _mock_report_with_recommendation(return_pct=12.0, sharpe=1.8, max_dd=4.0)

    def side_effect(*args, **kwargs):
        if kwargs.get("rebalance_freq") == "none":
            return report_none
        return report_monthly

    with patch("src.cli.simulation_cmd._run_simulation", side_effect=side_effect):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--rebalance",
                "none",
                "--rebalance",
                "monthly",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Rebalance Comparison" in result.output


def test_single_rebalance_no_comparison_table():
    """With a single rebalance mode, no comparison table should appear."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--rebalance",
                "none",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Rebalance Comparison" not in result.output


# ---------------------------------------------------------------------------
# --no-cache flag tests
# ---------------------------------------------------------------------------


def test_run_help_shows_no_cache_flag(monkeypatch):
    """Help text should include the --no-cache flag."""
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--no-cache" in result.output


def test_no_cache_flag_passed_to_run_simulation():
    """--no-cache should forward use_cache=False to _run_simulation."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--no-cache",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_fn.assert_called_once()
        args = mock_fn.call_args
        assert args.kwargs.get("use_cache") is False


def test_cache_enabled_by_default():
    """When --no-cache is not specified, use_cache should default to True."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()) as mock_fn:
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        args = mock_fn.call_args
        assert args.kwargs.get("use_cache") is True


def test_no_cache_shows_status_message():
    """When --no-cache is set, the output should include 'Cache: DISABLED'."""
    with patch("src.cli.simulation_cmd._run_simulation", return_value=_mock_report()):
        result = runner.invoke(
            app,
            [
                "run",
                "--stocks",
                "AAPL",
                "--no-cache",
                "--charts",
                "none",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Cache: DISABLED" in result.output
