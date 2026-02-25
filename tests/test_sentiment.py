from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.agents.strategies.sentiment import SentimentStrategy
from src.core.models import AssetType, MarketTick, ResearchReport, SignalDirection


def make_tick(symbol="AAPL", price="150.00"):
    return MarketTick(
        symbol=symbol,
        price=Decimal(price),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )


def make_report(symbol="AAPL", sentiment=0.8, summary="Positive outlook"):
    return ResearchReport(
        symbol=symbol,
        summary=summary,
        sentiment_score=sentiment,
        timestamp=datetime.now(UTC),
        sources=["news"],
    )


@pytest.fixture
def strategy():
    return SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)


async def test_buy_on_positive_sentiment(strategy):
    ticks = [make_tick()]
    reports = [make_report(sentiment=0.8)]
    signal = await strategy.evaluate("AAPL", ticks, research=reports)
    assert signal is not None
    assert signal.direction == SignalDirection.BUY


async def test_sell_on_negative_sentiment(strategy):
    ticks = [make_tick()]
    reports = [make_report(sentiment=-0.8)]
    signal = await strategy.evaluate("AAPL", ticks, research=reports)
    assert signal is not None
    assert signal.direction == SignalDirection.SELL


async def test_no_signal_neutral_sentiment(strategy):
    ticks = [make_tick()]
    reports = [make_report(sentiment=0.1)]
    signal = await strategy.evaluate("AAPL", ticks, research=reports)
    assert signal is None


async def test_no_signal_without_research(strategy):
    ticks = [make_tick()]
    signal = await strategy.evaluate("AAPL", ticks, research=None)
    assert signal is None


async def test_averages_multiple_reports(strategy):
    ticks = [make_tick()]
    reports = [make_report(sentiment=0.9), make_report(sentiment=0.5)]
    signal = await strategy.evaluate("AAPL", ticks, research=reports)
    assert signal is not None
    assert signal.direction == SignalDirection.BUY


async def test_has_name(strategy):
    assert strategy.name == "sentiment"
