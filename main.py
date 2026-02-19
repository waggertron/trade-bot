from __future__ import annotations

import asyncio
import logging
import os
import time
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
from src.providers.configs import OllamaSentimentConfig, RSSConfig
from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
from src.providers.rss import RSSNewsProvider
from src.sentiment.bridge import SentimentBridge
from src.sentiment.pipeline import SentimentPipeline

from src.core.models import Fill
from src.db.models import TradeRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("trade-bot")


async def persist_fill(
    db: Database,
    fill: Fill,
    strategy_name: str,
    is_paper: bool,
) -> None:
    """Persist a trade fill to the database. Failures are logged, not raised."""
    try:
        record = TradeRecord(
            symbol=fill.symbol,
            side=fill.side.value,
            quantity=str(fill.quantity),
            price=str(fill.fill_price),
            commission=str(fill.commission),
            strategy=strategy_name,
            paper=is_paper,
            timestamp=fill.timestamp,
        )
        await db.save_trade(record)
    except Exception:
        logger.exception("Failed to persist fill for %s", fill.symbol)


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


async def run_sentiment_cycle(
    pipeline: SentimentPipeline,
    bridge: SentimentBridge,
    orchestrator: Orchestrator,
    symbols: list[str],
) -> None:
    """Run one sentiment pipeline cycle and update orchestrator research."""
    try:
        await pipeline.run_cycle(symbols)
        reports = bridge.to_research_reports(symbols)
        orchestrator.set_research(reports)
        logger.info(
            "Sentiment cycle complete: %d reports, scores=%s",
            len(reports),
            {r.symbol: f"{r.sentiment_score:+.2f}" for r in reports},
        )
    except Exception:
        logger.exception("Error in sentiment pipeline cycle")


async def sentiment_loop(
    pipeline: SentimentPipeline,
    bridge: SentimentBridge,
    orchestrator: Orchestrator,
    symbols: list[str],
    interval_seconds: int,
) -> None:
    """Background task that runs sentiment pipeline cycles on a timer."""
    while True:
        await run_sentiment_cycle(pipeline, bridge, orchestrator, symbols)
        await asyncio.sleep(interval_seconds)


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
        db=db,
    )

    # Sentiment pipeline
    sentiment_task = None
    if settings.sentiment.enabled:
        rss_provider = RSSNewsProvider(
            RSSConfig(feed_urls=settings.sentiment.rss_feed_urls)
        )
        analyzer = OllamaSentimentAnalyzer(
            OllamaSentimentConfig(model=settings.ai.ollama_model)
        )
        sentiment_pipeline = SentimentPipeline(
            news_providers=[rss_provider],
            analyzer=analyzer,
        )
        sentiment_bridge = SentimentBridge(
            aggregator=sentiment_pipeline.aggregator
        )

        # Strip slash-pair suffixes for symbol matching (e.g. "BTC/USD" -> "BTC")
        sentiment_symbols = [
            s.split("/")[0] for s in settings.trading.symbols.crypto
        ]

        # Run initial sentiment cycle before trading starts
        await run_sentiment_cycle(
            sentiment_pipeline, sentiment_bridge, orchestrator, sentiment_symbols,
        )

        # Launch background sentiment loop
        sentiment_task = asyncio.create_task(
            sentiment_loop(
                sentiment_pipeline,
                sentiment_bridge,
                orchestrator,
                sentiment_symbols,
                settings.sentiment.pipeline_interval_seconds,
            )
        )
        logger.info(
            "Sentiment pipeline active: %d RSS feeds, %ds interval, analyzer=%s",
            len(settings.sentiment.rss_feed_urls),
            settings.sentiment.pipeline_interval_seconds,
            settings.sentiment.analyzer,
        )
    else:
        logger.info("Sentiment pipeline disabled")

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
                        await persist_fill(
                            db, fill,
                            strategy_name="consensus",
                            is_paper=settings.is_paper,
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
        if sentiment_task is not None:
            sentiment_task.cancel()
        await market_data.disconnect()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
