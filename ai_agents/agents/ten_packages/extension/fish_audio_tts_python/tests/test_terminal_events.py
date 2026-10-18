#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Terminal-event ownership tests for the Fish Audio TTS client."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack
import pytest

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    FishAudioTTSClient,
)

_POLL_INTERVAL = 0.001


class ScriptedSession:
    """Fake socket that records sends and can drop the receive loop."""

    def __init__(self, drop_after_text: bool = False) -> None:
        self.response = SimpleNamespace(headers={})
        self.sent: list[dict] = []
        self._incoming: asyncio.Queue[bytes] = asyncio.Queue()
        self._drop_after_text = drop_after_text
        self._dropped = False

    async def send(self, message: bytes) -> None:
        payload = ormsgpack.unpackb(message)
        self.sent.append(payload)
        if payload.get("event") == "stop":
            await self._incoming.put(
                ormsgpack.packb({"event": "finish", "reason": "stop"})
            )

    async def recv(self) -> bytes:
        if self._drop_after_text and not self._dropped:
            while not any(
                message.get("event") == "text" for message in self.sent
            ):
                await asyncio.sleep(_POLL_INTERVAL)
            self._dropped = True
            raise ConnectionError("simulated drop")
        return await self._incoming.get()

    async def close(self) -> None:
        return None


class FakeConnect:
    def __init__(self, session: ScriptedSession) -> None:
        self.session = session

    async def __aenter__(self) -> ScriptedSession:
        return self.session

    async def __aexit__(self, *_args) -> None:
        await self.session.close()


class VendorTerminalSession:
    """Fake socket that returns one vendor terminal event after text."""

    def __init__(self, message: dict) -> None:
        self.response = SimpleNamespace(headers={})
        self.message = message
        self.sent: list[dict] = []
        self._sent_terminal = False

    async def send(self, message: bytes) -> None:
        self.sent.append(ormsgpack.unpackb(message))

    async def recv(self) -> bytes:
        while not any(message.get("event") == "text" for message in self.sent):
            await asyncio.sleep(_POLL_INTERVAL)
        if not self._sent_terminal:
            self._sent_terminal = True
            return ormsgpack.packb(self.message)
        await asyncio.Future()

    async def close(self) -> None:
        return None


def _config() -> FishAudioTTSConfig:
    return FishAudioTTSConfig(api_key="test-key")


def test_final_chunk_after_interruption_does_not_start_a_session() -> None:
    async def run() -> tuple[list[tuple[bytes | None, int]], list[dict]]:
        session = ScriptedSession(drop_after_text=True)
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session),
        ):
            client = FishAudioTTSClient(_config(), MagicMock())
            async for _event in client.get(
                "first chunk", request_id="req-1", text_input_end=False
            ):
                pass
            for _ in range(50):
                if client.interruption("req-1") is not None:
                    break
                await asyncio.sleep(0.01)
            assert client.interruption("req-1") is not None
            events = [
                event
                async for event in client.get(
                    "", request_id="req-1", text_input_end=True
                )
            ]
            sent = list(session.sent)
            await client.clean()
        return events, sent

    events, sent = asyncio.run(run())

    assert [event for _payload, event in events] == [EVENT_TTS_ERROR]
    assert [message.get("event") for message in sent].count("start") == 1


def test_stale_terminal_event_is_not_delivered_to_another_request() -> None:
    async def run() -> list[tuple[bytes | None, int]]:
        session = ScriptedSession()
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session),
        ):
            client = FishAudioTTSClient(_config(), MagicMock())
            client._enqueue(None, EVENT_TTS_END, "req-old")
            events = [
                event
                async for event in client.get(
                    "hello", request_id="req-new", text_input_end=True
                )
            ]
            await client.clean()
        return events

    events = asyncio.run(run())

    assert [event for _payload, event in events] == [EVENT_TTS_END]


def test_connect_failure_is_latched_for_later_chunks() -> None:
    async def run() -> tuple[
        list[tuple[bytes | None, int]],
        list[tuple[bytes | None, int]],
        int,
        int,
    ]:
        connect_calls = 0

        def failing_connect(*_args, **_kwargs):
            nonlocal connect_calls
            connect_calls += 1
            raise TimeoutError("timed out during opening handshake")

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=failing_connect,
        ):
            client = FishAudioTTSClient(_config(), MagicMock())
            first = [
                event
                async for event in client.get(
                    "first chunk",
                    request_id="req-1",
                    text_input_end=False,
                )
            ]
            assert client.interruption("req-1") is not None
            calls_after_first = connect_calls
            second = [
                event
                async for event in client.get(
                    "",
                    request_id="req-1",
                    text_input_end=True,
                )
            ]
            calls_after_second = connect_calls
            await client.clean()
        return first, second, calls_after_first, calls_after_second

    first, second, calls_after_first, calls_after_second = asyncio.run(run())

    assert [event for _payload, event in first] == [EVENT_TTS_ERROR]
    assert [event for _payload, event in second] == [EVENT_TTS_ERROR]
    # The final empty chunk must reuse the latched failure instead of opening
    # another connection or completing as REQUEST_END.
    assert calls_after_second == calls_after_first


@pytest.mark.parametrize(
    "terminal_message",
    [
        {"event": "error", "error": "vendor failure"},
        {"event": "finish", "reason": "error"},
    ],
)
def test_vendor_terminal_is_delivered_without_explicit_request_id(
    terminal_message: dict,
) -> None:
    async def run() -> tuple[bytes | None, int]:
        session = VendorTerminalSession(terminal_message)
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session),
        ):
            client = FishAudioTTSClient(_config(), MagicMock())
            stream = client.get("hello")
            event = await asyncio.wait_for(stream.__anext__(), 1.0)
            await client.clean()
        return event

    payload, event = asyncio.run(run())

    assert event == EVENT_TTS_ERROR
    assert payload is not None
