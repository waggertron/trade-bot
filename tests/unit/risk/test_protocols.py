"""Tests for risk protocols — PositionSizer."""

from __future__ import annotations

from decimal import Decimal

from src.risk.protocols import PositionSizer


class _ConformingSizer:
    """A class that satisfies the PositionSizer protocol."""

    @property
    def name(self) -> str:
        return "conforming"

    async def compute_size(self, signal, portfolio, risk_context) -> Decimal:
        return Decimal("100")


class _NonConformingSizer:
    """A class that does NOT satisfy PositionSizer (missing compute_size)."""

    @property
    def name(self) -> str:
        return "nonconforming"


class TestPositionSizerProtocol:
    def test_runtime_checkable(self):
        """PositionSizer should be decorated with @runtime_checkable."""
        obj = _ConformingSizer()
        assert isinstance(obj, PositionSizer)

    def test_conforming_class_passes_isinstance(self):
        """A class with all required members passes isinstance check."""
        obj = _ConformingSizer()
        assert isinstance(obj, PositionSizer)

    def test_non_conforming_class_fails_isinstance(self):
        """A class missing required methods fails isinstance check."""
        obj = _NonConformingSizer()
        assert not isinstance(obj, PositionSizer)

    def test_protocol_has_name_attribute(self):
        """Protocol should define a name property."""
        assert "name" in dir(PositionSizer)

    def test_protocol_has_compute_size_method(self):
        """Protocol should define a compute_size method."""
        assert "compute_size" in dir(PositionSizer)
