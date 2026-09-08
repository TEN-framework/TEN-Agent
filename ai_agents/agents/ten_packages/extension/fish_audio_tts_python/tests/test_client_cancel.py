#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from unittest.mock import MagicMock, patch

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_FLUSH,
    EVENT_TTS_RESPONSE,
    FishAudioTTSClient,
)


class BlockingSession:
    def __init__(self) -> None:
        self.closed = asyncio.Event()
        self.close_calls = 0

    async def tts(self, **_kwargs):
        yield b"first-audio"
        await self.closed.wait()
        raise ConnectionError("session closed")

    async def close(self) -> None:
        self.close_calls += 1
        self.closed.set()


class SuccessfulSession:
    def __init__(self) -> None:
        self.close_calls = 0

    async def tts(self, **_kwargs):
        yield b"second-audio"

    async def close(self) -> None:
        self.close_calls += 1


class FailingCloseSession:
    async def close(self) -> None:
        raise ConnectionError("connection already closed")


@patch("fish_audio_tts_python.fish_audio_tts.AsyncWebSocketSession")
def test_cancel_closes_session_and_next_request_recovers(mock_session):
    async def run_test() -> None:
        blocked_session = BlockingSession()
        successful_session = SuccessfulSession()
        mock_session.side_effect = [blocked_session, successful_session]

        config = FishAudioTTSConfig(api_key="test-key")
        ten_env = MagicMock()
        client = FishAudioTTSClient(config, ten_env)

        first_stream = client.get("first request")
        assert await asyncio.wait_for(first_stream.__anext__(), 0.5) == (
            b"first-audio",
            EVENT_TTS_RESPONSE,
        )

        await asyncio.wait_for(client.cancel(), 0.5)
        assert blocked_session.close_calls == 1
        assert await asyncio.wait_for(first_stream.__anext__(), 0.5) == (
            None,
            EVENT_TTS_FLUSH,
        )

        second_stream = client.get("second request")
        assert await asyncio.wait_for(second_stream.__anext__(), 0.5) == (
            b"second-audio",
            EVENT_TTS_RESPONSE,
        )
        assert await asyncio.wait_for(second_stream.__anext__(), 0.5) == (
            None,
            EVENT_TTS_END,
        )
        assert mock_session.call_count == 2

        await client.clean()
        assert successful_session.close_calls == 1

    asyncio.run(run_test())


@patch("fish_audio_tts_python.fish_audio_tts.AsyncWebSocketSession")
def test_clean_ignores_vendor_close_failure(mock_session):
    async def run_test() -> None:
        mock_session.return_value = FailingCloseSession()
        ten_env = MagicMock()
        client = FishAudioTTSClient(
            FishAudioTTSConfig(api_key="test-key"), ten_env
        )

        await client.clean()

        assert client.client is None
        ten_env.log_warn.assert_called_once()

    asyncio.run(run_test())
