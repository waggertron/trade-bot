# Trade Bot

Protocol-first agentic trading system for crypto and equities.

## Overview

Trade Bot is a multi-asset automated trading system built on a protocol-first architecture. Every major subsystem -- providers, strategies, risk management, ML models -- is defined as a Python `typing.Protocol`, decoupling interface from implementation and making the entire system testable via mock providers. The system supports both paper and live trading through a consensus-based decision engine that coordinates six trading strategies, an ML pipeline, sentiment analysis, and regime-aware risk management.

## Architecture

```
+-------------------------------------------------------------+
|                     PROVIDER LAYER                          |
|                                                             |
|  NewsProvider    MarketDataProvider    OnChainProvider       |
|  +---------+    +---------------+     +--------------+     |
|  | RSS     |    | Kraken        |     | Blockchair   |     |
|  | Reddit  |    | Binance       |     | (Glassnode)  |     |
|  | NewsAPI |    | Yahoo Finance |     +--------------+     |
|  +----+----+    +------+--------+              |            |
|       |                |                       |            |
|       v                v                       v            |
|  +-----------------------------------------------------+    |
|  |              ProviderRegistry                       |    |
|  |   Instantiates from settings.yaml, health checks    |    |
|  +------------------------+----------------------------+    |
+---------------------------+-------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|                   PROCESSING LAYER                          |
|                                                             |
|  SentimentPipeline             FeatureEngine                |
|  +------------------+          +------------------------+   |
|  | ArticleBuffer    |          | Technical (TA-Lib)     |   |
|  | SentimentAnalyzer|--score-->| Sentiment (rolling)    |   |
|  |   Ollama (bulk)  |          | Cross-asset (corr)     |   |
|  |   FinBERT        |          | Regime (vol detect)    |   |
|  |   Claude (deep)  |          | On-chain (flows)       |   |
|  | Aggregator       |          +-----------+------------+   |
|  +------------------+                      |                |
|                                            v                |
|                                  FeatureStore (DB)          |
|                                  +------------------+       |
|                                  | symbol x time x  |       |
|                                  | feature -> value  |       |
|                                  +--------+---------+       |
+-------------------------------------------+-----------------+
                                            |
                             +--------------+--------------+
                             v                             v
+------------------------------+  +---------------------------+
|        ML LAYER              |  |     STRATEGY LAYER        |
|                              |  |                           |
|  ModelProvider               |  |  FeatureStrategy          |
|  +----------------+          |  |  +---------------------+  |
|  | XGBoost        |--train-->|  |  | Momentum (adapter)  |  |
|  | LSTM           |  walk-   |  |  | Quant (adapter)     |  |
|  | Ensemble       |  forward |  |  | Sentiment (adapter) |  |
|  +-------+--------+          |  |  | ML Ensemble (new)   |  |
|          |                   |  |  | Event-Driven (new)  |  |
|   Trainer / Evaluator        |  |  | Cross-Asset (new)   |  |
|   (weekly retrain)           |  |  +----------+----------+  |
+--------------+---------------+  +-------------+-------------+
               |                                |
               +----------+---------------------+
                          |  FeatureVector + Predictions
                          v
+-------------------------------------------------------------+
|                   DECISION LAYER                            |
|                                                             |
|  WeightedConsensus -> RiskManager -> PositionSizer          |
|  (config x accuracy x regime weights)                       |
|  DrawdownCircuitBreaker, regime limits, correlation checks  |
+------------------------+------------------------------------+
                         v
+-------------------------------------------------------------+
|                 EXECUTION & ANALYTICS                       |
|                                                             |
|  ExecutionAgent  PortfolioManager  Attribution  Monte Carlo |
|  (Paper/Live)    (Positions/P&L)   Reporter     Simulator   |
|                                    FastAPI      Discord Bot |
+-------------------------------------------------------------+
```

## Features

- **Protocol-first provider architecture** -- swap data sources (Kraken, Binance, Yahoo Finance) without code changes; the `ProviderRegistry` validates protocol conformance at registration time
- **Sentiment pipeline** -- RSS, Reddit, and NewsAPI article ingestion with Ollama (bulk), FinBERT (speed), and Claude (deep analysis) scoring
- **ML pipeline** -- XGBoost, LSTM, and ensemble models with walk-forward validation and weekly retraining
- **6 trading strategies** with weighted consensus -- Momentum, Quantitative, Sentiment, ML Ensemble, Event-Driven, and Cross-Asset
- **Risk management** -- regime-aware position limits, Kelly criterion / volatility-targeted sizing, drawdown circuit breakers, and correlation checks
- **Performance analytics** -- strategy attribution, Monte Carlo simulation, regime tagging, and report generation
- **On-chain data integration** -- Blockchair metrics for crypto flow analysis
- **Full CLI** for every subsystem -- 11 command groups covering providers, strategies, ML, risk, analytics, and more
- **FastAPI dashboard** with portfolio view, trade history, and control endpoints
- **Discord bot** for real-time trade alerts and portfolio formatting
- **882 tests** -- unit, component, and integration coverage with mock providers requiring no external services

## Quick Start

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url> trade-bot
cd trade-bot
uv sync
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
uv run tradebot --help
```

To install optional extras:

```bash
uv sync --extra ml        # XGBoost, scikit-learn, PyTorch
uv sync --extra yfinance  # Yahoo Finance provider
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `tradebot analytics` | Performance analytics, attribution, and reporting |
| `tradebot backtest` | Backtesting with strategy replay and demo mode |
| `tradebot config` | Validate, show, and inspect configuration schemas |
| `tradebot features` | Feature inspection and feature store queries |
| `tradebot ml` | ML pipeline status, training, and feature vectors |
| `tradebot news` | News fetching and article inspection |
| `tradebot portfolio` | Portfolio snapshots, positions, and P&L |
| `tradebot providers` | List, filter, and health-check registered providers |
| `tradebot risk` | Risk status, regime limits, and circuit breaker state |
| `tradebot sentiment` | Sentiment pipeline status and per-symbol scores |
| `tradebot strategies` | Strategy listing, weights, and signal inspection |

## Protocols

Every subsystem boundary is a `@runtime_checkable` protocol. Implement the protocol, register with the `ProviderRegistry`, and the rest of the system works unchanged.

| Protocol | Purpose | Implementations |
|----------|---------|-----------------|
| `MarketDataProvider` | Price feeds and OHLC bars | Kraken, Binance, Yahoo Finance, Mock |
| `NewsProvider` | Article fetching | RSS, Reddit, NewsAPI, Mock |
| `SentimentAnalyzer` | Text to sentiment score | Ollama, FinBERT, Mock |
| `OnChainProvider` | Blockchain metrics | Blockchair, Mock |
| `FeatureProvider` | Computed indicators | Technical (TA-Lib), Mock |
| `ModelProvider` | ML predict / train / evaluate | XGBoost, LSTM, Mock |
| `PositionSizer` | Order sizing | Fixed, Kelly, VolTargeted |
| `FeatureStrategy` | Signal generation | Momentum, Sentiment, Quant, ML Ensemble, Event-Driven, Cross-Asset |

Additional protocols: `HttpClient`, `DataStore`, `MarketDataAgent`, `ResearchAgent`, `StrategyAgent`, `RiskManagerAgent`, `ExecutionAgent`, `PortfolioAgent`.

## Project Structure

```
src/
  agents/          # Trading agents and strategies
    strategies/    # Momentum, Sentiment, Quant, ML Ensemble, Event-Driven, Cross-Asset
    execution.py   # Order execution (paper / live)
    portfolio.py   # Portfolio management
    risk_manager.py
  analytics/       # Attribution, Monte Carlo, regime tagging, reporting
  cli/             # Typer CLI -- 11 command groups
  core/            # Orchestrator, models, config, event bus, protocols
  data/            # Market data infrastructure
  db/              # SQLAlchemy async database layer
  dashboard/       # FastAPI web dashboard
  discord_bot/     # Discord alerting bot
  integrations/    # Exchange and LLM clients (Kraken, IBKR, Claude, Ollama)
  ml/              # Feature store, feature engine, model training, ML protocols
  providers/       # Protocol-based providers, registry, configs, mocks
  risk/            # Position sizing (Fixed, Kelly, VolTargeted), circuit breakers
  sentiment/       # Sentiment pipeline, article buffer, scoring, aggregation

tests/
  unit/            # Fast isolated tests with mock providers
  integration/     # Multi-component integration tests

docs/              # Architecture, guides, and subsystem documentation
config/            # Runtime configuration (settings.yaml)
```

## Testing

All tests use mock providers -- no external services or API keys required.

```bash
# Full suite (882 passed, 12 skipped)
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# With coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

## Documentation

Detailed documentation is in the `docs/` directory:

- [Architecture](docs/architecture.md) -- system overview, data flow, design decisions
- [Quickstart](docs/guides/quickstart.md) -- installation and first run
- [Adding a Provider](docs/guides/adding-a-provider.md) -- extend the system with new data sources
- [CLI Overview](docs/cli/overview.md) -- full command reference
- [Providers](docs/providers/overview.md) -- provider protocols and registry
- [Strategies](docs/strategies/overview.md) -- strategy layer and consensus
- [ML Pipeline](docs/ml/overview.md) -- feature store, models, training
- [Risk Management](docs/risk/overview.md) -- sizing, limits, circuit breakers
- [Analytics](docs/analytics/overview.md) -- attribution, Monte Carlo, reporting
- [Testing](docs/testing/overview.md) -- TDD workflow and mock patterns

## Tech Stack

- **Python 3.12+** with asyncio throughout
- **Pydantic v2** -- frozen immutable models for all domain objects
- **Typer + Rich** -- CLI with formatted tables and progress indicators
- **SQLAlchemy 2.0** + aiosqlite -- async database layer
- **FastAPI + Uvicorn** -- web dashboard
- **pandas + NumPy + TA-Lib** -- technical analysis and data processing
- **XGBoost + PyTorch + scikit-learn** -- ML pipeline (optional extras)
- **httpx + websockets** -- async HTTP and WebSocket clients
- **discord.py** -- trade alert bot
- **Ruff + mypy** -- linting and strict type checking
