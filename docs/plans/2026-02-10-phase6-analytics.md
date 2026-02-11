# Phase 6: Performance Analytics & Backtesting — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive analytics suite with per-strategy P&L attribution, regime-tagged performance, Monte Carlo simulation, and analytics CLI commands — extending the existing backtester.

**Architecture:** AttributedFill tags each fill with strategy + regime → StrategyAttribution computes per-strategy stats → RegimeTagger breaks down by volatility regime → MonteCarloSimulator validates edge statistically → Reporter generates summaries → CLI exposes all analytics.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, random (for Monte Carlo)

---

### Task 1: Analytics Models (Pydantic)

**Files:**
- Create: `src/analytics/__init__.py`
- Create: `src/analytics/models.py`
- Test: `tests/unit/analytics/__init__.py`
- Test: `tests/unit/analytics/test_models.py`

**What to build:**

`AttributedFill` — frozen Pydantic model:
- `fill: Fill` — the actual fill
- `strategy: str` — strategy that generated the signal
- `regime: str = "unknown"` — volatility regime at execution time ("low", "medium", "high", "unknown")

`StrategyStats` — frozen Pydantic model:
- `name: str`
- `total_trades: int = 0`
- `win_rate: float = 0.0` (ge=0, le=1)
- `total_pnl: float = 0.0`
- `avg_win: float = 0.0`
- `avg_loss: float = 0.0`
- `profit_factor: float = 0.0` (ge=0)
- `max_consecutive_losses: int = 0`

`AttributionReport` — frozen Pydantic model:
- `strategies: dict[str, StrategyStats]`
- `total_pnl: float = 0.0`
- `best_strategy: str = ""`
- `worst_strategy: str = ""`

`EquityPoint` — frozen Pydantic model:
- `timestamp: int` — unix timestamp
- `value: float`

`MonteCarloResult` — frozen Pydantic model:
- `actual_final_value: float`
- `percentile: float` — where actual result sits in simulated distribution (>95 = likely skill)
- `median_simulated: float`
- `p5_simulated: float`
- `p95_simulated: float`
- `worst_drawdown_p95: float`
- `n_simulations: int`

`Trade` — frozen Pydantic model (a paired buy/sell):
- `symbol: str`
- `entry_price: float`
- `exit_price: float`
- `quantity: float`
- `pnl: float`
- `strategy: str = ""`
- `regime: str = "unknown"`

**Tests:** Creation, validation, field constraints, serialization roundtrips for all models.

---

### Task 2: StrategyAttribution — Per-Strategy P&L Breakdown

**Files:**
- Create: `src/analytics/attribution.py`
- Test: `tests/unit/analytics/test_attribution.py`

**What to build:**

`StrategyAttribution` class:
- `analyze(fills: list[AttributedFill]) -> AttributionReport`
  - Group fills by strategy name
  - For each strategy, pair buy/sell fills (FIFO) to create Trade objects
  - Compute StrategyStats: total_trades, win_rate, total_pnl, avg_win, avg_loss, profit_factor, max_consecutive_losses
  - Return AttributionReport with per-strategy stats, total_pnl, best/worst strategy

Internal helpers:
- `_pair_fills(fills: list[AttributedFill]) -> list[Trade]` — FIFO pairing of buy/sell fills by symbol
- `_max_losing_streak(trades: list[Trade]) -> int` — count max consecutive losses

**Tests:** Empty fills, single strategy with wins and losses, multiple strategies, profit_factor calculation, max consecutive losses tracking, best/worst strategy identification, unpaired fills (orphan buys) don't crash.

---

### Task 3: MonteCarloSimulator — Statistical Edge Validation

**Files:**
- Create: `src/analytics/monte_carlo.py`
- Test: `tests/unit/analytics/test_monte_carlo.py`

**What to build:**

`MonteCarloSimulator` class:
- `__init__(n_simulations: int = 1000, seed: int | None = None)` — seed for reproducibility in tests
- `simulate(trades: list[Trade], initial_cash: float) -> MonteCarloResult`
  - Build actual equity curve from trades in order
  - For each simulation: shuffle trades, build equity curve, record final value and max drawdown
  - Calculate percentile: what % of simulated outcomes the actual result beats
  - Return MonteCarloResult

Internal helpers:
- `_build_equity(trades: list[Trade], initial_cash: float) -> list[float]` — cumulative equity curve from trade P&Ls
- `_max_drawdown(equity: list[float]) -> float` — max peak-to-trough as fraction

**Tests:** Empty trades returns baseline, single trade, multiple trades with known outcome, percentile calculation (good strategy > 50th percentile), seed produces deterministic results, drawdown calculation.

---

### Task 4: RegimeTagger — Tag Fills with Volatility Regime

**Files:**
- Create: `src/analytics/regime_tagger.py`
- Test: `tests/unit/analytics/test_regime_tagger.py`

**What to build:**

`RegimeTagger` class:
- `__init__(regime_map: dict[str, str] | None = None)` — maps "symbol:timestamp_bucket" to regime, or can be set manually
- `tag_fills(fills: list[Fill], strategy_map: dict[str, str] | None = None) -> list[AttributedFill]`
  - For each fill, look up regime and strategy
  - strategy_map: maps `fill.order_id` or `fill.id` to strategy name (from signal tracking)
  - If no regime found, uses "unknown"
  - Returns list of AttributedFill
- `set_regime(symbol: str, timestamp: int, regime: str) -> None` — manually set regime for a symbol/time
- `performance_by_regime(fills: list[AttributedFill]) -> dict[str, StrategyStats]`
  - Group fills by regime
  - Pair fills and compute stats per regime
  - Return dict mapping regime name to StrategyStats

**Tests:** Tag fills with known regimes, unknown regime defaults, performance_by_regime groups correctly, empty fills, set_regime works.

---

### Task 5: Reporter — Summary Report Generation

**Files:**
- Create: `src/analytics/reporter.py`
- Test: `tests/unit/analytics/test_reporter.py`

**What to build:**

`AnalyticsReporter` class:
- `__init__(attribution: StrategyAttribution, simulator: MonteCarloSimulator)`
- `generate_report(fills: list[AttributedFill], initial_cash: float) -> str`
  - Run attribution analysis
  - Pair all fills into trades
  - Run Monte Carlo simulation
  - Format into a multi-section text report:
    - Overall summary (total P&L, return %, total trades)
    - Per-strategy breakdown table
    - Monte Carlo results (percentile, confidence intervals)
  - Return formatted string

**Tests:** Report contains expected sections, handles empty fills, includes strategy names, includes Monte Carlo percentile.

---

### Task 6: Analytics CLI Commands

**Files:**
- Create: `src/cli/analytics_cmd.py`
- Modify: `src/cli/main.py` — register analytics subcommand
- Test: `tests/unit/cli/test_analytics_cmd.py`

**What to build:**

CLI commands:
- `tradebot analytics status` — show analytics module summary (available analyzers, placeholder for future connection to live data)
- `tradebot analytics attribution --strategy <name>` — show per-strategy P&L (placeholder that demonstrates the attribution format with example data)

**Tests:** Status command works (exit code 0, output contains expected text), attribution command works.

---

### Task 7: Integration Test — Analytics Pipeline E2E

**Files:**
- Create: `tests/integration/test_analytics_e2e.py`

**What to build:**

End-to-end test:
1. Create a list of Fill objects simulating a trading session (mix of buys and sells across strategies)
2. Create AttributedFill objects with strategy and regime tags
3. Run StrategyAttribution to get per-strategy breakdown
4. Pair fills into trades
5. Run MonteCarloSimulator on the trades
6. Run AnalyticsReporter to generate full report
7. Verify: attribution shows correct strategies, Monte Carlo returns valid percentile, report is non-empty string

---

### Task 8: Full Regression Check

Run full test suite, fix any regressions.

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```
