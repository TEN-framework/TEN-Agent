import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

from soniox_tts.config import SonioxTTSConfig
from soniox_tts.soniox_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    SonioxTTSClient,
    SonioxTTSError,
)


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = asyncio.Queue()
        for message in messages:
            self.messages.put_nowait(message)
        self.sent = []
        self.closed = False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return await self.messages.get()

    async def close(self):
        self.closed = True


def test_client_sends_soniox_protocol_and_decodes_audio():
    async def run():
        audio = b"\x00\x01" * 40
        stream_id = "stream-1"
        messages = [
            json.dumps(
                {
                    "stream_id": stream_id,
                    "audio": base64.b64encode(audio).decode(),
                    "audio_end": True,
                }
            ),
            json.dumps({"stream_id": stream_id, "terminated": True}),
        ]
        websocket = FakeWebSocket(messages)
        with patch(
            "soniox_tts.soniox_tts.websockets.connect",
            new=AsyncMock(return_value=websocket),
        ) as connect:
            client = SonioxTTSClient(
                SonioxTTSConfig(api_key="secret"), MagicMock()
            )
            await client.start()
            await client.start_stream(stream_id)
            await client.send_text("Hello", False)
            await client.send_text("", True)
            events = [event async for event in client.iter_events(stream_id)]
            await client.stop()

        assert connect.await_args.kwargs["additional_headers"] == {
            "Authorization": "Bearer secret"
        }
        assert websocket.sent[0]["stream_id"] == stream_id
        assert websocket.sent[0]["audio_format"] == "pcm_s16le"
        assert websocket.sent[1] == {
            "text": "Hello",
            "text_end": False,
            "stream_id": stream_id,
        }
        assert websocket.sent[2] == {
            "text": "",
            "text_end": True,
            "stream_id": stream_id,
        }
        assert events[0][1] == EVENT_TTS_TTFB_METRIC
        assert events[1] == (audio, EVENT_TTS_RESPONSE)
        assert events[2] == (None, EVENT_TTS_END)

    asyncio.run(run())


def test_client_reports_vendor_error():
    async def run():
        stream_id = "stream-error"
        websocket = FakeWebSocket(
            [
                json.dumps(
                    {
                        "stream_id": stream_id,
                        "error_code": 401,
                        "error_type": "unauthenticated",
                        "error_message": "invalid key",
                    }
                ),
                json.dumps({"stream_id": stream_id, "terminated": True}),
            ]
        )
        with patch(
            "soniox_tts.soniox_tts.websockets.connect",
            new=AsyncMock(return_value=websocket),
        ):
            client = SonioxTTSClient(
                SonioxTTSConfig(api_key="secret"), MagicMock()
            )
            await client.start()
            await client.start_stream(stream_id)
            events = [event async for event in client.iter_events(stream_id)]
            await client.stop()

        assert events[0][1] == EVENT_TTS_ERROR
        assert isinstance(events[0][0], SonioxTTSError)
        assert events[0][0].error_code == 401
        assert events[-1] == (None, EVENT_TTS_END)

    asyncio.run(run())


def test_client_sends_keepalive_between_streams(monkeypatch):
    async def run():
        websocket = FakeWebSocket([])
        with patch(
            "soniox_tts.soniox_tts.websockets.connect",
            new=AsyncMock(return_value=websocket),
        ):
            monkeypatch.setattr(
                "soniox_tts.soniox_tts.KEEPALIVE_INTERVAL", 0.001
            )
            client = SonioxTTSClient(
                SonioxTTSConfig(api_key="secret"), MagicMock()
            )
            await client.start()
            await asyncio.sleep(0.003)
            await client.stop()

        assert {"keep_alive": True} in websocket.sent

    asyncio.run(run())
