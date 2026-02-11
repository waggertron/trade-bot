from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Interval(StrEnum):
    """Candle interval with value in minutes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def minutes(self) -> int:
        return _INTERVAL_MINUTES[self]

    @property
    def label(self) -> str:
        return self.value


_INTERVAL_MINUTES: dict[Interval, int] = {
    Interval.M1: 1,
    Interval.M5: 5,
    Interval.M15: 15,
    Interval.M30: 30,
    Interval.H1: 60,
    Interval.H4: 240,
    Interval.D1: 1440,
    Interval.W1: 10080,
}


class ProviderName(StrEnum):
    KRAKEN = "kraken"
    CRYPTOCOMPARE = "cryptocompare"
    YFINANCE = "yfinance"
    BINANCE = "binance"


class OHLCBar(BaseModel):
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    source: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


CSV_COLUMNS: list[str] = ["timestamp", "open", "high", "low", "close", "volume"]


def normalize_symbol(symbol: str) -> str:
    """Normalize 'BTC/USD' -> 'BTCUSD'."""
    return symbol.replace("/", "").upper()
