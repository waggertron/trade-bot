# Phase 4: Advanced Risk Management — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build dynamic risk management with volatility regime-aware limits, correlation checking, Kelly/vol-targeted position sizing, and a drawdown circuit breaker — replacing the current static daily-loss + max-positions checks.

**Architecture:** RiskContext provides rich state → PositionSizers compute trade sizes → DrawdownCircuitBreaker halts trading on excessive losses → Enhanced RiskManager orchestrates regime-aware limits, correlation checks, and circuit breaker into a single evaluate_trade flow.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, Decimal arithmetic

---

### Task 1: Risk Models (Pydantic)

**Files:**
- Create: `src/risk/__init__.py`
- Create: `src/risk/models.py`
- Modify: `src/core/models.py` — add `size_multiplier` field to `RiskDecision`
- Test: `tests/unit/risk/__init__.py`
- Test: `tests/unit/risk/test_models.py`

**What to build:**

`VolatilityRegime` — str Enum:
- `LOW = "low"`
- `MEDIUM = "medium"`
- `HIGH = "high"`

`StrategyPerformance` — frozen Pydantic model:
- `name: str`
- `win_rate: float` (ge=0, le=1)
- `avg_win: Decimal` (ge=0)
- `avg_loss: Decimal` (ge=0)
- `total_trades: int` (ge=0)
- `recent_trades: int = 0` (ge=0)
- `recent_win_rate: float = 0.0` (ge=0, le=1)

`RiskContext` — frozen Pydantic model:
- `regime: VolatilityRegime`
- `correlation_matrix: dict[str, float]` — keys are `"SYM1:SYM2"` format for simplicity
- `strategy_stats: dict[str, StrategyPerformance]`
- `drawdown_from_peak: float` (ge=0, le=1)
- `portfolio: PortfolioSnapshot`
- `daily_pnl: Decimal`
- Helper: `get_correlation(sym_a: str, sym_b: str) -> float` — looks up both orderings, returns 0.0 if missing

**RiskDecision update** (`src/core/models.py`):
- Add field: `size_multiplier: Decimal | None = None` — when RiskAction.RESIZE, the orchestrator multiplies computed quantity by this

**Tests:** Creation, validation, field constraints, get_correlation both orderings, RiskDecision with size_multiplier, serialization roundtrips.

---

### Task 2: PositionSizer Protocol + FixedPositionSizer

**Files:**
- Create: `src/risk/protocols.py`
- Create: `src/risk/fixed_sizer.py`
- Test: `tests/unit/risk/test_protocols.py`
- Test: `tests/unit/risk/test_fixed_sizer.py`

**What to build:**

`PositionSizer` protocol (runtime_checkable):
- `name: str` property
- `async compute_size(signal: Signal, portfolio: PortfolioSnapshot, risk_context: RiskContext) -> Decimal` — returns trade value in base currency (not quantity)

`FixedPositionSizer` class implementing PositionSizer:
- `__init__(position_pct: float = 2.0)`
- `name` property → `"fixed"`
- `compute_size`: returns `portfolio.total_value * position_pct / 100`, capped at `portfolio.cash`

**Tests:** Protocol compliance (isinstance check), computes correct size, caps at cash, handles zero portfolio value, handles zero cash.

---

### Task 3: KellyPositionSizer + VolTargetedPositionSizer

**Files:**
- Create: `src/risk/kelly_sizer.py`
- Create: `src/risk/vol_sizer.py`
- Test: `tests/unit/risk/test_kelly_sizer.py`
- Test: `tests/unit/risk/test_vol_sizer.py`

**What to build:**

`KellyPositionSizer` implementing PositionSizer:
- `__init__(kelly_multiplier: float = 0.5)`
- `name` property → `"kelly"`
- `compute_size`:
  - Look up strategy stats from `risk_context.strategy_stats[signal.strategy_name]`
  - If no stats or `total_trades < 20`, fallback to 1% of portfolio
  - If `avg_loss == 0`, fallback to 1% of portfolio
  - Kelly formula: `kelly = (win_prob * payoff_ratio - loss_prob) / payoff_ratio`
  - Apply multiplier (half-Kelly by default)
  - Clamp kelly between 0 and 0.05 (5% cap)
  - Return `portfolio.total_value * kelly`, capped at cash

`VolTargetedPositionSizer` implementing PositionSizer:
- `__init__(target_vol_contribution: float = 0.01)`
- `name` property → `"vol_targeted"`
- `compute_size`:
  - Uses ATR from features if available in `risk_context` (check for `atr_14` feature key in correlation_matrix — actually, we need a better way to pass this)
  - For now: if `risk_context.regime == HIGH`, use 50% of fixed size; if MEDIUM, 75%; if LOW, 100%
  - Base size is `portfolio.total_value * target_vol_contribution`
  - Apply regime multiplier, cap at cash

**Tests:** Protocol compliance, Kelly with good stats, Kelly insufficient data fallback, Kelly zero loss fallback, Kelly caps at 5%, VolTargeted regime scaling, VolTargeted caps at cash.

---

### Task 4: DrawdownCircuitBreaker

**Files:**
- Create: `src/risk/circuit_breaker.py`
- Test: `tests/unit/risk/test_circuit_breaker.py`

**What to build:**

`DrawdownCircuitBreaker` class:
- `__init__(max_drawdown_pct: float = 10.0, cooldown_hours: float = 24.0)`
- `update(portfolio_value: Decimal, now: datetime) -> None` — tracks peak value
- `is_tripped(portfolio_value: Decimal, now: datetime) -> bool`:
  - If currently tripped and cooldown not expired → True
  - If cooldown expired → reset (clear tripped_at, set peak to current value), return False
  - If peak is 0 → False
  - Calculate drawdown: `(peak - current) / peak`
  - If drawdown >= threshold → trip (record timestamp), return True
  - Otherwise → False
- `reset() -> None` — manually reset the breaker
- `peak_value: Decimal` property
- `is_in_cooldown: bool` property (check if tripped_at is set)
- Internal state: `_peak_value: Decimal`, `_tripped_at: datetime | None`

**Tests:** Not tripped initially, updates peak, trips on drawdown, remains tripped during cooldown, resets after cooldown expires, manual reset, handles zero peak, sequential updates track peak correctly.

---

### Task 5: Enhanced RiskManager

**Files:**
- Modify: `src/agents/risk_manager.py` — rewrite with new capabilities
- Modify: `tests/test_risk_manager.py` — update existing tests, add new ones

**What to build:**

Rewrite `RiskManager` to integrate all new components:

```python
class RiskManager:
    def __init__(
        self,
        settings: RiskSettings,
        position_sizer: PositionSizer | None = None,
        circuit_breaker: DrawdownCircuitBreaker | None = None,
    ):
```

Updated `evaluate_trade` signature:
```python
async def evaluate_trade(
    self, signal: Signal, portfolio: PortfolioSnapshot,
    risk_context: RiskContext | None = None,
) -> RiskDecision:
```

Evaluation order:
1. **Circuit breaker check** — if tripped, VETO immediately
2. **Daily loss limit** — existing check, but use regime-adjusted limit if risk_context provided
3. **Max positions** — existing check, but use regime-adjusted limit if risk_context provided
4. **Correlation check** — if risk_context provided, check signal symbol against existing positions
5. **APPROVE** (or RESIZE if correlation triggered reduction)

Regime-aware limits (used when risk_context is provided):
```python
REGIME_LIMITS = {
    VolatilityRegime.LOW: {
        "max_position_pct": 3.0,
        "stop_loss_pct": 4.0,
        "max_open_positions": 12,
        "daily_loss_limit_pct": 4.0,
    },
    VolatilityRegime.MEDIUM: {
        "max_position_pct": 2.0,
        "stop_loss_pct": 5.0,
        "max_open_positions": 8,
        "daily_loss_limit_pct": 3.0,
    },
    VolatilityRegime.HIGH: {
        "max_position_pct": 1.0,
        "stop_loss_pct": 8.0,
        "max_open_positions": 4,
        "daily_loss_limit_pct": 2.0,
    },
}
```

Correlation checking:
- For each existing position, look up correlation with signal symbol via `risk_context.get_correlation()`
- If `abs(correlation) > settings.max_correlation` → VETO
- If `abs(correlation) > settings.max_correlation * 0.7` → RESIZE with `size_multiplier = 1 - (correlation / max_correlation)`

**Backward compatibility:** When `risk_context` is None, behavior is identical to current implementation (static limits from RiskSettings). All existing tests must continue to pass unchanged.

Additional methods:
- `update_circuit_breaker(portfolio_value: Decimal, now: datetime) -> None` — delegates to circuit breaker if present

**Tests:** All 6 existing tests still pass, circuit breaker veto, regime-adjusted daily loss limit, regime-adjusted max positions, correlation veto, correlation resize with size_multiplier, no risk_context falls back to static limits, circuit breaker update delegation.

---

### Task 6: Risk CLI Commands

**Files:**
- Create: `src/cli/risk_cmd.py`
- Modify: `src/cli/main.py` — register risk subcommand
- Test: `tests/unit/cli/test_risk_cmd.py`

**What to build:**

CLI commands:
- `tradebot risk status` — show risk settings summary (current limits, position sizer name, circuit breaker state)
- `tradebot risk limits --regime <low|medium|high>` — show regime-specific limits from REGIME_LIMITS

**Tests:** Status shows settings, limits shows regime-specific values.

---

### Task 7: Integration Test — Risk Pipeline E2E

**Files:**
- Create: `tests/integration/test_risk_e2e.py`

**What to build:**

End-to-end test: create portfolio snapshot → create risk context with regime → configure position sizer → evaluate trade through enhanced risk manager → verify regime-aware limits applied → verify correlation check → verify circuit breaker triggers on drawdown → verify full pipeline works together.

---

### Task 8: Full Regression Check

Run full test suite, fix any regressions.

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```
