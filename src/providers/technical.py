"""Technical indicator feature provider using TA-Lib."""

from __future__ import annotations

from typing import Any

import numpy as np
import talib

from src.providers.configs import TechnicalFeatureConfig


class TechnicalFeatureProvider:
    """Computes technical indicators from OHLCV data."""

    def __init__(self, config: TechnicalFeatureConfig | None = None) -> None:
        self._config = config or TechnicalFeatureConfig()

    @property
    def name(self) -> str:
        return "technical"

    @property
    def required_inputs(self) -> list[str]:
        return ["close", "high", "low", "volume"]

    async def compute(self, inputs: dict[str, Any]) -> dict[str, float]:
        """Compute configured technical indicators.

        Args:
            inputs: Must contain numpy arrays for "close", "high", "low", "volume".
                    Arrays should have enough data for the longest lookback period.

        Returns:
            Dict of feature_name -> latest value for each computed indicator.
        """
        close = np.asarray(inputs.get("close", []), dtype=float)
        high = np.asarray(inputs.get("high", []), dtype=float)
        low = np.asarray(inputs.get("low", []), dtype=float)
        np.asarray(inputs.get("volume", []), dtype=float)

        features: dict[str, float] = {}

        if len(close) < 2:
            return features

        indicators = self._config.indicators

        if "sma" in indicators:
            self._compute_sma(close, features)
        if "rsi" in indicators:
            self._compute_rsi(close, features)
        if "macd" in indicators:
            self._compute_macd(close, features)
        if "bbands" in indicators:
            self._compute_bbands(close, features)
        if "atr" in indicators:
            self._compute_atr(high, low, close, features)

        return features

    def _compute_sma(self, close: np.ndarray, features: dict[str, float]) -> None:
        for period in [14, 50]:
            if len(close) >= period:
                result = talib.SMA(close, timeperiod=period)
                val = result[-1]
                if not np.isnan(val):
                    features[f"sma_{period}"] = float(val)

    def _compute_rsi(self, close: np.ndarray, features: dict[str, float]) -> None:
        if len(close) >= 15:  # RSI needs at least period+1
            result = talib.RSI(close, timeperiod=14)
            val = result[-1]
            if not np.isnan(val):
                features["rsi_14"] = float(val)

    def _compute_macd(self, close: np.ndarray, features: dict[str, float]) -> None:
        if len(close) >= 34:  # MACD needs 26+8 for signal line
            _macd, _signal, hist = talib.MACD(close)
            val = hist[-1]
            if not np.isnan(val):
                features["macd_signal"] = float(val)

    def _compute_bbands(self, close: np.ndarray, features: dict[str, float]) -> None:
        if len(close) >= 20:
            upper, _middle, lower = talib.BBANDS(close, timeperiod=20)
            u, lo, c = upper[-1], lower[-1], close[-1]
            if not np.isnan(u) and not np.isnan(lo) and u != lo:
                features["bbands_position"] = float((c - lo) / (u - lo))

    def _compute_atr(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, features: dict[str, float]
    ) -> None:
        if len(close) >= 15:
            result = talib.ATR(high, low, close, timeperiod=14)
            val = result[-1]
            if not np.isnan(val):
                features["atr_14"] = float(val)
