"""Serves client configuration as a JavaScript global variable."""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import Response

from config import settings

router = APIRouter(tags=["config"])


@router.get("/api/config.js")
async def config_js() -> Response:
    config = {
        "appTitle": settings.app_title,
        "agentDisplayName": settings.agent_display_name,
    }
    js = f"window.__APP_CONFIG__ = {json.dumps(config)};"
    return Response(content=js, media_type="application/javascript")
