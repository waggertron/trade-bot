# Architecture

## System Overview

The trading bot is a multi-asset (crypto and stock) automated trading system built on a **protocol-first architecture**. Every major subsystem is defined as a Python `Protocol` (using `typing.Protocol` with `@runtime_checkable`), which decouples interface from implementation and makes the entire system testable via mock providers.

The core loop is: **ingest market data -> generate features -> produce signals -> evaluate risk -> execute trades**. An `Orchestrator` drives this loop, consuming `MarketTick` events and coordinating strategies, risk management, and execution. An `EventBus` provides pub/sub for cross-cutting concerns like trade alerts and logging.

All domain objects are **Pydantic v2 frozen models** (`ConfigDict(frozen=True)`), ensuring immutability throughout the pipeline. Providers are instantiated and registered through a `ProviderRegistry` that validates protocol conformance at registration time.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     PROVIDER LAYER                          │
│                                                             │
│  NewsProvider    MarketDataProvider    OnChainProvider       │
│  ┌─────────┐    ┌───────────────┐     ┌──────────────┐     │
│  │ RSS     │    │ Kraken        │     │ Blockchair   │     │
│  │ Reddit  │    │ Binance       │     │ (Glassnode)  │     │
│  │ NewsAPI │    │ Yahoo Finance │     └──────────────┘     │
│  └────┬────┘    └──────┬────────┘              │            │
│       │                │                       │            │
│       ▼                ▼                       ▼            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ProviderRegistry                       │    │
│  │   Instantiates from settings.yaml, health checks    │    │
│  └──────────────────────┬──────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   PROCESSING LAYER                          │
│                                                             │
│  SentimentPipeline             FeatureEngine                │
│  ┌──────────────────┐          ┌────────────────────────┐   │
│  │ ArticleBuffer    │          │ Technical (TA-Lib)     │   │
│  │ SentimentAnalyzer│──score──▶│ Sentiment (rolling)    │   │
│  │   Ollama (bulk)  │          │ Cross-asset (corr)     │   │
│  │   FinBERT        │          │ Regime (vol detect)    │   │
│  │   Claude (deep)  │          │ On-chain (flows)       │   │
│  │ Aggregator       │          └───────────┬────────────┘   │
│  └──────────────────┘                      │                │
│                                            ▼                │
│                                  FeatureStore (DB)          │
│                                  ┌──────────────────┐       │
│                                  │ symbol × time ×  │       │
│                                  │ feature → value  │       │
│                                  └────────┬─────────┘       │
└───────────────────────────────────────────┼─────────────────┘
                                            │
                             ┌──────────────┴──────────────┐
                             ▼                             ▼
┌──────────────────────────────┐  ┌───────────────────────────┐
│        ML LAYER              │  │     STRATEGY LAYER        │
│                              │  │                           │
│  ModelProvider               │  │  FeatureStrategy          │
│  ┌────────────────┐          │  │  ┌─────────────────────┐  │
│  │ XGBoost        │──train──▶│  │  │ Momentum (adapter)  │  │
│  │ LSTM           │  walk-   │  │  │ Quant (adapter)     │  │
│  │ Ensemble       │  forward │  │  │ Sentiment (adapter) │  │
│  └───────┬────────┘          │  │  │ ML Ensemble (new)   │  │
│          │                   │  │  │ Event-Driven (new)  │  │
│   Trainer / Evaluator        │  │  │ Cross-Asset (new)   │  │
│   (weekly retrain)           │  │  └──────────┬──────────┘  │
└──────────────┬───────────────┘  └─────────────┼─────────────┘
               │                                │
               └──────────┬─────────────────────┘
                          │  FeatureVector + Predictions
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   DECISION LAYER                            │
│                                                             │
│  WeightedConsensus → RiskManager → PositionSizer            │
│  (config × accuracy × regime weights)                       │
│  DrawdownCircuitBreaker, regime limits, correlation checks  │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 EXECUTION & ANALYTICS                       │
│                                                             │
│  ExecutionAgent  PortfolioManager  Attribution  Monte Carlo │
│  (Paper/Live)    (Positions/P&L)   Reporter     Simulator   │
│                                    FastAPI      Discord Bot │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### Provider Layer

The entry point for all external data. Each provider type is defined by a protocol (`MarketDataProvider`, `NewsProvider`, `OnChainProvider`) and can have multiple concrete implementations (e.g., Kraken, Binance, Yahoo Finance for market data). The `ProviderRegistry` acts as a dependency injection container: it accepts any object that satisfies a protocol, validates conformance via `isinstance()` at registration time, and exposes a `for_testing()` factory that pre-populates the registry with mock providers.

### Processing Layer

Transforms raw data into actionable features. The `SentimentPipeline` buffers articles, scores them through one or more `SentimentAnalyzer` implementations (Ollama for bulk, FinBERT for speed, Claude for deep analysis), and produces rolling sentiment scores. The `FeatureEngine` computes technical indicators (via TA-Lib), cross-asset correlations, volatility regime detection, and on-chain flow metrics. All results are written to the `FeatureStore`, a database table keyed by `(symbol, timestamp, feature_name)`.

### ML Layer

Houses the `ModelProvider` protocol, which standardizes `predict`, `train`, and `evaluate` across model types (XGBoost, LSTM, Ensemble). Training uses walk-forward validation (`WalkForwardResult`) to avoid look-ahead bias. Models consume `FeatureVector` objects from the FeatureStore and produce `Prediction` objects with direction, confidence, and feature attribution. Weekly retraining keeps models current.

### Strategy Layer

Strategies implement the `FeatureStrategy` protocol, which takes a `symbol` and `FeatureVector` and returns an optional `Signal`. Each strategy declares `required_features()` so the system can pre-fetch only the data it needs. Adapters wrap legacy strategies (Momentum, Quant, Sentiment) to conform to the feature-based interface, while new strategies (ML Ensemble, Event-Driven, Cross-Asset) are built natively on `FeatureVector`.

### Decision Layer

The `Orchestrator` gathers signals from all active strategies, finds majority consensus, and passes the winning signal through `RiskManagerAgent.evaluate_trade()`. The risk manager considers `RiskContext` -- current volatility regime, drawdown from peak, correlation matrix, and per-strategy performance statistics -- to approve, veto, or resize the trade. `PositionSizer` implementations (Fixed, Kelly, VolTargeted) compute the final trade value in base currency.

### Execution and Analytics

`ExecutionAgent` submits `Order` objects and returns `Fill` confirmations (paper or live mode). `PortfolioAgent` tracks positions, cash, and P&L. The `EventBus` publishes trade events that feed into the FastAPI dashboard (portfolio view, trade history, control endpoints) and the Discord bot (real-time trade alerts, portfolio formatting). Attribution and Monte Carlo simulation provide post-hoc analysis.

---

## Protocol Summary Table

| Protocol | Purpose | Implementations |
|----------|---------|-----------------|
| `NewsProvider` | Article fetching | RSS, Reddit, NewsAPI, Mock |
| `SentimentAnalyzer` | Text to sentiment score | Ollama, FinBERT, Mock |
| `OnChainProvider` | Blockchain metrics | Blockchair, Mock |
| `MarketDataProvider` | Price feeds | Kraken, Binance, Yahoo, Mock |
| `FeatureProvider` | Computed indicators | Technical (TA-Lib), Mock |
| `ModelProvider` | ML predict/train | XGBoost, LSTM, Mock |
| `PositionSizer` | Order sizing | Fixed, Kelly, VolTargeted |
| `FeatureStrategy` | Signal generation | Momentum, Sentiment, Quant, ML Ensemble, Event-Driven, Cross-Asset |

Supporting protocols not in the table above:

- `HttpClient` -- abstracts HTTP transport for testability (any `aiohttp` or `httpx` session).
- `DataStore` -- persistent storage for trades and signals (SQLite, Postgres, Mock).
- `MarketDataAgent` -- streaming tick interface with `connect`/`disconnect` lifecycle.
- `ResearchAgent` -- runs bulk research and headline scoring.
- `StrategyAgent` -- original strategy interface (tick-based); being migrated to `FeatureStrategy`.
- `RiskManagerAgent` -- evaluates trades and portfolio health.
- `ExecutionAgent` -- order submission and cancellation.
- `PortfolioAgent` -- portfolio snapshots, fill recording, position tracking, P&L.

---

## Key Design Decisions

**Protocol-first architecture.** Every subsystem boundary is a `typing.Protocol` decorated with `@runtime_checkable`. This means components depend on interfaces, not implementations. New providers (e.g., a new exchange) require zero changes to existing code -- just implement the protocol and register. The `ProviderRegistry` enforces protocol conformance at registration time, failing fast on misconfigured providers.

**Pydantic v2 frozen models.** Core domain objects (`MarketTick`, `Fill`, `PortfolioSnapshot`, `RiskDecision`, `FeatureVector`, `Prediction`) use `ConfigDict(frozen=True)`, making them immutable after creation. This eliminates an entire class of bugs where shared state is accidentally mutated across async tasks. Mutable containers (like `Dataset`) are used only where mutation is intentional and scoped.

**Async throughout.** Every protocol method is `async def`. The `Orchestrator` uses `asyncio.gather()` to evaluate strategies concurrently, and the `EventBus` dispatches events to async handlers. This keeps the system responsive under load -- slow providers or strategies do not block the main loop.

**Test-driven development.** The `ProviderRegistry.for_testing()` factory creates a fully-wired system with mock providers in a single call. Overrides let tests replace individual mocks while keeping the rest. Combined with protocol-based interfaces, this makes integration tests fast and deterministic without hitting external APIs.

**EventBus for cross-cutting concerns.** Rather than passing callbacks through the stack, the `EventBus` provides a lightweight pub/sub mechanism. Components publish events (trade executed, signal generated) and subscribers (Discord bot, dashboard, logger) react independently. History tracking can be enabled for testing.

**Consensus-based signal aggregation.** The `Orchestrator` requires majority agreement among strategies before acting. This reduces noise from individual strategy false positives. The highest-confidence signal among the agreeing strategies is forwarded to risk management, ensuring the strongest conviction drives execution.
