# ML Pipeline

## Overview

The ML subsystem provides a pluggable machine-learning pipeline for training predictive models on trading features and integrating their predictions into the strategy layer. The pipeline is designed around walk-forward validation to prevent lookahead bias, and uses a protocol-based model interface so that any ML framework (scikit-learn, PyTorch, XGBoost, etc.) can be plugged in.

Key components:

| Component           | Location                       | Role |
|---------------------|--------------------------------|------|
| `ModelProvider`     | `src/ml/protocols.py`          | Protocol for ML models (predict, train, evaluate) |
| `FeatureVector`     | `src/ml/models.py`             | Immutable named-feature container for a symbol at a timestamp |
| `FeatureStore`      | `src/ml/feature_store.py`      | In-memory storage of feature vectors keyed by (symbol, timestamp) |
| `FeatureEngine`     | `src/ml/feature_engine.py`     | Orchestrates feature computation across providers |
| `DatasetBuilder`    | `src/ml/dataset_builder.py`    | Builds labeled datasets from FeatureStore data |
| `WalkForwardTrainer`| `src/ml/trainer.py`            | Walk-forward validation loop |
| `MockModel`         | `src/ml/mock_model.py`         | Deterministic mock for testing |

Data models live in `src/ml/models.py`.

## ModelProvider Protocol

Defined in `src/ml/protocols.py`:

```python
@runtime_checkable
class ModelProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def predict(self, features: FeatureVector) -> Prediction: ...
    async def train(self, dataset: Dataset) -> TrainResult: ...
    async def evaluate(self, dataset: Dataset) -> EvalMetrics: ...
```

Any class that implements these three async methods and a `name` property satisfies the protocol. The `MLEnsembleStrategy` wraps any `ModelProvider` into the `FeatureStrategy` interface so its predictions become trading signals.

## Data Models

### FeatureVector

An immutable container of named float features for a single symbol at a point in time.

```python
fv = FeatureVector(
    symbol="BTC/USD",
    timestamp=1700000000,
    features={"sma_5": 42500.0, "rsi_14": 65.3, "close": 42800.0},
)
```

Utility methods:
- `to_array(feature_names)` -- Converts to an ordered `list[float]` for model input. Returns 0.0 for missing features.
- `subset(feature_names)` -- Returns a new `FeatureVector` containing only the specified features.

### Prediction

Returned by `ModelProvider.predict()`:

| Field          | Type          | Description |
|----------------|---------------|-------------|
| `direction`    | `str`         | `"buy"`, `"sell"`, or `"hold"` |
| `confidence`   | `float`       | 0.0 to 1.0 |
| `model`        | `str`         | Name of the model that produced this prediction |
| `features_used`| `list[str]`   | Which features were used (informational) |

### TrainResult

Returned by `ModelProvider.train()`:

| Field                | Type                | Description |
|----------------------|---------------------|-------------|
| `model`              | `str`               | Model name |
| `feature_importance` | `dict[str, float]`  | Per-feature importance scores |
| `train_samples`      | `int`               | Number of training samples |
| `train_accuracy`     | `float`             | Training accuracy |

### EvalMetrics

Returned by `ModelProvider.evaluate()`:

| Field          | Type    | Description |
|----------------|---------|-------------|
| `model`        | `str`   | Model name |
| `accuracy`     | `float` | Classification accuracy |
| `precision`    | `float` | Precision score |
| `recall`       | `float` | Recall score |
| `sharpe`       | `float` | Sharpe ratio of predicted trades |
| `test_samples` | `int`   | Number of test samples |

### Dataset

Mutable container for building training/test sets:

```python
dataset = Dataset(
    feature_names=["sma_5", "rsi_14", "close"],
    vectors=[fv1, fv2, fv3],
    labels=[0, 1, 2],  # 0=buy, 1=sell, 2=hold
)

X, y = dataset.to_arrays()  # list[list[float]], list[int]
```

### WalkForwardResult

One fold of walk-forward validation:

| Field          | Type                   | Description |
|----------------|------------------------|-------------|
| `train_period` | `tuple[int, int]`      | (start_ts, end_ts) of training window |
| `test_period`  | `tuple[int, int]`      | (start_ts, end_ts) of test window |
| `train_result` | `TrainResult`          | Training output for this fold |
| `eval_result`  | `EvalMetrics`          | Evaluation output for this fold |

## FeatureEngine

`FeatureEngine` orchestrates feature computation by running all registered `FeatureProvider` instances in parallel via `asyncio.gather`.

```python
engine = FeatureEngine(providers=[technical_provider, sentiment_provider], store=store)

# Compute and persist
fv = await engine.compute_and_store("BTC/USD", raw_data, timestamp=1700000000)

# Retrieve later
fv = await engine.get_vector("BTC/USD", timestamp=1700000000)
```

If a provider raises an exception, it is logged as a warning and skipped -- the remaining providers' features are still saved. This makes the pipeline resilient to individual provider failures.

## FeatureStore

In-memory key-value store for feature vectors, keyed by `(symbol, timestamp)`.

```python
store = FeatureStore()

# Save features
store.save("BTC/USD", 1700000000, {"sma_5": 42500.0, "rsi_14": 65.3})

# Merge additional features into the same key
store.save("BTC/USD", 1700000000, {"close": 42800.0})

# Load (returns a copy)
features = store.load("BTC/USD", 1700000000)
# {"sma_5": 42500.0, "rsi_14": 65.3, "close": 42800.0}

# Range query
vectors = store.load_range("BTC/USD", start_ts=1700000000, end_ts=1700100000)

# Introspection
store.feature_names()              # all known feature names
store.feature_names("BTC/USD")     # feature names for one symbol
store.count()                      # total stored vectors
store.symbols()                    # list of symbols with data
```

Saving to an existing `(symbol, timestamp)` key merges new features into the existing dictionary, updating existing keys and adding new ones.

## DatasetBuilder

Builds `Dataset` objects from `FeatureStore` data by loading feature vectors for a time range and applying a labeling function.

```python
builder = DatasetBuilder(store=store)
dataset = builder.build(
    symbols=["BTC/USD", "ETH/USD"],
    start_ts=1700000000,
    end_ts=1700100000,
    feature_names=["sma_5", "rsi_14", "close"],
)
```

### Default Labeling Function

The built-in `default_label_fn` labels each vector based on the next period's close price:
- `0` (buy) if next close > current close * 1.001 (up > 0.1%)
- `1` (sell) if next close < current close * 0.999 (down > 0.1%)
- `2` (hold) otherwise, or for the last vector in the sequence

### Custom Labeling

Pass a custom function to use different labeling logic:

```python
def my_label_fn(vectors: list[FeatureVector]) -> list[int]:
    # your labeling logic
    ...

builder = DatasetBuilder(store=store, label_fn=my_label_fn)
```

The function receives a list of `FeatureVector` objects (sorted by timestamp for a single symbol) and must return a `list[int]` of the same length.

## Walk-Forward Training

`WalkForwardTrainer` implements walk-forward validation: train on window N, test on window N+1, slide forward, repeat. This prevents lookahead bias by never evaluating on data that was used for training.

```python
from src.ml.trainer import WalkForwardTrainer

trainer = WalkForwardTrainer(
    model=my_model,                # any ModelProvider
    store=feature_store,
    train_window=86400 * 30,       # 30 days in seconds
    test_window=86400 * 7,         # 7 days in seconds
    step_size=86400 * 7,           # slide by 7 days
)

results = await trainer.run(
    symbols=["BTC/USD"],
    start_ts=1690000000,
    end_ts=1700000000,
    feature_names=["sma_5", "rsi_14", "close"],
)

for fold in results:
    print(f"Train: {fold.train_period}, Test: {fold.test_period}")
    print(f"  Train accuracy: {fold.train_result.train_accuracy:.2%}")
    print(f"  Test accuracy:  {fold.eval_result.accuracy:.2%}")
```

**Empty fold handling**: If either the train or test dataset for a fold has no vectors, that fold is skipped.

## MockModel

`MockModel` is a deterministic model for testing that returns configured predictions without any actual ML computation.

```python
from src.ml.mock_model import MockModel

model = MockModel(default_direction="buy", default_confidence=0.8)

prediction = await model.predict(feature_vector)
# prediction.direction == "buy"
# prediction.confidence == 0.8

train_result = await model.train(dataset)
# train_result.train_accuracy == 0.75

eval_result = await model.evaluate(dataset)
# eval_result.accuracy == 0.7
```

Call counters are exposed for test assertions:

```python
assert model.predict_count == 1
assert model.train_count == 1
assert model.evaluate_count == 1
```

## Configuration

| Setting                                | Default       | Where |
|----------------------------------------|---------------|-------|
| `WalkForwardTrainer.train_window`      | (required)    | Constructor, in seconds |
| `WalkForwardTrainer.test_window`       | (required)    | Constructor, in seconds |
| `WalkForwardTrainer.step_size`         | (required)    | Constructor, in seconds |
| `MockModel.default_direction`          | `"hold"`      | Constructor |
| `MockModel.default_confidence`         | `0.5`         | Constructor |
| `default_label_fn` threshold           | 0.1%          | Hardcoded in `dataset_builder.py` |

## Usage Examples

### End-to-end: store features, build dataset, train, predict

```python
from src.ml.feature_store import FeatureStore
from src.ml.dataset_builder import DatasetBuilder
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector

# 1. Populate feature store
store = FeatureStore()
for ts in range(1700000000, 1700010000, 60):
    store.save("BTC/USD", ts, {
        "sma_5": 42500.0 + (ts % 1000),
        "rsi_14": 55.0 + (ts % 100) / 10,
        "close": 42800.0 + (ts % 500),
    })

# 2. Build dataset
builder = DatasetBuilder(store=store)
dataset = builder.build(
    symbols=["BTC/USD"],
    start_ts=1700000000,
    end_ts=1700010000,
    feature_names=["sma_5", "rsi_14", "close"],
)

# 3. Train
model = MockModel(default_direction="buy", default_confidence=0.8)
result = await model.train(dataset)
print(f"Trained on {result.train_samples} samples")

# 4. Predict
fv = FeatureVector(
    symbol="BTC/USD",
    timestamp=1700010060,
    features={"sma_5": 42600.0, "rsi_14": 58.0, "close": 42900.0},
)
prediction = await model.predict(fv)
print(f"Prediction: {prediction.direction} ({prediction.confidence:.2f})")
```

## Adding Your Own

### Custom ModelProvider

```python
from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult

class XGBoostModel:
    def __init__(self) -> None:
        self._model = None  # xgboost.XGBClassifier

    @property
    def name(self) -> str:
        return "xgboost"

    async def predict(self, features: FeatureVector) -> Prediction:
        X = [features.to_array(self._feature_names)]
        proba = self._model.predict_proba(X)[0]
        direction_idx = proba.argmax()
        directions = ["buy", "sell", "hold"]
        return Prediction(
            direction=directions[direction_idx],
            confidence=float(proba[direction_idx]),
            model=self.name,
            features_used=self._feature_names,
        )

    async def train(self, dataset: Dataset) -> TrainResult:
        X, y = dataset.to_arrays()
        self._feature_names = dataset.feature_names
        self._model = xgboost.XGBClassifier()
        self._model.fit(X, y)
        importance = dict(zip(
            dataset.feature_names,
            self._model.feature_importances_.tolist(),
        ))
        return TrainResult(
            model=self.name,
            feature_importance=importance,
            train_samples=len(X),
            train_accuracy=self._model.score(X, y),
        )

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        X, y = dataset.to_arrays()
        accuracy = self._model.score(X, y)
        return EvalMetrics(
            model=self.name,
            accuracy=accuracy,
            test_samples=len(X),
        )
```

Then use it with the `MLEnsembleStrategy`:

```python
from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

strategy = MLEnsembleStrategy(model=XGBoostModel(), min_confidence=0.6)
```

### Custom FeatureProvider

```python
class RSIFeatureProvider:
    @property
    def name(self) -> str:
        return "rsi"

    @property
    def required_inputs(self) -> list[str]:
        return ["close_prices"]

    async def compute(self, inputs: dict[str, Any]) -> dict[str, float]:
        prices = inputs["close_prices"]
        rsi_14 = calculate_rsi(prices, 14)
        rsi_7 = calculate_rsi(prices, 7)
        return {"rsi_14": rsi_14, "rsi_7": rsi_7}
```

Register it with `FeatureEngine`:

```python
engine = FeatureEngine(providers=[rsi_provider, ...], store=store)
```

## Troubleshooting

**Walk-forward returns empty results** -- The time range is too short for even one train+test window. Ensure `end_ts - start_ts >= train_window + test_window`.

**DatasetBuilder produces empty datasets** -- No feature vectors exist in the store for the given symbols and time range. Verify that `FeatureStore.save` has been called with matching symbol names and timestamps within the range.

**FeatureVector.to_array returns all zeros** -- The feature names passed to `to_array` do not match the keys in `features`. Check for typos or mismatched naming conventions.

**FeatureEngine silently drops features** -- A provider raised an exception during `compute`. Check logs for warnings like "Feature provider X failed: ...". The remaining providers' features are still persisted.

**Labels are mostly 2 (hold)** -- The default label function uses a 0.1% threshold. If price movements between consecutive timestamps are smaller than this, most labels will be hold. Use a custom `label_fn` with a tighter threshold, or use wider time intervals between feature vectors.
