"""WebSocket connection tracker with concurrency limits and graceful shutdown."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from config import WS_CLOSE_GOING_AWAY
from live_state import delete_session_state

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Track active WebSocket connections, enforce limits, enable graceful shutdown."""

    def __init__(self, max_connections: int) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._max = max_connections
        self._lock = asyncio.Lock()

    async def accept(self, websocket: WebSocket, session_id: str) -> bool:
        """Register a WebSocket. Returns False if at capacity."""
        async with self._lock:
            if len(self._connections) >= self._max:
                return False
            self._connections[session_id] = websocket
            return True

    async def remove(self, session_id: str) -> None:
        """Unregister a connection and clean up its session state."""
        async with self._lock:
            self._connections.pop(session_id, None)
        delete_session_state(session_id)

    async def close_all(
        self,
        code: int = WS_CLOSE_GOING_AWAY,
        reason: str = "Server shutting down",
    ) -> None:
        """Gracefully close every active WebSocket (used during shutdown)."""
        async with self._lock:
            connections = list(self._connections.items())
            self._connections.clear()

        for sid, ws in connections:
            try:
                await ws.close(code, reason)
            except Exception:
                logger.debug("Error closing ws for session %s during shutdown", sid)
            delete_session_state(sid)

    @property
    def active_count(self) -> int:
        return len(self._connections)
