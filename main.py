from __future__ import annotations

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from src.agents.execution import PaperExecutionAgent
from src.agents.market_data import MarketDataManager
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.quantitative import QuantitativeStrategy
from src.agents.strategies.sentiment import SentimentStrategy
from src.core.config import Settings
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.db.database import Database
from src.integrations.kraken import KrakenFeed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("trade-bot")


class NullStockFeed:
    """Placeholder stock feed when IBKR is not connected."""

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")

    async def get_order_book(self, symbol: str) -> dict:
        return {"bids": [], "asks": []}


async def main():
    load_dotenv()

    config_path = Path("config/settings.yaml")
    settings = Settings.from_yaml(config_path)
    logger.info("Starting trade bot in %s mode", settings.mode)

    # Database
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///trade_bot.db")
    db = Database(db_url)
    await db.initialize()

    # Event bus
    event_bus = EventBus()
    event_bus.enable_history()

    # Agents
    portfolio = PortfolioManager(initial_cash=Decimal("100000"))
    risk_manager = RiskManager(settings.risk)
    executor = PaperExecutionAgent(slippage_pct=Decimal("0.05"))

    strategies = [
        MomentumStrategy(short_window=5, long_window=14),
        SentimentStrategy(),
        QuantitativeStrategy(lookback=10, z_threshold=2.0),
    ]

    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )

    # Market data — Kraken for crypto (no auth needed for public data)
    # IBKR skipped for now (needs TWS running)
    crypto_feed = KrakenFeed()
    market_data = MarketDataManager(
        stock_feed=NullStockFeed(),
        crypto_feed=crypto_feed,
        stock_symbols=[],  # Skip stocks until IBKR is configured
        crypto_symbols=settings.trading.symbols.crypto,
    )

    await market_data.connect()

    logger.info("Trade bot initialized with %d strategies", len(strategies))
    logger.info("Strategies: %s", [s.name for s in strategies])
    logger.info("Watching crypto: %s", settings.trading.symbols.crypto)
    logger.info("Paper trading with $%s initial capital", portfolio._cash)

    poll_interval = 30  # seconds between market data fetches
    tick_count = 0

    try:
        while True:
            try:
                ticks = await market_data.snapshot()
                tick_count += 1

                for tick in ticks:
                    # Update executor's price knowledge
                    executor.set_current_price(tick.symbol, tick.price)

                    logger.info(
                        "[Tick #%d] %s: $%s",
                        tick_count, tick.symbol, tick.price,
                    )

                    # Run through orchestrator
                    fills = await orchestrator.process_tick(tick)

                    for fill in fills:
                        logger.info(
                            "TRADE EXECUTED: %s %s qty=%s @ $%s",
                            fill.side.value.upper(),
                            fill.symbol,
                            fill.quantity,
                            fill.fill_price,
                        )

                # Log portfolio summary every 5 ticks
                if tick_count % 5 == 0:
                    snapshot = await portfolio.get_snapshot()
                    positions = await portfolio.get_positions()
                    logger.info(
                        "Portfolio: cash=$%s, positions=%d, total=$%s",
                        snapshot.cash, len(positions), snapshot.total_value,
                    )
                    for pos in positions:
                        logger.info(
                            "  %s: qty=%s, entry=$%s, current=$%s, pnl=$%s",
                            pos.symbol, pos.quantity, pos.avg_entry_price,
                            pos.current_price, pos.unrealized_pnl,
                        )

                    # Log tick history depth
                    for sym, hist in orchestrator._tick_history.items():
                        logger.info("  %s history: %d ticks", sym, len(hist))

            except Exception:
                logger.exception("Error in trading loop")

            await asyncio.sleep(poll_interval)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await market_data.disconnect()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
