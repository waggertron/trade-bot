# Quickstart Guide

Get the trade-bot running locally in under five minutes.

## Prerequisites

- **Python 3.12+** -- Verify with `python3 --version`.
- **uv** -- The project uses [uv](https://docs.astral.sh/uv/) for all
  Python operations. Install it with:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## Installation

Clone the repository and install all dependencies:

```bash
git clone <repo-url> trade-bot
cd trade-bot
uv sync
```

`uv sync` reads `pyproject.toml`, creates a virtual environment, and installs
both runtime and dev dependencies.

To also install optional extras (e.g., yfinance):

```bash
uv sync --extra yfinance
```

## Running the tests

```bash
# Full suite (skip DB tests that need a running database)
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# With coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

All tests use mock providers so no external services are required.

## Using the CLI

The CLI is registered as the `tradebot` console script. Start with:

```bash
uv run tradebot --help
```

### Key commands

```bash
# Configuration
uv run tradebot config validate --config config/settings.yaml
uv run tradebot config show --config config/settings.yaml --format json
uv run tradebot config schema RiskSettings

# Providers
uv run tradebot providers list
uv run tradebot providers list --protocol sentiment
uv run tradebot providers health --mock

# Sentiment
uv run tradebot sentiment status
uv run tradebot sentiment scores --symbol BTC

# ML / Features
uv run tradebot ml status
uv run tradebot ml features --symbol BTC

# Risk
uv run tradebot risk status
uv run tradebot risk limits --regime high

# Analytics
uv run tradebot analytics status
uv run tradebot analytics attribution
```

## Project structure

```
trade-bot/
  pyproject.toml           # Dependencies, scripts, tool config
  config/
    settings.yaml          # Runtime configuration

  src/
    cli/                   # Typer CLI commands
      main.py              # Root app, mounts all command groups
      config_cmd.py        # config validate / show / schema
      providers_cmd.py     # providers list / health
      sentiment_cmd.py     # sentiment status / scores
      ml_cmd.py            # ml status / features
      risk_cmd.py          # risk status / limits
      analytics_cmd.py     # analytics status / attribution

    core/                  # Shared models, config, event bus, orchestrator
      config.py            # Pydantic Settings, RiskSettings, etc.
      models.py            # MarketTick, AssetType, etc.
      event_bus.py         # Async event pub/sub
      orchestrator.py      # Main trading loop coordinator

    providers/             # Protocol-based provider layer
      protocols.py         # @runtime_checkable Protocol definitions
      configs.py           # Pydantic config models for each provider
      mock.py              # Mock implementations for all protocols
      registry.py          # ProviderRegistry (DI container)
      rss.py               # RSS news provider
      ollama_sentiment.py  # Ollama LLM sentiment analyzer
      technical.py         # Technical indicator feature provider

    sentiment/             # Sentiment analysis pipeline
      models.py            # SentimentResult, etc.
      pipeline.py          # Orchestrates news -> score -> aggregate
      article_buffer.py    # Deduplicates and buffers articles
      aggregator.py        # Aggregates scores per symbol
      store.py             # Persists articles and scores
      bridge.py            # Converts scores to research reports

    ml/                    # Machine learning subsystem
      models.py            # ML data models
      protocols.py         # ML-specific protocols
      feature_store.py     # Feature persistence
      feature_engine.py    # Feature computation
      dataset_builder.py   # Training dataset construction
      trainer.py           # Model training loop
      mock_model.py        # Mock ML model for testing

    risk/                  # Risk management
      models.py            # VolatilityRegime, risk data models
      protocols.py         # Risk protocol definitions
      fixed_sizer.py       # Fixed fraction position sizing
      kelly_sizer.py       # Kelly criterion sizing
      vol_sizer.py         # Volatility-adjusted sizing
      circuit_breaker.py   # Trading circuit breaker

    analytics/             # Post-trade analytics
      models.py            # Analytics data models
      attribution.py       # Strategy attribution
      monte_carlo.py       # Monte Carlo simulation
      regime_tagger.py     # Market regime classification
      reporter.py          # Report generation

    agents/                # Trading agents and strategies
      strategies/          # Strategy implementations
        momentum.py
        sentiment.py
        quantitative.py
        ml_ensemble.py
        event_driven.py
        cross_asset.py
        consensus.py       # Multi-strategy consensus
        adapters.py        # Strategy adapters
      execution.py         # Order execution agent
      market_data.py       # Market data agent
      portfolio.py         # Portfolio management agent
      research.py          # Research agent
      risk_manager.py      # Risk management agent

    db/                    # Database layer
      database.py          # SQLAlchemy async engine
      models.py            # TradeRecord, SignalRecord

    integrations/          # External service clients
      kraken.py            # Kraken exchange client
      claude_client.py     # Anthropic Claude client
      ollama_client.py     # Ollama local LLM client
      ibkr.py              # Interactive Brokers client

    dashboard/             # FastAPI web dashboard
      app.py               # Dashboard endpoints

    discord_bot/           # Discord alerting bot
      bot.py               # Discord bot implementation

  tests/                   # Test suite
    conftest.py            # Shared fixtures
    unit/                  # Fast, isolated unit tests
    integration/           # Multi-component integration tests

  docs/                    # Documentation
```

## Next steps

- Read the [CLI overview](../cli/overview.md) for detailed command reference.
- Read the [testing overview](../testing/overview.md) for TDD workflow and
  mock patterns.
- Read the [adding a provider](adding-a-provider.md) guide to extend the
  system with new data sources.
