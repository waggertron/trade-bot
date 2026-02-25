from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class Event:
    event_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., Any]]] = {}
        self._history: list[Event] | None = None

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        if self._history is not None:
            self._history.append(event)
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("Error in event handler for %s", event.event_type)

    def enable_history(self) -> None:
        self._history = []

    def get_history(self, event_type: str | None = None) -> list[Event]:
        if self._history is None:
            return []
        if event_type:
            return [e for e in self._history if e.event_type == event_type]
        return list(self._history)
