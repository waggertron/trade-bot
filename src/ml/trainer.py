"""Walk-forward model training and evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.ml.dataset_builder import DatasetBuilder
from src.ml.models import WalkForwardResult

if TYPE_CHECKING:
    from src.ml.feature_store import FeatureStore


class WalkForwardTrainer:
    """Train and evaluate models using walk-forward validation.

    Walk-forward validation trains on window N, tests on N+1, then slides
    forward by step_size, repeating until the end of the data range.
    This prevents lookahead bias by never testing on data that was used
    for training.
    """

    def __init__(
        self,
        model,  # ModelProvider (e.g. MockModel)
        store: FeatureStore,
        train_window: int,  # seconds
        test_window: int,  # seconds
        step_size: int,  # seconds
    ) -> None:
        self._model = model
        self._store = store
        self._train_window = train_window
        self._test_window = test_window
        self._step_size = step_size
        self._builder = DatasetBuilder(store=store)

    async def run(
        self,
        symbols: list[str],
        start_ts: int,
        end_ts: int,
        feature_names: list[str],
    ) -> list[WalkForwardResult]:
        """Execute walk-forward validation from start_ts to end_ts.

        Slides a training window followed by a test window across the
        time range, training and evaluating the model at each step.
        Folds with empty train or test data are skipped.
        """
        results: list[WalkForwardResult] = []
        cursor = start_ts + self._train_window

        while cursor + self._test_window <= end_ts:
            train_start = cursor - self._train_window
            train_end = cursor
            test_start = cursor
            test_end = cursor + self._test_window

            train_data = self._builder.build(symbols, train_start, train_end, feature_names)
            test_data = self._builder.build(symbols, test_start, test_end, feature_names)

            # Skip if either dataset is empty
            if not train_data.vectors or not test_data.vectors:
                cursor += self._step_size
                continue

            train_result = await self._model.train(train_data)
            eval_result = await self._model.evaluate(test_data)

            results.append(
                WalkForwardResult(
                    train_period=(train_start, train_end),
                    test_period=(test_start, test_end),
                    train_result=train_result,
                    eval_result=eval_result,
                )
            )

            cursor += self._step_size

        return results
