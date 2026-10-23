import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_FLUSH,
    EVENT_TTS_RESPONSE,
    FishAudioTTSClient,
)


class BlockingWebSocket:
    def __init__(self) -> None:
        self.response = SimpleNamespace(headers={})
        self.closed = asyncio.Event()
        self.close_calls = 0
        self.audio_sent = False

    async def send(self, _message: bytes) -> None:
        return None

    async def recv(self) -> bytes:
        await asyncio.sleep(0)
        if not self.audio_sent:
            self.audio_sent = True
            return ormsgpack.packb({"event": "audio", "audio": b"audio"})
        await self.closed.wait()
        raise ConnectionError("socket closed")

    async def close(self) -> None:
        self.close_calls += 1
        self.closed.set()


class SuccessfulWebSocket:
    def __init__(self) -> None:
        self.response = SimpleNamespace(headers={})
        self.close_calls = 0
        self.messages = [
            {"event": "audio", "audio": b"audio"},
            {"event": "finish", "reason": "stop"},
        ]
        self._closed = asyncio.Event()

    async def send(self, _message: bytes) -> None:
        return None

    async def recv(self) -> bytes:
        await asyncio.sleep(0)
        if self.messages:
            return ormsgpack.packb(self.messages.pop(0))
        await self._closed.wait()
        raise ConnectionError("socket closed")

    async def close(self) -> None:
        self.close_calls += 1
        self._closed.set()


class FakeConnect:
    def __init__(self, websocket) -> None:
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, *_args) -> None:
        await self.websocket.close()


class BlockingConnect:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.exited = asyncio.Event()

    async def __aenter__(self):
        self.started.set()
        await asyncio.Future()

    async def __aexit__(self, *_args) -> None:
        self.exited.set()


def test_cancel_closes_socket_and_new_client_recovers():
    async def run_test() -> None:
        blocked_socket = BlockingWebSocket()
        successful_socket = SuccessfulWebSocket()
        sockets = iter([blocked_socket, successful_socket])

        def fake_connect(*_args, **_kwargs):
            return FakeConnect(next(sockets))

        config = FishAudioTTSConfig(api_key="test-key")
        ten_env = MagicMock()

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=fake_connect,
        ):
            first_client = FishAudioTTSClient(config, ten_env)
            first_stream = first_client.get("first request")
            assert await asyncio.wait_for(first_stream.__anext__(), 0.5) == (
                b"audio",
                EVENT_TTS_RESPONSE,
            )

            await asyncio.wait_for(first_client.cancel(), 0.5)
            assert blocked_socket.close_calls >= 1
            assert await asyncio.wait_for(first_stream.__anext__(), 0.5) == (
                None,
                EVENT_TTS_FLUSH,
            )
            await first_stream.aclose()

            # Flush discards the old client. The extension creates a new one
            # so the next request has a clean connection.
            second_client = FishAudioTTSClient(config, ten_env)
            second_stream = second_client.get("second request")
            assert await asyncio.wait_for(second_stream.__anext__(), 0.5) == (
                b"audio",
                EVENT_TTS_RESPONSE,
            )
            assert await asyncio.wait_for(second_stream.__anext__(), 0.5) == (
                None,
                EVENT_TTS_END,
            )

            await second_client.clean()

    asyncio.run(run_test())


def test_cancel_interrupts_websocket_handshake():
    async def run_test() -> None:
        connect_context = BlockingConnect()
        ten_env = MagicMock()

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=connect_context,
        ):
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"), ten_env
            )
            stream = client.get("hello")
            receive_task = asyncio.create_task(stream.__anext__())
            await asyncio.wait_for(connect_context.started.wait(), 0.5)

            await asyncio.wait_for(client.cancel(), 0.5)
            assert await asyncio.wait_for(receive_task, 0.5) == (
                None,
                EVENT_TTS_FLUSH,
            )
            await stream.aclose()
            assert not connect_context.exited.is_set()

    asyncio.run(run_test())


def test_cancel_during_retry_backoff_stops_connection_attempts():
    async def run_test() -> None:
        connect_calls = 0
        first_failure = asyncio.Event()
        ten_env = MagicMock()

        def failing_connect(*_args, **_kwargs):
            nonlocal connect_calls
            connect_calls += 1
            first_failure.set()
            raise RuntimeError("boom")

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=failing_connect,
        ):
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"), ten_env
            )
            stream = client.get("hello")
            receive_task = asyncio.create_task(stream.__anext__())
            await asyncio.wait_for(first_failure.wait(), 0.5)

            await asyncio.wait_for(client.cancel(), 0.5)
            assert await asyncio.wait_for(receive_task, 0.5) == (
                None,
                EVENT_TTS_FLUSH,
            )
            await stream.aclose()

        # Cancelling during the backoff must stop the whole connection
        # operation. No second handshake and no text may follow.
        await asyncio.sleep(0.4)
        assert connect_calls == 1

    asyncio.run(run_test())
