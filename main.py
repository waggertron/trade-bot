# main.py
from __future__ import annotations

import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from src.agents.execution import PaperExecutionAgent
from src.agents.market_data import MarketDataManager
from src.agents.portfolio import PortfolioManager
from src.agents.research import ResearchManager
from src.agents.risk_manager import RiskManager
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.quantitative import QuantitativeStrategy
from src.agents.strategies.sentiment import SentimentStrategy
from src.core.config import Settings
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.db.database import Database
from src.integrations.claude_client import ClaudeClient
from src.integrations.ollama_client import OllamaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trade-bot")


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

    # AI clients
    claude = ClaudeClient(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        model=settings.ai.claude_model,
    )
    ollama = OllamaClient(
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model=settings.ai.ollama_model,
    )

    # Agents
    portfolio = PortfolioManager(initial_cash=Decimal("100000"))
    risk_manager = RiskManager(settings.risk)
    executor = PaperExecutionAgent()
    researcher = ResearchManager(claude=claude, ollama=ollama)

    strategies = []
    strategies.append(MomentumStrategy())
    strategies.append(SentimentStrategy())
    strategies.append(QuantitativeStrategy())

    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )

    logger.info("Trade bot initialized with %d strategies", len(strategies))
    logger.info("Strategies: %s", [s.name for s in strategies])

    # Placeholder main loop
    try:
        while True:
            await asyncio.sleep(60)
            logger.info("Bot running... (market data + dashboard coming in next tasks)")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await db.close()
        await ollama.close()


if __name__ == "__main__":
    asyncio.run(main())
