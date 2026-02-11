"""Provider registry for dependency injection and testing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from src.providers.mock import (
    MockDataStore,
    MockFeatureProvider,
    MockMarketDataProvider,
    MockNewsProvider,
    MockOnChainProvider,
    MockSentimentAnalyzer,
)
from src.providers.protocols import (
    DataStore,
    FeatureProvider,
    MarketDataProvider,
    NewsProvider,
    OnChainProvider,
    SentimentAnalyzer,
)

# Map of protocol types to their protocol class for isinstance checking
_PROTOCOL_MAP: dict[type, type] = {
    MarketDataProvider: MarketDataProvider,
    NewsProvider: NewsProvider,
    SentimentAnalyzer: SentimentAnalyzer,
    OnChainProvider: OnChainProvider,
    FeatureProvider: FeatureProvider,
    DataStore: DataStore,
}


class ProviderRegistry:
    """Registry that maps protocol types to concrete provider instances."""

    def __init__(self) -> None:
        self._providers: dict[type, Any] = {}

    def register(self, protocol_type: type, instance: Any) -> None:
        """Register a provider instance for a protocol type.

        Raises TypeError if the instance does not satisfy the protocol.
        """
        if protocol_type in _PROTOCOL_MAP:
            if not isinstance(instance, _PROTOCOL_MAP[protocol_type]):
                raise TypeError(
                    f"{type(instance).__name__} does not implement "
                    f"{protocol_type.__name__}"
                )
        self._providers[protocol_type] = instance

    def get(self, protocol_type: type) -> Any:
        """Get the registered provider for a protocol type.

        Raises KeyError if no provider is registered for the type.
        """
        if protocol_type not in self._providers:
            raise KeyError(
                f"No provider registered for {protocol_type.__name__}"
            )
        return self._providers[protocol_type]

    def has(self, protocol_type: type) -> bool:
        """Check whether a provider is registered for the given protocol type."""
        return protocol_type in self._providers

    def all(self) -> Iterator[tuple[str, Any]]:
        """Iterate over all registered providers as (protocol_name, instance) tuples."""
        for proto_type, instance in self._providers.items():
            yield proto_type.__name__, instance

    @classmethod
    def for_testing(cls, overrides: dict[type, Any] | None = None) -> ProviderRegistry:
        """Create a registry pre-populated with mock providers.

        Any entries in *overrides* replace the default mock for that protocol.
        """
        registry = cls()

        defaults: dict[type, Any] = {
            MarketDataProvider: MockMarketDataProvider(),
            NewsProvider: MockNewsProvider(),
            SentimentAnalyzer: MockSentimentAnalyzer(),
            OnChainProvider: MockOnChainProvider(),
            FeatureProvider: MockFeatureProvider(),
            DataStore: MockDataStore(),
        }

        if overrides:
            defaults.update(overrides)

        for proto_type, instance in defaults.items():
            registry.register(proto_type, instance)

        return registry
