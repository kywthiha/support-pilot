"""Application configuration, constants, and logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ── .env path (resolved once at import time) ─────────────────────────
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE)


# ── Settings ─────────────────────────────────────────────────────────
class Settings(BaseSettings):
    """
    Central application settings.

    Values are loaded from environment variables and an optional `.env`
    file using pydantic-settings.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "support-pilot"
    app_title: str = "SupportPilot"
    agent_display_name: str = "SupportPilot"
    log_level: str = "WARNING"

    # ── Agent (set per Cloud Run instance) ───────────────────────
    agent_id: str | None = None

    # ── Models ───────────────────────────────────────────────────
    agent_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    observe_model: str = "gemini-3-flash-preview"

    # ── WebSocket tuning ─────────────────────────────────────────
    ws_ping_interval: int = 25
    ws_ping_timeout: int = 10
    max_ws_connections: int = 100

    # ── Google API ──────────────────────────────────────────────────
    google_api_key: str | None = None

    # ── Google Cloud / Vertex AI ─────────────────────────────────
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"

    # ── Session cleanup ──────────────────────────────────────────
    session_timeout_seconds: float = 900.0

    # ── Memory (Vertex AI Memory Bank) ───────────────────────────
    agent_engine_id: str | None = None

    # ── Default RAG & Search (Local Dev Fallbacks) ───────────────
    rag_corpus: str | None = None
    search_domain: str | None = None

    # ── CORS ─────────────────────────────────────────────────────
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    )

    # ── Computed helpers ─────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse the comma-separated origins string into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_vertex_ai(self) -> bool:
        """True when a valid GCP project is configured."""
        return bool(
            self.google_cloud_project
            and self.google_cloud_project != "your-gcp-project-id"
        )


# ── Module-level singleton ───────────────────────────────────────────
settings = Settings()


# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# ── Terminal error codes from the Live API ───────────────────────────
TERMINAL_ERROR_CODES: frozenset[str] = frozenset(
    {
        "SAFETY",
        "PROHIBITED_CONTENT",
        "BLOCKLIST",
        "MAX_TOKENS",
        "CANCELLED",
    }
)

# ── RFC 6455 close codes ─────────────────────────────────────────────
WS_CLOSE_GOING_AWAY = 1001
WS_CLOSE_INTERNAL_ERROR = 1011
WS_CLOSE_TRY_AGAIN_LATER = 1013

# ── Binary message type tags ─────────────────────────────────────────
MSG_TYPE_VIDEO = 1
MSG_TYPE_AUDIO = 2
