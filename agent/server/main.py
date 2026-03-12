"""OmniSense mobile-first live assistant server."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from fastapi.staticfiles import StaticFiles

from config import settings
from dependencies import manager
from live_state import cleanup_inactive_sessions
from routes.health import router as health_router
from routes.ws import router as ws_router
from routes.config import router as config_router

logger = logging.getLogger(__name__)


# ── Lifespan (graceful shutdown) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Server starting up")
    cleanup_task = asyncio.create_task(cleanup_inactive_sessions())
    try:
        yield
    finally:
        cleanup_task.cancel()
        logger.info(
            "Server shutting down — closing %d active connections",
            manager.active_count,
        )
        await manager.close_all()


# ── App factory ──────────────────────────────────────────────────────
app = FastAPI(title="SupportPilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(config_router)
app.include_router(ws_router)

# ── Static files (SPA fallback) ─────────────────────────────────────
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        ws_ping_interval=settings.ws_ping_interval,
        ws_ping_timeout=settings.ws_ping_timeout,
        reload=False,
    )
