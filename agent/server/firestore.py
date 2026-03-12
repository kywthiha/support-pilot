"""Firestore client — read-only access for agent runner instances."""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import firestore

logger = logging.getLogger(__name__)

_db: firestore.AsyncClient | None = None

AGENTS_COLLECTION = "agents"


def _get_db() -> firestore.AsyncClient:
    """Return a cached async Firestore client."""
    global _db
    if _db is None:
        _db = firestore.AsyncClient()
    return _db


async def get_agent_config(agent_id: str) -> dict[str, Any]:
    """Load a single agent config from Firestore.

    Raises:
        ValueError: If the agent document does not exist.
    """
    db = _get_db()
    doc_ref = db.collection(AGENTS_COLLECTION).document(agent_id)
    doc = await doc_ref.get()

    if not doc.exists:
        raise ValueError(f"Agent '{agent_id}' not found in Firestore.")

    data = doc.to_dict()
    data["id"] = doc.id
    logger.info("Loaded agent config for '%s' (%s)", data.get("name"), agent_id)
    return data
