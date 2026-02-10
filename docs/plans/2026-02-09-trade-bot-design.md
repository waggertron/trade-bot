# Agentic Stock Market Research & Trading Bot — Design

## Summary

A fully autonomous, multi-agent trading bot that researches and executes trades across US stocks (Interactive Brokers) and crypto (Kraken). Uses Claude API for complex reasoning and Ollama for high-frequency lightweight decisions. Runs three independent strategies (momentum, sentiment, quantitative) with a configurable risk management layer. Monitored via Discord bot and a web dashboard. Starts in paper trading mode.

## Architecture Overview

The bot is a multi-agent system with specialized agents that collaborate through a central orchestrator. Each agent has a single responsibility and communicates via an internal async event bus.

### Core Agents

1. **Market Data Agent** — streams real-time price data, order book depth, and volume from IBKR (stocks) and Kraken (crypto) via WebSocket connections
2. **Research Agent** (Claude-powered) — analyzes news, SEC filings, earnings, social sentiment. Produces research reports and trade theses
3. **Strategy Agents** — three independent strategy modules (momentum/trend, sentiment-driven, quantitative/statistical) that each produce trade signals with confidence scores
4. **Risk Manager Agent** — enforces configurable position limits, stop-losses, drawdown limits, and portfolio correlation checks. Has veto power over all trades
5. **Execution Agent** — receives approved trade signals, handles order routing to IBKR/Kraken, manages fills, slippage, and retry logic
6. **Portfolio Agent** — tracks positions, P&L, performance metrics, and rebalancing

### AI Layer

- **Claude API** handles complex reasoning: research analysis, trade thesis generation, strategy arbitration when signals conflict, and end-of-day portfolio review
- **Local LLM (Ollama)** handles high-frequency lightweight tasks: quick sentiment scoring of headlines, technical indicator interpretation, and real-time signal filtering

## Data Flow

```
Market Data Agent
    | (price ticks, order book updates, volume spikes)
    v
Strategy Agents (3x parallel)
    | (trade signals with confidence scores)
    v
Orchestrator (Claude-powered arbitration when signals conflict)
    | (proposed trades)
    v
Risk Manager Agent (veto/approve/resize)
    | (approved orders)
    v
Execution Agent -> IBKR API / Kraken API
    | (fill confirmations)
    v
Portfolio Agent -> Discord alerts + Web dashboard
```

### Key Flows

- **Research flow**: Research Agent runs on a schedule (every 30 min during market hours, configurable). It pulls news via APIs, feeds them to Claude for analysis, and publishes research events that strategy agents consume
- **Trading flow**: Strategy agents independently emit signals. When multiple strategies agree, confidence is boosted. When they conflict, the orchestrator calls Claude to arbitrate based on current market context and research
- **Risk flow**: Every proposed trade passes through the Risk Manager before execution. It checks position sizing, portfolio exposure, daily loss limits, and correlation. It can veto, approve, or resize the trade
- **Monitoring flow**: All events (trades, signals, research, risk decisions) are published to both Discord (real-time alerts) and persisted to a SQLite database that the web dashboard reads

## Agent Interfaces (Protocols)

All agents are defined as Python Protocols for clean testing and mocking.

```python
# src/core/protocols.py

from typing import Protocol, AsyncIterator
from src.core.models import (
    Signal, Trade, Order, Fill, Position,
    ResearchReport, RiskDecision, MarketTick, PortfolioSnapshot
)

class MarketDataAgent(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def stream_ticks(self, symbols: list[str]) -> AsyncIterator[MarketTick]: ...
    async def get_order_book(self, symbol: str) -> dict: ...

class ResearchAgent(Protocol):
    async def run_research(self, symbols: list[str]) -> list[ResearchReport]: ...
    async def score_headline(self, headline: str) -> float: ...

class StrategyAgent(Protocol):
    name: str
    async def evaluate(self, symbol: str, market_data: list[MarketTick],
                       research: list[ResearchReport] | None = None) -> Signal | None: ...

class RiskManagerAgent(Protocol):
    async def evaluate_trade(self, signal: Signal,
                             portfolio: PortfolioSnapshot) -> RiskDecision: ...
    async def check_portfolio_health(self, portfolio: PortfolioSnapshot) -> list[str]: ...

class ExecutionAgent(Protocol):
    async def submit_order(self, order: Order) -> Fill: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def cancel_all(self) -> int: ...

class PortfolioAgent(Protocol):
    async def get_snapshot(self) -> PortfolioSnapshot: ...
    async def record_fill(self, fill: Fill) -> None: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_pnl(self, period: str) -> float: ...
```

### Why Protocols over ABCs

- No inheritance required — agents just need to match the shape
- Test mocks are trivial: just create a class with the same methods
- Multiple implementations (paper vs live) without subclassing
- Works naturally with `isinstance()` checks at runtime via `runtime_checkable`

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ (asyncio) |
| Stocks broker | Interactive Brokers (ib_insync) |
| Crypto exchange | Kraken (krakenex + pykrakenapi) |
| AI (complex) | Claude API (anthropic SDK) |
| AI (fast) | Ollama (local LLM) |
| Web dashboard | FastAPI + HTMX/Alpine.js |
| Database | SQLite + SQLAlchemy |
| Alerts | discord.py |
| Data analysis | pandas, numpy, ta-lib |
| Scheduling | APScheduler |
| Testing | pytest, pytest-asyncio, pytest-cov |

## Project Structure

```
trade-bot/
├── config/
│   ├── settings.yaml          # All configurable params (risk, strategies, API keys ref)
│   └── strategies/            # Per-strategy config files
├── src/
│   ├── agents/
│   │   ├── market_data.py     # Real-time price/volume streaming
│   │   ├── research.py        # News/sentiment analysis (Claude)
│   │   ├── strategies/
│   │   │   ├── momentum.py
│   │   │   ├── sentiment.py
│   │   │   └── quantitative.py
│   │   ├── risk_manager.py    # Position limits, stop-losses, veto logic
│   │   ├── execution.py       # Order routing, fill management
│   │   └── portfolio.py       # Position tracking, P&L
│   ├── core/
│   │   ├── orchestrator.py    # Central coordinator, signal arbitration
│   │   ├── event_bus.py       # Async event system
│   │   └── models.py          # Shared data models (Trade, Signal, Order, etc.)
│   ├── integrations/
│   │   ├── ibkr.py            # IBKR API wrapper
│   │   ├── kraken.py          # Kraken API wrapper
│   │   ├── claude_client.py   # Claude API wrapper
│   │   └── ollama_client.py   # Local LLM wrapper
│   ├── dashboard/
│   │   ├── app.py             # FastAPI web dashboard
│   │   ├── static/            # Frontend assets
│   │   └── templates/
│   ├── discord_bot/
│   │   └── bot.py             # Discord alerts + commands
│   └── db/
│       ├── database.py        # SQLAlchemy setup
│       └── models.py          # DB schema
├── tests/
├── docs/
├── .env.example               # API key template
├── pyproject.toml
└── main.py                    # Entry point
```

## Risk Management

### Configurable Parameters (settings.yaml)

- `max_position_pct`: max % of portfolio in a single trade (default: 2%)
- `max_sector_exposure_pct`: max % in one sector/asset class (default: 20%)
- `daily_loss_limit_pct`: halt trading if daily loss exceeds this (default: 3%)
- `weekly_drawdown_limit_pct`: reduce position sizes if weekly drawdown hits this (default: 5%)
- `max_open_positions`: cap on concurrent positions (default: 10)
- `stop_loss_pct`: default stop-loss per trade (default: 5%, overridable per strategy)
- `trailing_stop_pct`: trailing stop option (default: off)
- `max_correlation`: reject trades too correlated with existing positions (default: 0.7)

### Risk Manager Veto Logic

1. Check position size against limits
2. Check portfolio exposure (sector, asset class, total)
3. Check daily/weekly P&L against loss limits
4. Check correlation with existing positions
5. If any check fails -> veto or resize the trade, log the reason

### Paper Trading Mode

- Toggled by a single config flag: `mode: paper | live`
- In paper mode, the Execution Agent simulates fills using real-time market data with realistic slippage modeling
- All other agents run identically — same research, same signals, same risk checks
- Paper trades are stored in the same DB with a `paper=True` flag
- Switch to live by changing one config value. No code changes needed.

### Kill Switch

- Discord command `/kill` or web dashboard button immediately cancels all open orders and halts trading
- Auto-triggers if daily loss limit is breached

## Monitoring

### Discord Bot

- **Trade alerts**: instant notification on every fill with entry price, size, strategy reasoning
- **Risk alerts**: notifications when positions are vetoed, loss limits approached, or kill switch triggered
- **Daily digest**: end-of-day summary — P&L, trades taken, portfolio snapshot (Claude generates a natural language summary)
- **Commands**: `/status`, `/kill`, `/pause`, `/resume`, `/performance [7d|30d|all]`, `/config set <key> <value>`

### Web Dashboard (FastAPI)

- Real-time portfolio view with positions and unrealized P&L
- Trade history table with filters (by strategy, asset, date range)
- Equity curve chart (portfolio value over time)
- Strategy breakdown — which strategies are performing
- Risk dashboard — current exposure, proximity to limits
- Research log — browse AI-generated research reports and trade theses

## Testing Strategy

### Protocol-Based Mocking

Each agent has a corresponding mock that implements the same Protocol, records all calls, and returns configurable responses. No patching needed — just inject the mock at construction.

### Test Layers

- **Unit tests**: each agent in isolation with mocked dependencies
- **Integration tests**: orchestrator wired to mock agents, verify full flow from market tick to execution
- **Backtest harness**: replay historical market data through the full pipeline in paper mode
- **Smoke tests**: hit real IBKR/Kraken APIs in paper mode to verify connectivity (run manually, not in CI)

### Test Tooling

- pytest + pytest-asyncio for async agent tests
- pytest-cov for coverage
- Factory functions to generate test data with sensible defaults
