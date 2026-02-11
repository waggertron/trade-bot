# Phase 3: Feature Store & ML Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build centralized feature computation, an in-memory feature store, a technical feature provider using TA-Lib, ML model infrastructure (protocols, dataset builder, walk-forward trainer), and CLI commands for inspection.

**Architecture:** FeatureProviders compute features from raw data → FeatureEngine orchestrates computation → FeatureStore persists feature vectors → Dataset builder creates train/test splits → WalkForwardTrainer evaluates models → ModelProvider serves predictions.

**Tech Stack:** Python 3.12+, Pydantic v2, TA-Lib, numpy, asyncio, Typer CLI

---

### Task 1: FeatureVector + ML Models (Pydantic)

**Files:**
- Create: `src/ml/__init__.py`
- Create: `src/ml/models.py`
- Test: `tests/unit/ml/__init__.py`
- Test: `tests/unit/ml/test_models.py`

**What to build:**

`FeatureVector` — frozen Pydantic model:
- `symbol: str`
- `timestamp: int` (unix timestamp)
- `features: dict[str, float]`
- `to_array(feature_names: list[str]) -> list[float]` — ordered array for model input, returns 0.0 for missing features
- `subset(feature_names: list[str]) -> FeatureVector` — returns new vector with only requested features

`Prediction` — frozen Pydantic model:
- `direction: str` — "buy", "sell", or "hold"
- `confidence: float` (ge=0, le=1)
- `model: str` — model name
- `features_used: list[str]` (default empty)

`TrainResult` — frozen Pydantic model:
- `model: str`
- `feature_importance: dict[str, float]` (default empty)
- `train_samples: int = 0`
- `train_accuracy: float = 0.0`

`EvalMetrics` — frozen Pydantic model:
- `model: str`
- `accuracy: float = 0.0`
- `precision: float = 0.0`
- `recall: float = 0.0`
- `sharpe: float = 0.0`
- `test_samples: int = 0`

`Dataset` — Pydantic model (NOT frozen, mutable for building):
- `feature_names: list[str]`
- `vectors: list[FeatureVector]`
- `labels: list[int]` — 0=buy, 1=sell, 2=hold
- `to_arrays() -> tuple[list[list[float]], list[int]]` — converts to X, y arrays

**Tests:** Creation, validation, to_array ordering, subset filtering, Dataset to_arrays, serialization roundtrips.

---

### Task 2: FeatureStore — In-Memory Persistence

**Files:**
- Create: `src/ml/feature_store.py`
- Test: `tests/unit/ml/test_feature_store.py`

**What to build:**

`FeatureStore` class:
- `save(symbol: str, timestamp: int, features: dict[str, float]) -> None`
- `load(symbol: str, timestamp: int) -> dict[str, float]` — returns empty dict if not found
- `load_range(symbol: str, start_ts: int, end_ts: int) -> list[FeatureVector]` — sorted by timestamp
- `feature_names(symbol: str | None = None) -> set[str]` — all known feature names
- `count(symbol: str | None = None) -> int`
- `symbols() -> list[str]`

Internal: `dict[tuple[str, int], dict[str, float]]` keyed by (symbol, timestamp).

**Tests:** save/load, load_range, feature_names, count, symbols, missing data returns empty.

---

### Task 3: TechnicalFeatureProvider — TA-Lib Integration

**Files:**
- Create: `src/providers/technical.py`
- Test: `tests/unit/providers/test_technical.py`

**What to build:**

`TechnicalFeatureProvider` implementing `FeatureProvider` protocol:
- `__init__(config: TechnicalFeatureConfig)`
- `name` property → `"technical"`
- `required_inputs` property → `["close", "high", "low", "volume"]`
- `async compute(inputs: dict[str, Any]) -> dict[str, float]` — takes arrays of price data, computes configured indicators

Indicators to implement (each guarded by config.indicators check):
- `sma_14`, `sma_50` — Simple Moving Average
- `rsi_14` — Relative Strength Index
- `macd_signal` — MACD histogram (signal crossover)
- `bbands_position` — Position within Bollinger Bands (0-1)
- `atr_14` — Average True Range

Each indicator uses TA-Lib functions. If data is insufficient for an indicator's lookback, skip it (don't error).

**Inputs format:**
```python
inputs = {
    "close": np.array([...]),   # closing prices
    "high": np.array([...]),    # high prices
    "low": np.array([...]),     # low prices
    "volume": np.array([...]),  # volume
}
```

**Tests:** Protocol compliance, computes features from valid data, handles insufficient data, respects config.indicators filter, each indicator returns correct keys.

---

### Task 4: FeatureEngine — Orchestration

**Files:**
- Create: `src/ml/feature_engine.py`
- Test: `tests/unit/ml/test_feature_engine.py`

**What to build:**

`FeatureEngine` class:
- `__init__(providers: list[FeatureProvider], store: FeatureStore)`
- `async compute_and_store(symbol: str, raw_data: dict, timestamp: int) -> FeatureVector` — runs all providers in parallel (asyncio.gather), merges results, persists to store, returns FeatureVector
- `async get_vector(symbol: str, timestamp: int) -> FeatureVector` — loads from store
- Handles provider failures gracefully (log warning, skip failed provider)

**Tests:** Computes from single provider, merges multiple providers, handles provider failure, persists to store, get_vector retrieves stored data.

---

### Task 5: ModelProvider Protocol + MockModel

**Files:**
- Create: `src/ml/protocols.py`
- Create: `src/ml/mock_model.py`
- Test: `tests/unit/ml/test_protocols.py`
- Test: `tests/unit/ml/test_mock_model.py`

**What to build:**

`ModelProvider` protocol (runtime_checkable):
- `name: str` property
- `async predict(features: FeatureVector) -> Prediction`
- `async train(dataset: Dataset) -> TrainResult`
- `async evaluate(dataset: Dataset) -> EvalMetrics`

`MockModel` class implementing ModelProvider:
- `__init__(default_direction: str = "hold", default_confidence: float = 0.5)`
- Returns configured defaults
- Tracks call counts for testing

**Tests:** Protocol compliance, mock returns configured values, call tracking.

---

### Task 6: DatasetBuilder — Build Train/Test Splits

**Files:**
- Create: `src/ml/dataset_builder.py`
- Test: `tests/unit/ml/test_dataset_builder.py`

**What to build:**

`DatasetBuilder` class:
- `__init__(store: FeatureStore, label_fn: Callable | None = None)`
- `build(symbols: list[str], start_ts: int, end_ts: int, feature_names: list[str]) -> Dataset` — loads feature vectors from store, applies label function to generate labels
- Default label function: next-period return direction (buy if >0, sell if <0, hold if ~0)

The `label_fn` takes a list of FeatureVectors and returns labels. Default implementation looks at the next timestamp's close price vs current.

**Tests:** Builds dataset from store, applies labels, handles empty data, respects time range.

---

### Task 7: WalkForwardTrainer

**Files:**
- Create: `src/ml/trainer.py`
- Test: `tests/unit/ml/test_trainer.py`

**What to build:**

`WalkForwardResult` — frozen Pydantic model:
- `train_period: tuple[int, int]` — (start_ts, end_ts)
- `test_period: tuple[int, int]`
- `train_result: TrainResult`
- `eval_result: EvalMetrics`

`WalkForwardTrainer` class:
- `__init__(model: ModelProvider, store: FeatureStore, train_window: int, test_window: int, step_size: int)` — windows in seconds
- `async run(symbols: list[str], start_ts: int, end_ts: int, feature_names: list[str]) -> list[WalkForwardResult]` — slides window, builds datasets, trains, evaluates

**Tests:** Single window, multiple windows, insufficient data returns empty, results contain correct periods.

---

### Task 8: ML CLI Commands

**Files:**
- Create: `src/cli/ml_cmd.py`
- Modify: `src/cli/main.py` — register ml subcommand
- Test: `tests/unit/cli/test_ml_cmd.py`

**What to build:**

CLI commands:
- `tradebot ml features --symbol <SYM>` — show stored features for a symbol
- `tradebot ml status` — show feature store summary (count, symbols, feature names)

**Tests:** Status shows summary, features command works with symbol flag.

---

### Task 9: Integration Test — Feature Pipeline E2E

**Files:**
- Create: `tests/integration/test_feature_e2e.py`

**What to build:**

End-to-end test: create mock price data → compute technical features → store in feature store → build dataset → train mock model → evaluate → verify complete pipeline works.

---

### Task 10: Full Regression Check

Run full test suite, fix any regressions.

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```
