# Testing Overview

This project follows a strict test-driven development (TDD) workflow. All new
features begin with a failing test, proceed to a minimal passing
implementation, and finish with a refactoring pass.

## TDD workflow: RED -> GREEN -> REFACTOR

1. **RED** -- Write a test that describes the desired behavior. Run it and
   confirm it fails.
2. **GREEN** -- Write the minimum code to make the test pass.
3. **REFACTOR** -- Clean up duplication, improve naming, extract helpers.
   Rerun the tests to confirm nothing broke.

Repeat for every behavioral change. Never push code that does not have
corresponding tests.

## Running tests

Always use `uv run` -- never bare `pytest` or `python`.

```bash
# Run the full test suite (excluding DB tests that need a running database)
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py

# Run just unit tests
uv run pytest tests/unit/ -v

# Run just integration tests
uv run pytest tests/integration/ -v

# Run a single file
uv run pytest tests/unit/providers/test_registry.py -v

# Run with coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

## pytest configuration

The project-level pytest settings live in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Key points:

- **`asyncio_mode = "auto"`** -- Any `async def test_*` function is
  automatically treated as an asyncio test. You do not need to add
  `@pytest.mark.asyncio` unless you want to be explicit.
- **`testpaths`** -- pytest discovers tests from the `tests/` directory by
  default.

## Test directory structure

```
tests/
  conftest.py                      # Shared fixtures (settings, etc.)
  test_*.py                        # Legacy / top-level tests

  unit/                            # Fast, isolated, no I/O
    cli/
      test_config_cmd.py
      test_providers_cmd.py
      test_sentiment_cmd.py
      test_ml_cmd.py
      test_risk_cmd.py
      test_analytics_cmd.py
    providers/
      test_protocols.py            # Protocol isinstance checks
      test_configs.py              # Pydantic config validation
      test_registry.py             # ProviderRegistry tests
      test_compliance.py           # Protocol compliance suites
      test_mocks.py                # Mock behavior tests
      test_rss.py                  # RSS provider tests
      test_ollama_sentiment.py     # Ollama sentiment tests
      test_technical.py            # Technical feature tests
    sentiment/
      test_models.py
      test_article_buffer.py
      test_aggregator.py
      test_store.py
      test_pipeline.py
      test_bridge.py
    ml/
      test_models.py
      test_feature_store.py
      test_feature_engine.py
      test_protocols.py
      test_mock_model.py
      test_dataset_builder.py
      test_trainer.py
    risk/
      test_models.py
      test_protocols.py
      test_fixed_sizer.py
      test_kelly_sizer.py
      test_vol_sizer.py
      test_circuit_breaker.py
    strategies/
      test_protocol.py
      test_adapters.py
      test_ml_ensemble.py
      test_event_driven.py
      test_cross_asset.py
      test_consensus.py
    analytics/
      test_models.py
      test_attribution.py
      test_monte_carlo.py
      test_regime_tagger.py
      test_reporter.py

  integration/                     # Multi-component, end-to-end flows
    test_sentiment_e2e.py
    test_feature_e2e.py
    test_risk_e2e.py
    test_strategy_e2e.py
    test_analytics_e2e.py
```

### Test levels

| Level         | Location             | Purpose                                        |
| ------------- | -------------------- | ---------------------------------------------- |
| **Unit**      | `tests/unit/`        | Single class or function, fully mocked, fast   |
| **Integration** | `tests/integration/` | Multiple components wired together             |
| **Top-level** | `tests/test_*.py`    | Legacy tests, gradually being moved into `unit/` and `integration/` |

## Test markers

While `asyncio_mode = "auto"` handles most async cases, explicit markers are
available:

- `@pytest.mark.asyncio` -- Mark a test as async (optional with auto mode).
- Planned markers for selective runs: `unit`, `integration`, `slow`.

## Fixtures

The shared `tests/conftest.py` provides:

```python
@pytest.fixture
def settings():
    """Load test settings."""
    from src.core.config import Settings
    return Settings.for_testing()
```

`Settings.for_testing()` returns a paper-mode configuration with sensible
defaults (`BTC/USD` in the crypto symbols list, default risk settings, port
8080 for the dashboard).

## Mock patterns

The project uses hand-written mock implementations rather than `unittest.mock`.
All mocks live in `src/providers/mock.py` and implement the corresponding
protocol from `src/providers/protocols.py`.

### Available mocks

| Mock class                | Protocol            | Key behavior                            |
| ------------------------- | ------------------- | --------------------------------------- |
| `MockHttpClient`          | `HttpClient`        | Tracks calls, returns stubbed responses |
| `MockMarketDataProvider`  | `MarketDataProvider`| Configurable prices via `set_price()`   |
| `MockNewsProvider`        | `NewsProvider`      | Returns canned articles from config     |
| `MockSentimentAnalyzer`   | `SentimentAnalyzer` | Returns configurable score/magnitude    |
| `MockOnChainProvider`     | `OnChainProvider`   | Returns stub metrics                    |
| `MockFeatureProvider`     | `FeatureProvider`   | Returns configurable feature dict       |
| `MockDataStore`           | `DataStore`         | In-memory trade and signal storage      |

### Configuring mocks

Mocks accept Pydantic config objects for fine-grained control:

```python
from src.providers.mock import MockMarketDataProvider, MockNewsProvider
from src.providers.configs import MockMarketConfig, MockNewsConfig

# Market provider that simulates failures
failing_market = MockMarketDataProvider(
    MockMarketConfig(should_fail=True)
)

# Market provider with a custom price
market = MockMarketDataProvider(
    MockMarketConfig(default_prices={"BTC/USD": "50000"})
)

# News provider with canned articles and simulated latency
news = MockNewsProvider(
    MockNewsConfig(
        canned_articles=[{"title": "Headline", "body": "..."}],
        latency_ms=100,
    )
)
```

### Using the test registry

`ProviderRegistry.for_testing()` creates a registry pre-populated with default
mocks for all protocol types. Override specific providers as needed:

```python
from src.providers.registry import ProviderRegistry
from src.providers.protocols import MarketDataProvider

registry = ProviderRegistry.for_testing(
    overrides={MarketDataProvider: my_custom_mock}
)
```

### Protocol compliance tests

The project uses base compliance classes in
`tests/unit/providers/test_compliance.py` to verify that ANY implementation
(mock or real) satisfies its protocol contract. To test a new implementation,
subclass the appropriate compliance base and override the factory method:

```python
from tests.unit.providers.test_compliance import MarketDataCompliance

class TestMyProviderCompliance(MarketDataCompliance):
    def make_provider(self):
        return MyNewProvider()
```

This automatically runs all the shared assertions (`test_implements_protocol`,
`test_has_name`, `test_get_ticks_returns_list`, etc.) against your provider.

## How to write a mock implementation

1. Pick the protocol from `src/providers/protocols.py` (e.g.,
   `MarketDataProvider`).
2. Create a Pydantic config in `src/providers/configs.py` with fields like
   `should_fail`, `latency_ms`, and any canned return data.
3. Implement all protocol methods in a new class in `src/providers/mock.py`.
   Accept the config in `__init__` with a default of `None` so the mock
   works with zero configuration.
4. Add counters (e.g., `get_ticks_count`) and setter methods (e.g.,
   `set_price()`) so tests can inspect call history and inject state.
5. Register the mock as a default in `ProviderRegistry.for_testing()` inside
   `src/providers/registry.py`.
6. Verify compliance by subclassing the appropriate compliance base in
   `tests/unit/providers/test_compliance.py`.

## CLI testing with Typer

CLI commands are tested using `typer.testing.CliRunner`:

```python
from typer.testing import CliRunner
from src.cli.main import app

runner = CliRunner()

def test_config_validate(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(yaml.dump(valid_config))
    result = runner.invoke(app, ["config", "validate", "--config", str(cfg)])
    assert result.exit_code == 0
```

This invokes the full CLI in-process without spawning a subprocess, making
tests fast and deterministic.
