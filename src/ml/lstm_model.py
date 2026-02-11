"""LSTM model implementing ModelProvider protocol."""

from __future__ import annotations

import logging
from collections import defaultdict

from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult

try:
    import torch
    import torch.nn as nn
    from src.ml.lstm_network import LSTMNetwork

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)

DIRECTION_MAP = {0: "buy", 1: "sell", 2: "hold"}


class LSTMModel:
    """LSTM-based model implementing ModelProvider."""

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 64,
        num_layers: int = 2,
        sequence_length: int = 20,
        learning_rate: float = 0.001,
        epochs: int = 10,
    ) -> None:
        self._input_size = input_size
        self._hidden_size = hidden_size
        self._num_layers = num_layers
        self._sequence_length = sequence_length
        self._learning_rate = learning_rate
        self._epochs = epochs
        self._network = None  # lazily created on train
        self._feature_names: list[str] = []
        self._buffers: dict[str, list[list[float]]] = defaultdict(list)

    @property
    def name(self) -> str:
        return "lstm"

    async def predict(self, features: FeatureVector) -> Prediction:
        """Predict direction from a feature vector.

        Buffers incoming vectors per-symbol until a full sequence is available.
        Returns a hold/0.5 fallback when torch is missing, no network is trained,
        or the buffer is not yet full.
        """
        if not HAS_TORCH or self._network is None:
            # Still buffer even without a network so tests can inspect buffer state
            if self._feature_names:
                arr = features.to_array(self._feature_names)
                self._buffers[features.symbol].append(arr)
                if len(self._buffers[features.symbol]) > self._sequence_length:
                    self._buffers[features.symbol] = self._buffers[features.symbol][
                        -self._sequence_length :
                    ]
            return Prediction(direction="hold", confidence=0.5, model=self.name)

        # Convert features to array and buffer
        arr = features.to_array(self._feature_names)
        self._buffers[features.symbol].append(arr)
        # Keep only last sequence_length entries
        if len(self._buffers[features.symbol]) > self._sequence_length:
            self._buffers[features.symbol] = self._buffers[features.symbol][
                -self._sequence_length :
            ]

        # Need full sequence
        if len(self._buffers[features.symbol]) < self._sequence_length:
            return Prediction(direction="hold", confidence=0.5, model=self.name)

        # Run inference
        with torch.no_grad():
            x = torch.tensor([self._buffers[features.symbol]], dtype=torch.float32)
            logits = self._network(x)
            probs = torch.softmax(logits, dim=1)
            confidence, class_idx = torch.max(probs, dim=1)
            direction = DIRECTION_MAP[class_idx.item()]

        return Prediction(
            direction=direction,
            confidence=round(confidence.item(), 4),
            model=self.name,
            features_used=self._feature_names,
        )

    async def train(self, dataset: Dataset) -> TrainResult:
        """Train the LSTM on the given dataset.

        Creates the network, builds sliding-window sequences from the dataset
        vectors, and runs gradient descent for the configured number of epochs.
        """
        if not HAS_TORCH:
            return TrainResult(model=self.name, train_samples=len(dataset.vectors))

        self._feature_names = list(dataset.feature_names)
        input_size = len(self._feature_names)

        # Create/reset network
        self._network = LSTMNetwork(
            input_size=input_size,
            hidden_size=self._hidden_size,
            num_layers=self._num_layers,
        )

        # Build sequences
        X, y = self._vectors_to_sequences(
            dataset.vectors, dataset.labels, self._feature_names, self._sequence_length
        )
        if len(X) == 0:
            return TrainResult(model=self.name, train_samples=len(dataset.vectors))

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.long)

        optimizer = torch.optim.Adam(self._network.parameters(), lr=self._learning_rate)
        criterion = nn.CrossEntropyLoss()

        self._network.train()
        for _ in range(self._epochs):
            optimizer.zero_grad()
            output = self._network(X_tensor)
            loss = criterion(output, y_tensor)
            loss.backward()
            optimizer.step()

        # Compute training accuracy
        self._network.eval()
        with torch.no_grad():
            preds = self._network(X_tensor).argmax(dim=1)
            accuracy = (preds == y_tensor).float().mean().item()

        return TrainResult(
            model=self.name,
            train_samples=len(dataset.vectors),
            train_accuracy=round(accuracy, 4),
        )

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        """Evaluate the trained network on a dataset.

        Returns default metrics if torch is unavailable or the network
        has not been trained yet.
        """
        if not HAS_TORCH or self._network is None:
            return EvalMetrics(model=self.name, test_samples=len(dataset.vectors))

        X, y = self._vectors_to_sequences(
            dataset.vectors, dataset.labels, self._feature_names, self._sequence_length
        )
        if len(X) == 0:
            return EvalMetrics(model=self.name, test_samples=len(dataset.vectors))

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.long)

        self._network.eval()
        with torch.no_grad():
            preds = self._network(X_tensor).argmax(dim=1)
            accuracy = (preds == y_tensor).float().mean().item()

        return EvalMetrics(
            model=self.name,
            accuracy=round(accuracy, 4),
            test_samples=len(dataset.vectors),
        )

    @staticmethod
    def _vectors_to_sequences(
        vectors: list[FeatureVector],
        labels: list[int],
        feature_names: list[str],
        seq_len: int,
    ) -> tuple[list[list[list[float]]], list[int]]:
        """Slide window over vectors to create sequences.

        Returns (X, y) where X has shape (n_sequences, seq_len, n_features)
        and y has shape (n_sequences,).
        """
        arrays = [v.to_array(feature_names) for v in vectors]
        X: list[list[list[float]]] = []
        y: list[int] = []
        for i in range(len(arrays) - seq_len + 1):
            X.append(arrays[i : i + seq_len])
            y.append(labels[i + seq_len - 1])
        return X, y
