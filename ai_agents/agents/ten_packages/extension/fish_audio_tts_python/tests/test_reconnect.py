#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Supervisor reconnect ownership tests for the Fish Audio TTS client."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_RESPONSE,
    EVENT_TTS_END,
    FishAudioTTSClient,
)


class ReconnectSocket:
    def __init__(self, drop: bool) -> None:
        self.response = SimpleNamespace(headers={})
        self.drop = drop
        self.sent: list[dict] = []
        self._audio_sent = False
        self._incoming: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, message: bytes) -> None:
        data = ormsgpack.unpackb(message)
        self.sent.append(data)
        if data.get("event") == "text" and not self._audio_sent:
            self._audio_sent = True
            await self._incoming.put(
                ormsgpack.packb({"event": "audio", "audio": b"audio"})
            )
        elif data.get("event") == "stop":
            await self._incoming.put(
                ormsgpack.packb({"event": "finish", "reason": "stop"})
            )

    async def recv(self) -> bytes:
        if self.drop and self._audio_sent and self._incoming.empty():
            raise ConnectionError("simulated socket drop")
        return await self._incoming.get()

    async def close(self) -> None:
        return None


class FakeConnect:
    def __init__(self, socket: ReconnectSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> ReconnectSocket:
        return self.socket

    async def __aexit__(self, *_args) -> None:
        await self.socket.close()


def test_drop_reports_disconnect_and_replacement_serves_next_request() -> None:
    async def run_test() -> None:
        dropped = ReconnectSocket(drop=True)
        replacement = ReconnectSocket(drop=False)
        sockets = iter([dropped, replacement])
        statuses: list[str] = []
        disconnected = asyncio.Event()

        def fake_connect(*_args, **_kwargs):
            return FakeConnect(next(sockets))

        async def connecting() -> None:
            statuses.append("connecting")

        async def connected() -> None:
            statuses.append("connected")

        async def on_disconnected(**_kwargs) -> None:
            statuses.append("disconnected")
            disconnected.set()

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=fake_connect,
        ):
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"),
                MagicMock(),
                on_connection_connecting=connecting,
                on_connection_connected=connected,
                on_connection_disconnected=on_disconnected,
            )

            first = [
                event
                async for event in client.get(
                    "first", request_id="req-1", text_input_end=False
                )
            ]
            await asyncio.wait_for(disconnected.wait(), 2.0)

            second = [
                event
                async for event in client.get(
                    "second", request_id="req-2", text_input_end=True
                )
            ]
            assert statuses == [
                "connecting",
                "connected",
                "disconnected",
                "connecting",
                "connected",
            ]
            await client.clean()

        assert [event for _payload, event in first] in (
            [],
            [EVENT_TTS_RESPONSE],
        )
        assert [event for _payload, event in second] == [
            EVENT_TTS_RESPONSE,
            EVENT_TTS_END,
        ]
        assert [
            message["text"]
            for message in dropped.sent
            if message.get("event") == "text"
        ] == ["first"]
        assert [
            message["text"]
            for message in replacement.sent
            if message.get("event") == "text"
        ] == ["second"]

    asyncio.run(run_test())
