# Adding a Provider

This guide walks through the steps to add a new provider to the trade-bot.
Providers are pluggable components that satisfy a protocol contract defined in
`src/providers/protocols.py`.

## Step 1: Choose a protocol

Open `src/providers/protocols.py` and pick the protocol your provider will
implement. Each protocol is decorated with `@runtime_checkable` so that
`isinstance()` checks work at runtime.

Available protocols:

| Protocol              | Purpose                                     | Key methods                              |
| --------------------- | ------------------------------------------- | ---------------------------------------- |
| `HttpClient`          | Make HTTP requests                          | `get()`, `post()`, `close()`             |
| `MarketDataProvider`  | Fetch ticks and OHLC bars                   | `name`, `get_ticks()`, `get_ohlc()`, `health_check()` |
| `NewsProvider`        | Fetch news articles                         | `name`, `fetch_articles()`, `health_check()`, `rate_limit` |
| `SentimentAnalyzer`   | Score text sentiment                        | `name`, `score()`, `score_batch()`       |
| `OnChainProvider`     | Fetch on-chain blockchain metrics           | `name`, `get_metrics()`, `health_check()` |
| `FeatureProvider`     | Compute derived features for ML/strategies  | `name`, `required_inputs`, `compute()`   |
| `DataStore`           | Persist trades and signals                  | `initialize()`, `close()`, `save_trade()`, `list_trades()`, `save_signal()`, `list_signals()` |

For example, if you are adding a new exchange for market data, implement
`MarketDataProvider`. If you are adding a new news source, implement
`NewsProvider`.

## Step 2: Create a config model

Add a Pydantic config class in `src/providers/configs.py`. Inherit from the
appropriate base config and add fields for API keys, URLs, timeouts, etc.

```python
# src/providers/configs.py

class CoinGeckoMarketConfig(MarketDataConfig):
    base_url: str = "https://api.coingecko.com/api/v3"
    api_key: str = ""
```

All config models use `frozen=True` (immutable after creation) via the parent
class.

## Step 3: Implement the provider

Create a new file in `src/providers/` (e.g., `src/providers/coingecko.py`)
and implement every method required by the protocol:

```python
# src/providers/coingecko.py
"""CoinGecko market data provider."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.models import AssetType, MarketTick
from src.providers.configs import CoinGeckoMarketConfig
from src.providers.protocols import HttpClient


class CoinGeckoProvider:
    """MarketDataProvider backed by the CoinGecko API."""

    def __init__(
        self,
        config: CoinGeckoMarketConfig | None = None,
        http: HttpClient | None = None,
    ) -> None:
        self._config = config or CoinGeckoMarketConfig()
        self._http = http  # injected for testing

    @property
    def name(self) -> str:
        return "coingecko"

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]:
        # Call the CoinGecko API via self._http or a real client
        ...

    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...

    async def health_check(self) -> bool:
        try:
            resp = await self._http.get(f"{self._config.base_url}/ping")
            return resp.status_code == 200
        except Exception:
            return False
```

Key patterns:

- Accept the config and an `HttpClient` in `__init__`. This lets tests inject
  `MockHttpClient`.
- Every property and method from the protocol must be present, or
  `isinstance()` checks will fail.
- Return types must match the protocol signatures.

## Step 4: Write tests

### 4a. Protocol compliance test

Subclass the appropriate compliance base in
`tests/unit/providers/test_compliance.py` to verify your provider satisfies
the full protocol contract:

```python
# tests/unit/providers/test_compliance.py

from src.providers.coingecko import CoinGeckoProvider
from src.providers.mock import MockHttpClient
from src.providers.protocols import HttpResponse


class TestCoinGeckoCompliance(MarketDataCompliance):
    def make_provider(self):
        http = MockHttpClient()
        http.stub(
            "https://api.coingecko.com/api/v3/ping",
            HttpResponse(200, '{"gecko_says": "V3"}'),
        )
        return CoinGeckoProvider(http=http)
```

This automatically runs all shared protocol tests (`test_implements_protocol`,
`test_has_name`, `test_get_ticks_returns_list`, `test_get_ohlc_returns_list`,
`test_health_check_returns_bool`).

### 4b. Unit tests

Add a dedicated test file for provider-specific behavior:

```python
# tests/unit/providers/test_coingecko.py

import pytest
from src.providers.coingecko import CoinGeckoProvider
from src.providers.configs import CoinGeckoMarketConfig
from src.providers.mock import MockHttpClient
from src.providers.protocols import HttpResponse


class TestCoinGeckoProvider:
    def test_name(self):
        provider = CoinGeckoProvider()
        assert provider.name == "coingecko"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        http = MockHttpClient()
        http.stub(
            "https://api.coingecko.com/api/v3/ping",
            HttpResponse(200, '{"gecko_says": "V3"}'),
        )
        provider = CoinGeckoProvider(http=http)
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        http = MockHttpClient()
        http.stub(
            "https://api.coingecko.com/api/v3/ping",
            HttpResponse(500, "error"),
        )
        provider = CoinGeckoProvider(http=http)
        assert await provider.health_check() is False
```

Run the tests:

```bash
uv run pytest tests/unit/providers/test_coingecko.py -v
uv run pytest tests/unit/providers/test_compliance.py -v
```

## Step 5: Register in the provider catalog

Add an entry to the `PROVIDER_CATALOG` dictionary in
`src/cli/providers_cmd.py` so the CLI can list your provider:

```python
PROVIDER_CATALOG: dict[str, list[tuple[str, str, str]]] = {
    "market_data": [
        ("mock_market", "mock", "Mock market data provider for testing"),
        ("kraken", "external", "Kraken cryptocurrency exchange"),
        ("binance", "external", "Binance cryptocurrency exchange"),
        ("coingecko", "external", "CoinGecko market data"),  # <-- add this
    ],
    ...
}
```

Verify with:

```bash
uv run tradebot providers list --protocol market_data
```

## Step 6: Configure in settings.yaml

Add provider configuration to your `config/settings.yaml` (or environment
variables) so the orchestrator can instantiate your provider at runtime:

```yaml
providers:
  market_data:
    type: coingecko
    base_url: https://api.coingecko.com/api/v3
    api_key: ${COINGECKO_API_KEY}
```

The exact YAML schema depends on how the orchestrator resolves provider
configs. At minimum, your Pydantic config model should be importable and
validated at startup.

## Checklist

- [ ] Protocol chosen from `src/providers/protocols.py`
- [ ] Pydantic config added to `src/providers/configs.py`
- [ ] Provider class implements all protocol methods
- [ ] Protocol compliance test passes
- [ ] Unit tests cover success, failure, and edge cases
- [ ] Provider listed in `PROVIDER_CATALOG` in `src/cli/providers_cmd.py`
- [ ] Configuration documented in `settings.yaml`
