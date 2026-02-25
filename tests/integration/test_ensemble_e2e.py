"""End-to-end integration test for the full ensemble pipeline."""

from __future__ import annotations

import pytest

from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
from src.ml.ensemble import EnsembleModel
from src.ml.mock_model import MockModel
from src.ml.models import Dataset, FeatureVector


def _make_fv() -> FeatureVector:
    return FeatureVector(symbol="BTC/USD", timestamp=1700000000, features={"rsi": 55.0})


def _make_dataset() -> Dataset:
    return Dataset(
        feature_names=["rsi"],
        vectors=[_make_fv(), _make_fv()],
        labels=[0, 1],
    )


class TestEnsemblePipelineE2E:
    """Full end-to-end test: MockModels -> EnsembleModel -> MLEnsembleStrategy."""

    @pytest.mark.asyncio
    async def test_full_ensemble_pipeline(self):
        # ------------------------------------------------------------------
        # Step 1: Create 3 MockModels with different biases
        # ------------------------------------------------------------------
        bullish = MockModel(default_direction="buy", default_confidence=0.9)
        bearish = MockModel(default_direction="sell", default_confidence=0.6)
        neutral = MockModel(default_direction="hold", default_confidence=0.5)

        # ------------------------------------------------------------------
        # Step 2: Create EnsembleModel with bullish-heavy weights
        # ------------------------------------------------------------------
        ensemble = EnsembleModel(
            models=[bullish, bearish, neutral],
            weights=[0.5, 0.3, 0.2],
        )

        # ------------------------------------------------------------------
        # Step 3: Create a FeatureVector
        # ------------------------------------------------------------------
        fv = _make_fv()

        # ------------------------------------------------------------------
        # Step 4: Run ensemble predict — verify bullish wins
        # ------------------------------------------------------------------
        prediction = await ensemble.predict(fv)

        # direction_scores: buy = 0.9*0.5 = 0.45, sell = 0.6*0.3 = 0.18, hold = 0.5*0.2 = 0.10
        # winner = "buy", total = 0.73, confidence = 0.45/0.73 ~ 0.6164
        assert prediction.direction == "buy"
        assert prediction.confidence == pytest.approx(0.45 / 0.73, abs=1e-4)
        assert prediction.model == "ensemble"

        # Every sub-model should have been called once
        assert bullish.predict_count == 1
        assert bearish.predict_count == 1
        assert neutral.predict_count == 1

        # ------------------------------------------------------------------
        # Step 5: Train the ensemble — verify all sub-models trained
        # ------------------------------------------------------------------
        dataset = _make_dataset()
        train_result = await ensemble.train(dataset)

        assert train_result.model == "ensemble"
        assert train_result.train_samples == 2
        # MockModel.train always returns 0.75 accuracy; average of three = 0.75
        assert train_result.train_accuracy == pytest.approx(0.75, abs=1e-4)

        assert bullish.train_count == 1
        assert bearish.train_count == 1
        assert neutral.train_count == 1

        # ------------------------------------------------------------------
        # Step 6: Evaluate the ensemble — verify averaged metrics
        # ------------------------------------------------------------------
        eval_result = await ensemble.evaluate(dataset)

        assert eval_result.model == "ensemble"
        assert eval_result.test_samples == 2
        # MockModel.evaluate always returns accuracy=0.7; average = 0.7
        assert eval_result.accuracy == pytest.approx(0.7, abs=1e-4)

        assert bullish.evaluate_count == 1
        assert bearish.evaluate_count == 1
        assert neutral.evaluate_count == 1

        # ------------------------------------------------------------------
        # Step 7: Wire EnsembleModel into MLEnsembleStrategy
        # ------------------------------------------------------------------
        strategy = MLEnsembleStrategy(model=ensemble, min_confidence=0.5)

        # ------------------------------------------------------------------
        # Step 8: Run strategy evaluate — verify signal matches ensemble
        # ------------------------------------------------------------------
        signal = await strategy.evaluate("BTC/USD", fv)

        assert signal is not None
        assert signal.direction.value == "buy"
        assert signal.confidence == pytest.approx(0.45 / 0.73, abs=1e-4)
        assert signal.strategy_name == "ml_ensemble"
        assert signal.symbol == "BTC/USD"
