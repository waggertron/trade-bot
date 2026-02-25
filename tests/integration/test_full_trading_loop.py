"""Integration tests for the full orchestrator trading loop.

Exercises the complete pipeline: Orchestrator -> MomentumStrategy -> RiskManager
-> PaperExecutionAgent -> PortfolioManager with real component instances.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.agents.execution import PaperExecutionAgent
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.agents.strategies.momentum import MomentumStrategy
from src.core.config import RiskSettings
from src.core.event_bus import EventBus
from src.core.models import AssetType, MarketTick, OrderSide
from src.core.orchestrator import Orchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYMBOL = "BTC/USD"
BASE_TIME = datetime(2025, 7, 1, 12, 0, 0, tzinfo=UTC)


def _make_tick(price: Decimal, index: int) -> MarketTick:
    """Create a MarketTick at a deterministic timestamp offset."""
    return MarketTick(
        symbol=SYMBOL,
        price=price,
        volume=1000,
        timestamp=BASE_TIME + timedelta(minutes=index),
        asset_type=AssetType.CRYPTO,
    )


def _build_components(
    *,
    short_window: int = 5,
    long_window: int = 10,
    initial_cash: Decimal = Decimal("100000"),
    position_size_pct: float = 2.0,
) -> tuple[Orchestrator, PaperExecutionAgent, PortfolioManager]:
    """Wire up all real components and return (orchestrator, executor, portfolio)."""
    strategy = MomentumStrategy(short_window=short_window, long_window=long_window)
    risk_settings = RiskSettings(
        max_position_pct=5.0,
        daily_loss_limit_pct=5.0,
        max_open_positions=10,
        max_correlation=0.7,
    )
    risk_manager = RiskManager(settings=risk_settings)
    executor = PaperExecutionAgent(slippage_pct=Decimal("0"))
    portfolio = PortfolioManager(initial_cash=initial_cash)
    event_bus = EventBus()

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
        position_size_pct=position_size_pct,
    )
    return orchestrator, executor, portfolio


def _rising_prices(n: int, start: float = 50000.0, step: float = 500.0) -> list[Decimal]:
    """Generate *n* steadily rising prices."""
    return [Decimal(str(start + i * step)) for i in range(n)]


def _flat_prices(n: int, price: float = 50000.0) -> list[Decimal]:
    """Generate *n* identical prices."""
    return [Decimal(str(price))] * n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullTradingLoop:
    """Integration tests that push ticks through the full orchestrator pipeline."""

    async def test_uptrend_produces_buy_fill(self) -> None:
        """Feed 30 ticks with rising prices; the momentum strategy should
        eventually trigger a BUY signal that passes risk checks and results
        in at least one fill."""
        orchestrator, executor, _portfolio = _build_components(
            short_window=5,
            long_window=10,
        )

        prices = _rising_prices(30)
        all_fills = []

        for i, price in enumerate(prices):
            tick = _make_tick(price, i)
            executor.set_current_price(SYMBOL, price)
            fills = await orchestrator.process_tick(tick)
            all_fills.extend(fills)

        assert len(all_fills) >= 1, (
            f"Expected at least 1 BUY fill from an uptrend of 30 ticks, got {len(all_fills)}"
        )
        assert all(f.side == OrderSide.BUY for f in all_fills)
        assert all(f.symbol == SYMBOL for f in all_fills)

    async def test_no_trade_on_flat_market(self) -> None:
        """Feed 30 ticks at the exact same price; momentum strategy should
        never produce a signal because short MA == long MA."""
        orchestrator, executor, _portfolio = _build_components(
            short_window=5,
            long_window=10,
        )

        prices = _flat_prices(30)
        all_fills = []

        for i, price in enumerate(prices):
            tick = _make_tick(price, i)
            executor.set_current_price(SYMBOL, price)
            fills = await orchestrator.process_tick(tick)
            all_fills.extend(fills)

        assert len(all_fills) == 0, f"Expected 0 fills on a flat market, got {len(all_fills)}"

    async def test_portfolio_updated_after_trade(self) -> None:
        """After a fill, the PortfolioManager should hold a position in BTC/USD
        and its cash balance should have decreased."""
        initial_cash = Decimal("100000")
        orchestrator, executor, portfolio = _build_components(
            short_window=5,
            long_window=10,
            initial_cash=initial_cash,
        )

        prices = _rising_prices(30)

        for i, price in enumerate(prices):
            tick = _make_tick(price, i)
            executor.set_current_price(SYMBOL, price)
            await orchestrator.process_tick(tick)

        positions = await portfolio.get_positions()
        snapshot = await portfolio.get_snapshot()

        # We must have at least one position after the uptrend
        btc_positions = [p for p in positions if p.symbol == SYMBOL]
        assert len(btc_positions) == 1, f"Expected 1 BTC/USD position, got {len(btc_positions)}"

        pos = btc_positions[0]
        assert pos.quantity > 0, "Position quantity should be positive"
        assert snapshot.cash < initial_cash, (
            f"Cash should have decreased from {initial_cash}, but is {snapshot.cash}"
        )

    async def test_paused_orchestrator_skips_ticks(self) -> None:
        """When the orchestrator is paused, feeding ticks should produce
        no fills even when the market is trending."""
        orchestrator, executor, _portfolio = _build_components(
            short_window=5,
            long_window=10,
        )

        orchestrator.pause()
        assert orchestrator.is_paused is True

        prices = _rising_prices(30)
        all_fills = []

        for i, price in enumerate(prices):
            tick = _make_tick(price, i)
            executor.set_current_price(SYMBOL, price)
            fills = await orchestrator.process_tick(tick)
            all_fills.extend(fills)

        assert len(all_fills) == 0, f"Expected 0 fills while paused, got {len(all_fills)}"
