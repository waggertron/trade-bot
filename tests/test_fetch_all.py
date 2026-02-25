"""Tests for scripts.fetch_all task builder."""

from __future__ import annotations

from scripts.fetch_all import (
    BOND_SYMBOLS,
    CRYPTO_PAIRS,
    STOCK_SYMBOLS,
    DownloadTask,
    build_tasks,
)
from src.data.providers.base import Interval, ProviderName


def test_build_tasks_total_count() -> None:
    tasks = build_tasks()
    # 16 stocks + 4 bonds + 30 crypto-daily + 20 crypto-hourly = 70
    assert len(tasks) == 70


def test_stock_tasks_use_yfinance_daily() -> None:
    tasks = build_tasks()
    stock_tasks = [t for t in tasks if t.category == "stocks"]
    assert len(stock_tasks) == len(STOCK_SYMBOLS)
    for t in stock_tasks:
        assert t.source == ProviderName.YFINANCE
        assert t.interval == Interval.D1


def test_bond_tasks_use_yfinance_daily() -> None:
    tasks = build_tasks()
    bond_tasks = [t for t in tasks if t.category == "bonds"]
    assert len(bond_tasks) == len(BOND_SYMBOLS)
    for t in bond_tasks:
        assert t.source == ProviderName.YFINANCE
        assert t.interval == Interval.D1


def test_crypto_daily_has_three_sources() -> None:
    tasks = build_tasks()
    crypto_daily = [t for t in tasks if t.category == "crypto" and t.interval == Interval.D1]
    assert len(crypto_daily) == len(CRYPTO_PAIRS) * 3

    # Each pair should have exactly 3 sources
    for pair in CRYPTO_PAIRS:
        pair_tasks = [t for t in crypto_daily if t.symbol == pair]
        assert len(pair_tasks) == 3
        sources = {t.source for t in pair_tasks}
        assert sources == {ProviderName.CRYPTOCOMPARE, ProviderName.YFINANCE, ProviderName.BINANCE}


def test_crypto_hourly_has_two_sources() -> None:
    tasks = build_tasks()
    crypto_hourly = [t for t in tasks if t.category == "crypto" and t.interval == Interval.H1]
    assert len(crypto_hourly) == len(CRYPTO_PAIRS) * 2

    for pair in CRYPTO_PAIRS:
        pair_tasks = [t for t in crypto_hourly if t.symbol == pair]
        assert len(pair_tasks) == 2
        sources = {t.source for t in pair_tasks}
        assert sources == {ProviderName.CRYPTOCOMPARE, ProviderName.BINANCE}


def test_all_stock_symbols_present() -> None:
    tasks = build_tasks()
    stock_symbols = {t.symbol for t in tasks if t.category == "stocks"}
    assert stock_symbols == set(STOCK_SYMBOLS)


def test_all_bond_symbols_present() -> None:
    tasks = build_tasks()
    bond_symbols = {t.symbol for t in tasks if t.category == "bonds"}
    assert bond_symbols == set(BOND_SYMBOLS)


def test_download_task_dataclass() -> None:
    task = DownloadTask(
        symbol="SPY",
        source=ProviderName.YFINANCE,
        interval=Interval.D1,
        category="stocks",
    )
    assert task.symbol == "SPY"
    assert task.source == ProviderName.YFINANCE
    assert task.interval == Interval.D1
    assert task.category == "stocks"
