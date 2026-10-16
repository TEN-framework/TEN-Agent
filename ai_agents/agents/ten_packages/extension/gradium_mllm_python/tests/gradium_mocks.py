"""Shared helpers for mocking the streaming GradiumS2SClient in tests."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def make_streaming_mock_client(
    *,
    messages: list[dict[str, Any]] | None = None,
    connect_error: Exception | None = None,
    sent_audio: list[bytes] | None = None,
) -> MagicMock:
    """Build a mock GradiumS2SClient mimicking the real websocket client's API.

    - ``connect()`` raises ``connect_error`` if given, else succeeds
      immediately (mirrors the real client's connect() only returning after
      Gradium's "ready" has already been received and validated).
    - ``messages()`` yields the canned ``messages`` list in order, then
      blocks until ``close()`` is called -- keeps the extension's receive
      loop "connected" for the rest of the test, but still lets
      start_connection()'s `async for` loop return (and the test process
      shut down cleanly) once the extension tears the connection down.
      This mirrors the real websockets-backed client, where closing the
      underlying websocket is what makes `async for raw in self.ws:` end.
    - ``send_audio()`` records bytes into ``sent_audio`` if provided.
    - ``send_end_of_stream()`` is a no-op AsyncMock.
    """
    mock = MagicMock()

    if connect_error is not None:
        mock.connect = AsyncMock(side_effect=connect_error)
    else:
        mock.connect = AsyncMock()

    closed_event = asyncio.Event()

    async def _close() -> None:
        closed_event.set()

    mock.close = AsyncMock(side_effect=_close)
    mock.send_end_of_stream = AsyncMock()

    async def _send_audio(pcm_bytes: bytes) -> None:
        if sent_audio is not None:
            sent_audio.append(pcm_bytes)

    mock.send_audio = AsyncMock(side_effect=_send_audio)

    async def _messages():
        for m in messages or []:
            yield m
        await closed_event.wait()

    mock.messages.side_effect = _messages
    return mock
