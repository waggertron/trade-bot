from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SymbolsConfig:
    stocks: list[str] = field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL"])
    crypto: list[str] = field(default_factory=lambda: ["BTC/USD", "ETH/USD"])


@dataclass
class TradingSettings:
    symbols: SymbolsConfig = field(default_factory=SymbolsConfig)
    market_hours: dict[str, str] = field(default_factory=lambda: {
        "stocks_open": "09:30",
        "stocks_close": "16:00",
        "timezone": "US/Eastern",
    })


@dataclass
class RiskSettings:
    max_position_pct: float = 2.0
    max_sector_exposure_pct: float = 20.0
    daily_loss_limit_pct: float = 3.0
    weekly_drawdown_limit_pct: float = 5.0
    max_open_positions: int = 10
    stop_loss_pct: float = 5.0
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = 3.0
    max_correlation: float = 0.7


@dataclass
class AISettings:
    claude_model: str = "claude-sonnet-4-5-20250929"
    ollama_model: str = "llama3.2"


@dataclass
class Settings:
    mode: str = "paper"
    trading: TradingSettings = field(default_factory=TradingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    ai: AISettings = field(default_factory=AISettings)

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Settings:
        trading_data = data.get("trading", {})
        symbols_data = trading_data.pop("symbols", {})
        trading = TradingSettings(
            symbols=SymbolsConfig(**symbols_data),
            **{k: v for k, v in trading_data.items()
               if k in TradingSettings.__dataclass_fields__},
        )
        risk = RiskSettings(**{
            k: v for k, v in data.get("risk", {}).items()
            if k in RiskSettings.__dataclass_fields__
        })
        ai = AISettings(**{
            k: v for k, v in data.get("ai", {}).items()
            if k in AISettings.__dataclass_fields__
        })
        return cls(
            mode=data.get("mode", "paper"),
            trading=trading,
            risk=risk,
            ai=ai,
        )

    @classmethod
    def for_testing(cls, **overrides) -> Settings:
        defaults = {"mode": "paper"}
        defaults.update(overrides)
        return cls(**defaults)
