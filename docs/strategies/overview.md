# Trading Strategies

## Overview

The strategy layer generates trading signals by evaluating market data, sentiment scores, and computed features. Every strategy implements one of two protocols:

- **`StrategyAgent`** -- the original protocol that receives raw `MarketTick` lists and optional `ResearchReport` data.
- **`FeatureStrategy`** -- the newer protocol that receives pre-computed `FeatureVector` objects from the feature store.

Both protocols produce `Signal` objects carrying a direction (BUY / SELL / HOLD), a confidence score (0.0 to 1.0), and human-readable reasoning. Signals from multiple strategies are combined by `WeightedConsensus` into a single actionable signal.

All strategy code lives under `src/agents/strategies/`.

## FeatureStrategy Protocol

Defined in `src/core/protocols.py`:

```python
@runtime_checkable
class FeatureStrategy(Protocol):
    name: str

    async def evaluate(
        self, symbol: str, features: FeatureVector,
    ) -> Signal | None: ...

    def required_features(self) -> list[str]: ...
```

- `name` -- unique identifier used by consensus weighting and analytics attribution.
- `evaluate` -- returns a `Signal` when conditions are met, or `None` when the strategy has no opinion.
- `required_features` -- declares which feature keys the strategy reads from `FeatureVector.features`, enabling the engine to validate data availability.

## Built-in Strategies

### StrategyAgent implementations (raw market data)

These strategies implement the `StrategyAgent` protocol and operate directly on `MarketTick` lists.

| Strategy               | File                   | Logic                                                                 |
|------------------------|------------------------|-----------------------------------------------------------------------|
| `MomentumStrategy`     | `momentum.py`          | Compares short-window MA (default 14) to long-window MA (default 50). BUY when short > long. |
| `SentimentStrategy`    | `sentiment.py`         | Averages `ResearchReport.sentiment_score` for the symbol. BUY above 0.6, SELL below -0.6.    |
| `QuantitativeStrategy` | `quantitative.py`      | Mean-reversion via z-score over a lookback window (default 20). BUY when z <= -2, SELL when z >= 2. |

### FeatureStrategy implementations (feature vectors)

These strategies implement the `FeatureStrategy` protocol and consume `FeatureVector` objects.

| Strategy              | File                | Required features                                             | Logic |
|-----------------------|---------------------|---------------------------------------------------------------|-------|
| `MomentumAdapter`     | `adapters.py`       | `sma_5`, `sma_14`                                            | BUY when SMA5 > SMA14; confidence proportional to spread. |
| `SentimentAdapter`    | `adapters.py`       | `sentiment_avg_6h`                                           | BUY above 0.6, SELL below -0.6 (configurable thresholds). |
| `QuantitativeAdapter` | `adapters.py`       | `price_zscore`                                               | Mean-reversion: BUY when z <= -2, SELL when z >= 2 (configurable). |
| `MLEnsembleStrategy`  | `ml_ensemble.py`    | (all available)                                              | Delegates to any `ModelProvider.predict()`. Filters out `hold` and low-confidence predictions (default min 0.55). |
| `EventDrivenStrategy` | `event_driven.py`   | `article_volume_ratio`, `sentiment_avg_6h`, `sentiment_velocity` | Triggers when article volume spikes >= 3x and sentiment exceeds threshold. |
| `CrossAssetStrategy`  | `cross_asset.py`    | `btc_momentum_lead`, `btc_eth_corr_30d`, `sma_5`, `sma_14`  | Leader-follower divergence: BUY follower when leader is bullish but follower lags. Default pairs: ETH->BTC, SOL->BTC. |

## WeightedConsensus

`WeightedConsensus` (`src/agents/strategies/consensus.py`) combines multiple strategy signals into a single actionable signal.

### Scoring formula

Each signal's weighted score is:

```
weighted_score = confidence * config_weight * accuracy_weight * regime_weight
```

Where:

- **`confidence`** -- the signal's own confidence (0.0 to 1.0), set by the strategy.
- **`config_weight`** -- a static per-strategy weight from `strategy_weights` dict (default 1.0 if not specified).
- **`accuracy_weight`** -- derived from the strategy's recent win rate via `RiskContext.strategy_stats`. If the strategy has >= 10 recent trades, this equals `recent_win_rate`; otherwise it defaults to 0.5.
- **`regime_weight`** -- a multiplier looked up in `regime_multipliers` keyed by `(strategy_name, regime_value)`. Default 1.0 if not specified.

### Resolution process

1. Filter out HOLD signals (only BUY and SELL are actionable).
2. Compute `weighted_score` for each remaining signal.
3. Sum scores by direction (BUY vs SELL).
4. The direction with the highest total score wins.
5. If the winning total is below `min_consensus_score` (default 0.3), return `None` (no trade).
6. Return the individual signal with the highest weighted score in the winning direction.

### Constructor parameters

| Parameter             | Type                                | Default | Description |
|-----------------------|-------------------------------------|---------|-------------|
| `strategy_weights`    | `dict[str, float] | None`          | `{}`    | Static weight per strategy name |
| `regime_multipliers`  | `dict[tuple[str, str], float] | None` | `{}`  | `(strategy, regime)` -> multiplier |
| `min_consensus_score` | `float`                            | `0.3`   | Minimum total score to emit a signal |

## Configuration

### Strategy weights example

```python
consensus = WeightedConsensus(
    strategy_weights={
        "momentum": 1.0,
        "sentiment": 0.8,
        "quantitative": 1.2,
        "ml_ensemble": 1.5,
        "event_driven": 0.7,
        "cross_asset": 0.9,
    },
    regime_multipliers={
        ("momentum", "low"): 1.2,       # momentum works well in calm markets
        ("momentum", "high"): 0.6,      # less reliable in volatile markets
        ("sentiment", "high"): 1.3,     # sentiment driven moves in vol
    },
    min_consensus_score=0.3,
)
```

### Adapter thresholds

```python
SentimentAdapter(buy_threshold=0.6, sell_threshold=-0.6)
QuantitativeAdapter(z_threshold=2.0)
MLEnsembleStrategy(model=my_model, min_confidence=0.55)
EventDrivenStrategy(volume_spike_threshold=3.0, sentiment_threshold=0.5)
CrossAssetStrategy(leader_pairs={"ETH/USD": "BTC/USD"}, min_correlation=0.6)
```

## Usage Examples

### Evaluate a single strategy

```python
from src.agents.strategies.adapters import MomentumAdapter
from src.ml.models import FeatureVector

strategy = MomentumAdapter()
features = FeatureVector(
    symbol="BTC/USD",
    timestamp=1700000000,
    features={"sma_5": 42500.0, "sma_14": 42000.0},
)
signal = await strategy.evaluate("BTC/USD", features)
# signal.direction == SignalDirection.BUY
# signal.confidence ~= 0.119
```

### Combine multiple signals with consensus

```python
from src.agents.strategies.consensus import WeightedConsensus

consensus = WeightedConsensus(
    strategy_weights={"momentum": 1.0, "sentiment": 0.8},
)

signals = [momentum_signal, sentiment_signal, quant_signal]
result = await consensus.resolve(signals, risk_context=ctx)

if result is not None:
    print(f"Trade: {result.direction} {result.symbol} "
          f"(confidence {result.confidence:.2f})")
```

## Adding Your Own

1. **Create a new file** under `src/agents/strategies/`, e.g. `volume_profile.py`.

2. **Implement the FeatureStrategy protocol**:

```python
from src.core.models import Signal, SignalDirection
from src.ml.models import FeatureVector
from datetime import datetime, timezone

class VolumeProfileStrategy:
    name: str = "volume_profile"

    async def evaluate(
        self, symbol: str, features: FeatureVector,
    ) -> Signal | None:
        vpoc = features.features.get("volume_poc")
        current = features.features.get("close")

        if vpoc is None or current is None:
            return None

        deviation = (current - vpoc) / vpoc
        if abs(deviation) < 0.02:
            return None

        direction = SignalDirection.SELL if deviation > 0 else SignalDirection.BUY
        confidence = min(abs(deviation) * 10, 1.0)

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            reasoning=f"Price deviated {deviation:.2%} from VPOC",
            timestamp=datetime.now(timezone.utc),
        )

    def required_features(self) -> list[str]:
        return ["volume_poc", "close"]
```

3. **Register it** by adding the instance to your strategy list and including its name in the `strategy_weights` dict passed to `WeightedConsensus`.

4. **Ensure features are available** -- verify that a `FeatureProvider` computes the features declared in `required_features()`.

## Troubleshooting

**Strategy always returns None** -- Check that the required features exist in the `FeatureVector` with non-None values. Log `features.features` to verify.

**Low consensus scores** -- Inspect per-signal weighted scores. If `accuracy_weight` is 0.5 (default for < 10 trades), the effective score is halved. After accumulating trade history, accuracy weighting will adjust automatically.

**Conflicting signals cancel out** -- This is by design. When BUY and SELL scores are close and both fall below `min_consensus_score`, no trade is emitted. Lower the threshold only with caution.

**ML ensemble always holds** -- The default `min_confidence` is 0.55. If the model's predictions are consistently below this, no signals will fire. Lower the threshold or retrain the model.
