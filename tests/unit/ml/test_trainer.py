"""Tests for WalkForwardTrainer."""

from __future__ import annotations

import pytest

from src.ml.feature_store import FeatureStore
from src.ml.mock_model import MockModel
from src.ml.models import WalkForwardResult
from src.ml.trainer import WalkForwardTrainer


def _populated_store(n_minutes: int = 100, interval: int = 60) -> FeatureStore:
    """Create a FeatureStore with n_minutes of data at the given interval."""
    store = FeatureStore()
    for i in range(n_minutes):
        store.save("AAPL", i * interval, {"close": 100.0 + i, "rsi_14": 50.0})
    return store


@pytest.mark.asyncio
async def test_single_window_produces_one_result() -> None:
    """With exact room for one train+test window, expect exactly one result."""
    store = _populated_store(n_minutes=100, interval=60)
    model = MockModel()
    # train_window=3600 (60 min), test_window=1200 (20 min)
    # total needed: 3600 + 1200 = 4800s = 80 min of data
    # data spans 0..5940 (100 points at 60s intervals)
    # step_size large enough to prevent a second window
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=6000,  # larger than remaining range
    )
    results = await trainer.run(["AAPL"], 0, 5940, ["close", "rsi_14"])
    assert len(results) == 1
    assert isinstance(results[0], WalkForwardResult)


@pytest.mark.asyncio
async def test_multiple_windows_with_step_size() -> None:
    """Multiple folds should be produced when step_size allows sliding."""
    store = _populated_store(n_minutes=100, interval=60)
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,   # 60 min
        test_window=1200,    # 20 min
        step_size=1200,      # 20 min step
    )
    # data spans 0..5940
    # cursor starts at 0 + 3600 = 3600
    # fold 1: train [0, 3600), test [3600, 4800) -> 4800 <= 5940 OK
    # fold 2: cursor 4800, train [1200, 4800), test [4800, 6000) -> 6000 > 5940 NO
    # So we expect exactly 1 fold with this data range
    # Let's use a larger dataset for multiple folds
    store2 = _populated_store(n_minutes=200, interval=60)
    trainer2 = WalkForwardTrainer(
        model=model,
        store=store2,
        train_window=3600,   # 60 min
        test_window=1200,    # 20 min
        step_size=1200,      # 20 min step
    )
    # data spans 0..11940
    # cursor starts at 3600
    # fold 1: train [0, 3600), test [3600, 4800) -> 4800 <= 11940 OK
    # fold 2: cursor 4800, train [1200, 4800), test [4800, 6000) -> 6000 <= 11940 OK
    # fold 3: cursor 6000, train [2400, 6000), test [6000, 7200) -> 7200 <= 11940 OK
    # fold 4: cursor 7200, train [3600, 7200), test [7200, 8400) -> OK
    # fold 5: cursor 8400, train [4800, 8400), test [8400, 9600) -> OK
    # fold 6: cursor 9600, train [6000, 9600), test [9600, 10800) -> OK
    # fold 7: cursor 10800, train [7200, 10800), test [10800, 12000) -> 12000 > 11940 NO
    # So 6 folds
    results = await trainer2.run(["AAPL"], 0, 11940, ["close", "rsi_14"])
    assert len(results) == 6


@pytest.mark.asyncio
async def test_result_contains_correct_train_test_periods() -> None:
    """Each result should have the correct train and test period boundaries."""
    store = _populated_store(n_minutes=200, interval=60)
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=1200,
    )
    results = await trainer.run(["AAPL"], 0, 11940, ["close", "rsi_14"])

    # First fold
    assert results[0].train_period == (0, 3600)
    assert results[0].test_period == (3600, 4800)

    # Second fold
    assert results[1].train_period == (1200, 4800)
    assert results[1].test_period == (4800, 6000)

    # Third fold
    assert results[2].train_period == (2400, 6000)
    assert results[2].test_period == (6000, 7200)


@pytest.mark.asyncio
async def test_empty_store_returns_empty_results() -> None:
    """When the feature store has no data, trainer should return an empty list."""
    store = FeatureStore()  # empty
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=1200,
    )
    results = await trainer.run(["AAPL"], 0, 6000, ["close", "rsi_14"])
    assert results == []
    assert model.train_count == 0
    assert model.evaluate_count == 0


@pytest.mark.asyncio
async def test_insufficient_time_range_returns_empty() -> None:
    """When end_ts - start_ts < train_window + test_window, return empty."""
    store = _populated_store(n_minutes=50, interval=60)
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=1200,
    )
    # Only 50 min of data = 3000s, but we need 3600 + 1200 = 4800s
    results = await trainer.run(["AAPL"], 0, 2940, ["close", "rsi_14"])
    assert results == []


@pytest.mark.asyncio
async def test_model_train_evaluate_called_correct_times() -> None:
    """MockModel.train and .evaluate should be called once per fold."""
    store = _populated_store(n_minutes=200, interval=60)
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=1200,
    )
    results = await trainer.run(["AAPL"], 0, 11940, ["close", "rsi_14"])
    assert model.train_count == len(results)
    assert model.evaluate_count == len(results)
    assert model.train_count == 6


@pytest.mark.asyncio
async def test_result_train_result_and_eval_result_populated() -> None:
    """Each WalkForwardResult should have valid train_result and eval_result."""
    store = _populated_store(n_minutes=200, interval=60)
    model = MockModel()
    trainer = WalkForwardTrainer(
        model=model,
        store=store,
        train_window=3600,
        test_window=1200,
        step_size=1200,
    )
    results = await trainer.run(["AAPL"], 0, 11940, ["close", "rsi_14"])

    for r in results:
        assert r.train_result.model == "mock_model"
        assert r.train_result.train_accuracy == 0.75
        assert r.train_result.train_samples > 0
        assert r.eval_result.model == "mock_model"
        assert r.eval_result.accuracy == 0.7
        assert r.eval_result.test_samples > 0
