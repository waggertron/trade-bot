from __future__ import annotations

import importlib
from collections.abc import Callable, Coroutine
from typing import Any

from src.data.providers.base import Interval, OHLCBar, ProviderName

DownloadFunc = Callable[..., Coroutine[Any, Any, list[OHLCBar]]]

# Lazy imports to avoid import errors when optional deps are missing
_PROVIDERS: dict[ProviderName, str] = {
    ProviderName.KRAKEN: "src.data.providers.kraken",
    ProviderName.CRYPTOCOMPARE: "src.data.providers.cryptocompare",
    ProviderName.BINANCE: "src.data.providers.binance",
    ProviderName.YFINANCE: "src.data.providers.yfinance_provider",
}

PROVIDER_INTERVALS: dict[ProviderName, set[Interval]] = {
    ProviderName.KRAKEN: {
        Interval.M1, Interval.M5, Interval.M15, Interval.M30,
        Interval.H1, Interval.H4, Interval.D1, Interval.W1,
    },
    ProviderName.CRYPTOCOMPARE: {Interval.H1, Interval.D1},
    ProviderName.BINANCE: {
        Interval.M1, Interval.M5, Interval.M15, Interval.M30,
        Interval.H1, Interval.H4, Interval.D1, Interval.W1,
    },
    ProviderName.YFINANCE: {Interval.D1},
}

SOURCE_PRIORITY: dict[ProviderName, int] = {
    ProviderName.CRYPTOCOMPARE: 4,
    ProviderName.BINANCE: 3,
    ProviderName.KRAKEN: 2,
    ProviderName.YFINANCE: 1,
}


def get_provider_download(name: ProviderName) -> DownloadFunc:
    """Import and return the download function for a provider."""
    module = importlib.import_module(_PROVIDERS[name])
    fn: DownloadFunc = module.download
    return fn
