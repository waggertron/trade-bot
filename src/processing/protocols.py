"""Protocols for the processing subsystem.

Processor[T] — the single interface that any processing step must satisfy.
Any class with a ``name`` property and an async ``process(item)`` method
automatically satisfies this protocol (structural subtyping).
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T_contra = TypeVar("T_contra", contravariant=True)


@runtime_checkable
class Processor(Protocol[T_contra]):
    """A unit of work that consumes a single item of type T."""

    @property
    def name(self) -> str:
        """Human-readable identifier for logging and metrics."""
        ...

    async def process(self, item: T_contra) -> None:
        """Process one item.  Raise on unrecoverable errors."""
        ...
