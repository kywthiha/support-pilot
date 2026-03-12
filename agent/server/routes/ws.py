"""WebSocket endpoint for bidirectional live streaming with ADK."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types
from google.genai.errors import APIError

from config import (
    MSG_TYPE_AUDIO,
    MSG_TYPE_VIDEO,
    TERMINAL_ERROR_CODES,
    WS_CLOSE_GOING_AWAY,
    WS_CLOSE_INTERNAL_ERROR,
    WS_CLOSE_TRY_AGAIN_LATER,
    settings,
)
from agent import agent as agent_instance
from dependencies import create_run_config, manager, memory_service, runner, session_service
from live_state import update_latest_frame

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────
def _is_connected(websocket: WebSocket) -> bool:
    """Check if the WebSocket is still open."""
    return websocket.client_state == WebSocketState.CONNECTED


async def _send_text(websocket: WebSocket, data: str) -> None:
    """Send text only if the WebSocket is still open."""
    if _is_connected(websocket):
        await websocket.send_text(data)


async def _send_bytes(websocket: WebSocket, data: bytes) -> None:
    """Send bytes only if the WebSocket is still open."""
    if _is_connected(websocket):
        await websocket.send_bytes(data)


async def _send_json(websocket: WebSocket, payload: dict[str, object]) -> None:
    """Send JSON only if the WebSocket is still open."""
    if _is_connected(websocket):
        await websocket.send_text(json.dumps(payload))


def _parse_binary_message(data: bytes) -> tuple[int, bytes]:
    """Parse a binary message with a 1-byte type header and payload."""
    if not data:
        raise ValueError("Empty binary message received")
    return data[0], data[1:]


async def _handle_json_message(
    websocket: WebSocket,
    session_id: str,
    live_request_queue: LiveRequestQueue,
    payload: dict[str, object],
) -> None:
    """Dispatch a parsed JSON message from the client."""
    message_type = payload.get("type")

    if message_type == "ping":
        return

    if message_type == "text":
        text = str(payload.get("text") or "").strip()
        if text:
            live_request_queue.send_content(
                types.Content(parts=[types.Part(text=text)])
            )
        return

    await _send_json(
        websocket,
        {"type": "error", "message": f"Unsupported message type: {message_type}"},
    )


# ── WebSocket endpoint ──────────────────────────────────────────────
@router.websocket("/ws/{user_id}/{session_id}")
async def live_websocket(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
) -> None:
    await websocket.accept()

    # ── Enforce connection limit ──────────────────────────────────
    if not await manager.accept(websocket, session_id):
        logger.warning(
            "Connection limit reached (%d), rejecting session %s",
            settings.max_ws_connections,
            session_id,
        )
        await _send_json(
            websocket,
            {"type": "error", "message": "Server at capacity. Please retry later."},
        )
        await websocket.close(WS_CLOSE_TRY_AGAIN_LATER, "Server at capacity")
        return

    # ── Ensure ADK session exists ─────────────────────────────────
    session = await session_service.get_session(
        app_name=settings.app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=settings.app_name, user_id=user_id, session_id=session_id
        )

    live_request_queue = LiveRequestQueue()

    # ── Heartbeat (application-level keepalive) ────────────────────
    # Note: Starlette's WebSocket doesn't expose protocol-level .ping().
    # Use Uvicorn's --ws-ping-interval / --ws-ping-timeout for transport
    # keepalive, and this task for application-level liveness checks.
    async def heartbeat_task() -> None:
        """Send periodic JSON pings to detect dead connections."""
        try:
            while True:
                await asyncio.sleep(settings.ws_ping_interval)
                await _send_json(websocket, {"type": "ping"})
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass  # connection already gone or task cancelled

    # ── Upstream: client → server ─────────────────────────────────
    async def upstream_task() -> None:
        try:
            while True:
                message = await websocket.receive()

                # Binary frames (audio / video)
                if "bytes" in message and message["bytes"] is not None:
                    try:
                        msg_type, payload = _parse_binary_message(message["bytes"])
                        if msg_type == MSG_TYPE_AUDIO:
                            live_request_queue.send_realtime(
                                types.Blob(
                                    mime_type="audio/pcm;rate=16000",
                                    data=payload,
                                )
                            )
                        elif msg_type == MSG_TYPE_VIDEO:
                            update_latest_frame(session_id, payload, "image/jpeg")
                            live_request_queue.send_realtime(
                                types.Blob(mime_type="image/jpeg", data=payload)
                            )
                        else:
                            logger.warning("Unknown binary message type: %s", msg_type)
                    except ValueError as e:
                        logger.error("Failed to parse binary message: %s", e)
                    continue

                # Text frames (JSON)
                if "text" not in message or not message["text"]:
                    continue

                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _send_json(
                        websocket,
                        {"type": "error", "message": "Invalid JSON message."},
                    )
                    continue

                if not isinstance(payload, dict):
                    await _send_json(
                        websocket,
                        {"type": "error", "message": "Expected a JSON object message."},
                    )
                    continue

                await _handle_json_message(
                    websocket, session_id, live_request_queue, payload
                )
        except (WebSocketDisconnect, RuntimeError):
            logger.info("Client disconnected from session %s", session_id)
        except asyncio.CancelledError:
            pass  # TaskGroup cancellation
        except Exception as exc:
            logger.error(
                "Upstream error for session %s: %s", session_id, exc, exc_info=True
            )
        finally:
            live_request_queue.close()

    # ── Downstream helpers ────────────────────────────────────────
    async def _log_and_send_error(label: str, exc: Exception) -> None:
        logger.error(
            "%s for session %s: %s", label, session_id, exc, exc_info=True
        )
        try:
            await _send_json(websocket, {"type": "error", "message": str(exc)})
        except (RuntimeError, WebSocketDisconnect):
            pass

    async def _handle_live_event(event) -> bool:
        """Process a single live event. Returns False to stop the loop."""
        # Error events
        if event.error_code:
            await _send_json(
                websocket,
                {
                    "type": "error",
                    "code": event.error_code,
                    "message": event.error_message or event.error_code,
                },
            )
            if event.error_code in TERMINAL_ERROR_CODES:
                try:
                    await websocket.close(WS_CLOSE_INTERNAL_ERROR, "Terminal API error")
                except Exception:
                    pass
                return False
            return True

        parts = event.content.parts if event.content else []

        # No parts – forward the raw event as-is
        if not parts:
            await _send_text(
                websocket,
                event.model_dump_json(exclude_none=True, by_alias=True),
            )
            return True

        # Separate audio parts in a single pass
        audio_parts = [
            p.inline_data.data
            for p in parts
            if p.inline_data and p.inline_data.mime_type.startswith("audio/pcm")
        ]

        if audio_parts:
            # Stream each audio chunk as a binary frame
            for chunk in audio_parts:
                await _send_bytes(websocket, chunk)
            # Follow up with metadata (inline_data stripped to save bandwidth)
            await _send_text(
                websocket,
                event.model_dump_json(
                    exclude={"content": {"parts": {"__all__": {"inline_data"}}}},
                    by_alias=True,
                    exclude_none=True,
                ),
            )
            return True

        # Non-audio: check for function (tool) responses
        fn_responses = [
            {"name": p.function_response.name, "response": p.function_response.response}
            for p in parts
            if p.function_response
        ]
        if fn_responses:
            logger.debug("Tool responses: %s", fn_responses)
            await _send_json(
                websocket,
                {"type": "tool_response", "responses": fn_responses},
            )
            return True

        # Fallback: forward the full event
        await _send_text(
            websocket,
            event.model_dump_json(exclude_none=True, by_alias=True),
        )
        return True

    # ── Downstream: server → client ───────────────────────────────
    async def downstream_task() -> None:
        try:
            await _send_json(
                websocket,
                {"type": "ready", "sessionId": session_id, "agentName": agent_instance.name},
            )
            live_request_queue.send_content(
                types.Content(
                    parts=[
                        types.Part(
                            text="User has connected. Please introduce yourself briefly."
                        )
                    ]
                )
            )
        except (RuntimeError, WebSocketDisconnect):
            return

        reconnect_count = 0
        max_reconnects = 30
        while reconnect_count < max_reconnects:
            should_reconnect = False
            should_break = False
            try:
                if reconnect_count > 0:
                    context_msg = "We just had a brief connection drop. Please acknowledge this quickly and naturally continue assisting from where we left off."
                    live_request_queue.send_content(
                        types.Content(parts=[types.Part(text=context_msg)])
                    )

                async for event in runner.run_live(
                    user_id=user_id,
                    session_id=session_id,
                    live_request_queue=live_request_queue,
                    run_config=create_run_config(),
                ):
                    if not await _handle_live_event(event):
                        should_break = True
                        break
                if not should_break:
                    should_break = True
            except* APIError as eg:
                for exc in eg.exceptions:
                    err_str = str(exc).lower()
                    if getattr(exc, "status", None) == 1000 or "1000" in err_str:
                        logger.debug("Gemini Live API closed cleanly for session %s (1000). Reconnecting...", session_id)
                        should_reconnect = True
                    elif "1008" in err_str:
                        logger.warning("Ignored APIError 1008 for session %s. Reconnecting...", session_id)
                        should_reconnect = True
                    elif "1011" in err_str or "capacity" in err_str:
                        logger.warning("Ignored APIError 1011/capacity for session %s. Reconnecting...", session_id)
                        should_reconnect = True
                    elif "cancelled" in err_str:
                        should_reconnect = True
                    else:
                        await _log_and_send_error("Live API error", exc)
                        should_break = True

            except* Exception as eg:
                valid_exceptions = ["1008", "1000", "1011", "cancelled"]
                for exc in eg.exceptions:
                    err_str = str(exc).lower()
                    if any(val in err_str for val in valid_exceptions):
                        logger.warning("Caught recoverable Exception '%s' for session %s. Reconnecting...", err_str, session_id)
                        should_reconnect = True
                    else:
                        await _log_and_send_error("Downstream error", exc)
                        should_break = True

            if should_break and not should_reconnect:
                break
            
            if should_reconnect:
                reconnect_count += 1
                await asyncio.sleep(1)
            else:
                break

    # ── Run all tasks with proper cancellation ────────────────────
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(heartbeat_task())
            tg.create_task(upstream_task())
            tg.create_task(downstream_task())
    except* (WebSocketDisconnect, RuntimeError):
        logger.debug("Client disconnected normally from session %s", session_id)
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.error(
                "Unexpected error in session %s: %s", session_id, exc, exc_info=True
            )
    finally:
        live_request_queue.close()
        # Save session to memory for future recall
        try:
            session = await session_service.get_session(
                app_name=settings.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session:
                await memory_service.add_session_to_memory(session)
                logger.info("Session %s saved to memory", session_id)
        except Exception as mem_exc:
            logger.warning("Failed to save session %s to memory: %s", session_id, mem_exc)
        await manager.remove(session_id)
        logger.info(
            "Session %s cleaned up (active: %d)", session_id, manager.active_count
        )
