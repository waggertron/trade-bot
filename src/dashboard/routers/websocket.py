"""WebSocket endpoint for real-time updates."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.dashboard.dependencies import state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# Connected WebSocket clients
_clients: set[WebSocket] = set()


async def broadcast(event_type: str, data: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    message = json.dumps({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _clients.difference_update(disconnected)


@router.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket connection for real-time updates."""
    await ws.accept()
    _clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_clients))

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await ws.receive_text()
            # Clients can send ping/subscribe messages
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_clients))
