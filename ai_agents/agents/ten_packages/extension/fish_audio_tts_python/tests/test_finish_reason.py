#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Tests for the vendor ``finish`` reason reported by Fish Audio."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    FishAudioTTSClient,
)


class FinishSession:
    """Fake socket that finishes with a configurable reason after ``stop``."""

    def __init__(self, reason: str) -> None:
        self.response = SimpleNamespace(headers={})
        self.reason = reason
        self.sent: list[dict] = []
        self._incoming: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, message: bytes) -> None:
        payload = ormsgpack.unpackb(message)
        self.sent.append(payload)
        if payload.get("event") == "stop":
            await self._incoming.put(
                ormsgpack.packb({"event": "finish", "reason": self.reason})
            )

    async def recv(self) -> bytes:
        return await self._incoming.get()

    async def close(self) -> None:
        return None


class FakeConnect:
    def __init__(self, session: FinishSession) -> None:
        self.session = session

    async def __aenter__(self) -> FinishSession:
        return self.session

    async def __aexit__(self, *_args) -> None:
        await self.session.close()


def _config() -> FishAudioTTSConfig:
    return FishAudioTTSConfig(api_key="test-key")


def _run(reason: str) -> list[tuple[bytes | None, int]]:
    async def run() -> list[tuple[bytes | None, int]]:
        session = FinishSession(reason)
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session),
        ):
            client = FishAudioTTSClient(_config(), MagicMock())
            events = [
                event
                async for event in client.get(
                    "hello", request_id="request-1", text_input_end=True
                )
            ]
            await client.clean()
        return events

    return asyncio.run(run())


def test_finish_with_error_reason_is_reported_as_error() -> None:
    events = _run("error")

    assert len(events) == 1
    payload, event = events[0]
    assert event == EVENT_TTS_ERROR
    assert payload is not None
    assert b"error" in payload.lower()


def test_finish_with_stop_reason_is_reported_as_end() -> None:
    events = _run("stop")

    assert events == [(None, EVENT_TTS_END)]
