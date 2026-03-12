"""In-memory live session state for the VisionGuard mobile MVP."""

from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """A single camera frame."""
    data: bytes
    mime_type: str


@dataclass
class SessionState:
    """Per-session live state."""
    latest_frame: FrameData | None = None
    last_active: float = field(default_factory=time.time)


_STATE_BY_SESSION: dict[str, SessionState] = {}
_LOCK = Lock()


def create_session_state(session_id: str) -> SessionState:
    state = SessionState()
    with _LOCK:
        _STATE_BY_SESSION[session_id] = state
    return deepcopy(state)


def delete_session_state(session_id: str) -> None:
    with _LOCK:
        _STATE_BY_SESSION.pop(session_id, None)


def get_session_state(session_id: str) -> SessionState | None:
    with _LOCK:
        state = _STATE_BY_SESSION.get(session_id)
        if state is not None:
            state.last_active = time.time()
            return deepcopy(state)
        return None


def update_latest_frame(session_id: str, data: bytes, mime_type: str) -> None:
    with _LOCK:
        state = _STATE_BY_SESSION.setdefault(session_id, SessionState())
        state.latest_frame = FrameData(data=data, mime_type=mime_type)
        state.last_active = time.time()


def get_latest_frame(session_id: str) -> FrameData | None:
    with _LOCK:
        state = _STATE_BY_SESSION.get(session_id)
        if not state:
            return None
        state.last_active = time.time()
        return deepcopy(state.latest_frame) if state.latest_frame else None


async def cleanup_inactive_sessions() -> None:
    """Periodically clean up sessions that have been inactive."""
    timeout = settings.session_timeout_seconds
    while True:
        await asyncio.sleep(60)
        now = time.time()
        to_delete: list[str] = []
        with _LOCK:
            for session_id, state in _STATE_BY_SESSION.items():
                if now - state.last_active > timeout:
                    to_delete.append(session_id)
            for session_id in to_delete:
                _STATE_BY_SESSION.pop(session_id, None)
        if to_delete:
            logger.info("Cleaned up %d inactive session(s): %s", len(to_delete), to_delete)