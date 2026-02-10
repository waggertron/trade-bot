from __future__ import annotations

import asyncio
import logging
from collections import Counter
from decimal import Decimal

from src.core.event_bus import EventBus
from src.core.models import (
    Fill, MarketTick, Order, OrderSide, OrderType, Signal, SignalDirection,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        strategies: list,
        risk_manager,
        executor,
        portfolio,
        event_bus: EventBus,
    ):
        self._strategies = strategies
        self._risk_manager = risk_manager
        self._executor = executor
        self._portfolio = portfolio
        self._event_bus = event_bus
        self._paused = False
        self._tick_history: dict[str, list[MarketTick]] = {}
        self._max_history = 200

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    async def process_tick(self, tick: MarketTick) -> list[Fill]:
        if self._paused:
            return []

        # Accumulate tick history
        history = self._tick_history.setdefault(tick.symbol, [])
        history.append(tick)
        if len(history) > self._max_history:
            self._tick_history[tick.symbol] = history[-self._max_history:]

        signals = await self._gather_signals(tick)
        if not signals:
            return []

        consensus = self._find_consensus(signals)
        if consensus is None:
            return []

        portfolio = await self._portfolio.get_snapshot()
        decision = await self._risk_manager.evaluate_trade(consensus, portfolio)

        if not decision.is_approved:
            logger.info("Trade vetoed for %s: %s", tick.symbol, decision.reason)
            return []

        quantity = decision.adjusted_quantity or Decimal("10")
        order = Order(
            symbol=tick.symbol,
            side=OrderSide.BUY if consensus.direction == SignalDirection.BUY else OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=quantity,
            asset_type=tick.asset_type,
            signal_id=consensus.id,
        )

        fill = await self._executor.submit_order(order)
        await self._portfolio.record_fill(fill)
        return [fill]

    async def _gather_signals(self, tick: MarketTick) -> list[Signal]:
        history = self._tick_history.get(tick.symbol, [tick])
        tasks = [
            strategy.evaluate(tick.symbol, history)
            for strategy in self._strategies
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals = []
        for result in results:
            if isinstance(result, Signal):
                signals.append(result)
            elif isinstance(result, Exception):
                logger.exception("Strategy error: %s", result)
        return signals

    def _find_consensus(self, signals: list[Signal]) -> Signal | None:
        if not signals:
            return None

        directions = [s.direction for s in signals if s.direction != SignalDirection.HOLD]
        if not directions:
            return None

        counts = Counter(directions)
        most_common, count = counts.most_common(1)[0]

        # Need majority agreement
        if count <= len(directions) / 2:
            return None

        agreeing = [s for s in signals if s.direction == most_common]
        best = max(agreeing, key=lambda s: s.confidence)
        return best
