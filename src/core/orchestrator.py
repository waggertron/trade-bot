from __future__ import annotations

import asyncio
import logging
from collections import Counter
from decimal import Decimal

from src.core.event_bus import Event, EventBus
from src.core.event_types import FillEvent
from src.core.models import (
    Fill,
    MarketTick,
    Order,
    OrderSide,
    OrderType,
    ResearchReport,
    Signal,
    SignalDirection,
)
from src.db.models import SignalRecord

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        strategies: list,
        risk_manager,
        executor,
        portfolio,
        event_bus: EventBus,
        position_size_pct: float = 2.0,
        min_order_value: Decimal = Decimal("10"),
        db=None,
        position_sizer=None,
    ):
        self._strategies = strategies
        self._risk_manager = risk_manager
        self._executor = executor
        self._portfolio = portfolio
        self._event_bus = event_bus
        self._position_size_pct = Decimal(str(position_size_pct))
        self._min_order_value = min_order_value
        self._paused = False
        self._tick_history: dict[str, list[MarketTick]] = {}
        self._max_history = 200
        self._research: list[ResearchReport] | None = None
        self._db = db
        self._position_sizer = position_sizer

    def set_research(self, reports: list[ResearchReport]) -> None:
        """Update the research reports passed to strategies."""
        self._research = reports

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
            self._tick_history[tick.symbol] = history[-self._max_history :]

        signals = await self._gather_signals(tick)
        await self._persist_signals(signals)
        if not signals:
            return []

        # Publish signal events
        for _signal in signals:
            await self._event_bus.publish(Event(event_type="signal"))

        consensus = self._find_consensus(signals)
        if consensus is None:
            return []

        portfolio = await self._portfolio.get_snapshot()
        decision = await self._risk_manager.evaluate_trade(consensus, portfolio)

        # Publish risk decision event
        await self._event_bus.publish(Event(event_type="risk_decision"))

        if not decision.is_approved:
            logger.info("Trade vetoed for %s: %s", tick.symbol, decision.reason)
            return []

        side = OrderSide.BUY if consensus.direction == SignalDirection.BUY else OrderSide.SELL
        quantity = await self._compute_quantity(side, tick, portfolio, decision, consensus)

        if quantity <= 0:
            logger.info("Skipping %s %s: computed quantity is zero", side.value, tick.symbol)
            return []

        order = Order(
            symbol=tick.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            asset_type=tick.asset_type,
            signal_id=consensus.id,
        )

        fill = await self._executor.submit_order(order)
        await self._portfolio.record_fill(fill)

        # Publish fill event with payload
        await self._event_bus.publish(FillEvent(fill=fill, strategy="consensus"))

        return [fill]

    async def _compute_quantity(
        self,
        side: OrderSide,
        tick: MarketTick,
        portfolio,
        decision,
        signal: Signal | None = None,
    ) -> Decimal:
        """Compute order quantity with position sizing and hard limits."""
        if tick.price <= 0:
            return Decimal("0")

        if side == OrderSide.BUY:
            if self._position_sizer is not None and signal is not None:
                # Delegate to position sizer for trade value
                from src.risk.models import RiskContext, VolatilityRegime

                # Build a minimal risk context for the sizer
                risk_context = RiskContext(
                    regime=VolatilityRegime.MEDIUM,
                    correlation_matrix={},
                    strategy_stats={},
                    drawdown_from_peak=0.0,
                    portfolio=portfolio,
                    daily_pnl=Decimal("0"),
                )
                trade_value = await self._position_sizer.compute_size(
                    signal, portfolio, risk_context
                )
            else:
                # Size based on % of portfolio value
                trade_value = portfolio.total_value * self._position_size_pct / Decimal("100")
            # Never spend more than available cash
            trade_value = min(trade_value, portfolio.cash)
            # Skip if below minimum order value
            if trade_value < self._min_order_value:
                return Decimal("0")
            quantity = trade_value / tick.price
        else:
            # Sells: can only sell what we hold
            held = Decimal("0")
            for pos in portfolio.positions:
                if pos.symbol == tick.symbol:
                    held = pos.quantity
                    break
            if held <= 0:
                return Decimal("0")
            quantity = held

        # Risk manager can override quantity, but hard limits still apply
        if decision.adjusted_quantity is not None:
            quantity = decision.adjusted_quantity
            if side == OrderSide.BUY:
                max_affordable = portfolio.cash / tick.price
                quantity = min(quantity, max_affordable)
            else:
                held = Decimal("0")
                for pos in portfolio.positions:
                    if pos.symbol == tick.symbol:
                        held = pos.quantity
                        break
                quantity = min(quantity, held)

        return quantity

    async def _gather_signals(self, tick: MarketTick) -> list[Signal]:
        history = self._tick_history.get(tick.symbol, [tick])
        tasks = [
            strategy.evaluate(tick.symbol, history, research=self._research)
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

    async def _persist_signals(self, signals: list[Signal]) -> None:
        """Persist signals to the database if one is configured."""
        if self._db is None or not signals:
            return
        for signal in signals:
            try:
                record = SignalRecord(
                    symbol=signal.symbol,
                    direction=signal.direction.value,
                    confidence=signal.confidence,
                    strategy=signal.strategy_name,
                    reasoning=signal.reasoning,
                    timestamp=signal.timestamp,
                )
                await self._db.save_signal(record)
            except Exception:
                logger.exception("Failed to persist signal for %s", signal.symbol)

    def _find_consensus(self, signals: list[Signal]) -> Signal | None:
        if not signals:
            return None

        non_hold = [s for s in signals if s.direction != SignalDirection.HOLD]
        if not non_hold:
            return None

        counts = Counter(s.direction for s in non_hold)
        most_common, count = counts.most_common(1)[0]

        # Clear majority: use the majority direction
        if count > len(non_hold) / 2:
            agreeing = [s for s in non_hold if s.direction == most_common]
            return max(agreeing, key=lambda s: s.confidence)

        # Tie between directions: break by highest confidence signal
        return max(non_hold, key=lambda s: s.confidence)
