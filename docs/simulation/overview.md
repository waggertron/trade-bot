# Simulation System

The simulation system (`src/simulation/`) runs walk-forward backtests and Monte
Carlo projections across multiple risk levels and stocks. It supports two modes:
per-stock (default) and portfolio, with results exposed via CLI, API, and
frontend.

## Architecture

```
                    SimulationConfig
                         │
                         ▼
               ┌─────────────────┐
               │ SimulationEngine │
               │   run()          │
               └────────┬────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
    ┌─────▼─────┐  ┌───▼────┐  ┌────▼─────────┐
    │  yfinance  │  │Backtest│  │MonteCarloProj│
    │  download  │  │ Engine │  │   ector      │
    └───────────┘  └────────┘  └──────────────┘
                        │
          ┌─────────────┼─────────────┐
          │ (portfolio_mode=True)     │
          ▼                           ▼
  ┌───────────────┐      ┌───────────────────┐
  │Portfolio      │      │Correlated MC      │
  │Simulator      │      │(Cholesky GBM)     │
  └───────────────┘      └───────────────────┘
                        │
                        ▼
               SimulationReport
                  (JSON / CLI / Web)
```

## Components

### SimulationEngine (`src/simulation/engine.py`)

Orchestrates the full simulation pipeline:

1. For each risk level, iterates over all configured stocks
2. Fetches OHLC bars from yfinance
3. Splits into training and test windows
4. Runs walk-forward backtests on test data
5. Generates Monte Carlo price path projections from training data
6. Aggregates per-stock results into risk-level summaries
7. In portfolio mode, builds portfolio equity curve and correlated MC
8. Produces a recommendation for the optimal risk level

The scoring formula for recommendations is:
`score = sharpe * 0.5 + return * 0.3 - drawdown * 0.2`

### PortfolioSimulator (`src/simulation/portfolio.py`)

Manages portfolio-level simulation when `portfolio_mode=True`:

- **Capital allocation**: Splits initial balance across stocks by weight.
  Equal-weight mode assigns `1/n` per stock. Custom mode uses user-provided
  weights (must sum to 1.0).
- **Equity curve combination**: Normalizes each stock's equity curve by its
  starting value, scales by allocation weight, and sums at each timestep.
- **Portfolio metrics**: Computes Sharpe ratio (`mean/std * sqrt(252)`), Sortino
  ratio (downside deviation only), Calmar ratio (`annualized_return /
  max_drawdown`), and max drawdown from the portfolio equity curve.
- **Rebalancing**: Supports none, daily, weekly (every 5 trading days), and
  monthly (every 21 trading days) rebalancing frequencies.

### MonteCarloProjector (`src/simulation/projector.py`)

Generates forward price paths using geometric Brownian motion (GBM):

**Per-stock mode** (`generate_paths`):
- Computes log-return mean (mu) and standard deviation (sigma) from historical prices
- GBM formula: `S(t+1) = S(t) * exp((mu - sigma^2/2) + sigma * Z)`
- Returns ndarray of shape `(n_paths, days_forward)`

**Portfolio mode** (`generate_correlated_portfolio_paths`):
- Computes per-stock log returns and builds a correlation matrix via `np.corrcoef`
- Applies Cholesky decomposition to generate correlated random shocks
- Falls back to uncorrelated simulation if the correlation matrix is not
  positive definite
- Converts per-stock price paths to portfolio dollar values using allocation
  weights
- Returns portfolio paths and the correlation matrix

**Summary statistics** (`summarize`, `summarize_portfolio_paths`):
- Median, P5, P95 final values and return percentages
- Worst drawdown at the 95th percentile across all paths

## Data Models (`src/simulation/models.py`)

All models use `StrictBase` (Pydantic v2 with `extra="forbid"`, `frozen=True`).

| Model | Purpose |
|-------|---------|
| `SimulationConfig` | Input configuration (stocks, balance, days, risk levels, portfolio options) |
| `AllocationWeights` | Portfolio weight allocation (equal_weight or custom with validated sum) |
| `RebalanceConfig` | Rebalancing frequency and threshold |
| `StockSimResult` | Per-stock backtest result (return, Sharpe, drawdown, win rate, equity curve) |
| `MonteCarloProjection` | Per-stock MC forward projection (P5/median/P95, drawdown) |
| `PortfolioMetrics` | Portfolio-level performance (Sharpe, Sortino, Calmar, equity curve) |
| `PortfolioMonteCarloProjection` | Portfolio-level MC projection with correlation matrix |
| `RiskLevelResult` | Aggregated results for one risk level across all stocks |
| `Recommendation` | Optimal risk level with confidence and reasoning |
| `SimulationReport` | Complete report with all risk level results |

## Interfaces

### CLI (`src/cli/simulation_cmd.py`)

```bash
# Per-stock mode (default)
uv run tradebot simulation run --stocks AAPL MSFT GOOGL --balance 30000

# Portfolio mode
uv run tradebot simulation run --portfolio --stocks AAPL MSFT GOOGL \
  --weights '{"AAPL":0.5,"MSFT":0.3,"GOOGL":0.2}' --rebalance weekly

# Quick test
uv run tradebot simulation run --stocks AAPL --test-days 10 --mc-sims 50
```

Output includes Rich tables, ASCII charts (equity curves, bar charts,
heatmaps), portfolio metrics panels, MC projection tables, and a risk level
recommendation.

### API (`src/dashboard/routers/simulation.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/simulation/run` | POST | Run a new simulation |
| `/api/simulation/runs` | GET | List all simulation runs |
| `/api/simulation/runs/{id}` | GET | Get a specific run |

Request body for `/api/simulation/run`:

```json
{
  "stocks": ["AAPL", "MSFT", "GOOGL"],
  "initial_balance": 30000,
  "train_days": 60,
  "test_days": 30,
  "risk_levels": ["conservative", "moderate", "aggressive"],
  "mc_simulations": 1000,
  "portfolio_mode": true,
  "allocation_mode": "custom",
  "custom_weights": {"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2},
  "rebalance_frequency": "weekly",
  "rebalance_threshold_pct": 5.0
}
```

### Frontend (`web/src/app/simulation/page.tsx`)

The simulation page provides:

- **Configuration panel**: Stock selection, balance, training/test days, MC
  paths, risk level checkboxes, portfolio mode toggle, allocation controls,
  rebalance frequency dropdown
- **Risk level cards**: Clickable cards showing return, Sharpe, and drawdown per
  risk level, with the recommended level highlighted
- **Comparison charts**: Bar chart of return % vs max drawdown across risk
  levels
- **Per-stock results table**: Sortable table with return, Sharpe, drawdown, win
  rate, and P&L per stock
- **Monte Carlo projections table**: P5/Median/P95 final values per stock
- **Portfolio visualizations** (portfolio mode): Equity curve line chart,
  metrics card (Sharpe, Sortino, Calmar, max drawdown), MC projection cards
- **Previous runs table**: History of completed simulation runs

## Testing

```bash
# Unit tests
uv run pytest tests/simulation/test_portfolio_models.py -v    # 47 tests
uv run pytest tests/simulation/test_portfolio.py -v           # 22 tests
uv run pytest tests/simulation/test_portfolio_engine.py -v    # 5 tests
uv run pytest tests/simulation/test_correlated_mc.py -v       # 7 tests

# Integration tests
uv run pytest tests/simulation/test_portfolio_integration.py -v  # 5 tests

# All simulation tests
uv run pytest tests/simulation/ -v
```

## Key Design Decisions

**Backward compatibility.** `portfolio_mode=False` (default) preserves the
original per-stock simulation behavior. All new fields on existing models have
defaults.

**StrictBase models.** All simulation models use `extra="forbid"` and
`frozen=True`. Models are built complete in one pass and cannot be mutated after
construction.

**Cholesky fallback.** If the return correlation matrix is not positive definite
(rare with real data), the correlated Monte Carlo generator falls back to
uncorrelated simulation with a logged warning.

**Allocation validation.** Custom weights are validated via a Pydantic
`model_validator` to ensure they are non-empty, each value is in [0, 1], and
the sum is approximately 1.0 (tolerance of 1e-6).

**Sortino cap.** When all daily returns are positive (no downside deviation),
the Sortino ratio is capped at 99.99 rather than returning infinity, which
would break downstream computations and displays.
