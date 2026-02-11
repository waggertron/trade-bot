import pytest
import numpy as np
from src.providers.configs import TechnicalFeatureConfig


def _make_price_data(n=100, start=100.0, trend=0.1):
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    close = np.cumsum(np.random.randn(n) * 2 + trend) + start
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    volume = np.random.randint(1000, 10000, n).astype(float)
    return {"close": close, "high": high, "low": low, "volume": volume}


class TestTechnicalFeatureProvider:
    def test_creates_with_default_config(self):
        from src.providers.technical import TechnicalFeatureProvider
        p = TechnicalFeatureProvider()
        assert p.name == "technical"

    def test_implements_protocol(self):
        from src.providers.technical import TechnicalFeatureProvider
        from src.providers.protocols import FeatureProvider
        p = TechnicalFeatureProvider()
        assert isinstance(p, FeatureProvider)

    def test_required_inputs(self):
        from src.providers.technical import TechnicalFeatureProvider
        p = TechnicalFeatureProvider()
        assert "close" in p.required_inputs
        assert "high" in p.required_inputs

    @pytest.mark.asyncio
    async def test_computes_sma(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["sma"])
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "sma_14" in features
        assert "sma_50" in features

    @pytest.mark.asyncio
    async def test_computes_rsi(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["rsi"])
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "rsi_14" in features
        assert 0 <= features["rsi_14"] <= 100

    @pytest.mark.asyncio
    async def test_computes_macd(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["macd"])
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "macd_signal" in features

    @pytest.mark.asyncio
    async def test_computes_bbands(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["bbands"])
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "bbands_position" in features

    @pytest.mark.asyncio
    async def test_computes_atr(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["atr"])
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "atr_14" in features
        assert features["atr_14"] > 0

    @pytest.mark.asyncio
    async def test_all_default_indicators(self):
        from src.providers.technical import TechnicalFeatureProvider
        p = TechnicalFeatureProvider()  # default config has all indicators
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "sma_14" in features
        assert "rsi_14" in features
        assert "macd_signal" in features
        assert "bbands_position" in features
        assert "atr_14" in features

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_partial(self):
        from src.providers.technical import TechnicalFeatureProvider
        p = TechnicalFeatureProvider()
        data = _make_price_data(5)  # too little for most indicators
        features = await p.compute(data)
        # SMA_14 requires 14 bars, RSI needs 15, etc. — should skip what it can't compute
        assert "sma_50" not in features
        assert "rsi_14" not in features

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty(self):
        from src.providers.technical import TechnicalFeatureProvider
        p = TechnicalFeatureProvider()
        features = await p.compute({"close": [], "high": [], "low": [], "volume": []})
        assert features == {}

    @pytest.mark.asyncio
    async def test_respects_indicator_filter(self):
        from src.providers.technical import TechnicalFeatureProvider
        config = TechnicalFeatureConfig(indicators=["rsi"])  # only RSI
        p = TechnicalFeatureProvider(config)
        data = _make_price_data(100)
        features = await p.compute(data)
        assert "rsi_14" in features
        assert "sma_14" not in features  # not requested
        assert "macd_signal" not in features
