"""Tests for ML model protocols."""

from __future__ import annotations

from src.ml.protocols import ModelProvider


class _ConformingModel:
    """A class that satisfies the ModelProvider protocol."""

    @property
    def name(self) -> str:
        return "conforming"

    async def predict(self, features): ...

    async def train(self, dataset): ...

    async def evaluate(self, dataset): ...


class _NonConformingModel:
    """A class that does NOT satisfy the ModelProvider protocol (missing methods)."""

    @property
    def name(self) -> str:
        return "nonconforming"


class TestModelProviderProtocol:
    def test_runtime_checkable(self):
        """ModelProvider should be decorated with @runtime_checkable."""
        assert hasattr(ModelProvider, "__protocol_attrs__") or isinstance(ModelProvider, type)
        # The key test: isinstance checks should work
        obj = _ConformingModel()
        assert isinstance(obj, ModelProvider)

    def test_conforming_class_passes_isinstance(self):
        """A class with all required methods passes isinstance check."""
        obj = _ConformingModel()
        assert isinstance(obj, ModelProvider)

    def test_non_conforming_class_fails_isinstance(self):
        """A class missing required methods fails isinstance check."""
        obj = _NonConformingModel()
        assert not isinstance(obj, ModelProvider)
