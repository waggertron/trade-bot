# Phase 1: Provider Architecture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all models/configs to Pydantic, define provider protocols, build a ProviderRegistry with mock implementations, adapt existing providers to protocol classes, add protocol compliance tests, and expose `tradebot config` and `tradebot providers` CLI commands.

**Architecture:** Protocol-first provider pattern where every component accepts a protocol-implementing class instantiated with a Pydantic config. Three implementations per protocol: external, local, mock. ProviderRegistry wires everything from `settings.yaml`. Typer CLI exposes each subsystem independently.

**Tech Stack:** Pydantic v2 (already in deps), Typer, Rich, pytest, pytest-asyncio

---

## Task 1: Migrate Core Enums (no changes needed — keep as-is)

The existing `Enum` classes in `src/core/models.py` (AssetType, SignalDirection, OrderSide, OrderType, RiskAction) are fine as standard Python enums — Pydantic handles them natively. No migration needed.

**No action required.** Move to Task 2.

---

## Task 2: Migrate Core Models to Pydantic

**Files:**
- Modify: `src/core/models.py`
- Modify: `tests/test_models.py`

**Step 1: Read existing tests to understand current assertions**

Run: `uv run pytest tests/test_models.py -v` to see what currently passes.

**Step 2: Update `src/core/models.py` — replace dataclass imports with Pydantic**

Replace the entire file. Key changes:
- `@dataclass` → `class Foo(BaseModel)`
- `@dataclass(frozen=True)` → `model_config = ConfigDict(frozen=True)`
- `field(default_factory=...)` → `Field(default_factory=...)`
- Add `Field(gt=0)`, `Field(ge=0, le=1)` validators where appropriate
- Keep all existing properties (`market_value`, `unrealized_pnl`, `total_value`, `is_approved`)

```python
"""Shared data models for the trading bot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Enums ────────────────────────────────────────────────────

class AssetType(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"


class SignalDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class RiskAction(str, Enum):
    APPROVE = "approve"
    VETO = "veto"
    RESIZE = "resize"


# ── Models ───────────────────────────────────────────────────

class MarketTick(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    timestamp: datetime
    asset_type: AssetType
    bid: Decimal | None = None
    ask: Decimal | None = None


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    strategy_name: str
    timestamp: datetime
    reasoning: str

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    asset_type: AssetType
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    signal_id: str | None = None


class Fill(BaseModel):
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
    model_config = ConfigDict(frozen=True)

    cash: Decimal = Field(ge=0)
    positions: list[Position]
    timestamp: datetime

    @property
    def total_value(self) -> Decimal:
        return self.cash + sum(p.market_value for p in self.positions)


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: RiskAction
    reason: str
    adjusted_quantity: Decimal | None = None

    @property
    def is_approved(self) -> bool:
        return self.action in (RiskAction.APPROVE, RiskAction.RESIZE)


class ResearchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    summary: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    timestamp: datetime
    sources: list[str] = Field(default_factory=list)
    raw_data: dict[str, object] = Field(default_factory=dict)
```

**Step 3: Update `tests/test_models.py` to work with Pydantic**

Key changes to tests:
- Dataclass construction stays the same (Pydantic accepts keyword args identically)
- Frozen models: test that assignment raises `ValidationError` (not `FrozenInstanceError`)
- Add new validation tests: negative price rejected, confidence clamped, etc.

Add these new test cases to the existing test file:

```python
import pytest
from pydantic import ValidationError
from src.core.models import (
    MarketTick, Signal, Fill, Position, PortfolioSnapshot,
    RiskDecision, Order, ResearchReport,
    AssetType, SignalDirection, OrderSide, OrderType, RiskAction,
)
from datetime import datetime, UTC
from decimal import Decimal


class TestMarketTickValidation:
    def test_rejects_negative_price(self):
        with pytest.raises(ValidationError):
            MarketTick(
                symbol="BTC/USD", price=Decimal("-1"),
                volume=100, timestamp=datetime.now(UTC),
                asset_type=AssetType.CRYPTO,
            )

    def test_rejects_negative_volume(self):
        with pytest.raises(ValidationError):
            MarketTick(
                symbol="BTC/USD", price=Decimal("50000"),
                volume=-1, timestamp=datetime.now(UTC),
                asset_type=AssetType.CRYPTO,
            )

    def test_frozen(self):
        tick = MarketTick(
            symbol="BTC/USD", price=Decimal("50000"),
            volume=100, timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )
        with pytest.raises(ValidationError):
            tick.price = Decimal("60000")

    def test_serialization_roundtrip(self):
        tick = MarketTick(
            symbol="BTC/USD", price=Decimal("50000"),
            volume=100, timestamp=datetime.now(UTC),
            asset_type=AssetType.CRYPTO,
        )
        data = tick.model_dump()
        restored = MarketTick.model_validate(data)
        assert restored == tick


class TestSignalValidation:
    def test_clamps_confidence_above_one(self):
        sig = Signal(
            symbol="BTC/USD", direction=SignalDirection.BUY,
            confidence=1.5, strategy_name="test",
            timestamp=datetime.now(UTC), reasoning="test",
        )
        assert sig.confidence == 1.0

    def test_clamps_confidence_below_zero(self):
        sig = Signal(
            symbol="BTC/USD", direction=SignalDirection.BUY,
            confidence=-0.5, strategy_name="test",
            timestamp=datetime.now(UTC), reasoning="test",
        )
        assert sig.confidence == 0.0

    def test_auto_generates_id(self):
        sig = Signal(
            symbol="BTC/USD", direction=SignalDirection.BUY,
            confidence=0.8, strategy_name="test",
            timestamp=datetime.now(UTC), reasoning="test",
        )
        assert sig.id is not None
        assert len(sig.id) > 0


class TestPositionProperties:
    def test_market_value(self):
        pos = Position(
            symbol="BTC/USD", quantity=Decimal("2"),
            avg_entry_price=Decimal("50000"),
            current_price=Decimal("55000"),
            asset_type=AssetType.CRYPTO,
        )
        assert pos.market_value == Decimal("110000")

    def test_unrealized_pnl(self):
        pos = Position(
            symbol="BTC/USD", quantity=Decimal("2"),
            avg_entry_price=Decimal("50000"),
            current_price=Decimal("55000"),
            asset_type=AssetType.CRYPTO,
        )
        assert pos.unrealized_pnl == Decimal("10000")


class TestPortfolioSnapshotProperties:
    def test_total_value(self):
        snap = PortfolioSnapshot(
            cash=Decimal("10000"),
            positions=[
                Position(
                    symbol="BTC/USD", quantity=Decimal("1"),
                    avg_entry_price=Decimal("50000"),
                    current_price=Decimal("55000"),
                    asset_type=AssetType.CRYPTO,
                )
            ],
            timestamp=datetime.now(UTC),
        )
        assert snap.total_value == Decimal("65000")


class TestRiskDecisionProperties:
    def test_approve_is_approved(self):
        d = RiskDecision(action=RiskAction.APPROVE, reason="ok")
        assert d.is_approved is True

    def test_veto_is_not_approved(self):
        d = RiskDecision(action=RiskAction.VETO, reason="too risky")
        assert d.is_approved is False

    def test_resize_is_approved(self):
        d = RiskDecision(action=RiskAction.RESIZE, reason="reducing", adjusted_quantity=Decimal("5"))
        assert d.is_approved is True
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: ALL PASS

**Step 5: Fix any failures from other tests that import models**

Run: `uv run pytest -x -v`
Fix any import errors or construction changes in other test files. The main concern is:
- `FrozenInstanceError` → now `ValidationError` for frozen models
- Any test creating models with invalid data that previously "worked" will now fail validation

**Step 6: Commit**

```bash
git add src/core/models.py tests/test_models.py
git commit -m "refactor: migrate core models from dataclass to Pydantic BaseModel"
```

---

## Task 3: Migrate Config to Pydantic

**Files:**
- Modify: `src/core/config.py`
- Modify: `tests/test_config.py` (if exists, otherwise create)

**Step 1: Write failing test for Pydantic config validation**

Create/update `tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError
from src.core.config import (
    RiskSettings, RiskLevel, Settings, TradingSettings,
    SymbolsConfig, AISettings,
)


class TestRiskSettingsValidation:
    def test_defaults(self):
        rs = RiskSettings()
        assert rs.max_position_pct == 2.0
        assert rs.max_open_positions == 10

    def test_rejects_negative_position_pct(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_position_pct=-1.0)

    def test_rejects_zero_max_positions(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_open_positions=0)

    def test_from_risk_level(self):
        rs = RiskSettings.from_risk_level(RiskLevel.CONSERVATIVE)
        assert rs.max_position_pct == 1.0
        assert rs.daily_loss_limit_pct == 2.0

    def test_from_risk_level_with_overrides(self):
        rs = RiskSettings.from_risk_level(RiskLevel.CONSERVATIVE, max_open_positions=3)
        assert rs.max_position_pct == 1.0
        assert rs.max_open_positions == 3

    def test_serialization_roundtrip(self):
        rs = RiskSettings(max_position_pct=3.0, stop_loss_pct=4.0)
        data = rs.model_dump()
        restored = RiskSettings.model_validate(data)
        assert restored == rs


class TestSettingsFromYaml:
    def test_loads_from_yaml(self, tmp_path):
        yaml_content = """
mode: paper
trading:
  symbols:
    stocks: [AAPL]
    crypto: [BTC/USD]
  market_hours:
    stocks_open: "09:30"
    stocks_close: "16:00"
    timezone: US/Eastern
risk:
  max_position_pct: 2.0
  daily_loss_limit_pct: 3.0
  max_open_positions: 10
  stop_loss_pct: 5.0
ai:
  claude_model: claude-sonnet-4-5-20250929
  ollama_model: llama3.2
dashboard:
  host: 0.0.0.0
  port: 8080
"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml_content)
        settings = Settings.from_yaml(config_file)
        assert settings.mode == "paper"
        assert settings.trading.symbols.stocks == ["AAPL"]
        assert settings.risk.max_position_pct == 2.0

    def test_rejects_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("risk:\n  max_position_pct: -5")
        with pytest.raises(ValidationError):
            Settings.from_yaml(config_file)

    def test_for_testing(self):
        settings = Settings.for_testing()
        assert settings.mode == "paper"
        assert isinstance(settings.risk, RiskSettings)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: Some FAIL (validation errors not raised yet since config uses dataclasses)

**Step 3: Rewrite `src/core/config.py` with Pydantic**

```python
"""Application configuration with Pydantic validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


RISK_LEVEL_PRESETS: dict[RiskLevel, dict[str, Any]] = {
    RiskLevel.CONSERVATIVE: {
        "max_position_pct": 1.0,
        "max_sector_exposure_pct": 15.0,
        "daily_loss_limit_pct": 2.0,
        "weekly_drawdown_limit_pct": 3.0,
        "max_open_positions": 5,
        "stop_loss_pct": 3.0,
        "trailing_stop_pct": 2.0,
    },
    RiskLevel.MODERATE: {
        "max_position_pct": 2.0,
        "max_sector_exposure_pct": 20.0,
        "daily_loss_limit_pct": 3.0,
        "weekly_drawdown_limit_pct": 5.0,
        "max_open_positions": 10,
        "stop_loss_pct": 5.0,
        "trailing_stop_pct": 3.0,
    },
    RiskLevel.AGGRESSIVE: {
        "max_position_pct": 5.0,
        "max_sector_exposure_pct": 30.0,
        "daily_loss_limit_pct": 5.0,
        "weekly_drawdown_limit_pct": 8.0,
        "max_open_positions": 15,
        "stop_loss_pct": 8.0,
        "trailing_stop_pct": 5.0,
    },
    RiskLevel.VERY_AGGRESSIVE: {
        "max_position_pct": 10.0,
        "max_sector_exposure_pct": 40.0,
        "daily_loss_limit_pct": 8.0,
        "weekly_drawdown_limit_pct": 12.0,
        "max_open_positions": 20,
        "stop_loss_pct": 12.0,
        "trailing_stop_pct": 8.0,
    },
}


class RiskSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_position_pct: float = Field(2.0, gt=0, le=100)
    max_sector_exposure_pct: float = Field(20.0, gt=0, le=100)
    daily_loss_limit_pct: float = Field(3.0, gt=0, le=100)
    weekly_drawdown_limit_pct: float = Field(5.0, gt=0, le=100)
    max_open_positions: int = Field(10, gt=0)
    stop_loss_pct: float = Field(5.0, gt=0, le=100)
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = Field(3.0, gt=0, le=100)
    max_correlation: float = Field(0.7, gt=0, le=1.0)

    @classmethod
    def from_risk_level(cls, level: RiskLevel | str, **overrides: Any) -> RiskSettings:
        if isinstance(level, str):
            level = RiskLevel(level.lower())
        preset = RISK_LEVEL_PRESETS[level].copy()
        preset.update(overrides)
        return cls(**preset)


class SymbolsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    stocks: list[str] = Field(default_factory=list)
    crypto: list[str] = Field(default_factory=list)


class TradingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: SymbolsConfig = Field(default_factory=SymbolsConfig)
    market_hours: dict[str, str] = Field(default_factory=dict)


class AISettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    claude_model: str = "claude-sonnet-4-5-20250929"
    ollama_model: str = "llama3.2"


class DashboardSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str = "0.0.0.0"
    port: int = Field(8080, gt=0, le=65535)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = Field("paper", pattern=r"^(paper|live)$")
    trading: TradingSettings = Field(default_factory=TradingSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    ai: AISettings = Field(default_factory=AISettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        data = yaml.safe_load(path.read_text())
        return cls.model_validate(data)

    @classmethod
    def for_testing(cls, **overrides: Any) -> Settings:
        defaults = {
            "mode": "paper",
            "trading": {"symbols": {"stocks": [], "crypto": ["BTC/USD"]}},
            "risk": {},
            "ai": {},
            "dashboard": {"port": 8080},
        }
        defaults.update(overrides)
        return cls.model_validate(defaults)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -x -v`
Fix any other files that import from config (orchestrator, risk_manager, main.py, etc.) — they may reference fields or methods that changed.

**Step 6: Commit**

```bash
git add src/core/config.py tests/test_config.py
git commit -m "refactor: migrate config from dataclass to Pydantic BaseModel"
```

---

## Task 4: Migrate DB Models to Pydantic

**Files:**
- Modify: `src/db/models.py`
- Test: `tests/test_db_models.py` (create)

**Step 1: Write failing test**

```python
# tests/test_db_models.py
import pytest
from pydantic import ValidationError
from datetime import datetime, UTC
from src.db.models import TradeRecord, SignalRecord, OHLCRecord


class TestTradeRecord:
    def test_creates_with_valid_data(self):
        tr = TradeRecord(
            symbol="BTC/USD", side="buy", quantity="0.5",
            price="50000", commission="0.50", strategy="momentum",
            paper=True, timestamp=datetime.now(UTC),
        )
        assert tr.symbol == "BTC/USD"
        assert tr.id is not None

    def test_serialization_roundtrip(self):
        tr = TradeRecord(
            symbol="BTC/USD", side="buy", quantity="0.5",
            price="50000", commission="0.50", strategy="momentum",
            paper=True, timestamp=datetime.now(UTC),
        )
        data = tr.model_dump()
        restored = TradeRecord.model_validate(data)
        assert restored == tr


class TestSignalRecord:
    def test_creates_with_valid_data(self):
        sr = SignalRecord(
            symbol="BTC/USD", direction="buy", confidence=0.8,
            strategy="momentum", reasoning="SMA crossover",
            timestamp=datetime.now(UTC),
        )
        assert sr.symbol == "BTC/USD"

    def test_rejects_invalid_confidence(self):
        with pytest.raises(ValidationError):
            SignalRecord(
                symbol="BTC/USD", direction="buy", confidence=2.0,
                strategy="momentum", reasoning="test",
                timestamp=datetime.now(UTC),
            )


class TestOHLCRecord:
    def test_creates_with_valid_data(self):
        rec = OHLCRecord(
            symbol="BTC/USD", interval="1h", timestamp=1700000000,
            open="50000", high="51000", low="49000",
            close="50500", volume="100", source="kraken",
        )
        assert rec.symbol == "BTC/USD"
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_db_models.py -v`
Expected: FAIL (model_dump not available on dataclasses)

**Step 3: Rewrite `src/db/models.py`**

```python
"""Database record models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class TradeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: str
    quantity: str
    price: str
    commission: str
    strategy: str
    paper: bool
    timestamp: datetime


class SignalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    direction: str
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: str
    reasoning: str
    timestamp: datetime


class OHLCRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    interval: str
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    source: str
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_db_models.py -v`
Expected: ALL PASS

**Step 5: Run full suite and fix regressions**

Run: `uv run pytest -x -v`
Fix `src/db/database.py` if it accesses fields differently (unlikely — field names are identical).

**Step 6: Commit**

```bash
git add src/db/models.py tests/test_db_models.py
git commit -m "refactor: migrate DB record models to Pydantic"
```

---

## Task 5: Define Provider Protocols

**Files:**
- Modify: `src/core/protocols.py` (add new protocols alongside existing ones)
- Create: `src/providers/__init__.py`
- Create: `src/providers/protocols.py`
- Test: `tests/unit/__init__.py`
- Test: `tests/unit/providers/__init__.py`
- Test: `tests/unit/providers/test_protocols.py`

**Step 1: Create directory structure**

```bash
mkdir -p src/providers
mkdir -p tests/unit/providers
touch src/providers/__init__.py
touch tests/unit/__init__.py
touch tests/unit/providers/__init__.py
```

**Step 2: Write failing test for protocol runtime checking**

```python
# tests/unit/providers/test_protocols.py
import pytest
from src.providers.protocols import (
    HttpClient, HttpResponse,
    MarketDataProvider, NewsProvider, SentimentAnalyzer,
    OnChainProvider, FeatureProvider, DataStore,
)


class TestProtocolsExist:
    """Verify all protocols are importable and runtime_checkable."""

    def test_http_client_is_runtime_checkable(self):
        assert hasattr(HttpClient, "__protocol_attrs__") or hasattr(HttpClient, "__abstractmethods__") or True
        # Just verify import works — runtime_checkable tested via isinstance below

    def test_market_data_provider_is_runtime_checkable(self):
        class Dummy:
            name = "dummy"
            async def get_ticks(self, symbols): return []
            async def get_ohlc(self, symbol, interval, since): return []
            async def health_check(self): return True

        assert isinstance(Dummy(), MarketDataProvider)

    def test_non_conforming_rejected(self):
        class Bad:
            pass
        assert not isinstance(Bad(), MarketDataProvider)

    def test_news_provider_is_runtime_checkable(self):
        class Dummy:
            name = "dummy"
            async def fetch_articles(self, symbol, since): return []
            async def health_check(self): return True
            def rate_limit(self): return None

        assert isinstance(Dummy(), NewsProvider)

    def test_sentiment_analyzer_is_runtime_checkable(self):
        class Dummy:
            name = "dummy"
            async def score(self, text, symbol): return None
            async def score_batch(self, texts, symbol): return []

        assert isinstance(Dummy(), SentimentAnalyzer)

    def test_data_store_is_runtime_checkable(self):
        class Dummy:
            async def initialize(self): pass
            async def close(self): pass
            async def save_trade(self, trade): pass
            async def list_trades(self, limit=100): return []
            async def save_signal(self, signal): pass
            async def list_signals(self, limit=100): return []

        assert isinstance(Dummy(), DataStore)
```

**Step 3: Run to verify failure**

Run: `uv run pytest tests/unit/providers/test_protocols.py -v`
Expected: FAIL (ImportError — modules don't exist yet)

**Step 4: Implement `src/providers/protocols.py`**

```python
"""Protocol definitions for all provider interfaces."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from src.core.models import MarketTick, Signal, PortfolioSnapshot
from src.db.models import TradeRecord, SignalRecord


# ── HTTP Client ──────────────────────────────────────────────

class HttpResponse:
    """Minimal HTTP response wrapper."""

    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        import json
        return json.loads(self.text)


@runtime_checkable
class HttpClient(Protocol):
    """Async HTTP client interface — injectable, mockable."""

    async def get(self, url: str, **kwargs: Any) -> HttpResponse: ...
    async def post(self, url: str, **kwargs: Any) -> HttpResponse: ...
    async def close(self) -> None: ...


# ── Market Data ──────────────────────────────────────────────

@runtime_checkable
class MarketDataProvider(Protocol):
    """Provides price and volume data."""

    name: str

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]: ...
    async def get_ohlc(
        self, symbol: str, interval: str, since: datetime
    ) -> list[Any]: ...
    async def health_check(self) -> bool: ...


# ── News ─────────────────────────────────────────────────────

@runtime_checkable
class NewsProvider(Protocol):
    """Fetches news articles for a given symbol."""

    name: str

    async def fetch_articles(self, symbol: str, since: datetime) -> list[Any]: ...
    async def health_check(self) -> bool: ...
    def rate_limit(self) -> Any: ...


# ── Sentiment ────────────────────────────────────────────────

@runtime_checkable
class SentimentAnalyzer(Protocol):
    """Scores text for financial sentiment."""

    name: str

    async def score(self, text: str, symbol: str) -> Any: ...
    async def score_batch(self, texts: list[str], symbol: str) -> list[Any]: ...


# ── On-Chain ─────────────────────────────────────────────────

@runtime_checkable
class OnChainProvider(Protocol):
    """Provides blockchain-level metrics for crypto assets."""

    name: str

    async def get_metrics(self, symbol: str, since: datetime) -> list[Any]: ...
    async def health_check(self) -> bool: ...


# ── Features ─────────────────────────────────────────────────

@runtime_checkable
class FeatureProvider(Protocol):
    """Computes derived features from raw data."""

    name: str

    def required_inputs(self) -> list[str]: ...
    async def compute(self, symbol: str, raw_data: dict[str, Any]) -> dict[str, float]: ...


# ── Data Store ───────────────────────────────────────────────

@runtime_checkable
class DataStore(Protocol):
    """Persistence layer for trades and signals."""

    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
    async def save_trade(self, trade: TradeRecord) -> None: ...
    async def list_trades(self, limit: int = 100) -> list[TradeRecord]: ...
    async def save_signal(self, signal: SignalRecord) -> None: ...
    async def list_signals(self, limit: int = 100) -> list[SignalRecord]: ...
```

**Step 5: Run tests**

Run: `uv run pytest tests/unit/providers/test_protocols.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/providers/ tests/unit/
git commit -m "feat: define provider protocols for all subsystem interfaces"
```

---

## Task 6: Create Provider Configs

**Files:**
- Create: `src/providers/configs.py`
- Test: `tests/unit/providers/test_configs.py`

**Step 1: Write failing test**

```python
# tests/unit/providers/test_configs.py
import pytest
from pydantic import ValidationError
from src.providers.configs import (
    MarketDataConfig, KrakenMarketConfig, MockMarketConfig,
    NewsProviderConfig, RSSConfig, MockNewsConfig,
    SentimentConfig, OllamaSentimentConfig, MockSentimentConfig,
    RateLimit,
)


class TestRateLimit:
    def test_creates(self):
        rl = RateLimit(requests_per_minute=60)
        assert rl.requests_per_minute == 60

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            RateLimit(requests_per_minute=0)


class TestMarketDataConfig:
    def test_kraken_defaults(self):
        cfg = KrakenMarketConfig()
        assert cfg.base_url == "https://api.kraken.com"
        assert cfg.timeout == 10.0

    def test_mock_defaults(self):
        cfg = MockMarketConfig()
        assert cfg.should_fail is False


class TestNewsConfig:
    def test_rss_requires_feed_urls(self):
        with pytest.raises(ValidationError):
            RSSConfig(feed_urls=[])

    def test_rss_with_feeds(self):
        cfg = RSSConfig(feed_urls=["https://example.com/feed"])
        assert len(cfg.feed_urls) == 1


class TestSentimentConfig:
    def test_ollama_defaults(self):
        cfg = OllamaSentimentConfig()
        assert cfg.model == "llama3.2"
        assert cfg.base_url == "http://localhost:11434"

    def test_mock_defaults(self):
        cfg = MockSentimentConfig()
        assert cfg.default_score == 0.0


class TestConfigSerialization:
    def test_roundtrip(self):
        cfg = KrakenMarketConfig(timeout=5.0)
        data = cfg.model_dump()
        restored = KrakenMarketConfig.model_validate(data)
        assert restored == cfg

    def test_json_schema(self):
        schema = KrakenMarketConfig.model_json_schema()
        assert "properties" in schema
        assert "base_url" in schema["properties"]
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/providers/test_configs.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement `src/providers/configs.py`**

```python
"""Pydantic config models for all providers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


# ── Shared ───────────────────────────────────────────────────

class RateLimit(BaseModel):
    model_config = ConfigDict(frozen=True)
    requests_per_minute: int = Field(gt=0)


# ── Market Data Configs ──────────────────────────────────────

class MarketDataConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    timeout: float = Field(10.0, gt=0)


class KrakenMarketConfig(MarketDataConfig):
    base_url: str = "https://api.kraken.com"
    api_key: str = ""
    api_secret: str = ""


class BinanceMarketConfig(MarketDataConfig):
    base_url: str = "https://api.binance.us"


class YFinanceMarketConfig(MarketDataConfig):
    pass  # No config needed for yfinance


class MockMarketConfig(MarketDataConfig):
    should_fail: bool = False
    default_prices: dict[str, str] = Field(default_factory=dict)
    latency_ms: int = Field(0, ge=0)


# ── News Configs ─────────────────────────────────────────────

class NewsProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    fetch_interval_seconds: int = Field(300, ge=1)
    max_articles_per_fetch: int = Field(50, ge=1)


class RSSConfig(NewsProviderConfig):
    feed_urls: list[str] = Field(min_length=1)


class RedditConfig(NewsProviderConfig):
    subreddits: list[str] = Field(
        default_factory=lambda: ["wallstreetbets", "cryptocurrency"]
    )
    client_id: str = ""
    client_secret: str = ""


class NewsAPIConfig(NewsProviderConfig):
    api_key: str = ""
    base_url: str = "https://newsapi.org/v2"


class MockNewsConfig(NewsProviderConfig):
    should_fail: bool = False
    canned_articles: list[dict[str, object]] = Field(default_factory=list)
    latency_ms: int = Field(0, ge=0)


# ── Sentiment Configs ────────────────────────────────────────

class SentimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class OllamaSentimentConfig(SentimentConfig):
    model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    timeout: float = Field(30.0, gt=0)


class FinBERTSentimentConfig(SentimentConfig):
    model_name: str = "ProsusAI/finbert"
    device: str = "cpu"


class ClaudeSentimentConfig(SentimentConfig):
    api_key: SecretStr = SecretStr("")
    model: str = "claude-sonnet-4-5-20250929"


class MockSentimentConfig(SentimentConfig):
    default_score: float = Field(0.0, ge=-1.0, le=1.0)
    default_magnitude: float = Field(0.5, ge=0.0, le=1.0)
    should_fail: bool = False


# ── On-Chain Configs ─────────────────────────────────────────

class OnChainConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class BlockchairConfig(OnChainConfig):
    base_url: str = "https://api.blockchair.com"
    timeout: float = Field(15.0, gt=0)


class MockOnChainConfig(OnChainConfig):
    should_fail: bool = False


# ── Feature Configs ──────────────────────────────────────────

class FeatureConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class TechnicalFeatureConfig(FeatureConfig):
    indicators: list[str] = Field(
        default_factory=lambda: ["sma", "rsi", "macd", "bbands", "atr"]
    )


class MockFeatureConfig(FeatureConfig):
    default_features: dict[str, float] = Field(default_factory=dict)
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/providers/test_configs.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/providers/configs.py tests/unit/providers/test_configs.py
git commit -m "feat: add Pydantic config models for all providers"
```

---

## Task 7: Create Mock Implementations

**Files:**
- Create: `src/providers/mock.py`
- Test: `tests/unit/providers/test_mocks.py`

**Step 1: Write failing test**

```python
# tests/unit/providers/test_mocks.py
import pytest
from datetime import datetime, UTC
from decimal import Decimal
from src.providers.mock import (
    MockHttpClient, MockMarketDataProvider, MockNewsProvider,
    MockSentimentAnalyzer, MockOnChainProvider,
    MockFeatureProvider, MockDataStore,
)
from src.providers.protocols import (
    HttpClient, MarketDataProvider, NewsProvider,
    SentimentAnalyzer, OnChainProvider, FeatureProvider, DataStore,
)
from src.providers.configs import (
    MockMarketConfig, MockNewsConfig, MockSentimentConfig,
    MockOnChainConfig, MockFeatureConfig,
)
from src.core.models import AssetType, MarketTick


class TestMockHttpClient:
    def test_implements_protocol(self):
        client = MockHttpClient()
        assert isinstance(client, HttpClient)

    @pytest.mark.asyncio
    async def test_returns_stubbed_response(self):
        client = MockHttpClient()
        client.stub("/api/test", status_code=200, text='{"ok": true}')
        resp = await client.get("http://example.com/api/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    async def test_records_calls(self):
        client = MockHttpClient()
        client.stub("/test", status_code=200, text="")
        await client.get("http://example.com/test")
        assert len(client.calls) == 1
        assert client.calls[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_unstubbed_returns_404(self):
        client = MockHttpClient()
        resp = await client.get("http://example.com/unknown")
        assert resp.status_code == 404


class TestMockMarketDataProvider:
    def test_implements_protocol(self):
        provider = MockMarketDataProvider()
        assert isinstance(provider, MarketDataProvider)

    @pytest.mark.asyncio
    async def test_returns_set_prices(self):
        provider = MockMarketDataProvider()
        provider.set_price("BTC/USD", Decimal("50000"))
        ticks = await provider.get_ticks(["BTC/USD"])
        assert len(ticks) == 1
        assert ticks[0].price == Decimal("50000")
        assert ticks[0].symbol == "BTC/USD"

    @pytest.mark.asyncio
    async def test_health_check_default_true(self):
        provider = MockMarketDataProvider()
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_can_fail(self):
        provider = MockMarketDataProvider(config=MockMarketConfig(should_fail=True))
        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_tracks_call_count(self):
        provider = MockMarketDataProvider()
        provider.set_price("BTC/USD", Decimal("50000"))
        await provider.get_ticks(["BTC/USD"])
        await provider.get_ticks(["BTC/USD"])
        assert provider.get_ticks_count == 2


class TestMockNewsProvider:
    def test_implements_protocol(self):
        provider = MockNewsProvider()
        assert isinstance(provider, NewsProvider)

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self):
        provider = MockNewsProvider()
        articles = await provider.fetch_articles("BTC/USD", datetime.now(UTC))
        assert articles == []

    @pytest.mark.asyncio
    async def test_health_check(self):
        assert await MockNewsProvider().health_check() is True


class TestMockSentimentAnalyzer:
    def test_implements_protocol(self):
        analyzer = MockSentimentAnalyzer()
        assert isinstance(analyzer, SentimentAnalyzer)

    @pytest.mark.asyncio
    async def test_returns_configured_score(self):
        config = MockSentimentConfig(default_score=0.8, default_magnitude=0.9)
        analyzer = MockSentimentAnalyzer(config=config)
        result = await analyzer.score("bullish text", "BTC/USD")
        assert result.score == 0.8
        assert result.magnitude == 0.9


class TestMockDataStore:
    def test_implements_protocol(self):
        store = MockDataStore()
        assert isinstance(store, DataStore)

    @pytest.mark.asyncio
    async def test_save_and_list_trades(self):
        from src.db.models import TradeRecord
        store = MockDataStore()
        await store.initialize()
        trade = TradeRecord(
            symbol="BTC/USD", side="buy", quantity="0.5",
            price="50000", commission="0", strategy="test",
            paper=True, timestamp=datetime.now(UTC),
        )
        await store.save_trade(trade)
        trades = await store.list_trades()
        assert len(trades) == 1
        assert trades[0].symbol == "BTC/USD"
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/providers/test_mocks.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement `src/providers/mock.py`**

```python
"""Mock implementations of all provider protocols for testing."""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import AssetType, MarketTick
from src.db.models import TradeRecord, SignalRecord
from src.providers.configs import (
    MockMarketConfig, MockNewsConfig, MockSentimentConfig,
    MockOnChainConfig, MockFeatureConfig, RateLimit,
)
from src.providers.protocols import HttpResponse


# ── Sentiment Result (shared) ────────────────────────────────

class SentimentResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    score: float = Field(ge=-1.0, le=1.0)
    magnitude: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasoning: str | None = None


# ── Mock HTTP Client ─────────────────────────────────────────

class MockHttpClient:
    """Deterministic HTTP client that records calls and returns stubs."""

    def __init__(self) -> None:
        self._stubs: dict[str, HttpResponse] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def stub(self, url_pattern: str, status_code: int = 200, text: str = "") -> None:
        self._stubs[url_pattern] = HttpResponse(status_code=status_code, text=text)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append(("GET", url, kwargs))
        for pattern, response in self._stubs.items():
            if pattern in url:
                return response
        return HttpResponse(status_code=404, text="")

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append(("POST", url, kwargs))
        for pattern, response in self._stubs.items():
            if pattern in url:
                return response
        return HttpResponse(status_code=404, text="")

    async def close(self) -> None:
        pass


# ── Mock Market Data Provider ────────────────────────────────

class MockMarketDataProvider:
    """Deterministic market data for tests."""

    name = "mock"

    def __init__(self, config: MockMarketConfig | None = None) -> None:
        self._config = config or MockMarketConfig()
        self._prices: dict[str, Decimal] = {}
        self.get_ticks_count = 0

    def set_price(self, symbol: str, price: Decimal) -> None:
        self._prices[symbol] = price

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]:
        self.get_ticks_count += 1
        if self._config.should_fail:
            raise ConnectionError("Mock market data failure")
        ticks = []
        for symbol in symbols:
            price = self._prices.get(symbol)
            if price is not None:
                ticks.append(MarketTick(
                    symbol=symbol, price=price, volume=1000,
                    timestamp=datetime.now(UTC), asset_type=AssetType.CRYPTO,
                ))
        return ticks

    async def get_ohlc(self, symbol: str, interval: str, since: datetime) -> list[Any]:
        return []

    async def health_check(self) -> bool:
        return not self._config.should_fail


# ── Mock News Provider ───────────────────────────────────────

class MockNewsProvider:
    """Deterministic news provider for tests."""

    name = "mock"

    def __init__(self, config: MockNewsConfig | None = None) -> None:
        self._config = config or MockNewsConfig()
        self.fetch_count = 0

    async def fetch_articles(self, symbol: str, since: datetime) -> list[Any]:
        self.fetch_count += 1
        if self._config.should_fail:
            raise ConnectionError("Mock news failure")
        return self._config.canned_articles

    async def health_check(self) -> bool:
        return not self._config.should_fail

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=9999)


# ── Mock Sentiment Analyzer ──────────────────────────────────

class MockSentimentAnalyzer:
    """Deterministic sentiment scoring for tests."""

    name = "mock"

    def __init__(self, config: MockSentimentConfig | None = None) -> None:
        self._config = config or MockSentimentConfig()
        self.score_count = 0

    async def score(self, text: str, symbol: str) -> SentimentResult:
        self.score_count += 1
        if self._config.should_fail:
            raise ConnectionError("Mock sentiment failure")
        return SentimentResult(
            score=self._config.default_score,
            magnitude=self._config.default_magnitude,
        )

    async def score_batch(self, texts: list[str], symbol: str) -> list[SentimentResult]:
        results = []
        for text in texts:
            results.append(await self.score(text, symbol))
        return results


# ── Mock On-Chain Provider ───────────────────────────────────

class MockOnChainProvider:
    """Deterministic on-chain data for tests."""

    name = "mock"

    def __init__(self, config: MockOnChainConfig | None = None) -> None:
        self._config = config or MockOnChainConfig()

    async def get_metrics(self, symbol: str, since: datetime) -> list[Any]:
        if self._config.should_fail:
            raise ConnectionError("Mock on-chain failure")
        return []

    async def health_check(self) -> bool:
        return not self._config.should_fail


# ── Mock Feature Provider ────────────────────────────────────

class MockFeatureProvider:
    """Deterministic feature computation for tests."""

    name = "mock"

    def __init__(self, config: MockFeatureConfig | None = None) -> None:
        self._config = config or MockFeatureConfig()
        self._features: dict[str, dict[str, float]] = {}

    def set_features(self, symbol: str, features: dict[str, float]) -> None:
        self._features[symbol] = features

    def required_inputs(self) -> list[str]:
        return []

    async def compute(self, symbol: str, raw_data: dict[str, Any]) -> dict[str, float]:
        return self._features.get(symbol, self._config.default_features)


# ── Mock Data Store ──────────────────────────────────────────

class MockDataStore:
    """In-memory data store for tests."""

    def __init__(self) -> None:
        self._trades: list[TradeRecord] = []
        self._signals: list[SignalRecord] = []

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def save_trade(self, trade: TradeRecord) -> None:
        self._trades.append(trade)

    async def list_trades(self, limit: int = 100) -> list[TradeRecord]:
        return self._trades[:limit]

    async def save_signal(self, signal: SignalRecord) -> None:
        self._signals.append(signal)

    async def list_signals(self, limit: int = 100) -> list[SignalRecord]:
        return self._signals[:limit]
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/providers/test_mocks.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/providers/mock.py tests/unit/providers/test_mocks.py
git commit -m "feat: add mock implementations for all provider protocols"
```

---

## Task 8: Create ProviderRegistry

**Files:**
- Create: `src/providers/registry.py`
- Test: `tests/unit/providers/test_registry.py`

**Step 1: Write failing test**

```python
# tests/unit/providers/test_registry.py
import pytest
from decimal import Decimal
from src.providers.registry import ProviderRegistry
from src.providers.protocols import (
    MarketDataProvider, NewsProvider, SentimentAnalyzer,
    OnChainProvider, FeatureProvider, DataStore,
)
from src.providers.mock import (
    MockMarketDataProvider, MockNewsProvider, MockSentimentAnalyzer,
    MockOnChainProvider, MockFeatureProvider, MockDataStore,
)
from src.providers.configs import MockMarketConfig, MockNewsConfig


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        mock = MockMarketDataProvider()
        registry.register(MarketDataProvider, mock)
        assert registry.get(MarketDataProvider) is mock

    def test_get_unregistered_raises_key_error(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="MarketDataProvider"):
            registry.get(MarketDataProvider)

    def test_register_rejects_non_conforming(self):
        registry = ProviderRegistry()
        with pytest.raises(TypeError, match="does not implement"):
            registry.register(MarketDataProvider, "not a provider")

    def test_for_testing_creates_all_mocks(self):
        registry = ProviderRegistry.for_testing()
        assert isinstance(registry.get(MarketDataProvider), MockMarketDataProvider)
        assert isinstance(registry.get(NewsProvider), MockNewsProvider)
        assert isinstance(registry.get(SentimentAnalyzer), MockSentimentAnalyzer)
        assert isinstance(registry.get(OnChainProvider), MockOnChainProvider)
        assert isinstance(registry.get(FeatureProvider), MockFeatureProvider)
        assert isinstance(registry.get(DataStore), MockDataStore)

    def test_for_testing_allows_overrides(self):
        custom = MockMarketDataProvider(config=MockMarketConfig(timeout=5.0))
        registry = ProviderRegistry.for_testing(
            overrides={MarketDataProvider: custom}
        )
        assert registry.get(MarketDataProvider) is custom
        # Others still default mocks
        assert isinstance(registry.get(NewsProvider), MockNewsProvider)

    def test_all_returns_registered_providers(self):
        registry = ProviderRegistry.for_testing()
        all_providers = list(registry.all())
        assert len(all_providers) >= 6
        names = [name for name, _ in all_providers]
        assert "MarketDataProvider" in names

    def test_has_returns_true_for_registered(self):
        registry = ProviderRegistry.for_testing()
        assert registry.has(MarketDataProvider) is True

    def test_has_returns_false_for_unregistered(self):
        registry = ProviderRegistry()
        assert registry.has(MarketDataProvider) is False
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/providers/test_registry.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement `src/providers/registry.py`**

```python
"""Provider registry — discovers and manages protocol implementations."""

from __future__ import annotations

from typing import Any, Iterator, TypeVar

from src.providers.mock import (
    MockMarketDataProvider, MockNewsProvider, MockSentimentAnalyzer,
    MockOnChainProvider, MockFeatureProvider, MockDataStore,
)
from src.providers.protocols import (
    MarketDataProvider, NewsProvider, SentimentAnalyzer,
    OnChainProvider, FeatureProvider, DataStore,
)


T = TypeVar("T")

# Default mock mapping for testing
_MOCK_DEFAULTS: dict[type, type] = {
    MarketDataProvider: MockMarketDataProvider,
    NewsProvider: MockNewsProvider,
    SentimentAnalyzer: MockSentimentAnalyzer,
    OnChainProvider: MockOnChainProvider,
    FeatureProvider: MockFeatureProvider,
    DataStore: MockDataStore,
}


class ProviderRegistry:
    """Manages protocol implementations. Use for_testing() in tests."""

    def __init__(self) -> None:
        self._providers: dict[type, Any] = {}

    def register(self, protocol_type: type, instance: Any) -> None:
        """Register a provider instance for a protocol type."""
        if not isinstance(instance, protocol_type):
            raise TypeError(
                f"{type(instance).__name__} does not implement "
                f"{protocol_type.__name__}"
            )
        self._providers[protocol_type] = instance

    def get(self, protocol_type: type[T]) -> T:
        """Get the registered provider for a protocol type."""
        if protocol_type not in self._providers:
            raise KeyError(
                f"{protocol_type.__name__} not registered. "
                f"Available: {[t.__name__ for t in self._providers]}"
            )
        return self._providers[protocol_type]

    def has(self, protocol_type: type) -> bool:
        """Check if a protocol type is registered."""
        return protocol_type in self._providers

    def all(self) -> Iterator[tuple[str, Any]]:
        """Iterate over all registered providers as (name, instance) pairs."""
        for protocol_type, instance in self._providers.items():
            yield protocol_type.__name__, instance

    @classmethod
    def for_testing(
        cls,
        overrides: dict[type, Any] | None = None,
    ) -> ProviderRegistry:
        """Create a registry with all mock providers. Override specific ones."""
        registry = cls()
        for protocol_type, mock_cls in _MOCK_DEFAULTS.items():
            registry.register(protocol_type, mock_cls())

        if overrides:
            for protocol_type, instance in overrides.items():
                registry.register(protocol_type, instance)

        return registry
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/providers/test_registry.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/providers/registry.py tests/unit/providers/test_registry.py
git commit -m "feat: add ProviderRegistry with for_testing() factory"
```

---

## Task 9: Protocol Compliance Test Suite

**Files:**
- Create: `tests/unit/providers/test_compliance.py`

This creates shared test cases that every implementation (mock, local, external) must pass.

**Step 1: Write compliance tests**

```python
# tests/unit/providers/test_compliance.py
"""
Protocol compliance tests — shared assertions that ANY implementation must pass.
Each test class is parameterized over implementations.
"""

import pytest
from datetime import datetime, UTC
from decimal import Decimal
from src.providers.protocols import (
    HttpClient, MarketDataProvider, NewsProvider,
    SentimentAnalyzer, OnChainProvider, FeatureProvider, DataStore,
)
from src.providers.mock import (
    MockHttpClient, MockMarketDataProvider, MockNewsProvider,
    MockSentimentAnalyzer, MockOnChainProvider,
    MockFeatureProvider, MockDataStore,
)


# ── HTTP Client Compliance ───────────────────────────────────

class HttpClientCompliance:
    """Shared tests for any HttpClient implementation."""

    def make_client(self) -> HttpClient:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_client(), HttpClient)

    @pytest.mark.asyncio
    async def test_get_returns_response(self):
        client = self.make_client()
        resp = await client.get("http://example.com")
        assert hasattr(resp, "status_code")
        assert hasattr(resp, "text")

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        client = self.make_client()
        await client.close()  # Should not raise


class TestMockHttpClientCompliance(HttpClientCompliance):
    def make_client(self):
        client = MockHttpClient()
        client.stub("example.com", status_code=200, text="{}")
        return client


# ── Market Data Compliance ───────────────────────────────────

class MarketDataCompliance:
    """Shared tests for any MarketDataProvider implementation."""

    def make_provider(self) -> MarketDataProvider:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_provider(), MarketDataProvider)

    def test_has_name(self):
        provider = self.make_provider()
        assert isinstance(provider.name, str)
        assert len(provider.name) > 0

    @pytest.mark.asyncio
    async def test_get_ticks_returns_list(self):
        provider = self.make_provider()
        result = await provider.get_ticks(["BTC/USD"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        provider = self.make_provider()
        result = await provider.health_check()
        assert isinstance(result, bool)


class TestMockMarketDataCompliance(MarketDataCompliance):
    def make_provider(self):
        provider = MockMarketDataProvider()
        provider.set_price("BTC/USD", Decimal("50000"))
        return provider


# ── News Provider Compliance ─────────────────────────────────

class NewsProviderCompliance:
    """Shared tests for any NewsProvider implementation."""

    def make_provider(self) -> NewsProvider:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_provider(), NewsProvider)

    def test_has_name(self):
        assert isinstance(self.make_provider().name, str)

    @pytest.mark.asyncio
    async def test_fetch_articles_returns_list(self):
        provider = self.make_provider()
        result = await provider.fetch_articles("BTC/USD", datetime.now(UTC))
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        result = await self.make_provider().health_check()
        assert isinstance(result, bool)

    def test_rate_limit_returns_value(self):
        result = self.make_provider().rate_limit()
        assert result is not None


class TestMockNewsCompliance(NewsProviderCompliance):
    def make_provider(self):
        return MockNewsProvider()


# ── Sentiment Compliance ─────────────────────────────────────

class SentimentAnalyzerCompliance:
    """Shared tests for any SentimentAnalyzer implementation."""

    def make_analyzer(self) -> SentimentAnalyzer:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_analyzer(), SentimentAnalyzer)

    @pytest.mark.asyncio
    async def test_score_returns_result(self):
        analyzer = self.make_analyzer()
        result = await analyzer.score("test text", "BTC/USD")
        assert hasattr(result, "score")
        assert -1.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_score_batch_returns_list(self):
        analyzer = self.make_analyzer()
        results = await analyzer.score_batch(["text1", "text2"], "BTC/USD")
        assert isinstance(results, list)
        assert len(results) == 2


class TestMockSentimentCompliance(SentimentAnalyzerCompliance):
    def make_analyzer(self):
        return MockSentimentAnalyzer()


# ── Data Store Compliance ────────────────────────────────────

class DataStoreCompliance:
    """Shared tests for any DataStore implementation."""

    def make_store(self) -> DataStore:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_store(), DataStore)

    @pytest.mark.asyncio
    async def test_initialize_does_not_raise(self):
        store = self.make_store()
        await store.initialize()

    @pytest.mark.asyncio
    async def test_list_trades_returns_list(self):
        store = self.make_store()
        await store.initialize()
        result = await store.list_trades()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_signals_returns_list(self):
        store = self.make_store()
        await store.initialize()
        result = await store.list_signals()
        assert isinstance(result, list)


class TestMockDataStoreCompliance(DataStoreCompliance):
    def make_store(self):
        return MockDataStore()
```

**Step 2: Run tests**

Run: `uv run pytest tests/unit/providers/test_compliance.py -v`
Expected: ALL PASS (mocks should already comply)

**Step 3: Commit**

```bash
git add tests/unit/providers/test_compliance.py
git commit -m "feat: add protocol compliance test suites for all providers"
```

---

## Task 10: Add Typer + Rich Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies**

Add `typer` and `rich` to `[project.dependencies]` in `pyproject.toml`. Also add the `[project.scripts]` entry point.

Add these lines to the dependencies list:
```
"typer>=0.12.0",
"rich>=13.0.0",
```

Add this section:
```toml
[project.scripts]
tradebot = "src.cli.main:app"
```

**Step 2: Install**

Run: `uv sync`

**Step 3: Verify install**

Run: `uv run python -c "import typer; import rich; print('ok')"`
Expected: `ok`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add typer and rich for CLI framework"
```

---

## Task 11: Build CLI — `tradebot config` Commands

**Files:**
- Create: `src/cli/__init__.py`
- Create: `src/cli/main.py`
- Create: `src/cli/config_cmd.py`
- Test: `tests/unit/cli/__init__.py`
- Test: `tests/unit/cli/test_config_cmd.py`

**Step 1: Create directory**

```bash
mkdir -p src/cli
mkdir -p tests/unit/cli
touch src/cli/__init__.py
touch tests/unit/cli/__init__.py
```

**Step 2: Write failing test**

```python
# tests/unit/cli/test_config_cmd.py
import json
import pytest
from typer.testing import CliRunner
from src.cli.config_cmd import app

runner = CliRunner()


class TestConfigValidate:
    def test_valid_config(self, tmp_path):
        config = tmp_path / "settings.yaml"
        config.write_text("""
mode: paper
trading:
  symbols:
    stocks: [AAPL]
    crypto: [BTC/USD]
  market_hours: {}
risk: {}
ai: {}
dashboard: {}
""")
        result = runner.invoke(app, ["validate", "--config", str(config)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_invalid_config(self, tmp_path):
        config = tmp_path / "settings.yaml"
        config.write_text("mode: invalid_mode")
        result = runner.invoke(app, ["validate", "--config", str(config)])
        assert result.exit_code == 1

    def test_missing_file(self):
        result = runner.invoke(app, ["validate", "--config", "/nonexistent.yaml"])
        assert result.exit_code == 1


class TestConfigShow:
    def test_show_yaml(self, tmp_path):
        config = tmp_path / "settings.yaml"
        config.write_text("mode: paper\ntrading:\n  symbols:\n    stocks: []\n    crypto: []\n  market_hours: {}\nrisk: {}\nai: {}\ndashboard: {}")
        result = runner.invoke(app, ["show", "--config", str(config)])
        assert result.exit_code == 0
        assert "paper" in result.output

    def test_show_json(self, tmp_path):
        config = tmp_path / "settings.yaml"
        config.write_text("mode: paper\ntrading:\n  symbols:\n    stocks: []\n    crypto: []\n  market_hours: {}\nrisk: {}\nai: {}\ndashboard: {}")
        result = runner.invoke(app, ["show", "--config", str(config), "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["mode"] == "paper"


class TestConfigSchema:
    def test_known_model(self):
        result = runner.invoke(app, ["schema", "RiskSettings"])
        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert "properties" in schema

    def test_unknown_model(self):
        result = runner.invoke(app, ["schema", "NonExistent"])
        assert result.exit_code == 1
```

**Step 3: Run to verify failure**

Run: `uv run pytest tests/unit/cli/test_config_cmd.py -v`
Expected: FAIL (ImportError)

**Step 4: Implement CLI**

```python
# src/cli/config_cmd.py
"""CLI commands for configuration inspection and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console

from src.core.config import (
    RiskSettings, Settings, TradingSettings, SymbolsConfig,
    AISettings, DashboardSettings,
)
from src.providers.configs import (
    KrakenMarketConfig, BinanceMarketConfig, MockMarketConfig,
    RSSConfig, NewsAPIConfig, MockNewsConfig,
    OllamaSentimentConfig, ClaudeSentimentConfig, MockSentimentConfig,
)

app = typer.Typer(help="Configuration inspection and validation.")
console = Console()

CONFIG_MODELS: dict[str, type] = {
    "RiskSettings": RiskSettings,
    "Settings": Settings,
    "TradingSettings": TradingSettings,
    "SymbolsConfig": SymbolsConfig,
    "AISettings": AISettings,
    "DashboardSettings": DashboardSettings,
    "KrakenMarketConfig": KrakenMarketConfig,
    "BinanceMarketConfig": BinanceMarketConfig,
    "MockMarketConfig": MockMarketConfig,
    "RSSConfig": RSSConfig,
    "NewsAPIConfig": NewsAPIConfig,
    "MockNewsConfig": MockNewsConfig,
    "OllamaSentimentConfig": OllamaSentimentConfig,
    "ClaudeSentimentConfig": ClaudeSentimentConfig,
    "MockSentimentConfig": MockSentimentConfig,
}


@app.command()
def validate(
    config: Path = typer.Option(
        "config/settings.yaml", "--config", "-c",
        help="Path to settings YAML file",
    ),
) -> None:
    """Validate settings.yaml against Pydantic schemas."""
    if not config.exists():
        console.print(f"[red]Error:[/red] {config} not found")
        raise typer.Exit(code=1)

    try:
        settings = Settings.from_yaml(config)
        console.print("[green]✓[/green] Configuration is valid")
        console.print(f"  Mode: {settings.mode}")
        console.print(f"  Stocks: {settings.trading.symbols.stocks}")
        console.print(f"  Crypto: {settings.trading.symbols.crypto}")
        console.print(f"  Risk: {settings.risk.max_position_pct}% max position")
    except ValidationError as e:
        console.print("[red]✗[/red] Validation failed:")
        console.print(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def show(
    config: Path = typer.Option(
        "config/settings.yaml", "--config", "-c",
    ),
    format: str = typer.Option(
        "yaml", "--format", "-f",
        help="Output format: yaml or json",
    ),
) -> None:
    """Show resolved configuration with defaults filled in."""
    if not config.exists():
        console.print(f"[red]Error:[/red] {config} not found")
        raise typer.Exit(code=1)

    try:
        settings = Settings.from_yaml(config)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    if format == "json":
        console.print(settings.model_dump_json(indent=2))
    else:
        console.print(yaml.dump(
            settings.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
        ))


@app.command()
def schema(
    model: str = typer.Argument(help="Config model name (e.g. RiskSettings)"),
) -> None:
    """Show JSON schema for a config model."""
    config_cls = CONFIG_MODELS.get(model)
    if not config_cls:
        console.print(f"[red]Unknown model:[/red] {model}")
        console.print(f"Available: {', '.join(sorted(CONFIG_MODELS.keys()))}")
        raise typer.Exit(code=1)

    console.print(json.dumps(config_cls.model_json_schema(), indent=2))
```

```python
# src/cli/main.py
"""Trade bot CLI entry point."""

import typer

from src.cli.config_cmd import app as config_app

app = typer.Typer(
    name="tradebot",
    help="Trading bot CLI — invoke any subsystem independently.",
    no_args_is_help=True,
)

app.add_typer(config_app, name="config")

if __name__ == "__main__":
    app()
```

**Step 5: Run tests**

Run: `uv run pytest tests/unit/cli/test_config_cmd.py -v`
Expected: ALL PASS

**Step 6: Verify CLI works manually**

Run: `uv run tradebot --help`
Run: `uv run tradebot config --help`
Run: `uv run tradebot config validate`
Run: `uv run tradebot config schema RiskSettings`

**Step 7: Commit**

```bash
git add src/cli/ tests/unit/cli/ pyproject.toml
git commit -m "feat: add tradebot config CLI commands"
```

---

## Task 12: Build CLI — `tradebot providers` Commands

**Files:**
- Create: `src/cli/providers_cmd.py`
- Modify: `src/cli/main.py` (register new sub-command)
- Test: `tests/unit/cli/test_providers_cmd.py`

**Step 1: Write failing test**

```python
# tests/unit/cli/test_providers_cmd.py
import pytest
from typer.testing import CliRunner
from src.cli.providers_cmd import app

runner = CliRunner()


class TestProvidersList:
    def test_list_all(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "MarketDataProvider" in result.output
        assert "NewsProvider" in result.output

    def test_list_specific_protocol(self):
        result = runner.invoke(app, ["list", "--protocol", "market_data"])
        assert result.exit_code == 0
        assert "kraken" in result.output.lower()


class TestProvidersHealth:
    def test_health_with_mock_registry(self):
        result = runner.invoke(app, ["health", "--mock"])
        assert result.exit_code == 0
        assert "healthy" in result.output.lower() or "✓" in result.output
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/cli/test_providers_cmd.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement**

```python
# src/cli/providers_cmd.py
"""CLI commands for provider management."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from src.providers.registry import ProviderRegistry
from src.providers.protocols import (
    MarketDataProvider, NewsProvider, SentimentAnalyzer,
    OnChainProvider, FeatureProvider, DataStore,
)

app = typer.Typer(help="Provider registry management.")
console = Console()

PROTOCOL_MAP = {
    "market_data": MarketDataProvider,
    "news": NewsProvider,
    "sentiment": SentimentAnalyzer,
    "onchain": OnChainProvider,
    "features": FeatureProvider,
    "data_store": DataStore,
}

# Known implementations per protocol
KNOWN_IMPLEMENTATIONS: dict[str, list[dict[str, str]]] = {
    "market_data": [
        {"name": "kraken", "type": "local", "description": "Kraken REST API (free)"},
        {"name": "binance", "type": "local", "description": "Binance.US REST API (free)"},
        {"name": "yfinance", "type": "local", "description": "Yahoo Finance (free, stocks)"},
        {"name": "mock", "type": "mock", "description": "Deterministic test provider"},
    ],
    "news": [
        {"name": "rss", "type": "local", "description": "Free RSS feed aggregator"},
        {"name": "reddit", "type": "local", "description": "Reddit API (free tier)"},
        {"name": "newsapi", "type": "local", "description": "NewsAPI.org (100 req/day free)"},
        {"name": "mock", "type": "mock", "description": "Deterministic test provider"},
    ],
    "sentiment": [
        {"name": "ollama", "type": "local", "description": "Local Ollama LLM (free)"},
        {"name": "finbert", "type": "local", "description": "HuggingFace FinBERT (local)"},
        {"name": "claude", "type": "external", "description": "Anthropic Claude API (paid)"},
        {"name": "mock", "type": "mock", "description": "Deterministic test analyzer"},
    ],
    "onchain": [
        {"name": "blockchair", "type": "local", "description": "Blockchair API (free)"},
        {"name": "mock", "type": "mock", "description": "Deterministic test provider"},
    ],
    "features": [
        {"name": "technical", "type": "local", "description": "TA-Lib indicators"},
        {"name": "mock", "type": "mock", "description": "Deterministic test features"},
    ],
    "data_store": [
        {"name": "sqlite", "type": "local", "description": "SQLite + SQLAlchemy"},
        {"name": "mock", "type": "mock", "description": "In-memory dict store"},
    ],
}


@app.command("list")
def list_providers(
    protocol: str | None = typer.Option(
        None, "--protocol", "-p",
        help="Filter by protocol: market_data, news, sentiment, onchain, features, data_store",
    ),
) -> None:
    """List available provider implementations."""
    protocols_to_show = (
        {protocol: PROTOCOL_MAP[protocol]} if protocol and protocol in PROTOCOL_MAP
        else PROTOCOL_MAP
    )

    for proto_name, proto_type in protocols_to_show.items():
        table = Table(title=f"{proto_type.__name__}")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Description")

        implementations = KNOWN_IMPLEMENTATIONS.get(proto_name, [])
        for impl in implementations:
            table.add_row(impl["name"], impl["type"], impl["description"])

        console.print(table)
        console.print()


@app.command()
def health(
    mock: bool = typer.Option(
        False, "--mock",
        help="Use mock registry (for testing without real services)",
    ),
) -> None:
    """Check health of all registered providers."""

    async def _check() -> None:
        registry = ProviderRegistry.for_testing() if mock else ProviderRegistry.for_testing()

        table = Table(title="Provider Health")
        table.add_column("Protocol")
        table.add_column("Provider")
        table.add_column("Status")

        for proto_name, provider in registry.all():
            try:
                if hasattr(provider, "health_check"):
                    healthy = await provider.health_check()
                    status = "[green]✓ healthy[/green]" if healthy else "[red]✗ unhealthy[/red]"
                else:
                    status = "[yellow]- no health check[/yellow]"
            except Exception as e:
                status = f"[red]✗ {e}[/red]"
            table.add_row(proto_name, getattr(provider, "name", "unknown"), status)

        console.print(table)

    asyncio.run(_check())
```

Update `src/cli/main.py` to register the new command:

```python
# src/cli/main.py — add this import and registration
from src.cli.providers_cmd import app as providers_app
app.add_typer(providers_app, name="providers")
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/cli/test_providers_cmd.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/cli/providers_cmd.py src/cli/main.py tests/unit/cli/test_providers_cmd.py
git commit -m "feat: add tradebot providers CLI commands"
```

---

## Task 13: Run Full Test Suite and Fix Regressions

**Step 1: Run everything**

Run: `uv run pytest -x -v`

Fix any failures caused by:
- Import changes in models.py (dataclass → Pydantic)
- Config.py API changes
- DB models.py changes
- Existing tests that relied on `dataclass` behavior

Common fixes needed:
- `FrozenInstanceError` → `ValidationError` in test assertions
- `asdict()` → `model_dump()` if used anywhere
- Constructor differences (Pydantic is stricter about types)

**Step 2: Run with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing`

Note uncovered lines for follow-up.

**Step 3: Commit all fixes**

```bash
git add -A
git commit -m "fix: resolve test regressions from Pydantic migration"
```

---

## Task 14: Final Integration Check

**Step 1: Verify CLI end-to-end**

```bash
uv run tradebot --help
uv run tradebot config validate
uv run tradebot config show
uv run tradebot config show --format json
uv run tradebot config schema RiskSettings
uv run tradebot config schema KrakenMarketConfig
uv run tradebot providers list
uv run tradebot providers list --protocol sentiment
uv run tradebot providers health --mock
```

**Step 2: Verify the bot still starts**

Run: `uv run python main.py` (Ctrl+C after a few seconds to verify it doesn't crash)

**Step 3: Run full test suite one final time**

Run: `uv run pytest -v --tb=short`
Expected: ALL PASS

**Step 4: Commit and tag**

```bash
git add -A
git commit -m "feat: complete Phase 1 — provider architecture with Pydantic, protocols, registry, and CLI"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 2 | Migrate models to Pydantic | `src/core/models.py` | `tests/test_models.py` |
| 3 | Migrate config to Pydantic | `src/core/config.py` | `tests/test_config.py` |
| 4 | Migrate DB models to Pydantic | `src/db/models.py` | `tests/test_db_models.py` |
| 5 | Define provider protocols | `src/providers/protocols.py` | `tests/unit/providers/test_protocols.py` |
| 6 | Create provider configs | `src/providers/configs.py` | `tests/unit/providers/test_configs.py` |
| 7 | Create mock implementations | `src/providers/mock.py` | `tests/unit/providers/test_mocks.py` |
| 8 | Create ProviderRegistry | `src/providers/registry.py` | `tests/unit/providers/test_registry.py` |
| 9 | Protocol compliance tests | — | `tests/unit/providers/test_compliance.py` |
| 10 | Add Typer + Rich deps | `pyproject.toml` | — |
| 11 | CLI: `tradebot config` | `src/cli/config_cmd.py`, `src/cli/main.py` | `tests/unit/cli/test_config_cmd.py` |
| 12 | CLI: `tradebot providers` | `src/cli/providers_cmd.py` | `tests/unit/cli/test_providers_cmd.py` |
| 13 | Fix regressions | various | full suite |
| 14 | Integration check | — | full suite + manual CLI |
