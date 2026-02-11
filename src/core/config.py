"""Application configuration with Pydantic validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
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
        """Create RiskSettings from a named risk level with optional overrides."""
        if isinstance(level, str):
            level = RiskLevel(level.lower())
        preset = RISK_LEVEL_PRESETS[level].copy()
        preset.update(overrides)
        return cls.model_validate(preset)


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

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        """Load and validate settings from a YAML file."""
        data = yaml.safe_load(path.read_text())
        return cls.model_validate(data)

    @classmethod
    def for_testing(cls, **overrides: Any) -> Settings:
        """Create a Settings instance suitable for tests."""
        defaults: dict[str, Any] = {
            "mode": "paper",
            "trading": {"symbols": {"stocks": [], "crypto": ["BTC/USD"]}},
            "risk": {},
            "ai": {},
            "dashboard": {"port": 8080},
        }
        defaults.update(overrides)
        return cls.model_validate(defaults)
