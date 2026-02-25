"""Application configuration with Pydantic validation."""

from __future__ import annotations

import os
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ConfigDict, Field, field_validator

from src.core.base import StrictBase

if TYPE_CHECKING:
    from pathlib import Path


class RiskLevel(StrEnum):
    """Preset risk levels mapping to position sizing and risk parameters."""

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


class RiskSettings(StrictBase):
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
        """Create RiskSettings from a named risk level with optional overrides."""
        if isinstance(level, str):
            level = RiskLevel(level.lower())
        preset = RISK_LEVEL_PRESETS[level].copy()
        preset.update(overrides)
        return cls.model_validate(preset)


class SymbolsConfig(StrictBase):
    model_config = ConfigDict(frozen=True)

    stocks: list[str] = Field(default_factory=list)
    crypto: list[str] = Field(default_factory=list)


class TradingSettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    symbols: SymbolsConfig = Field(default_factory=SymbolsConfig)
    market_hours: dict[str, str] = Field(default_factory=dict)


class SentimentSettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    analyzer: str = "ollama"
    pipeline_interval_seconds: int = Field(300, ge=10)


class AISettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    claude_model: str = "claude-sonnet-4-5-20250929"
    ollama_model: str = "llama3.2"


class DashboardSettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    host: str = "0.0.0.0"
    port: int = Field(8080, gt=0, le=65535)


class AuthSettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    jwt_secret_key: str = Field(
        default_factory=lambda: os.environ.get("JWT_SECRET_KEY", ""),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(30, gt=0)
    refresh_token_expire_days: int = Field(7, gt=0)

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            msg = "JWT secret key must be at least 32 characters"
            raise ValueError(msg)
        return v


class MockSettings(StrictBase):
    model_config = ConfigDict(frozen=True)

    stock_feed: bool = True
    sentiment: bool = True
    onchain: bool = True
    ml: bool = True
    position_sizer: bool = True


class Settings(StrictBase):
    model_config = ConfigDict(frozen=True)

    mode: str = Field("paper", pattern=r"^(paper|live)$")
    trading: TradingSettings = Field(default_factory=TradingSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    sentiment: SentimentSettings = Field(default_factory=SentimentSettings)
    ai: AISettings = Field(default_factory=AISettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    use_mocks: MockSettings = Field(default_factory=MockSettings)

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        """Load and validate settings from a YAML file.

        Unknown top-level keys (e.g. ``strategies``, ``research``) are
        silently dropped so the YAML can contain sections consumed by
        other subsystems without breaking validation.
        """
        data = yaml.safe_load(path.read_text())
        known_fields = cls.model_fields.keys()
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls.model_validate(filtered)

    @classmethod
    def from_env(cls) -> Settings:
        """Create Settings entirely from environment variables.

        Env vars:
          TRADE_BOT_MODE           - paper|live (default: paper)
          TRADE_BOT_CRYPTO_SYMBOLS - comma-separated (default: BTC/USD)
          TRADE_BOT_STOCK_SYMBOLS  - comma-separated (default: empty)
          TRADE_BOT_DASHBOARD_PORT - int (default: 8080)
          JWT_SECRET_KEY           - JWT signing secret
        """
        mode = os.getenv("TRADE_BOT_MODE", "paper")
        crypto_raw = os.getenv("TRADE_BOT_CRYPTO_SYMBOLS", "BTC/USD")
        stock_raw = os.getenv("TRADE_BOT_STOCK_SYMBOLS", "")
        port_str = os.getenv("TRADE_BOT_DASHBOARD_PORT", "8080")

        crypto_symbols = [s.strip() for s in crypto_raw.split(",") if s.strip()]
        stock_symbols = [s.strip() for s in stock_raw.split(",") if s.strip()]

        return cls.model_validate(
            {
                "mode": mode,
                "trading": {"symbols": {"stocks": stock_symbols, "crypto": crypto_symbols}},
                "dashboard": {"port": int(port_str)},
            }
        )

    @classmethod
    def for_testing(cls, **overrides: Any) -> Settings:
        """Create a Settings instance suitable for tests."""
        defaults: dict[str, Any] = {
            "mode": "paper",
            "trading": {"symbols": {"stocks": [], "crypto": ["BTC/USD"]}},
            "risk": {},
            "ai": {},
            "dashboard": {"port": 8080},
            "auth": {
                "jwt_secret_key": "test-secret-key-for-unit-tests!!",
            },
        }
        defaults.update(overrides)
        return cls.model_validate(defaults)
