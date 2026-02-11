from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.providers.base import Interval, OHLCBar


def _mock_httpx_response(json_data: object, status_code: int = 200) -> MagicMock:
    """Create a mock that behaves like an httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _mock_async_client(response: MagicMock) -> AsyncMock:
    """Create a mock async httpx client context manager."""
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# Kraken
# ---------------------------------------------------------------------------

class TestKrakenProvider:
    async def test_parse_bars(self) -> None:
        from src.data.providers.kraken import download

        response = _mock_httpx_response({
            "error": [],
            "result": {
                "XXBTZUSD": [
                    [1700000000, "40000.0", "40500.0", "39500.0",
                     "40100.0", "40050.0", "100.5", 500],
                    [1700003600, "40100.0", "41000.0", "40000.0",
                     "40800.0", "40500.0", "120.3", 600],
                ],
                "last": 1700003600,
            },
        })
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.kraken.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.H1, max_bars=10)

        assert len(bars) == 2
        assert isinstance(bars[0], OHLCBar)
        assert bars[0].timestamp == 1700000000
        assert bars[0].open == "40000.0"
        assert bars[0].close == "40100.0"
        assert bars[0].volume == "100.5"
        assert bars[0].source == "kraken"

    async def test_api_error(self) -> None:
        from src.data.providers.kraken import download

        response = _mock_httpx_response({
            "error": ["EGeneral:Invalid arguments"],
            "result": {},
        })
        mock_client = _mock_async_client(response)

        with (
            patch(
                "src.data.providers.kraken.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(RuntimeError, match="Kraken API error"),
        ):
            await download("BTC/USD", Interval.H1)

    async def test_empty_response(self) -> None:
        from src.data.providers.kraken import download

        response = _mock_httpx_response({
            "error": [],
            "result": {"XXBTZUSD": [], "last": 0},
        })
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.kraken.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.H1)

        assert bars == []


# ---------------------------------------------------------------------------
# CryptoCompare
# ---------------------------------------------------------------------------

class TestCryptoCompareProvider:
    async def test_parse_bars(self) -> None:
        from src.data.providers.cryptocompare import download

        response = _mock_httpx_response({
            "Response": "Success",
            "Data": {
                "Data": [
                    {"time": 1700000000, "open": 40000, "high": 40500,
                     "low": 39500, "close": 40100, "volumefrom": 1000},
                    {"time": 1700086400, "open": 40100, "high": 41000,
                     "low": 40000, "close": 40800, "volumefrom": 1200},
                ],
            },
        })
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.cryptocompare.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.D1)

        assert len(bars) == 2
        assert bars[0].source == "cryptocompare"
        assert bars[0].open == "40000"
        assert bars[1].timestamp == 1700086400

    async def test_filters_empty_bars(self) -> None:
        from src.data.providers.cryptocompare import download

        response = _mock_httpx_response({
            "Response": "Success",
            "Data": {
                "Data": [
                    {"time": 1700000000, "open": 0, "high": 0,
                     "low": 0, "close": 0, "volumefrom": 0},
                    {"time": 1700086400, "open": 40000, "high": 41000,
                     "low": 39500, "close": 40800, "volumefrom": 100},
                ],
            },
        })
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.cryptocompare.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.D1)

        assert len(bars) == 1
        assert bars[0].timestamp == 1700086400

    async def test_invalid_symbol_format(self) -> None:
        from src.data.providers.cryptocompare import download

        with pytest.raises(ValueError, match="BASE/QUOTE"):
            await download("BTCUSD", Interval.D1)

    async def test_api_error(self) -> None:
        from src.data.providers.cryptocompare import download

        response = _mock_httpx_response({
            "Response": "Error",
            "Message": "Invalid fsym",
        })
        mock_client = _mock_async_client(response)

        with (
            patch(
                "src.data.providers.cryptocompare.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(RuntimeError, match="CryptoCompare error"),
        ):
            await download("BTC/USD", Interval.D1)


# ---------------------------------------------------------------------------
# Binance
# ---------------------------------------------------------------------------

class TestBinanceProvider:
    async def test_parse_bars(self) -> None:
        from src.data.providers.binance import download

        # Binance kline: [openTime, O, H, L, C, V, closeTime, quoteV, trades, ...]
        response = _mock_httpx_response([
            [1700000000000, "40000.0", "40500.0", "39500.0", "40100.0", "100.5",
             1700086399999, "4020050.0", 500, "50.0", "2010000.0", "0"],
            [1700086400000, "40100.0", "41000.0", "40000.0", "40800.0", "120.3",
             1700172799999, "4920240.0", 600, "60.0", "2460000.0", "0"],
        ])
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.binance.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.D1)

        assert len(bars) == 2
        assert bars[0].source == "binance"
        assert bars[0].timestamp == 1700000000  # ms -> seconds
        assert bars[0].open == "40000.0"
        assert bars[1].volume == "120.3"

    async def test_converts_ms_to_seconds(self) -> None:
        from src.data.providers.binance import download

        response = _mock_httpx_response([
            [1700000000123, "100", "101", "99", "100.5", "10",
             1700086399999, "1005", 100, "5", "500", "0"],
        ])
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.binance.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.D1)

        assert bars[0].timestamp == 1700000000

    async def test_empty_response(self) -> None:
        from src.data.providers.binance import download

        response = _mock_httpx_response([])
        mock_client = _mock_async_client(response)

        with patch(
            "src.data.providers.binance.httpx.AsyncClient",
            return_value=mock_client,
        ):
            bars = await download("BTC/USD", Interval.D1)

        assert bars == []


# ---------------------------------------------------------------------------
# yfinance
# ---------------------------------------------------------------------------

class TestYfinanceProvider:
    async def test_parse_bars(self) -> None:
        import pandas as pd

        dates = pd.to_datetime(["2023-11-15", "2023-11-16"])
        df = pd.DataFrame(
            {
                "Open": [40000.0, 40100.0],
                "High": [40500.0, 41000.0],
                "Low": [39500.0, 40000.0],
                "Close": [40100.0, 40800.0],
                "Volume": [1000000, 1200000],
            },
            index=dates,
        )

        mock_yf = MagicMock()
        mock_yf.download.return_value = df

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            from src.data.providers import yfinance_provider

            bars = await yfinance_provider.download("BTC/USD", Interval.D1)

        assert len(bars) == 2
        assert bars[0].source == "yfinance"
        assert bars[0].open == "40000.0"
        mock_yf.download.assert_called_once_with(
            "BTC-USD", period="max", interval="1d", progress=False,
        )

    async def test_unsupported_interval(self) -> None:
        from src.data.providers.yfinance_provider import download

        with pytest.raises(ValueError, match="only supports daily"):
            await download("BTC/USD", Interval.H1)

    async def test_empty_dataframe(self) -> None:
        import pandas as pd

        mock_yf = MagicMock()
        mock_yf.download.return_value = pd.DataFrame()

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            from src.data.providers import yfinance_provider

            bars = await yfinance_provider.download("BTC/USD", Interval.D1)

        assert bars == []
