"""Backtest endpoints: run, list, results."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.dashboard.schemas import BacktestRequest  # noqa: TC001
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# In-memory backtest run store
_backtest_runs: dict[str, dict] = {}


@router.post("/run")
async def run_backtest(req: BacktestRequest, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Start a backtest run."""
    run_id = str(uuid.uuid4())[:8]

    _backtest_runs[run_id] = {
        "id": run_id,
        "status": "running",
        "config": req.model_dump(),
        "started_at": datetime.now(UTC).isoformat(),
        "result": None,
    }

    # Try to run the actual backtester
    try:
        from src.data.backtester import run_backtest as _run_backtest

        if state.db:
            # Get OHLC data for the requested symbols
            from decimal import Decimal

            from src.core.models import AssetType, MarketTick

            all_ticks = []
            for symbol in req.symbols or ["BTC/USD"]:
                bars = await state.db.query_ohlc_bars(symbol=symbol, limit=10000)
                for bar in bars:
                    tick = MarketTick(
                        symbol=bar.symbol,
                        price=Decimal(bar.close),
                        volume=int(float(bar.volume)),
                        timestamp=datetime.fromtimestamp(bar.timestamp, tz=UTC),
                        asset_type=AssetType.CRYPTO if "/" in bar.symbol else AssetType.STOCK,
                    )
                    all_ticks.append(tick)

            if all_ticks:
                all_ticks.sort(key=lambda t: t.timestamp)
                result = await _run_backtest(all_ticks, initial_cash=req.initial_capital)
                _backtest_runs[run_id]["result"] = {
                    "total_ticks": result.total_ticks,
                    "total_trades": result.total_trades,
                    "winning_trades": result.winning_trades,
                    "losing_trades": result.losing_trades,
                    "win_rate": result.win_rate,
                    "return_pct": result.return_pct,
                    "max_drawdown": result.max_drawdown,
                    "sharpe_ratio": result.sharpe_ratio,
                    "equity_curve": [
                        {"index": i, "value": v} for i, v in enumerate(result.equity_curve)
                    ],
                }
                _backtest_runs[run_id]["status"] = "completed"
            else:
                _backtest_runs[run_id]["status"] = "completed"
                _backtest_runs[run_id]["result"] = {"error": "No market data available"}
        else:
            _backtest_runs[run_id]["status"] = "completed"
            _backtest_runs[run_id]["result"] = {"error": "Database not available"}
    except Exception as e:
        _backtest_runs[run_id]["status"] = "failed"
        _backtest_runs[run_id]["result"] = {"error": str(e)}

    return _backtest_runs[run_id]


@router.get("/runs")
async def list_runs(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """List previous backtest runs."""
    return list(_backtest_runs.values())


@router.get("/runs/{run_id}")
async def get_run(run_id: str, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Get specific backtest run results."""
    if run_id not in _backtest_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return _backtest_runs[run_id]
