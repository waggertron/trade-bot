# Phase 8: LSTM Model & Ensemble Combiner — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a PyTorch LSTM model and a weighted ensemble combiner, both implementing the existing `ModelProvider` protocol, enabling multi-model prediction pipelines.

**Architecture:** `LSTMModel` wraps a PyTorch LSTM network and maintains a per-symbol sliding window buffer for sequential predictions. `EnsembleModel` composes N `ModelProvider` instances, calls them in parallel via `asyncio.gather()`, and combines predictions via weighted voting. Both implement `ModelProvider` so they're interchangeable with MockModel and future models.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, PyTorch (optional — tests use mocks)

---

### Task 1: EnsembleModel — Weighted Multi-Model Combiner

**Files:**
- Create: `src/ml/ensemble.py`
- Test: `tests/unit/ml/test_ensemble.py`

**What to build:**

`EnsembleModel` class implementing `ModelProvider`:
- `__init__(models: list, weights: list[float] | None = None)` — if weights is None, use uniform 1/n
- `name` property → `"ensemble"`
- `async predict(features: FeatureVector) -> Prediction`:
  - Call `asyncio.gather(*[m.predict(features) for m in models])` for parallel execution
  - Weighted voting: for each prediction, add `pred.confidence * weight` to `direction_scores[pred.direction]`
  - Winner = direction with highest total score
  - Final confidence = `min(winner_score / sum(all_scores), 1.0)` if sum > 0, else 0.5
  - Return Prediction with winning direction, normalized confidence, model="ensemble"
- `async train(dataset: Dataset) -> TrainResult`:
  - Train all models sequentially: `for m in models: await m.train(dataset)`
  - Return TrainResult with model="ensemble", train_samples from dataset, train_accuracy = average of sub-model accuracies
- `async evaluate(dataset: Dataset) -> EvalMetrics`:
  - Evaluate all models sequentially
  - Return EvalMetrics with model="ensemble", averaged metrics

**Tests:**
- Protocol compliance: `isinstance(EnsembleModel(...), ModelProvider)`
- Predict with single model returns that model's prediction
- Predict with two models, same direction, combines confidences
- Predict with two models, different directions, higher weighted score wins
- Predict with custom weights amplifies weighted model
- Train delegates to all sub-models
- Evaluate delegates to all sub-models
- Empty models list: predict returns hold/0.5, train/evaluate return defaults
- Handles model predict failure gracefully (skip failed model)

---

### Task 2: LSTMNetwork — PyTorch Module

**Files:**
- Create: `src/ml/lstm_network.py`
- Test: `tests/unit/ml/test_lstm_network.py`

**What to build:**

`LSTMNetwork` — a pure PyTorch `nn.Module` (only instantiated when torch is available):
- `__init__(input_size: int, hidden_size: int = 64, num_layers: int = 2, num_classes: int = 3, dropout: float = 0.2)`
- Architecture:
  - `nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)`
  - `nn.Linear(hidden_size, num_classes)`
- `forward(x: Tensor) -> Tensor`:
  - x shape: `(batch_size, sequence_length, input_size)`
  - Pass through LSTM, take last hidden state: `out[:, -1, :]`
  - Pass through linear layer
  - Return logits shape: `(batch_size, num_classes)`

**Guard all torch imports:**
```python
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
```

**Tests:** (all skipped if torch not installed via `pytest.importorskip("torch")`)
- Forward pass with random input produces correct output shape
- Output has 3 classes (buy=0, sell=1, hold=2)
- Handles variable sequence lengths
- Handles batch_size=1

---

### Task 3: LSTMModel — ModelProvider Implementation

**Files:**
- Create: `src/ml/lstm_model.py`
- Test: `tests/unit/ml/test_lstm_model.py`

**What to build:**

`LSTMModel` class implementing `ModelProvider`:
- `__init__(input_size: int, hidden_size: int = 64, num_layers: int = 2, sequence_length: int = 20, learning_rate: float = 0.001, epochs: int = 10)`
- `name` property → `"lstm"`
- Internal state:
  - `_network: LSTMNetwork | None` — lazily created on first train
  - `_feature_names: list[str]` — set during training
  - `_buffers: dict[str, list[list[float]]]` — per-symbol sliding window of feature arrays
- `async predict(features: FeatureVector) -> Prediction`:
  - Convert features to array using `_feature_names`
  - Append to `_buffers[features.symbol]`, keep last `sequence_length` entries
  - If buffer < `sequence_length` → return Prediction(direction="hold", confidence=0.5, model="lstm")
  - Run network forward pass on buffer (no grad)
  - Apply softmax to get class probabilities
  - Map argmax → direction ("buy", "sell", "hold")
  - confidence = max probability
  - Return Prediction
- `async train(dataset: Dataset) -> TrainResult`:
  - Store `_feature_names = dataset.feature_names`
  - Create/reset `_network` with `input_size=len(feature_names)`
  - Reshape dataset vectors into sequences of `sequence_length`
  - Train with Adam optimizer, CrossEntropyLoss, for `epochs` epochs
  - Return TrainResult with accuracy on training data
- `async evaluate(dataset: Dataset) -> EvalMetrics`:
  - Reshape dataset into sequences
  - Run forward pass, compute accuracy/precision/recall
  - Return EvalMetrics

Internal helper:
- `_vectors_to_sequences(vectors, labels, feature_names, seq_len)` — slide window over vectors to create (X, y) pairs where X has shape (n_sequences, seq_len, n_features) and y has shape (n_sequences,)

**Tests:** (tests that need torch use `pytest.importorskip("torch")`, others use a mock network)
- Protocol compliance: `isinstance(LSTMModel(...), ModelProvider)`
- Name property returns "lstm"
- Predict with insufficient buffer returns hold
- Predict after buffer filled returns valid prediction
- `_vectors_to_sequences` creates correct shapes
- Train creates network and sets feature_names
- Evaluate returns valid metrics
- Buffer is per-symbol (two symbols don't interfere)

---

### Task 4: Wire Ensemble into MLEnsembleStrategy

**Files:**
- Modify: `src/agents/strategies/ml_ensemble.py` — no changes needed (already accepts any model)
- Test: `tests/unit/strategies/test_ml_ensemble_with_ensemble.py`

**What to build:**

Integration test verifying `MLEnsembleStrategy` works with `EnsembleModel`:
- Create two MockModels with different predictions
- Create EnsembleModel wrapping them
- Create MLEnsembleStrategy wrapping the EnsembleModel
- Call evaluate and verify the consensus prediction flows through correctly

**Tests:**
- MLEnsembleStrategy with EnsembleModel produces signal
- MLEnsembleStrategy with EnsembleModel filters hold
- MLEnsembleStrategy with EnsembleModel filters low confidence

---

### Task 5: Update Optional Dependencies

**Files:**
- Modify: `pyproject.toml` — add torch to ml optional deps

**What to build:**

Add `torch` to the `[project.optional-dependencies]` ml group:
```toml
ml = [
    "xgboost>=2.0.0",
    "scikit-learn>=1.4.0",
    "torch>=2.0.0",
]
```

---

### Task 6: Integration Test — Ensemble Pipeline E2E

**Files:**
- Create: `tests/integration/test_ensemble_e2e.py`

**What to build:**

End-to-end test:
1. Create multiple MockModels with varied predictions (one bullish, one bearish, one neutral)
2. Create EnsembleModel with custom weights
3. Create FeatureVector with sample data
4. Run ensemble predict — verify weighted consensus direction
5. Create Dataset, train ensemble — verify all sub-models trained
6. Evaluate ensemble — verify averaged metrics
7. Wire EnsembleModel into MLEnsembleStrategy
8. Run strategy evaluate — verify signal matches ensemble output

---

### Task 7: Full Regression Check

Run full test suite, fix any regressions.

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```
