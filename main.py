from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
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
from src.feeds.null_feed import NullStockFeed
from src.integrations.ibkr import IBKRFeed
from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
from src.ml.ensemble import EnsembleModel
from src.ml.feature_engine import FeatureEngine
from src.ml.feature_store import FeatureStore
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector
from src.providers.mock import MockFeatureProvider, MockOnChainProvider
from src.providers.onchain_features import OnChainFeatureProvider
from src.providers.protocols import (
    FeatureProvider,
    NewsProvider,
    OnChainProvider as OnChainProviderProtocol,
    SentimentAnalyzer,
)
from src.providers.registry import ProviderRegistry
from src.risk.circuit_breaker import DrawdownCircuitBreaker
from src.risk.fixed_sizer import FixedPositionSizer
from src.risk.vol_sizer import VolTargetedPositionSizer

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


class DailyPnLTracker:
    """Tracks daily PnL from a start-of-day portfolio value, resets at midnight."""

    def __init__(self) -> None:
        self.day_start_value: Decimal | None = None
        self._current_date: datetime | None = None

    def update(self, portfolio_value: Decimal, now: datetime) -> Decimal:
        """Update with current portfolio value. Returns daily PnL."""
        today = now.date()
        if self._current_date is None or today != self._current_date:
            # New day or first call — reset
            self.day_start_value = portfolio_value
            self._current_date = today
            return Decimal("0")
        return portfolio_value - self.day_start_value


def build_stock_feed(settings: Settings) -> tuple:
    """Build stock feed and symbol list based on mock settings."""
    if settings.use_mocks.stock_feed:
        return NullStockFeed(), []
    return IBKRFeed(), settings.trading.symbols.stocks


def build_circuit_breaker(settings: Settings) -> DrawdownCircuitBreaker:
    """Build a circuit breaker from risk settings."""
    return DrawdownCircuitBreaker(
        max_drawdown_pct=settings.risk.weekly_drawdown_limit_pct,
        cooldown_hours=24.0,
    )


def build_risk_manager(settings: Settings) -> RiskManager:
    """Build RiskManager with circuit breaker wired in."""
    circuit_breaker = build_circuit_breaker(settings)
    return RiskManager(settings.risk, circuit_breaker=circuit_breaker)


def build_position_sizer(settings: Settings):
    """Build position sizer based on mock settings."""
    if settings.use_mocks.position_sizer:
        return FixedPositionSizer(position_pct=settings.risk.max_position_pct)
    return VolTargetedPositionSizer(target_vol_contribution=0.01)


class MLTickAdapter:
    """Adapts an MLEnsembleStrategy (feature-based) to the tick-based orchestrator interface."""

    def __init__(self, ml_strategy: MLEnsembleStrategy, feature_store: FeatureStore) -> None:
        self._ml_strategy = ml_strategy
        self._feature_store = feature_store

    @property
    def name(self) -> str:
        return self._ml_strategy.name

    async def evaluate(self, symbol: str, market_data: list, research=None):
        """Bridge tick-based evaluate to feature-based evaluate."""
        if not market_data:
            return None
        latest_tick = market_data[-1]
        timestamp = int(latest_tick.timestamp.timestamp())
        features = self._feature_store.load(symbol, timestamp)
        if not features:
            return None
        vector = FeatureVector(symbol=symbol, timestamp=timestamp, features=features)
        return await self._ml_strategy.evaluate(symbol, vector)


def build_ml_strategy(settings: Settings) -> MLEnsembleStrategy:
    """Build ML ensemble strategy with mock or real model."""
    if settings.use_mocks.ml:
        model = MockModel()
    else:
        model = EnsembleModel(models=[])
    return MLEnsembleStrategy(model=model)


def build_registry(
    settings: Settings,
    news_provider=None,
    sentiment_analyzer=None,
    onchain_provider=None,
    feature_provider=None,
) -> ProviderRegistry:
    """Build provider registry and register all active providers."""
    registry = ProviderRegistry()
    if news_provider is not None:
        registry.register(NewsProvider, news_provider)
    if sentiment_analyzer is not None:
        registry.register(SentimentAnalyzer, sentiment_analyzer)
    if onchain_provider is not None:
        registry.register(OnChainProviderProtocol, onchain_provider)
    if feature_provider is not None:
        registry.register(FeatureProvider, feature_provider)
    return registry


def build_onchain_provider(settings: Settings) -> OnChainFeatureProvider:
    """Build on-chain feature provider with mock or real backend."""
    if settings.use_mocks.onchain:
        return OnChainFeatureProvider(MockOnChainProvider())
    from src.providers.blockchair import BlockchairProvider
    from src.providers.configs import BlockchairConfig
    from src.providers.mock import MockHttpClient
    client = MockHttpClient()  # Replaced with real HTTP client when available
    return OnChainFeatureProvider(BlockchairProvider(BlockchairConfig(), client))


def build_feature_engine(settings: Settings) -> tuple[FeatureEngine, FeatureStore]:
    """Build feature engine with mock or real providers."""
    store = FeatureStore()
    if settings.use_mocks.ml:
        providers = [MockFeatureProvider()]
    else:
        from src.providers.technical import TechnicalFeatureProvider
        providers = [TechnicalFeatureProvider()]
    engine = FeatureEngine(providers=providers, store=store)
    return engine, store


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
    risk_manager = build_risk_manager(settings)
    executor = PaperExecutionAgent(slippage_pct=Decimal("0.05"))
    position_sizer = build_position_sizer(settings)

    # Feature engine and on-chain provider (before strategies so adapter can use store)
    feature_engine, feature_store = build_feature_engine(settings)
    onchain_provider = build_onchain_provider(settings)
    logger.info(
        "Feature engine initialized with %d providers, on-chain: %s",
        len(feature_engine._providers),
        onchain_provider._provider.__class__.__name__,
    )

    # ML strategy with tick adapter
    ml_strategy = build_ml_strategy(settings)
    ml_adapter = MLTickAdapter(ml_strategy, feature_store)

    strategies = [
        MomentumStrategy(short_window=5, long_window=14),
        SentimentStrategy(),
        QuantitativeStrategy(lookback=10, z_threshold=2.0),
        ml_adapter,
    ]

    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
        db=db,
        position_sizer=position_sizer,
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

    # Provider registry
    registry = build_registry(
        settings,
        news_provider=rss_provider if settings.sentiment.enabled else None,
        sentiment_analyzer=analyzer if settings.sentiment.enabled else None,
        onchain_provider=onchain_provider._provider,
        feature_provider=feature_engine._providers[0] if feature_engine._providers else None,
    )
    logger.info("Provider registry: %d providers", len(list(registry.all())))

    # Market data
    crypto_feed = KrakenFeed()
    stock_feed, stock_symbols = build_stock_feed(settings)
    market_data = MarketDataManager(
        stock_feed=stock_feed,
        crypto_feed=crypto_feed,
        stock_symbols=stock_symbols,
        crypto_symbols=settings.trading.symbols.crypto,
    )

    await market_data.connect()

    logger.info("Trade bot initialized with %d strategies", len(strategies))
    logger.info("Strategies: %s", [s.name for s in strategies])
    logger.info("Watching crypto: %s", settings.trading.symbols.crypto)
    logger.info("Paper trading with $%s initial capital", portfolio._cash)

    poll_interval = 30  # seconds between market data fetches
    tick_count = 0
    pnl_tracker = DailyPnLTracker()

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

                # Update circuit breaker and daily PnL
                snapshot = await portfolio.get_snapshot()
                now = datetime.now(timezone.utc)
                risk_manager.update_circuit_breaker(snapshot.total_value, now)
                daily_pnl = pnl_tracker.update(snapshot.total_value, now)
                risk_manager.record_daily_pnl(daily_pnl)

                # Log portfolio summary every 5 ticks
                if tick_count % 5 == 0:
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
