# Trading Bot V2 — Architecture Redesign

**Date:** 2026-02-10
**Status:** Draft
**Goal:** Comprehensive upgrade across data ingestion, sentiment analysis, ML pipeline, risk management, strategy layer, analytics, and documentation — built on a protocol-first provider architecture for swappable implementations.

**Core Invariant:** Every component accepts a protocol-implementing class instantiated with a config object. For each service component, there are always three implementations: an **external client** (real API), a **local client** (self-hosted/free), and a **mock client** (for testing). The core system never changes regardless of which client is used.

**Type System:** All models, configs, and data structures use **Pydantic v2 `BaseModel`** — never plain dataclasses. This gives us runtime validation, JSON/YAML serialization, schema generation, and CLI integration for free.

**CLI Interface:** Every component is exposed via a documented CLI using **Typer** (built on Click). Each subsystem can be invoked, inspected, and tested independently from the command line.

**Testing Discipline:** Strict TDD throughout — write a failing test first, implement the code, verify the test passes. Target 100% unit test coverage, component test coverage, and integration test coverage.

---

## 0. Client Pattern & Testability

### The Rule

Every component in the system follows this pattern:

```
Protocol (interface)
    ├── ExternalClient (real API — paid, rate-limited)
    ├── LocalClient (self-hosted — Ollama, FinBERT, RSS)
    └── MockClient (deterministic — for tests)
```

Each client is instantiated with a **typed config dataclass**. The core system only ever sees the protocol — never the concrete class.

### Config Object Pattern

Every provider accepts a Pydantic model as config. Pydantic gives us runtime validation, serialization (`model_dump()` / `model_validate()`), JSON Schema generation, and env var loading for free:

```python
from pydantic import BaseModel, Field, SecretStr


class NewsProviderConfig(BaseModel):
    """Base configuration for any NewsProvider implementation."""
    model_config = ConfigDict(frozen=True)

    fetch_interval_seconds: int = Field(300, ge=1, description="Seconds between fetch cycles")
    max_articles_per_fetch: int = Field(50, ge=1, description="Max articles per fetch call")
    symbols_filter: list[str] | None = Field(None, description="Only fetch for these symbols")


class RSSConfig(NewsProviderConfig):
    """Config specific to RSS news provider."""
    feed_urls: list[str] = Field(default_factory=list, min_length=1)


class PolygonNewsConfig(NewsProviderConfig):
    """Config specific to Polygon.io news provider."""
    api_key: SecretStr = Field(..., description="Polygon.io API key")
    base_url: str = Field("https://api.polygon.io", description="API base URL")


class MockNewsConfig(NewsProviderConfig):
    """Config for mock news provider in tests."""
    canned_articles: list[Article] = Field(default_factory=list)
    should_fail: bool = False
    latency_ms: int = Field(0, ge=0)
```

**Why Pydantic everywhere:**

- **Validation**: `Field(ge=1)` catches bad config at startup, not at runtime
- **Serialization**: `config.model_dump()` → dict, `Config.model_validate(yaml_dict)` → typed config
- **Secrets**: `SecretStr` prevents API keys from leaking into logs
- **Schema**: `Config.model_json_schema()` auto-generates docs and CLI help text
- **Env vars**: `model_config = SettingsConfigDict(env_prefix="TRADEBOT_")` for 12-factor apps
- **Immutability**: `frozen=True` prevents accidental mutation

**All models use Pydantic — not just configs:**

```python
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import datetime


class MarketTick(BaseModel):
    """A single price observation."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    timestamp: datetime
    asset_type: AssetType
    bid: Decimal | None = None
    ask: Decimal | None = None


class Signal(BaseModel):
    """A trading signal from a strategy."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    strategy_name: str
    timestamp: datetime
    reasoning: str

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class Fill(BaseModel):
    """A completed trade execution."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    fill_price: Decimal = Field(gt=0)
    timestamp: datetime
    commission: Decimal = Field(default=Decimal("0"), ge=0)


class Position(BaseModel):
    """A current holding."""
    symbol: str
    quantity: Decimal = Field(gt=0)
    avg_entry_price: Decimal = Field(gt=0)
    current_price: Decimal = Field(gt=0)
    asset_type: AssetType
    sector: str | None = None

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.current_price - self.avg_entry_price) * self.quantity


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state."""
    model_config = ConfigDict(frozen=True)

    cash: Decimal = Field(ge=0)
    positions: list[Position]
    timestamp: datetime

    @property
    def total_value(self) -> Decimal:
        return self.cash + sum(p.market_value for p in self.positions)


class FeatureVector(BaseModel):
    """Named feature values for a symbol at a point in time."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: int
    features: dict[str, float]

    def to_array(self, feature_names: list[str]) -> list[float]:
        return [self.features.get(name, 0.0) for name in feature_names]

    def subset(self, feature_names: list[str]) -> "FeatureVector":
        return FeatureVector(
            symbol=self.symbol,
            timestamp=self.timestamp,
            features={k: v for k, v in self.features.items() if k in feature_names},
        )


class SentimentResult(BaseModel):
    """Sentiment score for a piece of text."""
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=-1.0, le=1.0)
    magnitude: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    reasoning: str | None = None


class Article(BaseModel):
    """A news article."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    body: str | None = None
    related_symbols: list[str]
    source: str
    url: str | None = None
    published_at: datetime


class Prediction(BaseModel):
    """An ML model prediction."""
    model_config = ConfigDict(frozen=True)

    direction: str  # "buy", "sell", "hold"
    confidence: float = Field(ge=0.0, le=1.0)
    model: str


class RiskContext(BaseModel):
    """Rich context passed to risk manager for every decision."""
    regime: VolatilityRegime
    correlation_matrix: dict[str, float]  # "BTC/USD:ETH/USD" -> 0.8
    strategy_stats: dict[str, "StrategyPerformance"]
    drawdown_from_peak: float = Field(ge=0.0, le=1.0)
    portfolio: PortfolioSnapshot
    daily_pnl: Decimal


class StrategyPerformance(BaseModel):
    """Rolling performance stats for a single strategy."""
    model_config = ConfigDict(frozen=True)

    name: str
    win_rate: float = Field(ge=0.0, le=1.0)
    avg_win: Decimal
    avg_loss: Decimal
    total_trades: int = Field(ge=0)
    recent_trades: int = Field(ge=0)
    recent_win_rate: float = Field(ge=0.0, le=1.0)


class BacktestResult(BaseModel):
    """Results from a backtest run."""
    total_ticks: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float | None = None
    initial_cash: float
    final_value: float
    equity_curve: list[float]

    @property
    def win_rate(self) -> float:
        total = self.winning_trades + self.losing_trades
        return self.winning_trades / total if total > 0 else 0.0

    @property
    def return_pct(self) -> float:
        return (self.final_value - self.initial_cash) / self.initial_cash * 100
```

### Client Implementation Pattern

Every provider follows the same structure. Here's the canonical example:

```python
# --- External client (real API) ---

class PolygonNewsProvider:
    """Fetches news from Polygon.io REST API."""

    name = "polygon"

    def __init__(self, config: PolygonNewsConfig, client: HttpClient) -> None:
        self._config = config
        self._client = client  # httpx.AsyncClient injected, not created

    async def fetch_articles(self, symbol: str, since: datetime) -> list[Article]:
        resp = await self._client.get(
            f"{self._config.base_url}/v2/reference/news",
            params={"ticker": symbol, "published_utc.gte": since.isoformat()},
            headers={"Authorization": f"Bearer {self._config.api_key}"},
        )
        return [self._parse(a) for a in resp.json()["results"]]

    async def health_check(self) -> bool:
        resp = await self._client.get(f"{self._config.base_url}/v1/marketstatus/now")
        return resp.status_code == 200

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=5)


# --- Local client (free/self-hosted) ---

class RSSNewsProvider:
    """Fetches news from RSS feeds. No API key needed."""

    name = "rss"

    def __init__(self, config: RSSConfig, client: HttpClient) -> None:
        self._config = config
        self._client = client

    async def fetch_articles(self, symbol: str, since: datetime) -> list[Article]:
        articles = []
        for feed_url in self._config.feed_urls:
            resp = await self._client.get(feed_url)
            parsed = feedparser.parse(resp.text)
            articles.extend(self._filter(parsed.entries, symbol, since))
        return articles[:self._config.max_articles_per_fetch]

    async def health_check(self) -> bool:
        return True  # RSS feeds are always "up"

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=60)


# --- Mock client (for testing) ---

class MockNewsProvider:
    """Deterministic news provider for tests."""

    name = "mock"

    def __init__(self, config: MockNewsConfig | None = None) -> None:
        self._config = config or MockNewsConfig()
        self.fetch_count = 0  # Track calls for assertions
        self.last_symbol: str | None = None

    async def fetch_articles(self, symbol: str, since: datetime) -> list[Article]:
        self.fetch_count += 1
        self.last_symbol = symbol

        if self._config.should_fail:
            raise ConnectionError("Mock failure")

        if self._config.latency_ms:
            await asyncio.sleep(self._config.latency_ms / 1000)

        return [
            a for a in self._config.canned_articles
            if symbol in a.related_symbols and a.published_at >= since
        ]

    async def health_check(self) -> bool:
        return not self._config.should_fail

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=9999)
```

### Dependency Injection

Components never instantiate their own dependencies. Everything is injected:

```python
# WRONG — creates its own client, untestable
class SentimentPipeline:
    def __init__(self):
        self._news = RSSNewsProvider(...)      # Hardcoded
        self._analyzer = OllamaSentiment(...)   # Hardcoded

# RIGHT — accepts protocols, any implementation works
class SentimentPipeline:
    def __init__(
        self,
        news: NewsProvider,           # Protocol
        analyzer: SentimentAnalyzer,  # Protocol
        store: SentimentStore,        # Protocol
        config: SentimentPipelineConfig,
    ) -> None:
        self._news = news
        self._analyzer = analyzer
        self._store = store
        self._config = config
```

### HttpClient Protocol

Even the HTTP client itself is a protocol, so providers don't depend on httpx directly:

```python
@runtime_checkable
class HttpClient(Protocol):
    """Minimal async HTTP client interface."""

    async def get(self, url: str, **kwargs) -> HttpResponse: ...
    async def post(self, url: str, **kwargs) -> HttpResponse: ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


# Real implementation wraps httpx
class HttpxClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def get(self, url: str, **kwargs) -> HttpResponse:
        resp = await self._client.get(url, **kwargs)
        return HttpResponse(status_code=resp.status_code, text=resp.text)


# Mock for tests — no network calls ever
class MockHttpClient:
    def __init__(self) -> None:
        self.responses: dict[str, HttpResponse] = {}
        self.calls: list[tuple[str, str, dict]] = []

    def stub(self, url_pattern: str, response: HttpResponse) -> None:
        self.responses[url_pattern] = response

    async def get(self, url: str, **kwargs) -> HttpResponse:
        self.calls.append(("GET", url, kwargs))
        for pattern, response in self.responses.items():
            if pattern in url:
                return response
        return HttpResponse(status_code=404, text="")
```

### Applied Across All Components

This pattern applies to **every** component in the system:

| Component | Protocol | External | Local | Mock |
|-----------|----------|----------|-------|------|
| News | `NewsProvider` | Polygon, Benzinga | RSS, Reddit, NewsAPI | `MockNewsProvider` |
| Sentiment | `SentimentAnalyzer` | Claude | Ollama, FinBERT | `MockSentimentAnalyzer` |
| On-chain | `OnChainProvider` | Glassnode, Nansen | Blockchair | `MockOnChainProvider` |
| Market data | `MarketDataProvider` | IBKR, Polygon | Kraken, Binance, Yahoo | `MockMarketDataProvider` |
| Features | `FeatureProvider` | — | TA-Lib, computed | `MockFeatureProvider` |
| ML models | `ModelProvider` | Cloud GPU | XGBoost, LSTM | `MockModelProvider` |
| Position sizing | `PositionSizer` | — | Fixed, Kelly, VolTarget | `MockPositionSizer` |
| HTTP | `HttpClient` | httpx | — | `MockHttpClient` |
| Database | `DataStore` | PostgreSQL | SQLite | `MockDataStore` (in-memory dict) |
| Event bus | `EventBus` | — | AsyncIO EventBus | `MockEventBus` (captures events) |

---

## 1. Provider Architecture

### Problem

The current bot has data sources wired directly into agents and strategies. Adding a new data source means touching business logic. Swapping a free API for a paid one requires code changes throughout.

### Solution

A **protocol layer** defines what each data source type must provide. Concrete implementations wrap specific clients, each accepting a typed config. A **ProviderRegistry** instantiates providers from config at startup.

### Directory Structure

```
src/providers/
├── protocols.py          # All Protocol definitions
├── configs.py            # All config dataclasses
├── registry.py           # Provider discovery & instantiation
├── news/
│   ├── rss.py            # Local: Free RSS feeds
│   ├── reddit.py         # Local: Reddit API (free tier)
│   ├── newsapi.py        # Local: NewsAPI.org (free 100 req/day)
│   ├── polygon.py        # External: Polygon.io (premium)
│   └── mock.py           # Mock: deterministic test provider
├── sentiment/
│   ├── ollama.py         # Local: Ollama for bulk scoring
│   ├── finbert.py        # Local: HuggingFace FinBERT
│   ├── claude.py         # External: Claude for deep analysis
│   └── mock.py           # Mock: deterministic test analyzer
├── onchain/
│   ├── blockchair.py     # Local: Free blockchain explorer
│   ├── glassnode.py      # External: Premium on-chain analytics
│   └── mock.py           # Mock: deterministic test provider
├── features/
│   ├── technical.py      # Local: TA-Lib indicators
│   ├── computed.py       # Local: Derived/composite features
│   └── mock.py           # Mock: deterministic test features
└── market_data/
    ├── kraken.py         # Local: Kraken REST (free)
    ├── binance.py        # Local: Binance REST (free)
    ├── yfinance.py       # Local: Yahoo Finance (free)
    ├── polygon.py        # External: Polygon.io (premium)
    └── mock.py           # Mock: deterministic test feed
```

### Protocol Definitions

Every protocol is `@runtime_checkable` so tests can verify compliance with `isinstance()`. Every implementation accepts a typed config as its first argument.

```python
from typing import Protocol, runtime_checkable
from datetime import datetime
from decimal import Decimal


# --- News ---

@runtime_checkable
class NewsProvider(Protocol):
    """Fetches news articles for a given symbol."""

    name: str

    async def fetch_articles(
        self, symbol: str, since: datetime
    ) -> list[Article]:
        """Return articles mentioning symbol published after `since`."""
        ...

    async def health_check(self) -> bool:
        """Return True if the provider is reachable and functional."""
        ...

    def rate_limit(self) -> RateLimit:
        """Declare this provider's rate limits for scheduling."""
        ...


# --- Sentiment ---

@runtime_checkable
class SentimentAnalyzer(Protocol):
    """Scores text for financial sentiment."""

    name: str

    async def score(self, text: str, symbol: str) -> SentimentResult:
        """Score a single piece of text. Returns -1.0 to 1.0."""
        ...

    async def score_batch(
        self, texts: list[str], symbol: str
    ) -> list[SentimentResult]:
        """Score multiple texts efficiently."""
        ...


# --- On-Chain ---

@runtime_checkable
class OnChainProvider(Protocol):
    """Provides blockchain-level metrics for crypto assets."""

    name: str

    async def get_metrics(
        self, symbol: str, since: datetime
    ) -> list[OnChainMetric]:
        ...

    async def health_check(self) -> bool:
        ...


# --- Market Data ---

@runtime_checkable
class MarketDataProvider(Protocol):
    """Provides price and volume data."""

    name: str

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]:
        ...

    async def get_ohlc(
        self, symbol: str, interval: str, since: datetime
    ) -> list[OHLCBar]:
        ...

    async def health_check(self) -> bool:
        ...


# --- Features ---

@runtime_checkable
class FeatureProvider(Protocol):
    """Computes derived features from raw data."""

    name: str

    def required_inputs(self) -> list[str]:
        """Declare what raw data this provider needs."""
        ...

    async def compute(
        self, symbol: str, raw_data: dict
    ) -> dict[str, float]:
        """Return feature_name -> value pairs."""
        ...


# --- ML Models ---

@runtime_checkable
class ModelProvider(Protocol):
    """Trainable model that produces trade predictions."""

    name: str

    async def predict(self, features: FeatureVector) -> Prediction:
        ...

    async def train(self, dataset: Dataset) -> TrainResult:
        ...

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        ...


# --- Position Sizing ---

@runtime_checkable
class PositionSizer(Protocol):
    """Determines order quantity given a signal and portfolio state."""

    name: str

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        ...


# --- Data Store ---

@runtime_checkable
class DataStore(Protocol):
    """Persistence layer for trades, signals, features."""

    async def initialize(self) -> None: ...
    async def save_trade(self, trade: TradeRecord) -> None: ...
    async def list_trades(self, limit: int = 100) -> list[TradeRecord]: ...
    async def save_signal(self, signal: SignalRecord) -> None: ...
    async def save_features(self, symbol: str, ts: int, features: dict[str, float]) -> None: ...
    async def load_features(self, symbol: str, ts: int) -> dict[str, float]: ...
```

### Provider Registry

The registry reads `settings.yaml`, builds the appropriate config dataclass, and instantiates the correct provider:

```python
class ProviderRegistry:
    """Discovers and instantiates providers from configuration."""

    def __init__(self) -> None:
        self._providers: dict[type, Any] = {}

    @classmethod
    def from_yaml(cls, path: Path) -> ProviderRegistry:
        """Build registry from settings.yaml provider config."""
        raw = yaml.safe_load(path.read_text())
        registry = cls()

        for protocol_type, section in PROTOCOL_SECTIONS.items():
            section_config = raw.get("providers", {}).get(section, {})
            provider_name = section_config.get("provider")
            if provider_name:
                provider_cls = PROVIDER_MAP[section][provider_name]
                config_cls = CONFIG_MAP[section][provider_name]
                config = config_cls(**section_config.get("client_config", {}))
                http_client = HttpxClient()  # or injected
                registry.register(protocol_type, provider_cls(config=config, client=http_client))

        return registry

    @classmethod
    def for_testing(cls, **overrides) -> ProviderRegistry:
        """Build registry with all mock providers. Override specific ones."""
        registry = cls()
        registry.register(NewsProvider, MockNewsProvider())
        registry.register(SentimentAnalyzer, MockSentimentAnalyzer())
        registry.register(OnChainProvider, MockOnChainProvider())
        registry.register(MarketDataProvider, MockMarketDataProvider())
        registry.register(FeatureProvider, MockFeatureProvider())
        registry.register(ModelProvider, MockModelProvider())
        registry.register(PositionSizer, MockPositionSizer())
        registry.register(DataStore, MockDataStore())

        for protocol_type, instance in overrides.items():
            registry.register(protocol_type, instance)

        return registry

    def register(self, protocol_type: type, instance: Any) -> None:
        assert isinstance(instance, protocol_type)
        self._providers[protocol_type] = instance

    def get(self, protocol_type: type[T]) -> T:
        return self._providers[protocol_type]
```

### Configuration Example

```yaml
# settings.yaml additions
providers:
  news:
    provider: rss              # swap to "polygon" later
    client_config:
      feed_urls:
        - https://feeds.finance.yahoo.com/rss/2.0/headline
        - https://www.coindesk.com/arc/outboundfeeds/rss/
      fetch_interval_seconds: 300

  sentiment:
    provider: ollama           # swap to "claude" for premium
    client_config:
      model: llama3.2
      base_url: http://localhost:11434

  onchain:
    provider: blockchair       # swap to "glassnode" later
    client_config:
      base_url: https://api.blockchair.com

  market_data:
    provider: kraken
    client_config: {}

  position_sizer:
    provider: fixed            # swap to "kelly" or "vol_targeted"
    client_config:
      position_pct: 2.0
```

---

## 2. Sentiment Analysis Pipeline

### Problem

The sentiment strategy currently returns `None` when no research reports exist. There is no continuous stream of sentiment data feeding the bot.

### Solution

A multi-stage pipeline: fetch articles from news providers, deduplicate and buffer them, score with sentiment analyzers, aggregate into rolling per-symbol scores, and persist for both live trading and backtesting.

### Pipeline Architecture

```
News Providers (RSS, Reddit, NewsAPI)
        │
        ▼
   ArticleBuffer          ← deduplicates, queues by symbol
        │
        ▼
   SentimentAnalyzer      ← Ollama (fast/free) or FinBERT (local)
        │
        ▼
   SentimentAggregator    ← time-weighted rolling scores per symbol
        │
        ▼
   SentimentStore (DB)    ← persisted for backtesting & features
        │
        ▼
   Strategies consume     ← sentiment strategy gets real data
```

### Directory Structure

```
src/sentiment/
├── pipeline.py           # Orchestrates the full flow
├── article_buffer.py     # Dedup, grouping, queueing
├── aggregator.py         # Time-weighted rolling scores
└── store.py              # DB persistence layer
```

### Key Components

#### ArticleBuffer

Handles deduplication and grouping of articles from multiple providers:

```python
class ArticleBuffer:
    """Deduplicates and queues articles by symbol."""

    def __init__(self, max_age: timedelta = timedelta(hours=24)) -> None:
        self._seen_hashes: set[str] = set()
        self._queue: dict[str, list[Article]] = defaultdict(list)
        self._max_age = max_age

    async def ingest(self, articles: list[Article]) -> int:
        """Add articles, skipping duplicates. Returns count of new articles."""
        new_count = 0
        for article in articles:
            content_hash = hashlib.sha256(
                article.title.encode() + article.body[:200].encode()
            ).hexdigest()

            if content_hash not in self._seen_hashes:
                self._seen_hashes.add(content_hash)
                for symbol in article.related_symbols:
                    self._queue[symbol].append(article)
                new_count += 1

        return new_count

    def drain(self, symbol: str) -> list[Article]:
        """Return and clear queued articles for a symbol."""
        articles = self._queue.pop(symbol, [])
        return articles
```

#### SentimentAggregator

Computes time-weighted rolling sentiment per symbol:

```python
class SentimentAggregator:
    """Time-weighted rolling sentiment scores."""

    def __init__(
        self,
        decay: str = "exponential",  # or "linear"
        half_life_hours: float = 6.0,
    ) -> None:
        self._scores: dict[str, list[SentimentResult]] = defaultdict(list)
        self._decay = decay
        self._half_life = timedelta(hours=half_life_hours)

    def add_scores(self, symbol: str, scores: list[SentimentResult]) -> None:
        self._scores[symbol].extend(scores)

    def aggregate(self, symbol: str, now: datetime) -> float:
        """Return weighted average sentiment for symbol."""
        scores = self._scores.get(symbol, [])
        if not scores:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for result in scores:
            age = now - result.timestamp
            if self._decay == "exponential":
                weight = 2 ** (-age / self._half_life)
            else:
                weight = max(0, 1 - age / (self._half_life * 4))

            weighted_sum += result.score * weight * result.magnitude
            weight_total += weight

        return weighted_sum / weight_total if weight_total > 0 else 0.0
```

### Two-Tier Scoring Strategy

- **Tier 1 (bulk):** Ollama or FinBERT scores every article as it arrives. Fast, free, handles volume. Good enough for the rolling aggregate.
- **Tier 2 (deep):** Claude is called only when:
  - The orchestrator detects conflicting signals between strategies
  - A signal confidence is in the "uncertain" zone (0.4–0.6)
  - Article volume spikes (possible major event)
  - On demand via dashboard/Discord command

This keeps Claude API costs near zero during normal operation while preserving access to deep reasoning when it matters.

### Rate-Limit Scheduling

Each news provider declares its limits. The pipeline scheduler respects them:

| Provider | Fetch Interval | Daily Limit | Notes |
|----------|---------------|-------------|-------|
| RSS | 5 min | Unlimited | Multiple feed URLs |
| Reddit | 2 min | ~1000 req/day | Free API tier |
| NewsAPI | 15 min | 100 req/day | Free tier, upgrade to 1000 |

### Database Schema

```sql
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'rss', 'reddit', 'newsapi'
    title TEXT NOT NULL,
    body TEXT,
    url TEXT,
    content_hash TEXT NOT NULL,
    published_at DATETIME NOT NULL,
    fetched_at DATETIME NOT NULL
);

CREATE TABLE sentiment_scores (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    article_id TEXT NOT NULL REFERENCES articles(id),
    analyzer TEXT NOT NULL,          -- 'ollama', 'finbert', 'claude'
    score FLOAT NOT NULL,           -- -1.0 to 1.0
    magnitude FLOAT NOT NULL,       -- strength of language, 0.0 to 1.0
    reasoning TEXT,                 -- why this score (from LLM analyzers)
    scored_at DATETIME NOT NULL,
    UNIQUE(article_id, analyzer)
);

CREATE INDEX idx_sentiment_symbol_time ON sentiment_scores(symbol, scored_at);
```

---

## 3. Feature Store & ML Pipeline

### Problem

Strategies currently compute their own indicators inline from raw ticks. There is no shared feature computation, no persistence for backtesting, and no infrastructure for ML model training.

### Solution

A centralized **FeatureEngine** computes features from all data sources, stores them in a **FeatureStore** (DB), and serves them to both live strategies and offline ML training.

### Architecture

```
Market Ticks ──┐
Sentiment ─────┤
On-Chain ──────┤──▶  FeatureEngine  ──▶  FeatureStore (DB)
Technical ─────┘         │                     │
                         │              ┌──────┴──────┐
                         ▼              ▼             ▼
                  Live Strategies    ML Training    Backtester
```

### Directory Structure

```
src/ml/
├── protocols.py          # ModelProvider protocol
├── feature_engine.py     # Computes & stores all features
├── feature_store.py      # DB read/write for feature vectors
├── trainer.py            # Walk-forward training loop
├── evaluation.py         # Sharpe, drawdown, win rate per model
├── serving.py            # Loads trained model, serves predictions
├── dataset.py            # Builds train/test datasets from store
└── models/
    ├── xgboost_model.py  # XGBoost classifier (local, fast, tabular)
    ├── lstm_model.py      # PyTorch LSTM (sequential patterns)
    └── ensemble.py        # Weighted combination of model outputs
```

### Feature Categories

#### Technical (from TA-Lib)

| Feature | Description | Lookback |
|---------|-------------|----------|
| `rsi_14` | Relative Strength Index, 14 periods | 14 |
| `macd_signal` | MACD signal line crossover | 26 |
| `bbands_position` | Where price sits in Bollinger Bands (0-1) | 20 |
| `atr_14` | Average True Range (volatility) | 14 |
| `obv_slope` | On-Balance Volume trend direction | 10 |
| `vwap_deviation` | Distance from VWAP as % | intraday |
| `sma_5`, `sma_14`, `sma_50`, `sma_200` | Simple moving averages | varies |
| `adx_14` | Average Directional Index (trend strength) | 14 |

#### Sentiment (from sentiment pipeline)

| Feature | Description |
|---------|-------------|
| `sentiment_avg_6h` | Rolling weighted sentiment, 6hr half-life |
| `sentiment_avg_24h` | Rolling weighted sentiment, 24hr half-life |
| `sentiment_velocity` | Rate of change of sentiment score |
| `article_volume_ratio` | Current article count / rolling avg count |
| `sentiment_dispersion` | Std dev of scores (disagreement among sources) |

#### Cross-Asset

| Feature | Description |
|---------|-------------|
| `btc_eth_corr_30d` | 30-day rolling correlation BTC/ETH |
| `btc_momentum_lead` | BTC momentum signal (for altcoin strategies) |
| `sector_momentum` | Avg momentum of related assets |
| `market_breadth` | % of tracked symbols above SMA_50 |

#### Regime

| Feature | Description |
|---------|-------------|
| `volatility_regime` | Categorical: low (0), medium (1), high (2) |
| `trend_regime` | Categorical: trending (1), ranging (0) |
| `vol_percentile_30d` | Current vol as percentile of last 30 days |

#### On-Chain (crypto only)

| Feature | Description |
|---------|-------------|
| `exchange_inflow_ratio` | Coins moving to exchanges / total volume |
| `active_addresses_trend` | 7d change in active addresses |
| `whale_tx_count` | Large transactions (>$100k) in last 24h |

### Feature Store Schema

```sql
CREATE TABLE features (
    symbol TEXT NOT NULL,
    timestamp INT NOT NULL,           -- Unix timestamp
    feature_name TEXT NOT NULL,
    value FLOAT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (symbol, timestamp, feature_name)
);

CREATE INDEX idx_features_symbol ON features(symbol, feature_name, timestamp);
```

### FeatureEngine

```python
class FeatureEngine:
    """Computes and stores features from all data sources."""

    def __init__(
        self,
        providers: list[FeatureProvider],
        store: FeatureStore,
    ) -> None:
        self._providers = providers
        self._store = store

    async def compute_and_store(
        self, symbol: str, raw_data: dict, timestamp: int
    ) -> FeatureVector:
        """Run all feature providers and persist results."""
        all_features: dict[str, float] = {}

        # Run all providers in parallel
        tasks = [p.compute(symbol, raw_data) for p in self._providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, result in zip(self._providers, results):
            if isinstance(result, Exception):
                logger.warning(f"Feature provider {provider.name} failed: {result}")
                continue
            all_features.update(result)

        # Persist
        await self._store.save(symbol, timestamp, all_features)

        return FeatureVector(
            symbol=symbol, timestamp=timestamp, features=all_features
        )

    async def get_vector(self, symbol: str, timestamp: int) -> FeatureVector:
        """Retrieve a stored feature vector."""
        features = await self._store.load(symbol, timestamp)
        return FeatureVector(symbol=symbol, timestamp=timestamp, features=features)
```

### FeatureVector

```python
@dataclass(frozen=True)
class FeatureVector:
    symbol: str
    timestamp: int
    features: dict[str, float]

    def to_array(self, feature_names: list[str]) -> list[float]:
        """Convert to ordered array for model input."""
        return [self.features.get(name, 0.0) for name in feature_names]

    def subset(self, feature_names: list[str]) -> FeatureVector:
        """Return a new vector with only the requested features."""
        return FeatureVector(
            symbol=self.symbol,
            timestamp=self.timestamp,
            features={k: v for k, v in self.features.items() if k in feature_names},
        )
```

### ML Models

#### XGBoost (primary)

Best for tabular feature data. Fast to train, interpretable feature importance.

```python
class XGBoostModel:
    """XGBoost classifier for trade direction prediction."""

    name = "xgboost"

    def __init__(self, params: dict | None = None) -> None:
        self._params = params or {
            "objective": "multi:softprob",
            "num_class": 3,            # buy, sell, hold
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 200,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        }
        self._model: xgb.XGBClassifier | None = None
        self._feature_names: list[str] = []

    async def predict(self, features: FeatureVector) -> Prediction:
        arr = features.to_array(self._feature_names)
        probas = self._model.predict_proba([arr])[0]
        # probas = [p_buy, p_sell, p_hold]
        direction = ["buy", "sell", "hold"][probas.argmax()]
        confidence = float(probas.max())
        return Prediction(
            direction=direction, confidence=confidence, model=self.name
        )

    async def train(self, dataset: Dataset) -> TrainResult:
        X, y = dataset.to_arrays(self._feature_names)
        self._model = xgb.XGBClassifier(**self._params)
        self._model.fit(X, y)
        importance = dict(zip(self._feature_names, self._model.feature_importances_))
        return TrainResult(model=self.name, feature_importance=importance)

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        X, y = dataset.to_arrays(self._feature_names)
        predictions = self._model.predict(X)
        accuracy = (predictions == y).mean()
        return EvalMetrics(model=self.name, accuracy=accuracy)
```

#### LSTM (sequential)

Captures temporal patterns that XGBoost misses. Takes sequences of feature vectors.

```python
class LSTMModel:
    """PyTorch LSTM for sequential feature pattern recognition."""

    name = "lstm"

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        sequence_length: int = 20,
    ) -> None:
        self._sequence_length = sequence_length
        self._model = LSTMNetwork(input_size, hidden_size, num_layers, num_classes=3)
        self._optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
```

#### Ensemble

Combines XGBoost and LSTM predictions with configurable weights:

```python
class EnsembleModel:
    """Weighted combination of multiple model predictions."""

    name = "ensemble"

    def __init__(
        self,
        models: list[ModelProvider],
        weights: list[float] | None = None,
    ) -> None:
        self._models = models
        self._weights = weights or [1.0 / len(models)] * len(models)

    async def predict(self, features: FeatureVector) -> Prediction:
        predictions = await asyncio.gather(
            *[m.predict(features) for m in self._models]
        )

        # Weighted vote
        direction_scores: dict[str, float] = defaultdict(float)
        for pred, weight in zip(predictions, self._weights):
            direction_scores[pred.direction] += pred.confidence * weight

        best = max(direction_scores, key=direction_scores.get)
        return Prediction(
            direction=best,
            confidence=direction_scores[best],
            model=self.name,
        )
```

### Walk-Forward Training

```python
class WalkForwardTrainer:
    """Train and evaluate models using walk-forward validation."""

    def __init__(
        self,
        model: ModelProvider,
        store: FeatureStore,
        train_window: timedelta = timedelta(days=180),
        test_window: timedelta = timedelta(days=30),
        step_size: timedelta = timedelta(days=30),
    ) -> None:
        self._model = model
        self._store = store
        self._train_window = train_window
        self._test_window = test_window
        self._step_size = step_size

    async def run(
        self, symbols: list[str], start: datetime, end: datetime
    ) -> list[WalkForwardResult]:
        """Execute walk-forward from start to end."""
        results = []
        cursor = start + self._train_window

        while cursor + self._test_window <= end:
            train_start = cursor - self._train_window
            train_end = cursor
            test_start = cursor
            test_end = cursor + self._test_window

            # Build datasets from feature store
            train_data = await self._store.build_dataset(
                symbols, train_start, train_end
            )
            test_data = await self._store.build_dataset(
                symbols, test_start, test_end
            )

            # Train and evaluate
            train_result = await self._model.train(train_data)
            eval_result = await self._model.evaluate(test_data)

            results.append(WalkForwardResult(
                train_period=(train_start, train_end),
                test_period=(test_start, test_end),
                train_result=train_result,
                eval_result=eval_result,
            ))

            cursor += self._step_size

        return results
```

### Configuration

```yaml
# settings.yaml additions
ml:
  feature_engine:
    providers:
      - technical
      - sentiment
      - cross_asset
      - regime

  training:
    train_window_days: 180
    test_window_days: 30
    step_size_days: 30
    retrain_schedule: "weekly"     # or "daily", "manual"

  models:
    xgboost:
      enabled: true
      weight: 0.6
      params:
        max_depth: 6
        learning_rate: 0.1
        n_estimators: 200
    lstm:
      enabled: true
      weight: 0.4
      params:
        hidden_size: 64
        num_layers: 2
        sequence_length: 20
```

---

## 4. Advanced Risk Management

### Problem

Current risk manager uses static checks: daily loss limit and max positions count. It does not adapt to market conditions, does not account for correlation between holdings, and uses fixed position sizing.

### Solution

A dynamic risk system that adjusts limits based on volatility regime, tracks correlation exposure, sizes positions using Kelly criterion, and includes a drawdown circuit breaker.

### New Data Models

```python
@dataclass
class RiskContext:
    """Rich context passed to risk manager for every decision."""
    regime: VolatilityRegime              # from feature store
    correlation_matrix: dict[tuple[str, str], float]
    strategy_stats: dict[str, StrategyPerformance]
    drawdown_from_peak: float             # 0.0 to 1.0
    portfolio: PortfolioSnapshot
    daily_pnl: Decimal


@dataclass
class StrategyPerformance:
    """Rolling performance stats for a single strategy."""
    name: str
    win_rate: float                       # 0.0 to 1.0
    avg_win: Decimal
    avg_loss: Decimal
    total_trades: int
    recent_trades: int                    # last N trades
    recent_win_rate: float                # win rate of last N


class VolatilityRegime(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

### Dynamic Position Sizing

Three implementations of the `PositionSizer` protocol:

```python
class FixedPositionSizer:
    """Current behavior: fixed % of portfolio per trade."""
    name = "fixed"

    def __init__(self, position_pct: float = 2.0) -> None:
        self._pct = position_pct

    async def compute_size(
        self, signal: Signal, portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        trade_value = portfolio.total_value * Decimal(str(self._pct)) / 100
        return min(trade_value, portfolio.cash)


class KellyPositionSizer:
    """Kelly criterion: size based on edge and payoff ratio."""
    name = "kelly"

    def __init__(self, kelly_multiplier: float = 0.5) -> None:
        # Half-Kelly is standard — full Kelly is too volatile
        self._multiplier = kelly_multiplier

    async def compute_size(
        self, signal: Signal, portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        stats = risk_context.strategy_stats.get(signal.strategy_name)
        if not stats or stats.total_trades < 20:
            # Not enough data — fall back to 1%
            return portfolio.total_value * Decimal("0.01")

        win_prob = Decimal(str(stats.win_rate))
        loss_prob = 1 - win_prob

        if stats.avg_loss == 0:
            return portfolio.total_value * Decimal("0.01")

        payoff_ratio = stats.avg_win / abs(stats.avg_loss)
        kelly = (win_prob * payoff_ratio - loss_prob) / payoff_ratio
        kelly = max(Decimal("0"), kelly * Decimal(str(self._multiplier)))

        # Cap at 5% regardless
        kelly = min(kelly, Decimal("0.05"))

        trade_value = portfolio.total_value * kelly
        return min(trade_value, portfolio.cash)


class VolTargetedPositionSizer:
    """Target a specific portfolio volatility contribution per trade."""
    name = "vol_targeted"

    def __init__(self, target_vol_contribution: float = 0.01) -> None:
        self._target = target_vol_contribution

    async def compute_size(
        self, signal: Signal, portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        # Size inversely proportional to asset volatility
        # High vol asset → smaller position, low vol → larger
        atr = risk_context.portfolio  # would pull ATR from feature store
        # Implementation uses ATR-based vol estimate
        ...
```

### Regime-Aware Risk Limits

The risk manager dynamically adjusts its limits based on the current volatility regime:

```python
REGIME_LIMITS = {
    VolatilityRegime.LOW: {
        "max_position_pct": 3.0,
        "stop_loss_pct": 4.0,
        "max_open_positions": 12,
        "daily_loss_limit_pct": 4.0,
    },
    VolatilityRegime.MEDIUM: {
        "max_position_pct": 2.0,
        "stop_loss_pct": 5.0,
        "max_open_positions": 8,
        "daily_loss_limit_pct": 3.0,
    },
    VolatilityRegime.HIGH: {
        "max_position_pct": 1.0,
        "stop_loss_pct": 8.0,
        "max_open_positions": 4,
        "daily_loss_limit_pct": 2.0,
    },
}
```

### Correlation-Aware Exposure

Before approving a trade, check correlation with existing positions:

```python
async def _check_correlation(
    self, symbol: str, risk_context: RiskContext
) -> RiskDecision:
    """Veto or reduce size if too correlated with existing holdings."""
    for position in risk_context.portfolio.positions:
        pair = (symbol, position.symbol)
        correlation = risk_context.correlation_matrix.get(pair, 0.0)

        if abs(correlation) > self._max_correlation:
            return RiskDecision(
                action=RiskAction.VETO,
                reason=(
                    f"{symbol} has {correlation:.2f} correlation "
                    f"with existing position {position.symbol}"
                ),
            )

        if abs(correlation) > self._max_correlation * 0.7:
            # Reduce size proportionally
            reduction = correlation / self._max_correlation
            return RiskDecision(
                action=RiskAction.RESIZE,
                reason=f"Reducing size due to {correlation:.2f} correlation with {position.symbol}",
                adjusted_quantity=None,  # Orchestrator applies reduction
                size_multiplier=Decimal(str(1 - reduction)),
            )

    return RiskDecision(action=RiskAction.APPROVE, reason="Correlation check passed")
```

### Drawdown Circuit Breaker

```python
class DrawdownCircuitBreaker:
    """Halts trading when portfolio drawdown exceeds threshold."""

    def __init__(
        self,
        max_drawdown_pct: float = 10.0,
        cooldown_hours: float = 24.0,
    ) -> None:
        self._max_drawdown = max_drawdown_pct / 100
        self._cooldown = timedelta(hours=cooldown_hours)
        self._peak_value: Decimal = Decimal("0")
        self._tripped_at: datetime | None = None

    def update(self, portfolio_value: Decimal, now: datetime) -> None:
        self._peak_value = max(self._peak_value, portfolio_value)

    def is_tripped(self, portfolio_value: Decimal, now: datetime) -> bool:
        if self._tripped_at:
            if now - self._tripped_at < self._cooldown:
                return True
            # Cooldown expired — reset
            self._tripped_at = None
            self._peak_value = portfolio_value

        if self._peak_value == 0:
            return False

        drawdown = float((self._peak_value - portfolio_value) / self._peak_value)
        if drawdown >= self._max_drawdown:
            self._tripped_at = now
            return True

        return False
```

### Configuration

```yaml
# settings.yaml additions
risk:
  position_sizer: kelly          # or "fixed", "vol_targeted"
  kelly_multiplier: 0.5
  max_correlation: 0.7
  regime_aware: true
  circuit_breaker:
    max_drawdown_pct: 10.0
    cooldown_hours: 24.0
```

---

## 5. Enhanced Strategy Layer

### Problem

Strategies compute their own indicators from raw ticks, don't benefit from the feature store, and use simple majority voting for consensus. No ML-driven strategies exist.

### Solution

Refactor strategies to consume `FeatureVector` objects from the feature store. Add ML-driven and event-driven strategies. Replace majority voting with weighted consensus that accounts for strategy accuracy and market regime.

### Updated Strategy Protocol

```python
class Strategy(Protocol):
    """Generates trading signals from feature vectors."""

    name: str

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None:
        """Evaluate features and return a signal or None."""
        ...

    def required_features(self) -> list[str]:
        """Declare which features this strategy needs."""
        ...
```

### Existing Strategy Adapters

The three existing strategies get thin adapters that extract their needed features from the vector:

```python
class MomentumStrategyAdapter:
    """Wraps existing MomentumStrategy to consume FeatureVector."""

    name = "momentum"

    def required_features(self) -> list[str]:
        return ["sma_5", "sma_14"]

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None:
        sma_short = features.features.get("sma_5")
        sma_long = features.features.get("sma_14")

        if sma_short is None or sma_long is None:
            return None

        if sma_short > sma_long:
            spread = abs(sma_short - sma_long) / sma_long
            confidence = min(spread * 10, 1.0)
            return Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence=confidence,
                strategy_name=self.name,
                reasoning=f"SMA5 ({sma_short:.2f}) > SMA14 ({sma_long:.2f})",
                timestamp=datetime.now(UTC),
            )
        # ... sell logic mirrors
```

### New: ML Ensemble Strategy

Delegates to the trained ML model ensemble:

```python
class MLEnsembleStrategy:
    """Generates signals from ML model predictions."""

    name = "ml_ensemble"

    def __init__(self, model: ModelProvider, min_confidence: float = 0.55) -> None:
        self._model = model
        self._min_confidence = min_confidence

    def required_features(self) -> list[str]:
        return []  # Uses all available features

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None:
        prediction = await self._model.predict(features)

        if prediction.direction == "hold":
            return None
        if prediction.confidence < self._min_confidence:
            return None

        return Signal(
            symbol=symbol,
            direction=SignalDirection[prediction.direction.upper()],
            confidence=prediction.confidence,
            strategy_name=self.name,
            reasoning=f"ML ensemble: {prediction.direction} with {prediction.confidence:.2f} confidence",
            timestamp=datetime.now(UTC),
        )
```

### New: Event-Driven Strategy

Reacts to sudden sentiment spikes — fires when article volume and sentiment both spike:

```python
class EventDrivenStrategy:
    """Detects and reacts to sentiment-volume spikes."""

    name = "event_driven"

    def __init__(
        self,
        volume_spike_threshold: float = 3.0,
        sentiment_threshold: float = 0.5,
    ) -> None:
        self._vol_threshold = volume_spike_threshold
        self._sent_threshold = sentiment_threshold

    def required_features(self) -> list[str]:
        return [
            "article_volume_ratio",
            "sentiment_avg_6h",
            "sentiment_velocity",
        ]

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None:
        vol_ratio = features.features.get("article_volume_ratio", 1.0)
        sentiment = features.features.get("sentiment_avg_6h", 0.0)
        velocity = features.features.get("sentiment_velocity", 0.0)

        # Need both volume spike AND strong directional sentiment
        if vol_ratio < self._vol_threshold:
            return None
        if abs(sentiment) < self._sent_threshold:
            return None

        direction = SignalDirection.BUY if sentiment > 0 else SignalDirection.SELL

        # Confidence scales with both volume spike and sentiment strength
        confidence = min(
            (vol_ratio / self._vol_threshold) * abs(sentiment), 1.0
        )

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            reasoning=(
                f"Sentiment spike: {vol_ratio:.1f}x article volume, "
                f"sentiment={sentiment:.2f}, velocity={velocity:.2f}"
            ),
            timestamp=datetime.now(UTC),
        )
```

### New: Cross-Asset Strategy

Exploits lead-lag relationships between correlated assets:

```python
class CrossAssetStrategy:
    """Trades lagging assets based on leader momentum."""

    name = "cross_asset"

    def __init__(
        self,
        leader_pairs: dict[str, str] | None = None,
        min_correlation: float = 0.6,
    ) -> None:
        # Default pairs: BTC leads ETH, NVDA leads AMD
        self._pairs = leader_pairs or {
            "ETH/USD": "BTC/USD",
            "SOL/USD": "BTC/USD",
        }
        self._min_correlation = min_correlation

    def required_features(self) -> list[str]:
        return ["btc_momentum_lead", "btc_eth_corr_30d", "sma_5", "sma_14"]

    async def evaluate(
        self, symbol: str, features: FeatureVector
    ) -> Signal | None:
        leader = self._pairs.get(symbol)
        if not leader:
            return None

        leader_momentum = features.features.get("btc_momentum_lead", 0.0)
        correlation = features.features.get("btc_eth_corr_30d", 0.0)

        if abs(correlation) < self._min_correlation:
            return None

        # Leader is bullish but this asset hasn't moved yet
        own_sma5 = features.features.get("sma_5", 0)
        own_sma14 = features.features.get("sma_14", 0)

        if leader_momentum > 0 and own_sma5 <= own_sma14:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence=min(abs(leader_momentum) * correlation, 1.0),
                strategy_name=self.name,
                reasoning=f"Leader {leader} bullish, {symbol} lagging",
                timestamp=datetime.now(UTC),
            )

        return None
```

### Weighted Consensus

Replace simple majority voting:

```python
async def _weighted_consensus(
    self,
    signals: list[Signal],
    risk_context: RiskContext,
) -> Signal | None:
    """Weighted signal consensus using config weight, accuracy, and regime."""

    if not signals:
        return None

    direction_scores: dict[SignalDirection, float] = defaultdict(float)
    best_signal: dict[SignalDirection, Signal] = {}

    for signal in signals:
        if signal.direction == SignalDirection.HOLD:
            continue

        # Three weighting factors:
        config_weight = self._strategy_weights.get(signal.strategy_name, 1.0)

        stats = risk_context.strategy_stats.get(signal.strategy_name)
        accuracy_weight = stats.recent_win_rate if stats and stats.recent_trades >= 10 else 0.5

        regime = risk_context.regime
        regime_weight = self._regime_multipliers.get(
            (signal.strategy_name, regime), 1.0
        )

        weighted = signal.confidence * config_weight * accuracy_weight * regime_weight
        direction_scores[signal.direction] += weighted

        if signal.direction not in best_signal or weighted > direction_scores.get(signal.direction, 0):
            best_signal[signal.direction] = signal

    if not direction_scores:
        return None

    best_direction = max(direction_scores, key=direction_scores.get)

    # Require minimum threshold
    if direction_scores[best_direction] < self._min_consensus_score:
        return None

    return best_signal[best_direction]
```

### Configuration

```yaml
# settings.yaml additions
strategies:
  momentum:
    enabled: true
    weight: 0.3
  sentiment:
    enabled: true
    weight: 0.2
  quantitative:
    enabled: true
    weight: 0.15
  ml_ensemble:
    enabled: true
    weight: 0.6
    min_confidence: 0.55
  event_driven:
    enabled: true
    weight: 0.4
    volume_spike_threshold: 3.0
    sentiment_threshold: 0.5
  cross_asset:
    enabled: true
    weight: 0.25
    min_correlation: 0.6

consensus:
  min_score: 0.3                    # minimum weighted score to trade
  regime_multipliers:
    # Boost momentum strategies in trending markets
    momentum:
      low: 1.2
      medium: 1.0
      high: 0.6
    # Boost mean-reversion in ranging markets
    quantitative:
      low: 0.8
      medium: 1.2
      high: 0.6
    # ML adapts to all regimes
    ml_ensemble:
      low: 1.0
      medium: 1.0
      high: 1.0
```

---

## 6. Performance Analytics & Backtesting

### Problem

The current backtester tracks basic metrics (trade count, win rate, P&L, Sharpe, drawdown). No per-strategy attribution, no regime tagging, no statistical validation of edge.

### Solution

A comprehensive analytics suite with walk-forward backtesting, per-strategy P&L attribution, regime-tagged performance, Monte Carlo simulation, and dashboard visualizations.

### Directory Structure

```
src/analytics/
├── protocols.py          # AnalyticsProvider protocol
├── walk_forward.py       # Walk-forward backtesting engine
├── attribution.py        # Per-strategy P&L breakdown
├── monte_carlo.py        # Outcome distribution simulation
├── regime_tagger.py      # Tags trades with regime context
└── reporter.py           # Generates summary reports
```

### Walk-Forward Backtesting Engine

Extends the existing backtester with proper train/test splitting:

```python
class WalkForwardBacktester:
    """Replay historical data with walk-forward model retraining."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        feature_store: FeatureStore,
        trainer: WalkForwardTrainer,
    ) -> None:
        self._orchestrator = orchestrator
        self._store = feature_store
        self._trainer = trainer

    async def run(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        initial_cash: Decimal = Decimal("100000"),
    ) -> BacktestReport:
        """Full walk-forward backtest."""

        # 1. Retrain models at each walk-forward step
        wf_results = await self._trainer.run(symbols, start, end)

        # 2. Replay ticks through orchestrator using test-period models
        fills: list[AttributedFill] = []
        equity_curve: list[EquityPoint] = []

        for wf_step in wf_results:
            # Load model trained on this step
            ticks = await self._store.get_ticks(
                symbols, wf_step.test_period[0], wf_step.test_period[1]
            )
            for tick in ticks:
                step_fills = await self._orchestrator.process_tick(tick)
                for fill in step_fills:
                    fills.append(AttributedFill(
                        fill=fill,
                        strategy=fill.strategy_name,
                        regime=self._get_regime_at(tick.timestamp),
                    ))

                equity_curve.append(EquityPoint(
                    timestamp=tick.timestamp,
                    value=self._orchestrator.portfolio.total_value,
                ))

        # 3. Build report
        return BacktestReport(
            fills=fills,
            equity_curve=equity_curve,
            walk_forward_results=wf_results,
        )
```

### Per-Strategy Attribution

Break down P&L by which strategy generated each trade:

```python
class StrategyAttribution:
    """Attributes P&L to individual strategies."""

    def analyze(self, fills: list[AttributedFill]) -> AttributionReport:
        by_strategy: dict[str, StrategyStats] = {}

        for strategy_name, strategy_fills in groupby(fills, key=lambda f: f.strategy):
            trades = self._pair_fills(list(strategy_fills))

            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]

            by_strategy[strategy_name] = StrategyStats(
                name=strategy_name,
                total_trades=len(trades),
                win_rate=len(wins) / len(trades) if trades else 0,
                total_pnl=sum(t.pnl for t in trades),
                avg_win=mean(t.pnl for t in wins) if wins else Decimal(0),
                avg_loss=mean(t.pnl for t in losses) if losses else Decimal(0),
                profit_factor=(
                    sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses))
                    if losses else float("inf")
                ),
                max_consecutive_losses=self._max_streak(trades, losing=True),
            )

        return AttributionReport(strategies=by_strategy)
```

### Monte Carlo Simulation

Statistical validation that returns are from skill, not luck:

```python
class MonteCarloSimulator:
    """Shuffle trade outcomes to build confidence intervals."""

    def __init__(self, n_simulations: int = 1000) -> None:
        self._n = n_simulations

    def simulate(
        self, trades: list[Trade], initial_cash: Decimal
    ) -> MonteCarloResult:
        actual_equity = self._build_equity(trades, initial_cash)
        actual_final = actual_equity[-1]

        simulated_finals: list[float] = []
        simulated_drawdowns: list[float] = []

        for _ in range(self._n):
            shuffled = trades.copy()
            random.shuffle(shuffled)
            equity = self._build_equity(shuffled, initial_cash)
            simulated_finals.append(float(equity[-1]))
            simulated_drawdowns.append(self._max_drawdown(equity))

        # What percentile is our actual result?
        percentile = sum(
            1 for f in simulated_finals if f < float(actual_final)
        ) / self._n * 100

        return MonteCarloResult(
            actual_final_value=float(actual_final),
            percentile=percentile,                      # >95 = likely skill
            median_simulated=median(simulated_finals),
            p5_simulated=percentile_calc(simulated_finals, 5),
            p95_simulated=percentile_calc(simulated_finals, 95),
            worst_drawdown_p95=percentile_calc(simulated_drawdowns, 95),
        )
```

### Regime-Tagged Performance

Tag every trade with the volatility regime at execution time:

```python
class RegimeTagger:
    """Tags trades with the market regime at time of execution."""

    def __init__(self, feature_store: FeatureStore) -> None:
        self._store = feature_store

    async def tag(self, fills: list[Fill]) -> list[AttributedFill]:
        tagged = []
        for fill in fills:
            regime = await self._store.get_regime_at(fill.symbol, fill.timestamp)
            tagged.append(AttributedFill(fill=fill, regime=regime))
        return tagged

    def performance_by_regime(
        self, fills: list[AttributedFill]
    ) -> dict[VolatilityRegime, StrategyStats]:
        """Break down performance by market regime."""
        by_regime = groupby(fills, key=lambda f: f.regime)
        return {
            regime: self._compute_stats(list(regime_fills))
            for regime, regime_fills in by_regime
        }
```

### Database Schema

```sql
CREATE TABLE backtest_runs (
    id TEXT PRIMARY KEY,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    config_snapshot TEXT NOT NULL,     -- JSON of full config used
    train_start INT NOT NULL,
    train_end INT NOT NULL,
    test_start INT NOT NULL,
    test_end INT NOT NULL,
    initial_cash TEXT NOT NULL,
    final_value TEXT,
    status TEXT NOT NULL               -- 'running', 'completed', 'failed'
);

CREATE TABLE backtest_metrics (
    run_id TEXT NOT NULL REFERENCES backtest_runs(id),
    strategy TEXT NOT NULL,
    regime TEXT,                       -- 'low', 'medium', 'high', 'all'
    sharpe FLOAT,
    sortino FLOAT,
    max_drawdown FLOAT,
    win_rate FLOAT,
    profit_factor FLOAT,
    total_trades INT,
    total_pnl FLOAT,
    PRIMARY KEY (run_id, strategy, regime)
);

CREATE TABLE monte_carlo_results (
    run_id TEXT NOT NULL REFERENCES backtest_runs(id),
    percentile FLOAT NOT NULL,
    median_simulated FLOAT NOT NULL,
    p5_simulated FLOAT NOT NULL,
    p95_simulated FLOAT NOT NULL,
    worst_drawdown_p95 FLOAT NOT NULL,
    PRIMARY KEY (run_id)
);
```

### Dashboard Additions

New FastAPI endpoints:

```python
@app.get("/api/analytics/attribution")
async def get_attribution(strategy: str | None = None):
    """Per-strategy P&L breakdown."""

@app.get("/api/analytics/equity-curve")
async def get_equity_curve(run_id: str | None = None):
    """Equity curve with drawdown overlay."""

@app.get("/api/analytics/regime-performance")
async def get_regime_performance():
    """Performance breakdown by volatility regime."""

@app.get("/api/analytics/monte-carlo")
async def get_monte_carlo(run_id: str):
    """Monte Carlo simulation results."""

@app.get("/api/analytics/backtest-runs")
async def list_backtest_runs(limit: int = 10):
    """List recent backtest runs with summary metrics."""
```

---

## 7. Documentation

### Structure

```
docs/
├── architecture.md              # System overview & data flow diagram
├── providers/
│   ├── overview.md              # Protocol pattern, how to add new providers
│   ├── news-providers.md        # RSS, Reddit, NewsAPI setup & examples
│   ├── sentiment-analyzers.md   # Ollama, FinBERT, Claude setup & examples
│   ├── onchain-providers.md     # Blockchair setup, adding Glassnode later
│   └── market-data-providers.md # Kraken, Binance, Yahoo protocol docs
├── ml/
│   ├── feature-store.md         # Feature categories, adding new features
│   ├── model-training.md        # Walk-forward training, evaluation
│   ├── adding-a-model.md        # Step-by-step: implement ModelProvider
│   └── serving.md               # Model loading and live prediction serving
├── strategies/
│   ├── overview.md              # Strategy protocol, consensus logic
│   ├── built-in.md              # Momentum, quant, sentiment docs
│   ├── ml-ensemble.md           # ML strategy config & tuning
│   ├── event-driven.md          # Sentiment spike detection
│   └── adding-a-strategy.md     # Step-by-step: implement, register, test
├── risk/
│   ├── overview.md              # Risk architecture, regime-aware limits
│   ├── position-sizing.md       # Fixed vs Kelly vs vol-targeted
│   └── circuit-breakers.md      # Drawdown breaker, correlation limits
├── analytics/
│   ├── backtesting.md           # Walk-forward engine usage
│   ├── attribution.md           # Per-strategy P&L analysis
│   └── monte-carlo.md           # Running simulations, reading output
├── testing/
│   ├── overview.md              # TDD workflow, test levels, coverage targets
│   ├── writing-mock-clients.md  # How to write mock implementations
│   ├── protocol-compliance.md   # Shared compliance test suites
│   ├── factories.md             # Test data factories reference
│   └── running-tests.md         # Commands, markers, coverage reports
├── cli/
│   ├── overview.md              # CLI architecture, how commands are structured
│   ├── config.md                # tradebot config commands
│   ├── providers.md             # tradebot providers commands
│   ├── news.md                  # tradebot news commands
│   ├── sentiment.md             # tradebot sentiment commands
│   ├── features.md              # tradebot features commands
│   ├── models.md                # tradebot models commands
│   ├── risk.md                  # tradebot risk commands
│   ├── strategies.md            # tradebot strategies commands
│   ├── backtest.md              # tradebot backtest commands
│   ├── portfolio.md             # tradebot portfolio commands
│   └── adding-a-command.md      # How to add a new CLI command
└── guides/
    ├── quickstart.md            # Get running in 5 minutes
    ├── adding-a-provider.md     # Generic guide for any protocol
    └── going-live.md            # Paper to live checklist
```

### Document Template

Every doc follows this structure:

```markdown
# [Component Name]

## Overview
What it does, why it exists, where it fits in the architecture.

## Configuration
Relevant settings.yaml options with defaults explained.

## Usage Examples

### Basic
Minimal working example with code.

### With Registry
How it works when wired through the provider system.

### Adding Your Own
How to implement the protocol and register a new provider.

## Protocol Reference
Full protocol definition with parameter documentation.

## Troubleshooting
Common issues and solutions.
```

### Key Guide: Adding a Provider

The most important doc — makes the whole protocol architecture accessible:

```markdown
# Adding a Provider

## Steps

### 1. Choose a Protocol
Look at `src/providers/protocols.py`. Pick the protocol that matches
your data source type (NewsProvider, SentimentAnalyzer, etc).

### 2. Implement It
Create a new file in the appropriate subdirectory:

    ```python
    # src/providers/news/my_source.py

    class MyNewsProvider:
        name = "my_source"

        def __init__(self, api_key: str, base_url: str) -> None:
            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        async def fetch_articles(
            self, symbol: str, since: datetime
        ) -> list[Article]:
            resp = await self._client.get(
                "/articles", params={"q": symbol, "from": since.isoformat()}
            )
            return [Article(**a) for a in resp.json()["articles"]]

        async def health_check(self) -> bool:
            resp = await self._client.get("/health")
            return resp.status_code == 200

        def rate_limit(self) -> RateLimit:
            return RateLimit(requests_per_minute=10)
    ```

### 3. Register in Provider Map
Add your class to `PROVIDER_MAP` in `src/providers/registry.py`:

    ```python
    PROVIDER_MAP = {
        "news": {
            "rss": RSSNewsProvider,
            "reddit": RedditNewsProvider,
            "my_source": MyNewsProvider,  # Add here
        },
    }
    ```

### 4. Configure
Set it in `config/settings.yaml`:

    ```yaml
    providers:
      news:
        provider: my_source
        client_config:
          api_key: ${MY_API_KEY}
          base_url: https://api.mysource.com
    ```

### 5. Test
Write a test verifying protocol compliance:

    ```python
    async def test_my_provider_implements_protocol():
        provider = MyNewsProvider(api_key="test", base_url="http://mock")
        assert isinstance(provider, NewsProvider)

    async def test_fetch_articles():
        provider = MyNewsProvider(...)
        articles = await provider.fetch_articles("BTC/USD", one_hour_ago)
        assert all(isinstance(a, Article) for a in articles)
    ```
```

---

## 8. Complete Data Flow

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
│  ModelProvider               │  │  Strategy                 │
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
│  Orchestrator                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Collect signals from all strategies              │    │
│  │ 2. Weighted consensus (config × accuracy × regime)  │    │
│  │ 3. Pass to risk manager                             │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         ▼                                   │
│  RiskManager                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ RiskContext:                                        │    │
│  │   regime → adjusts limits dynamically               │    │
│  │   correlation_matrix → exposure checks              │    │
│  │   strategy_stats → per-strategy track record        │    │
│  │   drawdown_from_peak → circuit breaker              │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         ▼                                   │
│  PositionSizer                                              │
│  ┌──────────────┐                                           │
│  │ Fixed %      │                                           │
│  │ Kelly        │                                           │
│  │ Vol-targeted │                                           │
│  └──────┬───────┘                                           │
└─────────┼───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  EXECUTION LAYER                            │
│                                                             │
│  ExecutionAgent          PortfolioManager                   │
│  ┌──────────────┐        ┌──────────────────────┐           │
│  │ Paper        │──fill─▶│ Positions & P&L      │           │
│  │ (Kraken live)│        │ Strategy attribution  │           │
│  │ (IBKR live)  │        └──────────┬───────────┘           │
│  └──────────────┘                   │                       │
└─────────────────────────────────────┼───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 ANALYTICS & MONITORING                       │
│                                                             │
│  Walk-Forward    Monte Carlo    Attribution    Dashboard     │
│  Backtester      Simulator      Reporter       (FastAPI)    │
│                                                Discord Bot  │
│                                                             │
│  backtest_runs   backtest_metrics   monte_carlo_results     │
│  (per-strategy, per-regime breakdown)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Protocol Summary

| Protocol | Purpose | Free Implementations | Premium Slot |
|----------|---------|---------------------|-------------|
| `NewsProvider` | Article fetching | RSS, Reddit, NewsAPI | Polygon, Benzinga |
| `SentimentAnalyzer` | Text → sentiment score | Ollama, FinBERT | Claude, proprietary |
| `OnChainProvider` | Blockchain metrics | Blockchair | Glassnode, Nansen |
| `MarketDataProvider` | Price feeds | Kraken, Binance, Yahoo | Polygon, IBKR |
| `FeatureProvider` | Computed indicators | TA-Lib, custom | — |
| `ModelProvider` | ML predict/train | XGBoost, LSTM | Cloud GPU services |
| `PositionSizer` | Order sizing | Fixed, Kelly, VolTargeted | — |

---

## 10. New Dependencies

```toml
# pyproject.toml additions

[project.dependencies]
pydantic = ">=2.6.0"       # All models, configs, validation
pydantic-settings = ">=2.2.0"  # Env var loading for configs
typer = ">=0.12.0"         # CLI framework
rich = ">=13.0.0"          # Terminal formatting (tables, colors)

[project.optional-dependencies]
ml = [
    "xgboost>=2.0.0",
    "torch>=2.0.0",
    "scikit-learn>=1.4.0",
    "transformers>=4.40.0",  # for FinBERT
]
feeds = [
    "feedparser>=6.0.0",    # RSS parsing
    "praw>=7.7.0",          # Reddit API
    "newsapi-python>=0.2.7",
]

[project.scripts]
tradebot = "src.cli.main:app"
```

---

## 11. Testing Strategy

### TDD Workflow

Every feature follows this cycle — no exceptions:

```
1. Write a failing test        (RED)
2. Write minimal code to pass  (GREEN)
3. Refactor                    (REFACTOR)
4. Repeat
```

### Test Directory Structure

```
tests/
├── conftest.py                    # Shared fixtures: mock providers, configs, factories
├── unit/                          # Test individual classes in isolation
│   ├── providers/
│   │   ├── test_rss_provider.py
│   │   ├── test_reddit_provider.py
│   │   ├── test_ollama_sentiment.py
│   │   ├── test_finbert_sentiment.py
│   │   ├── test_blockchair_provider.py
│   │   ├── test_technical_features.py
│   │   └── test_registry.py
│   ├── sentiment/
│   │   ├── test_article_buffer.py
│   │   ├── test_aggregator.py
│   │   └── test_pipeline.py
│   ├── ml/
│   │   ├── test_feature_engine.py
│   │   ├── test_feature_store.py
│   │   ├── test_xgboost_model.py
│   │   ├── test_lstm_model.py
│   │   ├── test_ensemble.py
│   │   └── test_trainer.py
│   ├── risk/
│   │   ├── test_kelly_sizer.py
│   │   ├── test_vol_targeted_sizer.py
│   │   ├── test_correlation_check.py
│   │   ├── test_regime_limits.py
│   │   └── test_circuit_breaker.py
│   ├── strategies/
│   │   ├── test_ml_ensemble_strategy.py
│   │   ├── test_event_driven_strategy.py
│   │   ├── test_cross_asset_strategy.py
│   │   └── test_weighted_consensus.py
│   └── analytics/
│       ├── test_attribution.py
│       ├── test_monte_carlo.py
│       └── test_regime_tagger.py
├── component/                     # Test subsystems with mock boundaries
│   ├── test_sentiment_pipeline.py     # Pipeline with MockNewsProvider + MockAnalyzer
│   ├── test_feature_pipeline.py       # FeatureEngine with MockProviders → MockStore
│   ├── test_ml_training_loop.py       # Trainer with MockModel + MockStore
│   ├── test_risk_decision_flow.py     # RiskManager with MockPortfolio + MockContext
│   ├── test_strategy_evaluation.py    # Strategies with MockFeatureStore
│   └── test_orchestrator_flow.py      # Orchestrator with all mock agents
├── integration/                   # Test real subsystem interactions
│   ├── test_news_to_sentiment.py      # Real RSS → real Ollama → real DB
│   ├── test_ticks_to_features.py      # Real ticks → FeatureEngine → SQLite
│   ├── test_features_to_signals.py    # Real features → strategies → signals
│   ├── test_signal_to_execution.py    # Signal → risk → sizing → paper execution
│   ├── test_full_trading_loop.py      # End-to-end with mock market data
│   └── test_backtest_pipeline.py      # Walk-forward backtest end-to-end
└── fixtures/
    ├── factories.py               # Factory functions for test data
    ├── market_data.py             # Canned tick/OHLC data
    ├── articles.py                # Canned news articles
    └── feature_vectors.py         # Canned feature vectors
```

### Test Levels

#### Unit Tests (100% coverage target)

Test each class in complete isolation. All dependencies are mocks. No I/O, no network, no database.

```python
# tests/unit/sentiment/test_aggregator.py

class TestSentimentAggregator:
    """Unit tests for time-weighted sentiment aggregation."""

    def test_empty_scores_returns_zero(self):
        aggregator = SentimentAggregator(config=AggregatorConfig())
        result = aggregator.aggregate("BTC/USD", now=datetime.now(UTC))
        assert result == 0.0

    def test_single_score_returns_that_score(self):
        aggregator = SentimentAggregator(config=AggregatorConfig())
        aggregator.add_scores("BTC/USD", [
            SentimentResult(score=0.8, magnitude=1.0, timestamp=datetime.now(UTC))
        ])
        result = aggregator.aggregate("BTC/USD", now=datetime.now(UTC))
        assert result == pytest.approx(0.8, abs=0.01)

    def test_older_scores_weighted_less(self):
        config = AggregatorConfig(decay="exponential", half_life_hours=6.0)
        aggregator = SentimentAggregator(config=config)
        now = datetime.now(UTC)

        aggregator.add_scores("BTC/USD", [
            SentimentResult(score=1.0, magnitude=1.0, timestamp=now),
            SentimentResult(score=-1.0, magnitude=1.0, timestamp=now - timedelta(hours=12)),
        ])

        result = aggregator.aggregate("BTC/USD", now=now)
        # Recent positive should dominate old negative
        assert result > 0.0

    def test_magnitude_amplifies_score(self):
        aggregator = SentimentAggregator(config=AggregatorConfig())
        now = datetime.now(UTC)

        aggregator.add_scores("BTC/USD", [
            SentimentResult(score=0.5, magnitude=1.0, timestamp=now),
            SentimentResult(score=-0.5, magnitude=0.1, timestamp=now),
        ])

        result = aggregator.aggregate("BTC/USD", now=now)
        # High-magnitude positive should outweigh low-magnitude negative
        assert result > 0.0
```

```python
# tests/unit/risk/test_circuit_breaker.py

class TestDrawdownCircuitBreaker:
    """Unit tests for drawdown circuit breaker."""

    def test_not_tripped_when_no_drawdown(self):
        breaker = DrawdownCircuitBreaker(
            config=CircuitBreakerConfig(max_drawdown_pct=10.0)
        )
        breaker.update(Decimal("100000"), now=datetime.now(UTC))
        assert not breaker.is_tripped(Decimal("100000"), now=datetime.now(UTC))

    def test_tripped_when_drawdown_exceeds_threshold(self):
        breaker = DrawdownCircuitBreaker(
            config=CircuitBreakerConfig(max_drawdown_pct=10.0)
        )
        now = datetime.now(UTC)
        breaker.update(Decimal("100000"), now)
        assert breaker.is_tripped(Decimal("89000"), now)  # 11% drawdown

    def test_not_tripped_when_drawdown_below_threshold(self):
        breaker = DrawdownCircuitBreaker(
            config=CircuitBreakerConfig(max_drawdown_pct=10.0)
        )
        now = datetime.now(UTC)
        breaker.update(Decimal("100000"), now)
        assert not breaker.is_tripped(Decimal("91000"), now)  # 9% drawdown

    def test_stays_tripped_during_cooldown(self):
        config = CircuitBreakerConfig(max_drawdown_pct=10.0, cooldown_hours=24.0)
        breaker = DrawdownCircuitBreaker(config=config)
        now = datetime.now(UTC)

        breaker.update(Decimal("100000"), now)
        assert breaker.is_tripped(Decimal("85000"), now)  # Trip it

        # 12 hours later — still in cooldown
        later = now + timedelta(hours=12)
        assert breaker.is_tripped(Decimal("100000"), later)

    def test_resets_after_cooldown(self):
        config = CircuitBreakerConfig(max_drawdown_pct=10.0, cooldown_hours=24.0)
        breaker = DrawdownCircuitBreaker(config=config)
        now = datetime.now(UTC)

        breaker.update(Decimal("100000"), now)
        assert breaker.is_tripped(Decimal("85000"), now)

        # 25 hours later — cooldown expired
        later = now + timedelta(hours=25)
        assert not breaker.is_tripped(Decimal("100000"), later)
```

```python
# tests/unit/providers/test_registry.py

class TestProviderRegistry:
    """Unit tests for provider registry."""

    def test_register_and_get(self):
        registry = ProviderRegistry()
        mock_news = MockNewsProvider()
        registry.register(NewsProvider, mock_news)
        assert registry.get(NewsProvider) is mock_news

    def test_get_unregistered_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError):
            registry.get(NewsProvider)

    def test_for_testing_creates_all_mocks(self):
        registry = ProviderRegistry.for_testing()
        assert isinstance(registry.get(NewsProvider), MockNewsProvider)
        assert isinstance(registry.get(SentimentAnalyzer), MockSentimentAnalyzer)
        assert isinstance(registry.get(MarketDataProvider), MockMarketDataProvider)

    def test_for_testing_allows_overrides(self):
        custom_news = MockNewsProvider(config=MockNewsConfig(
            canned_articles=[make_article("BTC crash")]
        ))
        registry = ProviderRegistry.for_testing(**{NewsProvider: custom_news})
        assert registry.get(NewsProvider) is custom_news

    def test_register_rejects_non_conforming_instance(self):
        registry = ProviderRegistry()
        with pytest.raises(AssertionError):
            registry.register(NewsProvider, "not a news provider")
```

#### Component Tests (100% coverage target)

Test subsystems working together with mock boundaries. Real logic, mock I/O.

```python
# tests/component/test_sentiment_pipeline.py

class TestSentimentPipeline:
    """Component test: news → buffer → analyzer → aggregator."""

    @pytest.fixture
    def pipeline(self):
        articles = [
            make_article("Bitcoin surges to new high", symbol="BTC/USD", score=0.9),
            make_article("Bitcoin surges to new high", symbol="BTC/USD", score=0.9),  # dupe
            make_article("Ethereum faces resistance", symbol="ETH/USD", score=-0.3),
        ]
        news = MockNewsProvider(config=MockNewsConfig(canned_articles=articles))
        analyzer = MockSentimentAnalyzer(config=MockSentimentConfig(
            default_score=0.7, default_magnitude=0.8
        ))
        store = MockSentimentStore()

        return SentimentPipeline(
            news=news,
            analyzer=analyzer,
            store=store,
            config=SentimentPipelineConfig(),
        )

    async def test_deduplicates_articles(self, pipeline):
        await pipeline.run_cycle(symbols=["BTC/USD"])
        # 2 identical articles → only 1 scored
        assert pipeline._analyzer.score_count == 1

    async def test_scores_persisted_to_store(self, pipeline):
        await pipeline.run_cycle(symbols=["BTC/USD"])
        scores = await pipeline._store.get_scores("BTC/USD")
        assert len(scores) == 1
        assert scores[0].score == 0.7

    async def test_aggregation_reflects_scores(self, pipeline):
        await pipeline.run_cycle(symbols=["BTC/USD"])
        agg = pipeline.get_aggregate("BTC/USD")
        assert agg > 0.0

    async def test_handles_provider_failure_gracefully(self):
        news = MockNewsProvider(config=MockNewsConfig(should_fail=True))
        analyzer = MockSentimentAnalyzer()
        store = MockSentimentStore()
        pipeline = SentimentPipeline(
            news=news, analyzer=analyzer, store=store,
            config=SentimentPipelineConfig(),
        )

        # Should not raise — logs warning and continues
        await pipeline.run_cycle(symbols=["BTC/USD"])
        assert analyzer.score_count == 0
```

```python
# tests/component/test_orchestrator_flow.py

class TestOrchestratorFlow:
    """Component test: full orchestrator with all mock agents."""

    @pytest.fixture
    def system(self):
        """Wire up orchestrator with all mock dependencies."""
        registry = ProviderRegistry.for_testing()

        # Configure mock market data to return predictable prices
        market = registry.get(MarketDataProvider)
        market.set_prices({"BTC/USD": Decimal("50000")})

        # Configure mock features
        features = registry.get(FeatureProvider)
        features.set_features("BTC/USD", {
            "sma_5": 50500, "sma_14": 49000,  # bullish crossover
            "sentiment_avg_6h": 0.7,
            "volatility_regime": 1,  # medium
        })

        strategies = [
            MomentumStrategyAdapter(),
            SentimentStrategyAdapter(),
            MLEnsembleStrategy(model=registry.get(ModelProvider)),
        ]
        risk = RiskManager(config=RiskSettings())
        sizer = registry.get(PositionSizer)
        executor = PaperExecutionAgent(config=ExecutionConfig())
        portfolio = PortfolioManager(config=PortfolioConfig(initial_cash=100000))

        orch = Orchestrator(
            strategies=strategies,
            risk_manager=risk,
            executor=executor,
            portfolio=portfolio,
            feature_engine=FeatureEngine(providers=[features], store=MockFeatureStore()),
            position_sizer=sizer,
            config=OrchestratorConfig(),
        )

        return orch, market, portfolio

    async def test_bullish_consensus_produces_buy(self, system):
        orch, market, portfolio = system
        tick = MarketTick(
            symbol="BTC/USD", price=Decimal("50000"),
            volume=1000, timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )

        fills = await orch.process_tick(tick)
        assert len(fills) == 1
        assert fills[0].side == OrderSide.BUY

    async def test_risk_veto_prevents_trade(self, system):
        orch, market, portfolio = system
        # Drain cash so risk manager vetoes
        portfolio._cash = Decimal("0")

        tick = MarketTick(
            symbol="BTC/USD", price=Decimal("50000"),
            volume=1000, timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )

        fills = await orch.process_tick(tick)
        assert len(fills) == 0
```

#### Integration Tests (100% coverage target)

Test real subsystem interactions. Real DB, real computation, mock only external APIs.

```python
# tests/integration/test_full_trading_loop.py

class TestFullTradingLoop:
    """Integration test: mock market data → real everything else → real DB."""

    @pytest.fixture
    async def system(self, tmp_path):
        db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
        db = Database(db_url)
        await db.initialize()

        # Only mock external data sources — everything else is real
        mock_market = MockMarketDataProvider()
        mock_market.set_prices({"BTC/USD": Decimal("50000")})

        mock_news = MockNewsProvider(config=MockNewsConfig(
            canned_articles=[make_article("BTC bullish", symbol="BTC/USD")]
        ))
        mock_analyzer = MockSentimentAnalyzer(config=MockSentimentConfig(
            default_score=0.8
        ))

        # Real components
        feature_store = FeatureStore(db=db)
        feature_engine = FeatureEngine(
            providers=[TechnicalFeatureProvider(config=TechnicalConfig())],
            store=feature_store,
        )
        portfolio = PortfolioManager(config=PortfolioConfig(initial_cash=100000))
        risk = RiskManager(config=RiskSettings())
        executor = PaperExecutionAgent(config=ExecutionConfig())
        sizer = FixedPositionSizer(config=FixedSizerConfig(position_pct=2.0))

        strategies = [
            MomentumStrategyAdapter(),
            QuantStrategyAdapter(),
        ]

        orch = Orchestrator(
            strategies=strategies,
            risk_manager=risk,
            executor=executor,
            portfolio=portfolio,
            feature_engine=feature_engine,
            position_sizer=sizer,
            config=OrchestratorConfig(),
        )

        return orch, db, mock_market

    async def test_end_to_end_trade_persisted(self, system):
        orch, db, market = system

        # Simulate 30 ticks to build enough history for momentum
        for i in range(30):
            tick = MarketTick(
                symbol="BTC/USD",
                price=Decimal("50000") + Decimal(str(i * 100)),  # trending up
                volume=1000,
                timestamp=datetime.now(UTC) + timedelta(minutes=i),
                asset_type=AssetType.CRYPTO,
            )
            fills = await orch.process_tick(tick)

        # Should have at least one trade
        trades = await db.list_trades()
        assert len(trades) > 0
        assert trades[0].symbol == "BTC/USD"
```

### Protocol Compliance Tests

Every mock and every real implementation gets a shared protocol compliance test suite:

```python
# tests/unit/providers/test_protocol_compliance.py

class NewsProviderComplianceTests:
    """Shared tests that ANY NewsProvider implementation must pass."""

    @abstractmethod
    def make_provider(self) -> NewsProvider:
        """Subclass must create the provider to test."""
        ...

    def test_implements_protocol(self):
        provider = self.make_provider()
        assert isinstance(provider, NewsProvider)

    def test_has_name(self):
        provider = self.make_provider()
        assert isinstance(provider.name, str)
        assert len(provider.name) > 0

    async def test_fetch_returns_list_of_articles(self):
        provider = self.make_provider()
        result = await provider.fetch_articles("BTC/USD", datetime.now(UTC) - timedelta(hours=1))
        assert isinstance(result, list)
        for article in result:
            assert isinstance(article, Article)

    async def test_health_check_returns_bool(self):
        provider = self.make_provider()
        result = await provider.health_check()
        assert isinstance(result, bool)

    def test_rate_limit_returns_rate_limit(self):
        provider = self.make_provider()
        result = provider.rate_limit()
        assert isinstance(result, RateLimit)
        assert result.requests_per_minute > 0


# Apply to every implementation:

class TestMockNewsCompliance(NewsProviderComplianceTests):
    def make_provider(self):
        return MockNewsProvider()

class TestRSSNewsCompliance(NewsProviderComplianceTests):
    def make_provider(self):
        return RSSNewsProvider(
            config=RSSConfig(feed_urls=["https://example.com/feed"]),
            client=MockHttpClient(),
        )

class TestPolygonNewsCompliance(NewsProviderComplianceTests):
    def make_provider(self):
        return PolygonNewsProvider(
            config=PolygonNewsConfig(api_key="test"),
            client=MockHttpClient(),
        )
```

### Shared Fixtures & Factories

All test data created through factory functions — never inline magic values:

```python
# tests/fixtures/factories.py

def make_article(
    title: str = "Test Article",
    symbol: str = "BTC/USD",
    score: float | None = None,
    published_at: datetime | None = None,
) -> Article:
    return Article(
        id=str(uuid4()),
        title=title,
        body=f"Article body about {symbol}",
        related_symbols=[symbol],
        source="test",
        url="https://example.com/article",
        published_at=published_at or datetime.now(UTC),
    )


def make_tick(
    symbol: str = "BTC/USD",
    price: Decimal | float = 50000,
    volume: int = 1000,
    asset_type: AssetType = AssetType.CRYPTO,
    timestamp: datetime | None = None,
) -> MarketTick:
    return MarketTick(
        symbol=symbol,
        price=Decimal(str(price)),
        volume=volume,
        timestamp=timestamp or datetime.now(UTC),
        asset_type=asset_type,
    )


def make_signal(
    symbol: str = "BTC/USD",
    direction: SignalDirection = SignalDirection.BUY,
    confidence: float = 0.8,
    strategy: str = "test",
) -> Signal:
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strategy_name=strategy,
        timestamp=datetime.now(UTC),
        reasoning="Test signal",
    )


def make_feature_vector(
    symbol: str = "BTC/USD",
    overrides: dict[str, float] | None = None,
) -> FeatureVector:
    defaults = {
        "sma_5": 50500, "sma_14": 49000, "sma_50": 48000,
        "rsi_14": 55.0, "macd_signal": 0.5,
        "bbands_position": 0.6, "atr_14": 1200.0,
        "sentiment_avg_6h": 0.0, "sentiment_velocity": 0.0,
        "article_volume_ratio": 1.0,
        "volatility_regime": 1.0, "trend_regime": 1.0,
    }
    if overrides:
        defaults.update(overrides)
    return FeatureVector(
        symbol=symbol,
        timestamp=int(datetime.now(UTC).timestamp()),
        features=defaults,
    )


def make_portfolio(
    cash: Decimal | float = 100000,
    positions: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> PortfolioSnapshot:
    pos_list = []
    if positions:
        for sym, (qty, price) in positions.items():
            pos_list.append(Position(
                symbol=sym, quantity=Decimal(str(qty)),
                avg_entry_price=Decimal(str(price)),
                current_price=Decimal(str(price)),
                asset_type=AssetType.CRYPTO,
            ))
    return PortfolioSnapshot(
        cash=Decimal(str(cash)),
        positions=pos_list,
        timestamp=datetime.now(UTC),
    )
```

### conftest.py

```python
# tests/conftest.py

@pytest.fixture
def mock_registry():
    """Full mock registry — no I/O, no network, no DB."""
    return ProviderRegistry.for_testing()


@pytest.fixture
def mock_http():
    """Mock HTTP client that records all calls."""
    return MockHttpClient()


@pytest.fixture
async def test_db(tmp_path):
    """Real SQLite database in a temp directory."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def mock_news():
    return MockNewsProvider()


@pytest.fixture
def mock_sentiment():
    return MockSentimentAnalyzer()


@pytest.fixture
def mock_features():
    return MockFeatureProvider()


@pytest.fixture
def mock_model():
    return MockModelProvider()
```

### Coverage Configuration

```toml
# pyproject.toml additions
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (no I/O)",
    "component: Component tests (mock boundaries)",
    "integration: Integration tests (real I/O)",
    "slow: Slow tests (ML training, Monte Carlo)",
]

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
fail_under = 100
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "@overload",
    "\\.\\.\\.",           # Protocol method stubs
]

[tool.coverage.paths]
source = ["src/"]
```

### Running Tests

```bash
# All unit tests (fast, no I/O)
uv run pytest tests/unit -m unit --cov --cov-report=term-missing

# Component tests
uv run pytest tests/component -m component --cov --cov-report=term-missing

# Integration tests (needs DB, slower)
uv run pytest tests/integration -m integration --cov --cov-report=term-missing

# Everything with full coverage report
uv run pytest --cov --cov-report=term-missing --cov-report=html

# Fast feedback loop during TDD
uv run pytest tests/unit/risk/test_circuit_breaker.py -x -v
```

### TDD Checklist Per Feature

For every new class or method added:

1. [ ] Write protocol/interface test (compliance test) — RED
2. [ ] Implement protocol stub — GREEN
3. [ ] Write mock implementation — test passes with mock
4. [ ] Write unit tests for real implementation — RED
5. [ ] Implement real class — GREEN
6. [ ] Write component test wiring class into subsystem — RED
7. [ ] Wire into subsystem — GREEN
8. [ ] Write integration test with real DB — RED
9. [ ] Verify end-to-end — GREEN
10. [ ] Check coverage is 100% — `uv run pytest --cov --cov-fail-under=100`

---

## 12. CLI Interface

Every subsystem is exposed via a documented CLI built with **Typer**. This makes each component independently invocable for debugging, testing, and operations — without needing the full system running.

### CLI Structure

```
src/cli/
├── __init__.py           # Root Typer app
├── main.py               # Entry point, registers all sub-commands
├── news.py               # News provider commands
├── sentiment.py          # Sentiment pipeline commands
├── features.py           # Feature engine commands
├── models.py             # ML model commands
├── risk.py               # Risk manager commands
├── strategies.py         # Strategy evaluation commands
├── backtest.py           # Backtesting commands
├── portfolio.py          # Portfolio inspection commands
├── providers.py          # Provider registry commands
└── config.py             # Config inspection/validation commands
```

### Root CLI

```python
# src/cli/main.py
import typer
from src.cli import (
    news, sentiment, features, models,
    risk, strategies, backtest, portfolio,
    providers, config,
)

app = typer.Typer(
    name="tradebot",
    help="Trading bot CLI — invoke any subsystem independently.",
    no_args_is_help=True,
)

app.add_typer(news.app, name="news")
app.add_typer(sentiment.app, name="sentiment")
app.add_typer(features.app, name="features")
app.add_typer(models.app, name="models")
app.add_typer(risk.app, name="risk")
app.add_typer(strategies.app, name="strategies")
app.add_typer(backtest.app, name="backtest")
app.add_typer(portfolio.app, name="portfolio")
app.add_typer(providers.app, name="providers")
app.add_typer(config.app, name="config")

if __name__ == "__main__":
    app()
```

### Entry Point

```toml
# pyproject.toml
[project.scripts]
tradebot = "src.cli.main:app"
```

After install: `uv run tradebot --help` shows all commands.

### Command Reference

#### `tradebot config`

Inspect and validate configuration.

```bash
# Validate settings.yaml — catches bad config before startup
$ uv run tradebot config validate
✓ settings.yaml is valid
✓ All provider configs pass Pydantic validation
✓ Risk settings within bounds

# Show resolved config (with defaults filled in)
$ uv run tradebot config show
mode: paper
providers:
  news:
    provider: rss
    fetch_interval_seconds: 300
    ...

# Show JSON schema for a specific config model
$ uv run tradebot config schema --model RSSConfig
{
  "title": "RSSConfig",
  "type": "object",
  "properties": {
    "feed_urls": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "fetch_interval_seconds": {"type": "integer", "minimum": 1, "default": 300},
    ...
  }
}

# Show all available providers for a protocol
$ uv run tradebot config providers --protocol news
Available NewsProvider implementations:
  rss       - Free RSS feed aggregator
  reddit    - Reddit API (free tier)
  newsapi   - NewsAPI.org (100 req/day free)
  polygon   - Polygon.io (paid)
  mock      - Deterministic test provider
```

```python
# src/cli/config.py
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Configuration inspection and validation.")
console = Console()


@app.command()
def validate(
    config_path: Path = typer.Option(
        "config/settings.yaml", "--config", "-c",
        help="Path to settings YAML file",
    ),
) -> None:
    """Validate settings.yaml against Pydantic schemas."""
    try:
        settings = Settings.from_yaml(config_path)
        console.print("[green]✓[/green] settings.yaml is valid")

        # Validate each provider config
        registry = ProviderRegistry.from_yaml(config_path)
        for protocol_name, provider in registry.all():
            console.print(f"[green]✓[/green] {protocol_name}: {provider.name}")

    except ValidationError as e:
        console.print(f"[red]✗[/red] Validation failed:")
        console.print(e)
        raise typer.Exit(code=1)


@app.command()
def show(
    config_path: Path = typer.Option("config/settings.yaml", "--config", "-c"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format: yaml or json"),
) -> None:
    """Show resolved configuration with defaults filled in."""
    settings = Settings.from_yaml(config_path)
    if format == "json":
        console.print_json(settings.model_dump_json(indent=2))
    else:
        console.print(yaml.dump(settings.model_dump(), default_flow_style=False))


@app.command()
def schema(
    model: str = typer.Argument(help="Config model name (e.g. RSSConfig, RiskSettings)"),
) -> None:
    """Show JSON schema for a config model."""
    config_cls = CONFIG_MODELS.get(model)
    if not config_cls:
        console.print(f"[red]Unknown model:[/red] {model}")
        console.print(f"Available: {', '.join(CONFIG_MODELS.keys())}")
        raise typer.Exit(code=1)
    console.print_json(json.dumps(config_cls.model_json_schema(), indent=2))
```

#### `tradebot providers`

Manage and inspect providers.

```bash
# List all registered providers and their health
$ uv run tradebot providers health
Provider Health Check:
  news (rss)           ✓ healthy    rate: 60 req/min
  sentiment (ollama)   ✓ healthy    model: llama3.2
  market_data (kraken) ✓ healthy    symbols: 3
  onchain (blockchair) ✗ unreachable

# List available implementations for a protocol
$ uv run tradebot providers list --protocol sentiment
  ollama   - Local Ollama LLM (free)
  finbert  - HuggingFace FinBERT (local, free)
  claude   - Anthropic Claude API (paid)
  mock     - Deterministic test analyzer
```

```python
# src/cli/providers.py
app = typer.Typer(help="Provider registry management.")


@app.command()
def health(
    config_path: Path = typer.Option("config/settings.yaml", "--config", "-c"),
) -> None:
    """Check health of all registered providers."""
    async def _check():
        registry = ProviderRegistry.from_yaml(config_path)
        table = Table(title="Provider Health")
        table.add_column("Protocol")
        table.add_column("Provider")
        table.add_column("Status")

        for protocol_name, provider in registry.all():
            try:
                healthy = await provider.health_check()
                status = "[green]✓ healthy[/green]" if healthy else "[red]✗ unhealthy[/red]"
            except Exception as e:
                status = f"[red]✗ {e}[/red]"
            table.add_row(protocol_name, provider.name, status)

        console.print(table)

    asyncio.run(_check())
```

#### `tradebot news`

Fetch and inspect news articles.

```bash
# Fetch articles for a symbol right now
$ uv run tradebot news fetch --symbol BTC/USD --since 1h
Fetched 12 articles for BTC/USD (last 1 hour):
  [Reuters]  "Bitcoin rises above $50k amid institutional buying"   2m ago
  [CoinDesk] "ETF inflows hit record high"                          15m ago
  ...

# Show configured feeds
$ uv run tradebot news feeds
RSS Feeds:
  https://feeds.finance.yahoo.com/rss/2.0/headline
  https://www.coindesk.com/arc/outboundfeeds/rss/

# Dry-run: fetch and show what would be scored (without scoring)
$ uv run tradebot news dry-run --symbol BTC/USD --since 1h
Would score 12 articles (3 deduplicated from 15 raw)
```

```python
# src/cli/news.py
app = typer.Typer(help="News provider operations.")


@app.command()
def fetch(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Symbol to fetch news for"),
    since: str = typer.Option("1h", "--since", help="Time window: 1h, 6h, 24h, 7d"),
    config_path: Path = typer.Option("config/settings.yaml", "--config", "-c"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Override provider"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
) -> None:
    """Fetch news articles for a symbol."""
    async def _fetch():
        since_dt = parse_duration(since)
        registry = ProviderRegistry.from_yaml(config_path)
        news_provider = registry.get(NewsProvider)
        articles = await news_provider.fetch_articles(symbol, since_dt)

        if output == "json":
            console.print_json(
                json.dumps([a.model_dump(mode="json") for a in articles], indent=2)
            )
        else:
            table = Table(title=f"Articles for {symbol}")
            table.add_column("Source")
            table.add_column("Title")
            table.add_column("Age")
            for article in articles:
                table.add_row(article.source, article.title, humanize_age(article.published_at))
            console.print(table)

    asyncio.run(_fetch())
```

#### `tradebot sentiment`

Run sentiment analysis pipeline.

```bash
# Score a single piece of text
$ uv run tradebot sentiment score --text "Bitcoin crashes 20% in flash crash"
Score: -0.85  Magnitude: 0.95  Analyzer: ollama

# Score articles for a symbol and show aggregate
$ uv run tradebot sentiment analyze --symbol BTC/USD --since 6h
Scored 23 articles for BTC/USD:
  Aggregate score:  0.42 (mildly bullish)
  Score velocity:   +0.15/hr (improving)
  Article volume:   1.2x normal

# Run full pipeline cycle (fetch → dedup → score → aggregate → store)
$ uv run tradebot sentiment run-cycle --symbols BTC/USD,ETH/USD
Cycle complete:
  BTC/USD: 15 articles scored, aggregate=0.42
  ETH/USD: 8 articles scored, aggregate=-0.12

# Show stored sentiment history
$ uv run tradebot sentiment history --symbol BTC/USD --since 24h --output json
```

```python
# src/cli/sentiment.py
app = typer.Typer(help="Sentiment analysis pipeline.")


@app.command()
def score(
    text: str = typer.Option(..., "--text", "-t", help="Text to score"),
    analyzer: str = typer.Option("ollama", "--analyzer", "-a", help="Analyzer to use"),
    config_path: Path = typer.Option("config/settings.yaml", "--config", "-c"),
) -> None:
    """Score a single text for financial sentiment."""
    async def _score():
        registry = ProviderRegistry.from_yaml(config_path)
        sentiment = registry.get(SentimentAnalyzer)
        result = await sentiment.score(text, symbol="")
        console.print(f"Score: {result.score:.2f}  Magnitude: {result.magnitude:.2f}  Analyzer: {sentiment.name}")
        if result.reasoning:
            console.print(f"Reasoning: {result.reasoning}")

    asyncio.run(_score())


@app.command()
def analyze(
    symbol: str = typer.Option(..., "--symbol", "-s"),
    since: str = typer.Option("6h", "--since"),
    config_path: Path = typer.Option("config/settings.yaml", "--config", "-c"),
) -> None:
    """Fetch articles, score them, and show aggregate sentiment."""
    async def _analyze():
        since_dt = parse_duration(since)
        registry = ProviderRegistry.from_yaml(config_path)
        pipeline = SentimentPipeline(
            news=registry.get(NewsProvider),
            analyzer=registry.get(SentimentAnalyzer),
            store=registry.get(DataStore),
            config=SentimentPipelineConfig(),
        )
        await pipeline.run_cycle(symbols=[symbol])
        agg = pipeline.get_aggregate(symbol)
        console.print(f"Aggregate sentiment for {symbol}: {agg:.2f}")

    asyncio.run(_analyze())
```

#### `tradebot features`

Compute and inspect features.

```bash
# Compute features for a symbol right now
$ uv run tradebot features compute --symbol BTC/USD
Computed 24 features for BTC/USD:
  sma_5:              50,500.00
  sma_14:             49,000.00
  rsi_14:             55.3
  macd_signal:        0.52
  sentiment_avg_6h:   0.42
  volatility_regime:  medium
  ...

# Show stored feature history
$ uv run tradebot features history --symbol BTC/USD --feature rsi_14 --since 7d

# List all available feature names
$ uv run tradebot features list
Technical:  sma_5, sma_14, sma_50, sma_200, rsi_14, macd_signal, bbands_position, atr_14, obv_slope, vwap_deviation, adx_14
Sentiment:  sentiment_avg_6h, sentiment_avg_24h, sentiment_velocity, article_volume_ratio, sentiment_dispersion
Cross:      btc_eth_corr_30d, btc_momentum_lead, sector_momentum, market_breadth
Regime:     volatility_regime, trend_regime, vol_percentile_30d
On-chain:   exchange_inflow_ratio, active_addresses_trend, whale_tx_count

# Export features as CSV for external analysis
$ uv run tradebot features export --symbol BTC/USD --since 30d --output features.csv
```

#### `tradebot models`

Train, evaluate, and inspect ML models.

```bash
# Train models using walk-forward validation
$ uv run tradebot models train --symbols BTC/USD,ETH/USD --start 2025-01-01 --end 2025-12-31
Walk-forward training:
  Window 1: train 2025-01 to 2025-06 → test 2025-07  accuracy=0.58
  Window 2: train 2025-02 to 2025-07 → test 2025-08  accuracy=0.61
  ...
  Average test accuracy: 0.59

# Evaluate a trained model on specific data
$ uv run tradebot models evaluate --model xgboost --start 2025-10-01 --end 2025-12-31
XGBoost evaluation:
  Accuracy: 0.61  Precision: 0.58  Recall: 0.63
  Buy accuracy: 0.62  Sell accuracy: 0.55  Hold accuracy: 0.67

# Show feature importance for trained model
$ uv run tradebot models importance --model xgboost
Feature Importance (XGBoost):
  rsi_14:              0.142
  sentiment_velocity:  0.118
  atr_14:              0.103
  ...

# Get a prediction for current features
$ uv run tradebot models predict --symbol BTC/USD
Prediction: BUY  Confidence: 0.67  Model: ensemble
  XGBoost:  BUY (0.71)
  LSTM:     BUY (0.62)
```

#### `tradebot risk`

Inspect risk state and simulate decisions.

```bash
# Show current risk context
$ uv run tradebot risk status
Risk Status:
  Regime:              medium volatility
  Drawdown from peak:  2.3%
  Circuit breaker:     not tripped (threshold: 10%)
  Open positions:      4 / 8 max
  Daily P&L:           +$230 (limit: -3%)

# Simulate a risk decision without executing
$ uv run tradebot risk check --symbol BTC/USD --direction buy --size 2000
Risk Decision: APPROVE
  Position size:     $2,000 (2.0% of portfolio)
  Correlation:       0.3 with ETH/USD (below 0.7 threshold)
  Regime-adjusted:   no adjustment (medium vol)

$ uv run tradebot risk check --symbol ETH/USD --direction buy --size 5000
Risk Decision: RESIZE → $1,200
  Reason: 0.82 correlation with existing BTC/USD position

# Show strategy performance stats (used for Kelly sizing)
$ uv run tradebot risk strategy-stats
Strategy Performance (last 100 trades):
  momentum:     62% win rate, avg win $340, avg loss -$210, Kelly: 1.8%
  ml_ensemble:  58% win rate, avg win $520, avg loss -$380, Kelly: 1.2%
  event_driven: 71% win rate, avg win $180, avg loss -$290, Kelly: 0.9%
```

#### `tradebot strategies`

Evaluate strategies independently.

```bash
# Evaluate a single strategy for a symbol
$ uv run tradebot strategies evaluate --strategy momentum --symbol BTC/USD
Momentum Strategy → BUY
  Confidence: 0.72
  Reasoning: SMA5 (50,500) > SMA14 (49,000)

# Evaluate all strategies and show consensus
$ uv run tradebot strategies consensus --symbol BTC/USD
Strategy Consensus for BTC/USD:
  momentum:      BUY  (conf=0.72, weight=0.30, regime=1.0) → 0.216
  sentiment:     BUY  (conf=0.65, weight=0.20, regime=1.0) → 0.130
  ml_ensemble:   BUY  (conf=0.67, weight=0.60, regime=1.0) → 0.402
  event_driven:  HOLD
  cross_asset:   BUY  (conf=0.40, weight=0.25, regime=1.0) → 0.100
  ──────────────────────────────────────────────────────
  Consensus: BUY  (weighted score: 0.848, threshold: 0.30) ✓

# List all registered strategies
$ uv run tradebot strategies list
  momentum       enabled  weight=0.30
  sentiment      enabled  weight=0.20
  quantitative   enabled  weight=0.15
  ml_ensemble    enabled  weight=0.60
  event_driven   enabled  weight=0.40
  cross_asset    enabled  weight=0.25
```

#### `tradebot backtest`

Run backtests and view results.

```bash
# Run a walk-forward backtest
$ uv run tradebot backtest run --symbols BTC/USD,ETH/USD --start 2025-01-01 --end 2025-12-31 --cash 100000
Backtest complete (run_id: abc123):
  Return:       +18.4%  ($100,000 → $118,400)
  Sharpe:       1.42
  Sortino:      1.89
  Max drawdown: -8.2%
  Win rate:     59%
  Total trades: 342

# Show attribution for a backtest run
$ uv run tradebot backtest attribution --run-id abc123
Strategy Attribution:
  ml_ensemble:   +$12,400 (67% of gains)  win_rate=61%
  momentum:      +$4,200  (23% of gains)  win_rate=58%
  event_driven:  +$2,800  (15% of gains)  win_rate=71%
  quantitative:  -$1,000  (drag)          win_rate=48%

# Run Monte Carlo simulation
$ uv run tradebot backtest monte-carlo --run-id abc123 --simulations 1000
Monte Carlo (1000 simulations):
  Actual final value:  $118,400
  Percentile:          92nd (likely skill, >95 = high confidence)
  Median simulated:    $104,200
  5th percentile:      $88,100
  95th percentile:     $121,300

# Show performance by regime
$ uv run tradebot backtest regime --run-id abc123
Performance by Regime:
  Low vol:     +12.1% return, Sharpe 1.8, 180 trades
  Medium vol:  +5.3% return, Sharpe 1.1, 120 trades
  High vol:    +1.0% return, Sharpe 0.3, 42 trades

# Compare two backtest runs
$ uv run tradebot backtest compare --runs abc123,def456
```

#### `tradebot portfolio`

Inspect portfolio state.

```bash
# Show current portfolio
$ uv run tradebot portfolio show
Portfolio ($118,400):
  Cash: $45,200
  Positions:
    BTC/USD   0.5 BTC   @ $50,000  now $52,000  unrealized +$1,000
    ETH/USD   10 ETH    @ $3,200   now $3,100    unrealized -$1,000
    AAPL      50 shares @ $180     now $195       unrealized +$750

# Show trade history
$ uv run tradebot portfolio trades --limit 20 --strategy ml_ensemble
$ uv run tradebot portfolio trades --symbol BTC/USD --since 7d

# Show P&L summary
$ uv run tradebot portfolio pnl --period 30d
P&L (last 30 days):
  Realized:    +$3,200
  Unrealized:  +$750
  Total:       +$3,950
  Win rate:    61% (28 of 46 trades)
```

### CLI Testing

Every CLI command gets its own test using Typer's `CliRunner`:

```python
# tests/unit/cli/test_config_cli.py
from typer.testing import CliRunner
from src.cli.config import app

runner = CliRunner()


class TestConfigCLI:
    def test_validate_valid_config(self, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(VALID_SETTINGS_YAML)
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "✓" in result.output

    def test_validate_invalid_config(self, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text("risk:\n  max_position_pct: -5")  # Invalid
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 1

    def test_schema_known_model(self):
        result = runner.invoke(app, ["schema", "RSSConfig"])
        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert "properties" in schema
        assert "feed_urls" in schema["properties"]

    def test_schema_unknown_model(self):
        result = runner.invoke(app, ["schema", "DoesNotExist"])
        assert result.exit_code == 1


# tests/unit/cli/test_news_cli.py

class TestNewsCLI:
    def test_fetch_with_mock_provider(self, mock_registry):
        """CLI fetches articles using injected mock provider."""
        # CLI accepts --provider mock for testing
        result = runner.invoke(app, [
            "fetch", "--symbol", "BTC/USD", "--since", "1h", "--provider", "mock"
        ])
        assert result.exit_code == 0

    def test_fetch_json_output(self, mock_registry):
        result = runner.invoke(app, [
            "fetch", "--symbol", "BTC/USD", "--since", "1h",
            "--output", "json", "--provider", "mock"
        ])
        assert result.exit_code == 0
        articles = json.loads(result.output)
        assert isinstance(articles, list)
```

### New Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
typer = ">=0.12.0"        # CLI framework
rich = ">=13.0.0"         # Terminal formatting (tables, colors)
```

---

## 13. Implementation Order

Suggested build sequence, each phase independently valuable. **Every phase follows TDD — tests first, then implementation.** Every phase includes CLI commands for the new components.

1. **Provider architecture** — Pydantic configs, protocols, registry, mock implementations, protocol compliance tests, adapt existing providers, `tradebot config` and `tradebot providers` CLI
2. **Sentiment pipeline** — news providers (with mock), article buffer, Ollama scoring (with mock), aggregator, pipeline component tests, `tradebot news` and `tradebot sentiment` CLI
3. **Feature store** — feature engine, technical features, DB persistence, mock feature store, feature vector tests, `tradebot features` CLI
4. **Risk upgrades** — regime detection, dynamic sizing (with mock sizer), correlation checks, circuit breaker, risk context tests, `tradebot risk` CLI
5. **ML pipeline** — XGBoost model (with mock), walk-forward trainer, ML ensemble strategy, training loop component tests, `tradebot models` CLI
6. **New strategies** — event-driven, cross-asset, weighted consensus, strategy adapter tests, `tradebot strategies` CLI
7. **Analytics** — attribution, Monte Carlo, regime tagging, dashboard endpoints, analytics component tests, `tradebot backtest` CLI
8. **LSTM model** — sequential model, ensemble combiner, ensemble prediction tests
9. **Integration tests** — full trading loop, backtest pipeline, news-to-sentiment, ticks-to-features end-to-end
10. **Portfolio CLI** — `tradebot portfolio` commands
11. **Documentation** — all docs written following template, including CLI reference
12. **On-chain data** — Blockchair provider (with mock), on-chain features, compliance tests
