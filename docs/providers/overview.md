# Data Providers

## Overview

The provider subsystem defines abstract contracts (protocols) for all external data sources and implements a dependency-injection registry that maps those contracts to concrete implementations. This makes it straightforward to swap real API clients for mocks during testing, or to replace one market-data vendor with another without touching strategy or risk code.

All provider protocols live in `src/providers/protocols.py`. Concrete implementations, mock stubs, and Pydantic config models sit alongside them in the `src/providers/` package.

## Protocol Pattern

Every provider interface is a Python `Protocol` decorated with `@runtime_checkable`. This gives two benefits:

1. **Static type checking** -- any class whose methods match the protocol signature is treated as compatible by mypy / pyright without explicit inheritance.
2. **Runtime isinstance() checks** -- the `ProviderRegistry` uses `isinstance(instance, protocol_type)` at registration time to catch wiring mistakes early.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MarketDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]: ...
    async def get_ohlc(self, symbol: str, interval: str, limit: int = 100) -> list[dict[str, Any]]: ...
    async def health_check(self) -> bool: ...
```

## Available Protocols

| Protocol             | Key methods                                           | Purpose                          |
|----------------------|-------------------------------------------------------|----------------------------------|
| `MarketDataProvider` | `get_ticks`, `get_ohlc`, `health_check`               | Price feeds and OHLC bars        |
| `NewsProvider`       | `fetch_articles`, `health_check`, `rate_limit`        | News article ingestion           |
| `SentimentAnalyzer`  | `score`, `score_batch`                                | Text sentiment scoring           |
| `OnChainProvider`    | `get_metrics`, `health_check`                         | Blockchain metrics (e.g. flows)  |
| `FeatureProvider`    | `compute`, `required_inputs`                          | Derived feature computation      |
| `DataStore`          | `save_trade`, `list_trades`, `save_signal`, `list_signals` | Persistent trade/signal storage |
| `HttpClient`         | `get`, `post`, `close`                                | Generic async HTTP requests      |

Each protocol requires a `name` property so that logging and diagnostics can identify the concrete implementation in use.

## ProviderRegistry

`ProviderRegistry` (`src/providers/registry.py`) is a lightweight service locator:

```python
registry = ProviderRegistry()
registry.register(MarketDataProvider, KrakenMarketData(config))
registry.register(NewsProvider, RSSNewsProvider(config))

# Retrieve later
market = registry.get(MarketDataProvider)
```

Key features:

- **Type-safe registration** -- `register()` raises `TypeError` if the instance does not satisfy the protocol.
- **Lookup by protocol** -- `get(protocol_type)` returns the registered instance, or raises `KeyError`.
- **Existence check** -- `has(protocol_type)` returns `True`/`False`.
- **Iteration** -- `all()` yields `(protocol_name, instance)` tuples.
- **Test factory** -- `ProviderRegistry.for_testing(overrides=...)` returns a registry pre-populated with mock providers. Any entry in `overrides` replaces the default mock for that protocol.

```python
# Quick test setup
registry = ProviderRegistry.for_testing()

# Override one provider
registry = ProviderRegistry.for_testing({
    MarketDataProvider: MyCustomMock(),
})
```

## Configuration

Each provider has a Pydantic config model in `src/providers/configs.py`. Configs are frozen (immutable) and use `Field` validators for safety.

**Market Data configs:**

| Config               | Key fields                              | Default               |
|----------------------|-----------------------------------------|-----------------------|
| `KrakenMarketConfig` | `base_url`, `api_key`, `api_secret`     | Kraken public API     |
| `BinanceMarketConfig`| `base_url`                              | Binance US API        |
| `YFinanceMarketConfig`| (inherits `timeout`)                   | --                    |
| `MockMarketConfig`   | `should_fail`, `default_prices`, `latency_ms` | Non-failing mock |

**News configs:**

| Config           | Key fields                              | Default                     |
|------------------|-----------------------------------------|-----------------------------|
| `RSSConfig`      | `feed_urls`                             | (required, min 1 URL)       |
| `RedditConfig`   | `subreddits`, `client_id`, `client_secret` | `wallstreetbets`, `cryptocurrency` |
| `NewsAPIConfig`  | `api_key`, `base_url`                   | newsapi.org                 |
| `MockNewsConfig` | `should_fail`, `canned_articles`        | Non-failing mock            |

All news configs share `fetch_interval_seconds` (default 300) and `max_articles_per_fetch` (default 50).

**Sentiment configs:**

| Config                  | Key fields               | Default               |
|-------------------------|--------------------------|-----------------------|
| `OllamaSentimentConfig` | `model`, `base_url`      | `llama3.2`, localhost |
| `FinBERTSentimentConfig`| `model_name`, `device`   | `ProsusAI/finbert`, CPU |
| `ClaudeSentimentConfig` | `api_key`, `model`       | claude-sonnet-4-5     |
| `MockSentimentConfig`   | `default_score`, `default_magnitude` | 0.0, 0.5    |

**On-chain and Feature configs:**

| Config                   | Key fields            | Default                |
|--------------------------|-----------------------|------------------------|
| `BlockchairConfig`       | `base_url`, `timeout` | blockchair.com, 15s    |
| `TechnicalFeatureConfig` | `indicators`          | sma, rsi, macd, bbands, atr |

## Usage Examples

### Register a real provider

```python
from src.providers.configs import KrakenMarketConfig
from src.providers.protocols import MarketDataProvider
from src.providers.registry import ProviderRegistry

config = KrakenMarketConfig(api_key="...", api_secret="...")
kraken = KrakenMarketData(config)  # your concrete class

registry = ProviderRegistry()
registry.register(MarketDataProvider, kraken)

ticks = await registry.get(MarketDataProvider).get_ticks(["BTC/USD"])
```

### Use mock providers in tests

```python
registry = ProviderRegistry.for_testing()
provider = registry.get(MarketDataProvider)
ticks = await provider.get_ticks(["BTC/USD"])
```

## Adding Your Own

Follow these steps to add a new provider type (e.g. `FundingRateProvider`):

1. **Define the protocol** in `src/providers/protocols.py`:

```python
@runtime_checkable
class FundingRateProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def get_funding_rate(self, symbol: str) -> float: ...
    async def health_check(self) -> bool: ...
```

2. **Add a config model** in `src/providers/configs.py`:

```python
class FundingRateConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    base_url: str = "https://api.example.com"
```

3. **Write the concrete implementation** in a new file (e.g. `src/providers/funding.py`):

```python
class ExchangeFundingRateProvider:
    def __init__(self, config: FundingRateConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "exchange_funding"

    async def get_funding_rate(self, symbol: str) -> float:
        # call API ...
        return rate

    async def health_check(self) -> bool:
        return True
```

4. **Write a mock** in `src/providers/mock.py`:

```python
class MockFundingRateProvider:
    @property
    def name(self) -> str:
        return "mock_funding"

    async def get_funding_rate(self, symbol: str) -> float:
        return 0.01

    async def health_check(self) -> bool:
        return True
```

5. **Register the protocol** in `registry.py`:
   - Add the new protocol to `_PROTOCOL_MAP`.
   - Add the mock to `for_testing()` defaults.

6. **Register the concrete instance** wherever you bootstrap the application:

```python
registry.register(FundingRateProvider, ExchangeFundingRateProvider(config))
```

## Troubleshooting

**TypeError on register** -- The instance does not satisfy the protocol. Double-check that all required methods and properties (including `name`) are implemented with matching signatures.

**KeyError on get** -- No provider has been registered for that protocol type. Make sure the registration step runs before any code calls `registry.get(...)`.

**health_check returns False** -- The upstream service is unreachable. Verify network connectivity, API keys, and base URLs in the config.

**rate_limit exceeded (NewsProvider)** -- The `rate_limit` property reports the provider's requests-per-minute cap. Back off or increase `fetch_interval_seconds` in the news config.
