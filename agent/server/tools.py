"""SupportPilot — screen analysis tools for live software support."""

from __future__ import annotations

import logging
from typing import Any

import asyncio
import random
from typing import Any

from google import genai
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import BaseModel, Field

from config import settings
from live_state import get_latest_frame

logger = logging.getLogger(__name__)

MAX_RETRIES = 1
RETRY_BASE_DELAY = 1.0  # seconds

# ---------------------------------------------------------------------------
# GenAI client (lazy singleton — only used by this module)
# ---------------------------------------------------------------------------
_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    """Return a cached genai.Client, initialized on first call."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    if settings.is_vertex_ai:
        location = "global" if "preview" in settings.observe_model.lower() else settings.google_cloud_location
        logger.info(
            "Initializing GenAI client for Vertex AI (project=%s, location=%s)",
            settings.google_cloud_project,
            location,
        )
        _genai_client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=location,
        )
    else:
        logger.warning(
            "GOOGLE_CLOUD_PROJECT not set or default. "
            "Falling back to Google AI Studio."
        )
        _genai_client = genai.Client(api_key=settings.google_api_key)

    return _genai_client


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------
class ScreenAnalysis(BaseModel):
    """Structured analysis of the customer's shared software screen."""

    is_view_clear: bool = Field(
        description="True if the screen share is clear and readable. False if it is too blurry, too small, or not showing the software interface."
    )
    current_page: str = Field(
        description="The software page or section currently visible (e.g., 'Dashboard', 'Settings page', 'User management', 'Module configuration')."
    )
    visible_elements: str = Field(
        description="Key UI elements visible on screen: buttons, form fields, error messages, notifications, menus, modals, tabs, and their current states (enabled/disabled, filled/empty, selected/unselected)."
    )
    customer_issue_or_goal: str = Field(
        description="What the customer appears to be doing or what problem they are encountering, based strictly on what is visible on screen."
    )
    suggested_next_step: str = Field(
        description="The recommended next action the customer should take within the software interface to accomplish their goal or resolve their issue."
    )

class AnalysisError(BaseModel):
    """Standardized error payload returned by tools."""
    status: str = Field(default="error")
    error_code: str = Field(description="Machine-readable error code.")
    error_message: str = Field(description="Human-readable explanation.")
    tool_name: str = Field(default="")


class ToolResponse(BaseModel):
    """Wrapper that every tool returns for consistent downstream handling."""
    status: str = Field(default="success")
    tool_name: str = Field(description="Name of the tool that produced this response.")
    data: dict[str, Any] | None = Field(
        default=None,
        description="Analysis payload on success.",
    )
    error: AnalysisError | None = Field(
        default=None,
        description="Error details when the tool fails.",
    )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
ANALYZE_PROMPT = """\
You are the screen-reading engine for SupportPilot, a live customer support system for SaaS software platforms.
Your job is to analyze the customer's shared screen and extract precise, actionable insights about their current software state.

## Core Directives
1. **Absolute Objectivity**: Describe ONLY what is explicitly visible on the screen. Do not hallucinate or assume content that is off-screen.
2. **Screen Quality Assessment**: Assess if the screen share is clear and readable. If it is too blurry, too small, cropped badly, or not showing the software interface, set `is_view_clear` to `false`.
3. **Page Identification**: Clearly identify which software page or section is visible — dashboards, settings panels, configuration pages, module views, user management, reports, etc. Include the URL path if visible in the browser address bar.
4. **UI Element Detail**: Catalog visible buttons, form fields (and their values if readable), dropdown states, error banners, success toasts, modal dialogs, navigation state (which sidebar item is active), and any validation messages.
5. **Issue Detection**: Look for error messages, warning banners, incorrectly filled fields, grayed-out buttons, or any visual indicator of a problem. Document these in `customer_issue_or_goal`.
6. **Actionable Guidance**: Based on what you see, provide a clear, specific `suggested_next_step` — e.g., "Click the 'Save' button in the top right" or "The 'Name' field is empty, it needs a value before saving."

Remember: You are the eyes of the support agent. The main agent relies on your exact description to guide the customer. Be thorough and precise about UI elements.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _session_id(tool_context: ToolContext | None) -> str | None:
    if tool_context is None:
        return None
    session = getattr(tool_context, "session", None)
    session_id = getattr(session, "id", None)
    return str(session_id) if session_id else None


def _make_error(tool_name: str, code: str, message: str) -> dict[str, Any]:
    return ToolResponse(
        status="error",
        tool_name=tool_name,
        error=AnalysisError(
            error_code=code,
            error_message=message,
            tool_name=tool_name,
        ),
    ).model_dump(exclude_none=True)


async def _call_model_with_retry(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    frame: dict[str, Any],
) -> ScreenAnalysis:
    schema = ScreenAnalysis.model_json_schema()

    last_exc: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type=frame["mime_type"],
                                    data=frame["data"],
                                ),
                            ),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=schema,
                    thinking_config=types.ThinkingConfig(
                        thinking_level="MINIMAL"
                    ),
                ),
            )
            return ScreenAnalysis.model_validate_json(response.text)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = (RETRY_BASE_DELAY * (2 ** attempt)) + random.uniform(0, 1)
                logger.warning(
                    "Gemini vision call attempt %d failed (%s), retrying in %.1fs…",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------
async def analyze_screen(
    instruction_or_question: str = "Analyze the current software screen",
    tool_context: ToolContext | None = None
) -> dict[str, Any]:
    """
    Analyzes the customer's shared screen to understand which software
    page they are on, identify UI elements, detect errors or issues, and
    suggest the next step.

    Call this tool when you need a detailed reading of the customer's screen,
    such as reading small text, error messages, or complex settings pages.

    Args:
        instruction_or_question: What specific aspect of the screen you want to analyze.

    Returns:
        dict: ToolResponse with a structured analysis of the current screen.
    """
    tool_name = "analyze_screen"
    session_id = _session_id(tool_context)

    logger.info("analyze_screen called for session=%s with request: %r", session_id, instruction_or_question)

    if not session_id:
        return _make_error(tool_name, "NO_SESSION", "Live session is unavailable.")

    frame_data = get_latest_frame(session_id)
    if not frame_data:
        return _make_error(
            tool_name,
            "NO_FRAME",
            "No screen share available yet. Ask the customer to share their screen.",
        )

    try:
        client = _get_genai_client()
        prompt = f"{ANALYZE_PROMPT}\n\nAgent's specific request: {instruction_or_question}"

        frame = {"mime_type": frame_data.mime_type, "data": frame_data.data}
        analysis = await _call_model_with_retry(
            client,
            model=settings.observe_model,
            prompt=prompt,
            frame=frame,
        )

        logger.info("analyze_screen result: %r", analysis.model_dump())

        return ToolResponse(
            status="success",
            tool_name=tool_name,
            data=analysis.model_dump(),
        ).model_dump(exclude_none=True)

    except Exception as exc:
        logger.error(
            "%s failed with model %s: %s",
            tool_name,
            settings.observe_model,
            exc,
            exc_info=True,
        )
        return _make_error(
            tool_name,
            "ANALYSIS_FAILED",
            "Failed to analyze the screen clearly.",
        )


class CopyItem(BaseModel):
    """A single item for the customer to copy."""
    label: str = Field(description="A short label describing what this is (e.g., 'Order ID', 'Email Address')")
    text: str = Field(description="The exact text value to be copied")

# ---------------------------------------------------------------------------
# send_copy_text — sends a small text snippet to the client to copy
# ---------------------------------------------------------------------------
async def send_copy_text(
    items_to_copy: list[CopyItem],
    explanation: str = "Here is the information you need.",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Sends precise text snippets to the customer's screen so they can copy and
    paste them easily. Use this for URLs, email addresses, order IDs, API keys, 
    names, or specific code snippets. You can send multiple items at once.

    Do NOT use this for step-by-step instructions.

    Args:
        items_to_copy: A list of items for the customer to copy.
        explanation: A brief description of what these items are for.

    Returns:
        dict: ToolResponse containing the items in data.items and data.explanation.
    """
    tool_name = "send_copy_text"
    session_id = _session_id(tool_context)

    logger.info("send_copy_text called for session=%s items=%d", session_id, len(items_to_copy))

    try:
        # Convert items robustly since the model may pass dicts or strings directly
        items_data = []
        for item in items_to_copy:
            if hasattr(item, "model_dump"):
                items_data.append(item.model_dump())
            elif isinstance(item, dict):
                items_data.append(item)
            else:
                items_data.append({"label": "Value", "text": str(item)})

        return ToolResponse(
            status="success",
            tool_name=tool_name,
            data={
                "items": items_data,
                "explanation": explanation
            },
        ).model_dump(exclude_none=True)

    except Exception as exc:
        logger.error(
            "%s failed: %s", tool_name, exc, exc_info=True
        )
        return _make_error(
            tool_name,
            "SEND_TEXT_FAILED",
            "Failed to send the text snippet.",
        )