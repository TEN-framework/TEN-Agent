import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_INVALID_KEY_ERROR,
    EVENT_TTS_RESPONSE,
    FishAudioTTSClient,
)


class FakeSession:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.response = SimpleNamespace(headers=DuplicateHeaders())
        self.sent_messages: list[dict] = []
        self.received = False

    async def send(self, message: bytes) -> None:
        self.sent_messages.append(ormsgpack.unpackb(message))

    async def recv(self) -> bytes:
        await asyncio.sleep(0)
        if not self.received:
            self.received = True
            return ormsgpack.packb({"event": "audio", "audio": b"audio"})
        return ormsgpack.packb({"event": "finish", "reason": "stop"})

    async def close(self) -> None:
        self.events.append("close")


class DuplicateHeaders:
    def raw_items(self):
        return [
            ("x-fishaudio-datacenter", "us-east-1"),
            ("x-request-id", "request-123"),
            ("server-timing", "edge;dur=1"),
            ("server-timing", "inference;dur=2"),
        ]


class PersistentFakeSession:
    def __init__(self) -> None:
        self.response = SimpleNamespace(headers={})
        self.sent_messages: list[dict] = []
        self.responses: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, message: bytes) -> None:
        data = ormsgpack.unpackb(message)
        self.sent_messages.append(data)
        if data.get("event") == "text":
            await self.responses.put(
                ormsgpack.packb({"event": "audio", "audio": b"audio"})
            )
        elif data.get("event") == "stop":
            await self.responses.put(
                ormsgpack.packb({"event": "finish", "reason": "stop"})
            )

    async def recv(self) -> bytes:
        return await self.responses.get()

    async def close(self) -> None:
        return None


class FakeConnect:
    def __init__(self, session: FakeSession, events: list[str]) -> None:
        self.session = session
        self.events = events

    async def __aenter__(self) -> FakeSession:
        self.events.append("connect")
        return self.session

    async def __aexit__(self, *_args) -> None:
        await self.session.close()

    async def close(self) -> None:
        return None


def test_traceparent_is_sent_and_response_headers_are_logged():
    async def run_test() -> None:
        events: list[str] = []
        session = FakeSession(events)
        ten_env = MagicMock()

        connector = patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session, events),
        )
        connector.start()
        try:
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"),
                ten_env,
                on_request_start=lambda: events.append("request_start"),
            )

            stream = client.get("hello")
            assert await stream.__anext__() == (
                b"audio",
                EVENT_TTS_RESPONSE,
            )
            assert await stream.__anext__() == (None, EVENT_TTS_END)
        finally:
            connector.stop()

        traceparent = client._traceparent
        version, trace_id, span_id, flags = traceparent.split("-")
        assert version == "00"
        assert len(trace_id) == 32
        assert len(span_id) == 16
        assert flags == "01"

        # The handshake and every outbound event are logged too, so pick the
        # response-header entry instead of relying on call order.
        header_logs = [
            call.args[0]
            for call in ten_env.log_info.call_args_list
            if "WebSocket response headers" in call.args[0]
        ]
        assert len(header_logs) == 1
        log_message = header_logs[0]
        assert "us-east-1" in log_message
        assert trace_id in log_message
        assert "x-request-id" in log_message
        assert events[:2] == ["request_start", "connect"]
        assert session.sent_messages[0]["event"] == "start"
        assert session.sent_messages[1] == {"event": "text", "text": "hello"}
        # The final chunk is followed by stop, which flushes server-side, so
        # no protocol-level flush is emitted for it.
        assert session.sent_messages[2] == {"event": "stop"}

        await client.clean()

    asyncio.run(run_test())


def test_request_start_callback_runs_before_sdk_tts():
    async def run_test() -> None:
        events: list[str] = []
        session = FakeSession(events)
        ten_env = MagicMock()

        connector = patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session, events),
        )
        connector.start()
        try:
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"),
                ten_env,
                on_request_start=lambda: events.append("request_start"),
            )

            stream = client.get("hello")
            await stream.__anext__()
        finally:
            connector.stop()

        assert events[:2] == ["request_start", "connect"]
        await client.clean()

    asyncio.run(run_test())


def test_appended_text_reuses_one_websocket_session():
    async def run_test() -> None:
        session = PersistentFakeSession()
        ten_env = MagicMock()
        connect_calls = 0

        def fake_connect(*_args, **_kwargs):
            nonlocal connect_calls
            connect_calls += 1
            return FakeConnect(session, [])

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=fake_connect,
        ):
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"), ten_env
            )
            first = [
                event
                async for event in client.get(
                    "first ", request_id="request-1", text_input_end=False
                )
            ]
            second = [
                event
                async for event in client.get(
                    "second", request_id="request-1", text_input_end=True
                )
            ]
            await client.clean()

        assert connect_calls == 1
        assert session.sent_messages[0]["event"] == "start"
        assert [message["event"] for message in session.sent_messages] == [
            "start",
            "text",
            "flush",
            "text",
            "stop",
        ]
        assert all(event[1] == EVENT_TTS_RESPONSE for event in first)
        assert (
            sum(event[1] == EVENT_TTS_RESPONSE for event in first + second) == 2
        )
        assert second[-1] == (None, EVENT_TTS_END)

    asyncio.run(run_test())


def test_connection_status_callbacks_cover_socket_lifecycle():
    async def run_test() -> None:
        session = FakeSession([])
        statuses: list[str] = []
        ten_env = MagicMock()

        async def connecting() -> None:
            statuses.append("connecting")

        async def connected() -> None:
            statuses.append("connected")

        async def disconnected(**_kwargs) -> None:
            statuses.append("disconnected")

        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(session, []),
        ):
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"),
                ten_env,
                on_connection_connecting=connecting,
                on_connection_connected=connected,
                on_connection_disconnected=disconnected,
            )
            await client.get("hello").__anext__()
            await client.clean()

        assert statuses == ["connecting", "connected", "disconnected"]

    asyncio.run(run_test())


def test_payment_required_handshake_is_reported_as_invalid_key():
    async def run_test() -> None:
        ten_env = MagicMock()
        connector = patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=RuntimeError("<Response [402 Payment Required]>"),
        )
        connector.start()
        try:
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"), ten_env
            )
            event = await client.get("hello").__anext__()
        finally:
            connector.stop()

        assert event[1] == EVENT_TTS_INVALID_KEY_ERROR
        assert b"Payment Required" in event[0]

    asyncio.run(run_test())


def test_terminal_connect_failure_is_reported_as_disconnected():
    async def run_test() -> None:
        ten_env = MagicMock()
        notifications: list[dict[str, object]] = []

        async def disconnected(**kwargs) -> None:
            notifications.append(kwargs)

        connector = patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            side_effect=RuntimeError("boom"),
        )
        connector.start()
        try:
            client = FishAudioTTSClient(
                FishAudioTTSConfig(api_key="test-key"),
                ten_env,
                on_connection_disconnected=disconnected,
            )
            event = await client.get("hello").__anext__()
        finally:
            connector.stop()

        assert event[1] == EVENT_TTS_ERROR
        # The handshake failure must leave the reported state at
        # ``disconnected`` instead of leaving it at ``connecting``.
        assert notifications == [
            {"code": 0, "message": "connect failed: RuntimeError"}
        ]

    asyncio.run(run_test())
