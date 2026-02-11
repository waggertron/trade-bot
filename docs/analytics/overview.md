# Analytics Suite

## Overview

The analytics subsystem provides post-trade performance analysis. It answers questions like: Which strategy is making money? Is the realized performance statistically significant or just luck? How does performance differ across volatility regimes?

Key components:

| Component              | Location                           | Role |
|------------------------|------------------------------------|------|
| `StrategyAttribution`  | `src/analytics/attribution.py`     | Pairs fills into trades via FIFO, computes per-strategy stats |
| `MonteCarloSimulator`  | `src/analytics/monte_carlo.py`     | Shuffles trade order to test statistical significance |
| `RegimeTagger`         | `src/analytics/regime_tagger.py`   | Labels fills with volatility regime, computes per-regime stats |
| `AnalyticsReporter`    | `src/analytics/reporter.py`        | Combines attribution + Monte Carlo into a formatted text report |

Data models live in `src/analytics/models.py`.

## Data Models

| Model              | Purpose |
|--------------------|---------|
| `AttributedFill`   | A `Fill` tagged with `strategy` name and `regime` label |
| `Trade`            | A paired entry/exit with computed P&L, strategy, and regime |
| `StrategyStats`    | Aggregate stats: win rate, total P&L, avg win/loss, profit factor, max consecutive losses |
| `AttributionReport`| Contains `strategies: dict[str, StrategyStats]`, total P&L, best/worst strategy names |
| `EquityPoint`      | A `(timestamp, value)` point on an equity curve |
| `MonteCarloResult` | Simulation output: actual final value, percentile rank, median/p5/p95 simulated values, worst drawdown at 95th percentile |

All models are Pydantic `BaseModel` instances with `frozen=True` (immutable).

## StrategyAttribution

`StrategyAttribution` takes a list of `AttributedFill` objects (fills already tagged with strategy names and regime labels) and produces an `AttributionReport`.

### FIFO Fill Pairing

Fills are grouped by strategy, then by symbol. For each symbol, buy fills are matched with sell fills in FIFO order:

1. The first buy is paired with the first sell.
2. The quantity of each trade is `min(buy_quantity, sell_quantity)`.
3. P&L = `(exit_price - entry_price) * quantity`.
4. Unmatched fills (open positions) are not included in statistics.

### Per-Strategy Statistics

For each strategy, the following are computed from the paired trades:

- **total_trades** -- number of paired round-trip trades.
- **win_rate** -- fraction of trades with `pnl > 0`.
- **total_pnl** -- sum of all trade P&Ls.
- **avg_win** -- average P&L of winning trades.
- **avg_loss** -- average P&L of losing trades (negative value).
- **profit_factor** -- `sum(wins) / abs(sum(losses))`. Zero if there are no losses.
- **max_consecutive_losses** -- longest streak of trades with `pnl <= 0`.

### Attribution Report

The report identifies:
- **best_strategy** -- strategy name with highest total P&L (among strategies with at least one trade).
- **worst_strategy** -- strategy name with lowest total P&L.

## MonteCarloSimulator

The Monte Carlo simulator tests whether the actual trade sequence was statistically significant or could have been achieved by chance.

### How It Works

1. Build the actual equity curve from the ordered list of trades (cumulative P&L starting from `initial_cash`).
2. For each of `n_simulations` iterations (default 1000):
   - Randomly shuffle the trade order.
   - Build a simulated equity curve from the shuffled trades.
   - Record the final portfolio value and max drawdown.
3. Compute the **percentile** of the actual final value among simulated finals: `count(simulated < actual) / n_simulations * 100`.

### Result Fields

| Field                | Description |
|----------------------|-------------|
| `actual_final_value` | Portfolio value after all trades in original order |
| `percentile`         | Where actual result ranks among simulations (0-100) |
| `median_simulated`   | 50th percentile of simulated final values |
| `p5_simulated`       | 5th percentile (worst-case) |
| `p95_simulated`      | 95th percentile (best-case) |
| `worst_drawdown_p95` | 95th percentile of max drawdowns across simulations |
| `n_simulations`      | Number of simulations run |

**Interpreting the percentile**: If `percentile` is 85, the actual trade ordering produced a better result than 85% of random orderings. A high percentile suggests the strategy benefits from trade sequencing or market timing, not just raw edge.

### Reproducibility

Pass a `seed` to get deterministic results:

```python
simulator = MonteCarloSimulator(n_simulations=1000, seed=42)
```

## RegimeTagger

`RegimeTagger` associates fills with volatility regime labels and computes per-regime performance.

### Regime Storage

Regimes are stored as `(symbol, timestamp) -> regime_label` mappings:

```python
tagger = RegimeTagger()
tagger.set_regime("BTC/USD", 1700000000, "high")
tagger.get_regime("BTC/USD", 1700000000)  # "high"
tagger.get_regime("BTC/USD", 1700099999)  # "unknown" (not set)
```

### Fill Tagging

`tag_fills` converts raw `Fill` objects into `AttributedFill` objects by looking up the regime for each fill's `(symbol, timestamp)` and optionally mapping `fill.id` to a strategy name:

```python
strategy_map = {"fill-uuid-1": "momentum", "fill-uuid-2": "sentiment"}
attributed = tagger.tag_fills(raw_fills, strategy_map=strategy_map)
```

### Per-Regime Performance

`performance_by_regime` groups attributed fills by regime label, pairs them into trades (FIFO), and returns a `dict[str, StrategyStats]` keyed by regime name. This reveals whether the system performs better in low- or high-volatility environments.

## AnalyticsReporter

`AnalyticsReporter` combines `StrategyAttribution` and `MonteCarloSimulator` into a single formatted text report.

### Report Sections

1. **Header** -- Total P&L, return percentage, total trade count.
2. **Strategy Breakdown** -- Per-strategy stats (trades, win rate, P&L, profit factor, avg win/loss, max consecutive losses).
3. **Monte Carlo Analysis** -- Actual final value, percentile, median simulated, 95% confidence interval, worst drawdown at 95th percentile.

## Configuration

| Setting                         | Default | Where |
|---------------------------------|---------|-------|
| `MonteCarloSimulator.n_simulations` | 1000  | Constructor |
| `MonteCarloSimulator.seed`      | `None`  | Constructor (optional, for reproducibility) |

The attribution and regime tagger have no configuration -- they operate purely on the data passed to them.

## Usage Examples

### Full analytics pipeline

```python
from src.analytics.attribution import StrategyAttribution
from src.analytics.monte_carlo import MonteCarloSimulator
from src.analytics.regime_tagger import RegimeTagger
from src.analytics.reporter import AnalyticsReporter

# 1. Tag fills with regime and strategy
tagger = RegimeTagger()
tagger.set_regime("BTC/USD", 1700000000, "medium")
tagger.set_regime("BTC/USD", 1700086400, "medium")

strategy_map = {fill.id: "momentum" for fill in raw_fills}
attributed_fills = tagger.tag_fills(raw_fills, strategy_map)

# 2. Run attribution
attribution = StrategyAttribution()
report = attribution.analyze(attributed_fills)
print(f"Best strategy: {report.best_strategy}")
print(f"Total P&L: ${report.total_pnl:,.2f}")

# 3. Per-regime breakdown
regime_stats = tagger.performance_by_regime(attributed_fills)
for regime, stats in regime_stats.items():
    print(f"{regime}: {stats.total_trades} trades, {stats.win_rate:.1%} win rate")

# 4. Monte Carlo
simulator = MonteCarloSimulator(n_simulations=1000, seed=42)

# 5. Generate combined report
reporter = AnalyticsReporter(attribution, simulator)
text_report = reporter.generate_report(attributed_fills, initial_cash=100000.0)
print(text_report)
```

### Example report output

```
==================================================
ANALYTICS REPORT
==================================================
Total P&L:        $3,450.00
Return:           3.45%
Total Trades:     42
--------------------------------------------------
STRATEGY BREAKDOWN
--------------------------------------------------
momentum:
  Trades: 25  Win Rate: 56.0%
  P&L: $2,100.00  Profit Factor: 1.45
  Avg Win: $210.00  Avg Loss: $-105.00
  Max Consecutive Losses: 3
sentiment:
  Trades: 17  Win Rate: 47.1%
  P&L: $1,350.00  Profit Factor: 1.22
  Avg Win: $180.00  Avg Loss: $-90.00
  Max Consecutive Losses: 4
--------------------------------------------------
MONTE CARLO ANALYSIS (1000 simulations)
--------------------------------------------------
Actual Final:     $103,450.00
Percentile:       72.0%
Median Simulated: $103,200.00
95% CI:           $99,800.00 - $106,900.00
Worst Drawdown (95%): 4.2%
==================================================
```

## Adding Your Own

### Custom analysis module

To add a new analysis (e.g. rolling Sharpe ratio), create a class that accepts `list[Trade]` and implement your metric:

```python
class RollingSharpeAnalyzer:
    def __init__(self, window: int = 20) -> None:
        self._window = window

    def compute(self, trades: list[Trade]) -> list[float]:
        # sliding window Sharpe over trade P&Ls
        ...
```

Then integrate it into `AnalyticsReporter.generate_report` by adding a new section to the output.

## Troubleshooting

**AttributionReport shows 0 trades** -- Fills are present but not pairing. FIFO pairing requires both buy and sell fills for the same symbol. Check that your fill list includes matching buy/sell pairs.

**Monte Carlo percentile is near 50%** -- The actual trade ordering is not significantly different from random. This is normal for strategies without strong timing signals; the raw edge matters more than ordering.

**Regime stats all show "unknown"** -- `set_regime` was not called before `tag_fills`. Make sure you populate regime data for the relevant `(symbol, timestamp)` pairs.

**Profit factor is 0.0** -- There are no losing trades (division by zero is avoided) or no trades at all. This can happen early in a backtest before enough round trips have completed.
