"""Shared singleton instances used across routes."""

from __future__ import annotations

import logging

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import agent, agent_voice_name
from config import settings
from connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

session_service = InMemorySessionService()

# ── Memory service ───────────────────────────────────────────────────
# Use Vertex AI Memory Bank in production, InMemory for local dev.
if settings.agent_engine_id and settings.is_vertex_ai:
    try:
        from google.adk.memory import VertexAiMemoryBankService

        memory_service = VertexAiMemoryBankService(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
            agent_engine_id=settings.agent_engine_id,
        )
        logger.info(
            "Using Vertex AI Memory Bank (engine_id=%s)",
            settings.agent_engine_id,
        )
    except Exception as exc:
        logger.warning("Failed to init Vertex AI Memory Bank, falling back: %s", exc)
        memory_service = InMemoryMemoryService()
else:
    memory_service = InMemoryMemoryService()
    logger.info("Using InMemoryMemoryService (set AGENT_ENGINE_ID for Vertex AI)")

runner = Runner(
    app_name=settings.app_name,
    agent=agent,
    session_service=session_service,
    memory_service=memory_service,
)

manager = ConnectionManager(settings.max_ws_connections)


# ── RunConfig factory ────────────────────────────────────────────────
def create_run_config() -> RunConfig:
    """Build a RunConfig for bidirectional live streaming."""
    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=100000,
            sliding_window=types.SlidingWindow(target_tokens=80000),
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=agent_voice_name
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
        proactivity=types.ProactivityConfig(proactive_audio=True),
        enable_affective_dialog=True,
    )
