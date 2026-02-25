"""Simulation endpoints: run, list, get results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user
from src.dashboard.schemas import SimulationRequest  # noqa: TC001
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# In-memory store for simulation runs
_simulation_runs: dict[str, dict] = {}


async def _run_async(req: SimulationRequest) -> dict:
    """Run simulation engine and return report dict."""
    from src.core.config import RiskLevel
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import AllocationWeights, RebalanceConfig, SimulationConfig

    config = SimulationConfig(
        stocks=req.stocks,
        initial_balance=req.initial_balance,
        train_days=req.train_days,
        test_days=req.test_days,
        risk_levels=[RiskLevel(r) for r in req.risk_levels],
        mc_simulations=req.mc_simulations,
        mc_seed=req.mc_seed,
        max_position_pct=req.max_position_pct,
        portfolio_mode=req.portfolio_mode,
        allocation=AllocationWeights(
            mode=req.allocation_mode,
            weights=req.custom_weights,
        ),
        rebalance=RebalanceConfig(
            frequency=req.rebalance_frequency,
            threshold_pct=req.rebalance_threshold_pct,
        ),
    )
    engine = SimulationEngine(config)
    report = await engine.run()
    return report.model_dump()


@router.post("/run")
async def run_simulation(req: SimulationRequest, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Run a new simulation."""
    report = await _run_async(req)
    _simulation_runs[report["id"]] = report
    return report


@router.get("/runs")
async def list_runs(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """List all simulation runs."""
    return list(_simulation_runs.values())


@router.get("/runs/{run_id}")
async def get_run(run_id: str, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Get a specific simulation run."""
    if run_id not in _simulation_runs:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return _simulation_runs[run_id]
