# Phase 5: Enhanced Strategy Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor strategies to consume FeatureVector objects, add ML-driven and event-driven strategies, and replace majority voting with weighted consensus that accounts for strategy accuracy and market regime.

**Architecture:** New FeatureStrategy protocol takes FeatureVector instead of raw ticks → Thin adapters wrap existing strategies → New strategies (ML ensemble, event-driven, cross-asset) implement FeatureStrategy → WeightedConsensus replaces simple majority voting.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio

---

### Task 1: FeatureStrategy Protocol

**Files:**
- Modify: `src/core/protocols.py` — add `FeatureStrategy` protocol
- Test: `tests/unit/strategies/__init__.py`
- Test: `tests/unit/strategies/test_protocol.py`

**What to build:**

Add `FeatureStrategy` protocol to `src/core/protocols.py` (keep existing `StrategyAgent` unchanged for backward compatibility):

```python
@runtime_checkable
class FeatureStrategy(Protocol):
    name: str

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None: ...

    def required_features(self) -> list[str]: ...
```

Import `FeatureVector` from `src.ml.models`.

**Tests:** Protocol is runtime_checkable, conforming class passes isinstance, non-conforming fails.

---

### Task 2: Strategy Adapters (Momentum, Sentiment, Quantitative)

**Files:**
- Create: `src/agents/strategies/adapters.py`
- Test: `tests/unit/strategies/test_adapters.py`

**What to build:**

Three thin adapter classes that implement `FeatureStrategy` by extracting needed data from FeatureVector:

`MomentumAdapter`:
- `name = "momentum"`
- `required_features()` → `["sma_5", "sma_14"]`
- `evaluate(symbol, features)`:
  - Extract `sma_5` and `sma_14` from features.features
  - If either is None → return None
  - If `sma_5 > sma_14` → BUY with confidence = `min(abs(sma_5 - sma_14) / sma_14 * 10, 1.0)`
  - If `sma_5 < sma_14` → SELL with same confidence formula
  - If equal → return None

`SentimentAdapter`:
- `name = "sentiment"`
- `__init__(buy_threshold: float = 0.6, sell_threshold: float = -0.6)`
- `required_features()` → `["sentiment_avg_6h"]`
- `evaluate(symbol, features)`:
  - Extract `sentiment_avg_6h` from features.features
  - If None → return None
  - If `>= buy_threshold` → BUY with confidence = min(abs(sentiment), 1.0)
  - If `<= sell_threshold` → SELL with confidence = min(abs(sentiment), 1.0)
  - Otherwise → return None

`QuantitativeAdapter`:
- `name = "quantitative"`
- `__init__(z_threshold: float = 2.0)`
- `required_features()` → `["price_zscore"]`
- `evaluate(symbol, features)`:
  - Extract `price_zscore` from features.features
  - If None → return None
  - If `<= -z_threshold` → BUY (mean reversion, price below mean)
  - If `>= z_threshold` → SELL (price above mean)
  - Confidence = min(abs(zscore) / (z_threshold * 2), 1.0)
  - Otherwise → return None

**Tests:** Each adapter: protocol compliance, BUY signal, SELL signal, no signal (missing feature), no signal (neutral), confidence capping.

---

### Task 3: MLEnsembleStrategy

**Files:**
- Create: `src/agents/strategies/ml_ensemble.py`
- Test: `tests/unit/strategies/test_ml_ensemble.py`

**What to build:**

`MLEnsembleStrategy` implementing FeatureStrategy:
- `__init__(model: ModelProvider, min_confidence: float = 0.55)`
- `name = "ml_ensemble"`
- `required_features()` → `[]` (uses all available features)
- `evaluate(symbol, features)`:
  - Call `await self._model.predict(features)`
  - If prediction.direction == "hold" → return None
  - If prediction.confidence < min_confidence → return None
  - Return Signal with direction mapped via `SignalDirection[prediction.direction.upper()]`

**Tests:** Protocol compliance, generates BUY signal from model, generates SELL signal, filters hold, filters low confidence, uses model name in reasoning.

---

### Task 4: EventDrivenStrategy

**Files:**
- Create: `src/agents/strategies/event_driven.py`
- Test: `tests/unit/strategies/test_event_driven.py`

**What to build:**

`EventDrivenStrategy` implementing FeatureStrategy:
- `__init__(volume_spike_threshold: float = 3.0, sentiment_threshold: float = 0.5)`
- `name = "event_driven"`
- `required_features()` → `["article_volume_ratio", "sentiment_avg_6h", "sentiment_velocity"]`
- `evaluate(symbol, features)`:
  - Extract `article_volume_ratio` (default 1.0), `sentiment_avg_6h` (default 0.0), `sentiment_velocity` (default 0.0)
  - If `vol_ratio < volume_spike_threshold` → return None
  - If `abs(sentiment) < sentiment_threshold` → return None
  - direction = BUY if sentiment > 0 else SELL
  - confidence = `min((vol_ratio / volume_spike_threshold) * abs(sentiment), 1.0)`
  - Return Signal with reasoning including vol_ratio, sentiment, velocity

**Tests:** Protocol compliance, BUY on positive sentiment spike, SELL on negative sentiment spike, no signal below volume threshold, no signal below sentiment threshold, confidence calculation, default feature values.

---

### Task 5: CrossAssetStrategy

**Files:**
- Create: `src/agents/strategies/cross_asset.py`
- Test: `tests/unit/strategies/test_cross_asset.py`

**What to build:**

`CrossAssetStrategy` implementing FeatureStrategy:
- `__init__(leader_pairs: dict[str, str] | None = None, min_correlation: float = 0.6)`
- Default pairs: `{"ETH/USD": "BTC/USD", "SOL/USD": "BTC/USD"}`
- `name = "cross_asset"`
- `required_features()` → `["btc_momentum_lead", "btc_eth_corr_30d", "sma_5", "sma_14"]`
- `evaluate(symbol, features)`:
  - Look up leader for this symbol; if not in pairs → return None
  - Extract `btc_momentum_lead` (default 0.0), `btc_eth_corr_30d` (default 0.0)
  - If `abs(correlation) < min_correlation` → return None
  - Extract `sma_5` and `sma_14` (default 0)
  - If `leader_momentum > 0` and `sma_5 <= sma_14` → BUY (leader bullish, asset lagging)
  - Confidence = `min(abs(leader_momentum) * abs(correlation), 1.0)`
  - Otherwise → return None

**Tests:** Protocol compliance, BUY when leader bullish and asset lagging, no signal for untracked symbol, no signal when correlation too low, no signal when asset already trending, custom pairs, confidence calculation.

---

### Task 6: WeightedConsensus

**Files:**
- Create: `src/agents/strategies/consensus.py`
- Test: `tests/unit/strategies/test_consensus.py`

**What to build:**

`WeightedConsensus` class:
- `__init__(strategy_weights: dict[str, float] | None = None, regime_multipliers: dict[tuple[str, str], float] | None = None, min_consensus_score: float = 0.3)`
- Default weights: all strategies get 1.0
- `async resolve(signals: list[Signal], risk_context: RiskContext | None = None) -> Signal | None`:
  - Filter out HOLD signals
  - For each signal:
    - `config_weight = strategy_weights.get(signal.strategy_name, 1.0)`
    - `accuracy_weight`: if risk_context has strategy stats with recent_trades >= 10, use `recent_win_rate`; else 0.5
    - `regime_weight`: if risk_context, look up `(strategy_name, regime.value)` in regime_multipliers; else 1.0
    - `weighted_score = signal.confidence * config_weight * accuracy_weight * regime_weight`
    - Add to direction_scores[signal.direction]
    - Track best signal per direction (highest weighted score)
  - If no direction_scores → return None
  - Find direction with highest total score
  - If score < min_consensus_score → return None
  - Return best signal for that direction

**Tests:** Returns None for empty signals, returns None for all HOLD, returns best BUY when BUY wins, returns best SELL when SELL wins, applies strategy weights, applies accuracy weights from risk_context, applies regime multipliers, returns None below min_consensus_score, no risk_context uses defaults, single signal above threshold returns it.

---

### Task 7: Integration Test — Strategy Pipeline E2E

**Files:**
- Create: `tests/integration/test_strategy_e2e.py`

**What to build:**

End-to-end test:
1. Create FeatureVector with technical + sentiment features
2. Run all adapters (momentum, sentiment, quantitative) against features
3. Run MLEnsembleStrategy with MockModel
4. Run EventDrivenStrategy
5. Collect all signals
6. Run WeightedConsensus to get final signal
7. Verify the pipeline produces a valid consensus signal

---

### Task 8: Full Regression Check

Run full test suite, fix any regressions.

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```
