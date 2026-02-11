"""Pydantic models for the ML pipeline."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FeatureVector(BaseModel):
    """An immutable vector of named features for a symbol at a point in time."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: int  # unix timestamp
    features: dict[str, float] = Field(default_factory=dict)

    def to_array(self, feature_names: list[str]) -> list[float]:
        """Convert to ordered array for model input. Returns 0.0 for missing features."""
        return [self.features.get(name, 0.0) for name in feature_names]

    def subset(self, feature_names: list[str]) -> FeatureVector:
        """Return new vector with only the requested features."""
        return FeatureVector(
            symbol=self.symbol,
            timestamp=self.timestamp,
            features={k: v for k, v in self.features.items() if k in feature_names},
        )


class Prediction(BaseModel):
    """An immutable prediction from a model."""

    model_config = ConfigDict(frozen=True)

    direction: str  # "buy", "sell", "hold"
    confidence: float = Field(ge=0, le=1)
    model: str
    features_used: list[str] = Field(default_factory=list)


class TrainResult(BaseModel):
    """Immutable result of a model training run."""

    model_config = ConfigDict(frozen=True)

    model: str
    feature_importance: dict[str, float] = Field(default_factory=dict)
    train_samples: int = 0
    train_accuracy: float = 0.0


class EvalMetrics(BaseModel):
    """Immutable evaluation metrics for a trained model."""

    model_config = ConfigDict(frozen=True)

    model: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    sharpe: float = 0.0
    test_samples: int = 0


class WalkForwardResult(BaseModel):
    """Immutable result of a single walk-forward validation fold."""

    model_config = ConfigDict(frozen=True)

    train_period: tuple[int, int]  # (start_ts, end_ts)
    test_period: tuple[int, int]  # (start_ts, end_ts)
    train_result: TrainResult
    eval_result: EvalMetrics


class Dataset(BaseModel):
    """Mutable container for building training/test datasets."""

    feature_names: list[str] = Field(default_factory=list)
    vectors: list[FeatureVector] = Field(default_factory=list)
    labels: list[int] = Field(default_factory=list)  # 0=buy, 1=sell, 2=hold

    def to_arrays(self) -> tuple[list[list[float]], list[int]]:
        """Convert to X, y arrays for model training."""
        X = [v.to_array(self.feature_names) for v in self.vectors]
        return X, list(self.labels)
