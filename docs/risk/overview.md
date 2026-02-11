# Risk Management

## Overview

The risk subsystem sits between signal generation and order execution. Every proposed trade passes through the `RiskManager`, which can approve it, resize it, or veto it entirely. The system is regime-aware: position limits, stop-losses, and daily loss caps tighten automatically when market volatility increases.

Key components:

| Component                 | Location                        | Role |
|---------------------------|---------------------------------|------|
| `RiskManager`             | `src/agents/risk_manager.py`    | Central evaluator -- runs all checks in sequence |
| `PositionSizer` (protocol)| `src/risk/protocols.py`        | Computes trade size in base currency |
| `FixedPositionSizer`      | `src/risk/fixed_sizer.py`      | Fixed-percentage sizing |
| `KellyPositionSizer`      | `src/risk/kelly_sizer.py`      | Kelly Criterion sizing |
| `VolTargetedPositionSizer`| `src/risk/vol_sizer.py`        | Volatility-targeted sizing |
| `DrawdownCircuitBreaker`  | `src/risk/circuit_breaker.py`  | Halts trading on excessive drawdown |
| `RiskContext`             | `src/risk/models.py`            | Snapshot of regime, correlations, strategy stats |
| `VolatilityRegime`        | `src/risk/models.py`            | Enum: LOW, MEDIUM, HIGH |

## Volatility Regime and Regime-Aware Limits

The `VolatilityRegime` enum classifies the current market environment into three levels. When a `RiskContext` is provided to `evaluate_trade`, the `RiskManager` uses regime-specific limits instead of static settings:

| Parameter            | LOW    | MEDIUM | HIGH   |
|----------------------|--------|--------|--------|
| `max_position_pct`   | 3.0%   | 2.0%   | 1.0%   |
| `stop_loss_pct`      | 4.0%   | 5.0%   | 8.0%   |
| `max_open_positions` | 12     | 8      | 4      |
| `daily_loss_limit_pct`| 4.0%  | 3.0%   | 2.0%   |

In LOW volatility, the system allows larger positions and more concurrent trades. In HIGH volatility, it clamps down on exposure: smaller positions, fewer open trades, and a tighter daily loss cap. Stop-losses widen in HIGH regime to avoid getting stopped out by noise.

When no `RiskContext` is provided, the `RiskManager` falls back to the static values from `RiskSettings`.

## RiskManager Evaluation Pipeline

The `evaluate_trade` method runs these checks in order. The first failing check returns immediately:

1. **Circuit breaker** -- If the `DrawdownCircuitBreaker` is tripped, VETO.
2. **Daily loss limit** -- If cumulative daily loss has reached the effective limit, VETO.
3. **Max open positions** -- If the portfolio already holds the maximum number of distinct positions and the signal is for a new symbol, VETO.
4. **Correlation check** (only with `RiskContext`) -- For each existing position, compute absolute correlation with the proposed symbol:
   - If `abs(corr) > max_correlation` (default 0.7): VETO.
   - If `abs(corr) > max_correlation * 0.7`: RESIZE with a multiplier of `1 - corr/max_correlation`.
5. **Approve** -- All checks passed.

The method returns a `RiskDecision` with an `action` of APPROVE, RESIZE, or VETO, plus a human-readable `reason`.

### Portfolio health check

`check_portfolio_health` returns warning strings when the portfolio is approaching limits. Currently warns when daily loss reaches 80% of the configured daily loss limit.

## Position Sizing

### PositionSizer Protocol

Defined in `src/risk/protocols.py`:

```python
@runtime_checkable
class PositionSizer(Protocol):
    @property
    def name(self) -> str: ...

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        """Returns trade value in base currency (not quantity)."""
        ...
```

All sizers return a `Decimal` value in base currency, capped at available cash.

### Fixed Position Sizer

Allocates a fixed percentage of total portfolio value.

```python
sizer = FixedPositionSizer(position_pct=2.0)
# With a $100,000 portfolio: size = $2,000
```

- **Default**: 2% of total portfolio value.
- **Cap**: never exceeds available cash.

### Kelly Position Sizer

Uses the Kelly Criterion to size positions based on historical strategy performance.

```python
sizer = KellyPositionSizer(kelly_multiplier=0.5)
```

**Kelly formula**: `f = (p * b - q) / b`
- `p` = win probability (from `StrategyPerformance.win_rate`)
- `q` = 1 - p
- `b` = payoff ratio (`avg_win / avg_loss`)
- Result is multiplied by `kelly_multiplier` (default 0.5, i.e. half-Kelly)

**Safety rails**:
- Falls back to 1% of portfolio when strategy has fewer than 20 trades.
- Falls back to 1% when `avg_loss` is zero (cannot compute payoff ratio).
- Kelly fraction is floored at 0% and capped at 5%.
- Final size is capped at available cash.

### Vol-Targeted Position Sizer

Sizes positions to target a specific volatility contribution, scaling down in higher-volatility regimes.

```python
sizer = VolTargetedPositionSizer(target_vol_contribution=0.01)
```

**Base size** = `total_value * target_vol_contribution` (default 1%).

**Regime multipliers**:

| Regime | Multiplier |
|--------|------------|
| LOW    | 1.0x       |
| MEDIUM | 0.75x      |
| HIGH   | 0.5x       |

Example: $100,000 portfolio, 1% target, MEDIUM regime = $100,000 * 0.01 * 0.75 = $750.

## DrawdownCircuitBreaker

The circuit breaker halts all trading when the portfolio drops too far from its peak (high-water mark).

```python
breaker = DrawdownCircuitBreaker(
    max_drawdown_pct=10.0,  # trip at 10% drawdown
    cooldown_hours=24.0,     # stay halted for 24 hours
)
```

### Lifecycle

1. **update(portfolio_value, now)** -- Call on every tick to track the high-water mark.
2. **is_tripped(portfolio_value, now)** -- Returns `True` if drawdown from peak exceeds `max_drawdown_pct`, or if the breaker is still in cooldown.
3. After cooldown expires, the breaker resets: peak is set to the current value and trading resumes.
4. **reset()** -- Manual reset: clears peak and tripped state.

### Properties

- `peak_value` -- current high-water mark.
- `is_in_cooldown` -- whether the breaker is currently in cooldown period.

## Configuration

### RiskSettings

`RiskSettings` (in `src/core/config.py`) holds all static risk parameters:

| Field                      | Default | Range       |
|----------------------------|---------|-------------|
| `max_position_pct`         | 2.0     | (0, 100]    |
| `max_sector_exposure_pct`  | 20.0    | (0, 100]    |
| `daily_loss_limit_pct`     | 3.0     | (0, 100]    |
| `weekly_drawdown_limit_pct`| 5.0     | (0, 100]    |
| `max_open_positions`       | 10      | > 0         |
| `stop_loss_pct`            | 5.0     | (0, 100]    |
| `trailing_stop_enabled`    | False   | --          |
| `trailing_stop_pct`        | 3.0     | (0, 100]    |
| `max_correlation`          | 0.7     | (0, 1.0]    |

### Risk Level Presets

Create `RiskSettings` from a named preset:

```python
settings = RiskSettings.from_risk_level("conservative")
settings = RiskSettings.from_risk_level("moderate")
settings = RiskSettings.from_risk_level("aggressive")
settings = RiskSettings.from_risk_level("very_aggressive")
```

Presets can be customized with overrides:

```python
settings = RiskSettings.from_risk_level("moderate", max_open_positions=15)
```

## Usage Examples

### Initialize the RiskManager

```python
from src.core.config import RiskSettings
from src.agents.risk_manager import RiskManager
from src.risk.circuit_breaker import DrawdownCircuitBreaker
from src.risk.kelly_sizer import KellyPositionSizer

settings = RiskSettings.from_risk_level("moderate")
breaker = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
sizer = KellyPositionSizer(kelly_multiplier=0.5)

manager = RiskManager(
    settings=settings,
    position_sizer=sizer,
    circuit_breaker=breaker,
)
```

### Evaluate a trade

```python
decision = await manager.evaluate_trade(signal, portfolio, risk_context)

if decision.action == RiskAction.APPROVE:
    size = await sizer.compute_size(signal, portfolio, risk_context)
    # proceed to execution
elif decision.action == RiskAction.RESIZE:
    size = await sizer.compute_size(signal, portfolio, risk_context)
    size *= decision.size_multiplier
    # proceed with reduced size
else:  # VETO
    print(f"Trade vetoed: {decision.reason}")
```

### Update circuit breaker in the main loop

```python
manager.update_circuit_breaker(portfolio.total_value, datetime.now(timezone.utc))
```

## Adding Your Own

### Custom Position Sizer

Implement the `PositionSizer` protocol:

```python
from decimal import Decimal
from src.risk.protocols import PositionSizer

class ATRPositionSizer:
    @property
    def name(self) -> str:
        return "atr"

    async def compute_size(
        self, signal, portfolio, risk_context,
    ) -> Decimal:
        # your sizing logic using ATR
        risk_per_trade = portfolio.total_value * Decimal("0.01")
        atr = Decimal(str(risk_context.correlation_matrix.get("atr", 1.0)))
        size = risk_per_trade / atr if atr > 0 else Decimal("0")
        return min(size, portfolio.cash)
```

Then pass it to `RiskManager`:

```python
manager = RiskManager(settings=settings, position_sizer=ATRPositionSizer())
```

## Troubleshooting

**All trades vetoed with "Circuit breaker tripped"** -- The portfolio has dropped more than `max_drawdown_pct` from its peak. Wait for the cooldown period to expire, or call `breaker.reset()` to manually re-enable trading.

**Trades vetoed with "Daily loss limit exceeded"** -- The day's cumulative P&L has hit the limit. Call `manager.reset_daily_pnl()` at the start of each trading day.

**Trades vetoed with "Max open positions reached"** -- Close an existing position or increase `max_open_positions` in settings. Note: this only blocks new symbols; adding to an existing position is allowed.

**Correlation check causing unexpected RESIZE** -- The resize threshold is `max_correlation * 0.7`. With the default `max_correlation=0.7`, resize kicks in at correlation 0.49. Increase `max_correlation` if your universe is naturally highly correlated (e.g., crypto pairs).

**Kelly sizer returning very small sizes** -- If the strategy has fewer than 20 trades, Kelly falls back to 1%. Build up more trade history before relying on Kelly sizing.
