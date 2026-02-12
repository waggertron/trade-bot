"""Shared state container for dashboard dependency injection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.agents.execution import PaperExecutionAgent
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.core.config import Settings
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.db.database import Database


@dataclass
class DashboardState:
    """Holds references to all shared application state for the dashboard."""

    portfolio: PortfolioManager | None = None
    db: Database | None = None
    orchestrator: Orchestrator | None = None
    executor: PaperExecutionAgent | None = None
    risk_manager: RiskManager | None = None
    event_bus: EventBus | None = None
    settings: Settings | None = None
    strategies: list = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Singleton instance — set by create_app()
state = DashboardState()
