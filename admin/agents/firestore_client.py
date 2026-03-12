"""Firestore client for the admin panel — full CRUD access."""

from __future__ import annotations

import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.cloud import firestore

logger = logging.getLogger(__name__)

# Load env variables explicitly for firestore client
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

from google.cloud import firestore

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "prefab-lamp-489711-j3")
DATABASE_ID = os.environ.get("FIRESTORE_DATABASE", "(default)")
# Using a single-region location (us-central1) instead of multi-region (nam5)
LOCATION_ID = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1") 

AGENTS_COLLECTION = "agents"

_db: firestore.Client | None = None


def _get_db() -> firestore.Client:
    """Return a cached synchronous Firestore client."""
    global _db
    if _db is None:
        # Initialize client referencing the specific database
        _db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID) if PROJECT_ID else firestore.Client(database=DATABASE_ID)
    return _db


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------
def list_agents(owner_id: int | str | None = None) -> list[dict[str, Any]]:
    """Return agents, optionally filtered by owner_id. Sorted by created_at descending."""
    db = _get_db()
    query = db.collection(AGENTS_COLLECTION)
    if owner_id is not None:
        query = query.where("owner_id", "==", str(owner_id))
    
    docs = query.stream()
    agents = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        agents.append(data)
    
    # Sort in memory to avoid missing index errors in Firestore
    # when filtering by owner_id and sorting by created_at
    agents.sort(key=lambda x: x.get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return agents


def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Load a single agent config by ID."""
    db = _get_db()
    doc = db.collection(AGENTS_COLLECTION).document(agent_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def create_agent(data: dict[str, Any], owner_id: int | str | None = None) -> str:
    """Create a new agent and return its ID."""
    db = _get_db()
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc_data = {
        "name": data["name"],
        "agent_key": data.get("agent_key", data["name"].lower().replace(" ", "-")),
        "instruction": data.get("instruction", ""),
        "description": data.get("description", ""),
        "voice_name": data.get("voice_name", "Kore"),
        "google_search_enabled": data.get("google_search_enabled", True),
        "search_domains": data.get("search_domains", ""),
        "knowledge_enabled": data.get("knowledge_enabled", True),
        "rag_corpus": data.get("rag_corpus", ""),
        "is_demo": data.get("is_demo", False),
        "owner_id": str(owner_id) if owner_id else "",
        "created_at": now,
        "updated_at": now,
    }
    db.collection(AGENTS_COLLECTION).document(agent_id).set(doc_data)
    logger.info("Created agent '%s' with ID %s for owner %s", data["name"], agent_id, owner_id)
    return agent_id


def update_agent(agent_id: str, data: dict[str, Any]) -> None:
    """Update an existing agent config."""
    db = _get_db()
    data["updated_at"] = datetime.now(timezone.utc)
    db.collection(AGENTS_COLLECTION).document(agent_id).update(data)
    logger.info("Updated agent %s", agent_id)


def delete_agent(agent_id: str) -> None:
    """Delete an agent config."""
    db = _get_db()
    db.collection(AGENTS_COLLECTION).document(agent_id).delete()
    logger.info("Deleted agent %s", agent_id)

def check_agent_key_exists(agent_key: str, exclude_id: str | None = None) -> bool:
    """Check if an agent_key is already in use by another agent."""
    db = _get_db()
    query = db.collection(AGENTS_COLLECTION).where("agent_key", "==", agent_key)
    docs = query.stream()
    for doc in docs:
        if exclude_id and doc.id == exclude_id:
            continue
        return True
    return False
