"""Shared state container and auth dependencies for dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from src.agents.execution import PaperExecutionAgent
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.auth.dependencies import get_current_user
from src.core.config import Settings
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.db.database import Database
from src.db.models import UserRecord


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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _jwt_secret() -> str:
    if state.settings is None or not state.settings.auth.jwt_secret_key:
        raise HTTPException(status_code=503, detail="Auth not configured")
    return state.settings.auth.jwt_secret_key


async def require_user(token: str | None = Depends(oauth2_scheme)) -> UserRecord:
    """FastAPI dependency: extracts and validates the current user from JWT."""
    if token is None:
        raise HTTPException(
            status_code=401, detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return await get_current_user(
        token=token, db=state.db, secret=_jwt_secret(),
    )
