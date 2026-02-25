"""Analytics endpoints: attribution, Monte Carlo, drawdown, correlation."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dashboard.dependencies import require_user, state
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _build_attributed_fills():
    """Build attributed fills from portfolio fill history."""
    from src.analytics.models import AttributedFill

    if state.portfolio is None:
        return []

    fills = state.portfolio._fills
    attributed = []
    for fill in fills:
        # Try to determine strategy from DB records
        strategy = "unknown"
        attributed.append(AttributedFill(fill=fill, strategy=strategy))
    return attributed


@router.get("/attribution")
async def get_attribution(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Full strategy attribution report."""
    from src.analytics.attribution import StrategyAttribution

    fills = _build_attributed_fills()

    # Try to get strategy info from DB
    if state.db and fills:
        trades = await state.db.list_trades(limit=1000)
        # Build a map of (symbol, side, approximate_time) -> strategy
        from src.analytics.models import AttributedFill

        strategy_map: dict[str, str] = {}
        for t in trades:
            strategy_map[t.id] = t.strategy

        # Re-attribute fills using trade records
        attributed = []
        trade_list = list(trades)
        for fill in state.portfolio._fills:
            strategy = "unknown"
            # Match by symbol and side
            for t in trade_list:
                if t.symbol == fill.symbol and t.side == fill.side.value:
                    strategy = t.strategy
                    trade_list.remove(t)
                    break
            attributed.append(AttributedFill(fill=fill, strategy=strategy))
        fills = attributed

    analyzer = StrategyAttribution()
    report = analyzer.analyze(fills)

    return {
        "strategies": {
            name: {
                "name": stats.name,
                "total_trades": stats.total_trades,
                "win_rate": stats.win_rate,
                "total_pnl": stats.total_pnl,
                "avg_win": stats.avg_win,
                "avg_loss": stats.avg_loss,
                "profit_factor": stats.profit_factor,
                "max_consecutive_losses": stats.max_consecutive_losses,
            }
            for name, stats in report.strategies.items()
        },
        "total_pnl": report.total_pnl,
        "best_strategy": report.best_strategy,
        "worst_strategy": report.worst_strategy,
    }


@router.get("/monte-carlo")
async def get_monte_carlo(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Monte Carlo simulation results with percentile curves."""
    from src.analytics.attribution import StrategyAttribution
    from src.analytics.monte_carlo import MonteCarloSimulator

    fills = _build_attributed_fills()
    if not fills:
        return {
            "actual_final_value": 100000,
            "percentile": 50,
            "median_simulated": 100000,
            "p5_simulated": 100000,
            "p95_simulated": 100000,
            "worst_drawdown_p95": 0,
            "n_simulations": 0,
            "equity_curves": {},
        }

    analyzer = StrategyAttribution()
    analyzer.analyze(fills)

    # Gather all trades from all strategies
    all_trades = []
    for strategy_fills in _group_fills_by_strategy(fills).values():
        from src.analytics.attribution import _pair_fills

        all_trades.extend(_pair_fills(strategy_fills))

    initial_cash = 100000.0
    if state.portfolio:
        initial_cash = float(state.portfolio._cash) + sum(
            float(f.fill_price * f.quantity)
            if f.side.value == "buy"
            else -float(f.fill_price * f.quantity)
            for f in state.portfolio._fills
        )

    simulator = MonteCarloSimulator(n_simulations=500, seed=42)
    result = simulator.simulate(all_trades, initial_cash)

    return {
        "actual_final_value": result.actual_final_value,
        "percentile": result.percentile,
        "median_simulated": result.median_simulated,
        "p5_simulated": result.p5_simulated,
        "p95_simulated": result.p95_simulated,
        "worst_drawdown_p95": result.worst_drawdown_p95,
        "n_simulations": result.n_simulations,
    }


@router.get("/drawdown")
async def get_drawdown(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Drawdown curve data."""
    if state.portfolio is None:
        return {"points": []}

    fills = state.portfolio._fills
    if not fills:
        return {"points": []}

    # Build equity curve
    initial = 100000.0
    equity = [initial]
    running = initial
    for fill in fills:
        impact = float(fill.fill_price * fill.quantity)
        if fill.side.value == "sell":
            running += impact
        else:
            running -= impact
        equity.append(running)

    # Compute drawdown curve
    peak = equity[0]
    drawdown_points = []
    for i, value in enumerate(equity):
        if value > peak:
            peak = value
        dd = (peak - value) / peak * 100 if peak > 0 else 0
        drawdown_points.append(
            {
                "index": i,
                "value": value,
                "drawdown_pct": dd,
            }
        )

    return {"points": drawdown_points}


@router.get("/correlation")
async def get_correlation(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Correlation matrix between symbols."""
    if state.db is None:
        return {"symbols": [], "matrix": []}

    # Get OHLC data for correlation calculation
    bars = await state.db.query_ohlc_bars(limit=5000)
    if not bars:
        return {"symbols": [], "matrix": []}

    # Group closes by symbol
    from collections import defaultdict

    closes: dict[str, list[float]] = defaultdict(list)
    for bar in bars:
        closes[bar.symbol].append(float(bar.close))

    symbols = sorted(closes.keys())
    if len(symbols) < 2:
        return {"symbols": symbols, "matrix": [[1.0]]}

    # Simple correlation calculation
    import math

    def correlation(x: list[float], y: list[float]) -> float:
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        x, y = x[:n], y[:n]
        mx = sum(x) / n
        my = sum(y) / n
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x) / n)
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y) / n)
        if sx == 0 or sy == 0:
            return 0.0
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=False)) / n
        return cov / (sx * sy)

    matrix = []
    for s1 in symbols:
        row = []
        for s2 in symbols:
            if s1 == s2:
                row.append(1.0)
            else:
                row.append(round(correlation(closes[s1], closes[s2]), 4))
        matrix.append(row)

    return {"symbols": symbols, "matrix": matrix}


def _group_fills_by_strategy(fills):
    from collections import defaultdict

    grouped = defaultdict(list)
    for f in fills:
        grouped[f.strategy].append(f)
    return grouped
