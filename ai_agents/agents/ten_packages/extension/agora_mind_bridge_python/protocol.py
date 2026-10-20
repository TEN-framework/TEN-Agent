"""Pure protocol helpers for the Agora Mind TEN bridge."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any


def utc_timestamp(value: Any = None) -> str:
    """Return an ISO-8601 UTC timestamp suitable for pure-text input."""

    if isinstance(value, str) and value.strip():
        return value
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def pure_text_input(text: str, created_at: Any = None) -> dict[str, str]:
    """Build the input object expected by Agora Mind's pure-text format."""

    return {"created_at": utc_timestamp(created_at), "text": text}


def asr_final_key(
    payload: dict[str, Any], text: str
) -> tuple[int, int, str] | None:
    """Identify a final within the graph's single ASR audio timeline."""

    start_ms = payload.get("start_ms")
    duration_ms = payload.get("duration_ms")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (start_ms, duration_ms)
    ):
        return None
    if start_ms < 0 or duration_ms <= 0:
        return None
    return start_ms, duration_ms, text


def session_id_from_response(response_json: str) -> int | None:
    """Extract a session ID from a successful ``session.created`` response."""

    try:
        response = json.loads(response_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(response, dict):
        return None
    session_id = response.get("session_id")
    if isinstance(session_id, bool):
        return None
    if isinstance(session_id, int) and session_id > 0:
        return session_id
    return None


def turn_text_from_event(
    event_json: str, expected_session_id: int | None = None
) -> tuple[int, str] | None:
    """Extract final top-level text from a Workspace event envelope.

    Agora Mind publishes model output as a list of typed result items. Only
    top-level ``session_turn_completed`` events are user-visible responses;
    monitoring events must not be sent to the TTS path.
    """

    try:
        envelope = json.loads(event_json)
    except (TypeError, ValueError):
        return None
    if (
        not isinstance(envelope, dict)
        or envelope.get("type") != "workspace.event"
    ):
        return None

    event = envelope.get("event")
    if not isinstance(event, dict):
        return None
    if event.get("type") != "session_turn_completed":
        return None

    session_id = event.get("session_id")
    if isinstance(session_id, bool) or not isinstance(session_id, int):
        return None
    if expected_session_id is not None and session_id != expected_session_id:
        return None

    source = event.get("source")
    if isinstance(source, dict) and source.get("type") != "top_level":
        return None

    result = event.get("result")
    if not isinstance(result, list):
        return None
    text = "".join(
        item.get("text", "")
        for item in result
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    )
    if not text.strip():
        return None
    return session_id, text


def turn_key(event_json: str) -> tuple[Any, ...] | None:
    """Return a stable key for suppressing duplicate turn-completed events."""

    try:
        envelope = json.loads(event_json)
    except (TypeError, ValueError):
        return None
    event = envelope.get("event") if isinstance(envelope, dict) else None
    if not isinstance(event, dict):
        return None
    if event.get("type") != "session_turn_completed":
        return None
    session_id = event.get("session_id")
    sequence_range = event.get("input_sequence_range")
    if isinstance(sequence_range, dict):
        return (
            session_id,
            sequence_range.get("first"),
            sequence_range.get("last"),
        )
    result = event.get("result")
    return (session_id, json.dumps(result, sort_keys=True))
