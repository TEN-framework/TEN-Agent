import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from client import (
    SpekoRouterError,
    SpekoTTSClient,
    SpekoTTSEventType,
)


class FakeWebSocket:
    def __init__(self, *messages):
        self.messages = asyncio.Queue()
        for message in messages:
            self.messages.put_nowait(message)
        self.sent = []
        self.closed = False

    async def send(self, value):
        self.sent.append(value)

    async def recv(self):
        return await self.messages.get()

    async def close(self):
        self.closed = True


def make_client():
    return SpekoTTSClient(
        api_key="test-key",
        base_url="https://router.speko.dev",
        configure={
            "type": "session.configure",
            "audio": {
                "encoding": "pcm_s16le",
                "sample_rate_hz": 24000,
                "channels": 1,
            },
        },
        ready_timeout_sec=1,
        receive_timeout_sec=1,
    )


@pytest.mark.asyncio
async def test_append_commit_audio_and_usage():
    websocket = FakeWebSocket(
        json.dumps(
            {
                "type": "session.ready",
                "request_id": "req_1",
                "route": {
                    "provider": "cartesia",
                    "model": "sonic-3",
                    "region": "us",
                    "attempt_id": "att_1",
                },
            }
        ),
        json.dumps({"type": "utterance.started", "sequence": 1}),
        b"pcm-audio",
        json.dumps({"type": "usage.updated", "usage": {"characters": 5}}),
        json.dumps({"type": "utterance.done", "sequence": 1}),
        json.dumps({"type": "session.closed", "usage": {"characters": 5}}),
    )
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
        events = [event async for event in client.stream_text("hello")]

    assert [event.type for event in events] == [
        SpekoTTSEventType.TTFB,
        SpekoTTSEventType.AUDIO,
        SpekoTTSEventType.USAGE,
        SpekoTTSEventType.DONE,
    ]
    assert events[1].value == b"pcm-audio"
    assert client.usage == {"characters": 5}
    assert json.loads(websocket.sent[1]) == {
        "type": "input.append",
        "text": "hello",
    }
    assert json.loads(websocket.sent[2]) == {"type": "input.commit"}
    await client.close()


@pytest.mark.asyncio
async def test_cancel_sends_protocol_cancel_before_close():
    websocket = FakeWebSocket(
        json.dumps(
            {
                "type": "session.ready",
                "request_id": "req_1",
                "route": {
                    "provider": "x",
                    "model": "y",
                    "region": "us",
                    "attempt_id": "att_1",
                },
            }
        )
    )
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
        await client.cancel()

    sent_types = [json.loads(value)["type"] for value in websocket.sent]
    assert sent_types == [
        "session.configure",
        "input.cancel",
        "session.close",
    ]
    assert websocket.closed is True


@pytest.mark.asyncio
async def test_router_error_keeps_retryable_flag():
    websocket = FakeWebSocket(
        json.dumps(
            {
                "type": "session.ready",
                "request_id": "req_1",
                "route": {
                    "provider": "x",
                    "model": "y",
                    "region": "us",
                    "attempt_id": "att_1",
                },
            }
        ),
        json.dumps(
            {
                "type": "error",
                "error": {
                    "code": "rate_limited",
                    "message": "slow down",
                    "hint": "retry",
                    "retryable": True,
                },
            }
        ),
    )
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
        with pytest.raises(SpekoRouterError) as caught:
            _ = [event async for event in client.stream_text("hello")]

    assert caught.value.code == "rate_limited"
    assert caught.value.retryable is True


@pytest.mark.asyncio
async def test_close_surfaces_terminal_router_error():
    websocket = FakeWebSocket(
        json.dumps(
            {
                "type": "session.ready",
                "request_id": "req_1",
                "route": {
                    "provider": "x",
                    "model": "y",
                    "region": "us",
                    "attempt_id": "att_1",
                },
            }
        ),
        json.dumps({"type": "utterance.started", "sequence": 1}),
        b"pcm",
        json.dumps({"type": "utterance.done", "sequence": 1}),
        json.dumps(
            {
                "type": "error",
                "error": {
                    "code": "provider_error",
                    "message": "settlement failed",
                    "hint": "retry",
                    "retryable": True,
                },
            }
        ),
    )
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
        _ = [event async for event in client.stream_text("hello")]
        with pytest.raises(SpekoRouterError) as caught:
            await client.close()

    assert caught.value.code == "provider_error"
    assert websocket.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (402, "insufficient_credit", False),
        (429, "rate_limited", True),
        (503, "provider_unavailable", True),
    ],
)
async def test_upgrade_preserves_classified_error(status, code, retryable):
    from unittest.mock import MagicMock
    from websockets.exceptions import InvalidStatus

    response = MagicMock(status_code=status, reason_phrase="denied")
    response.body = json.dumps(
        {
            "error": {
                "code": code,
                "message": "classified denial",
                "retryable": retryable,
            }
        }
    ).encode()
    client = make_client()
    with patch(
        "client.websockets.connect",
        AsyncMock(side_effect=InvalidStatus(response)),
    ):
        with pytest.raises(SpekoRouterError) as caught:
            await client.connect()
    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert not client.is_ready


@pytest.mark.asyncio
async def test_cancel_during_handshake_closes_socket():
    websocket = FakeWebSocket()
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        connecting = asyncio.create_task(client.connect())
        await asyncio.sleep(0)
        connecting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await connecting
    assert websocket.closed
    assert not client.is_ready


@pytest.mark.asyncio
@pytest.mark.parametrize("consume_audio", [False, True])
async def test_cancel_stops_buffered_audio_without_reading_closed_socket(
    consume_audio,
):
    websocket = FakeWebSocket(
        json.dumps({"type": "session.ready"}),
        json.dumps({"type": "utterance.started", "sequence": 1}),
        b"audio",
    )
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
    stream = client.stream_text("hello")
    assert (await anext(stream)).type == SpekoTTSEventType.TTFB
    if consume_audio:
        assert (await anext(stream)).type == SpekoTTSEventType.AUDIO
    await client.cancel()
    assert [event async for event in stream] == []
    assert websocket.closed


@pytest.mark.asyncio
async def test_cancel_discards_a_receive_completing_during_close():
    websocket = FakeWebSocket(json.dumps({"type": "session.ready"}))
    client = make_client()
    with patch("client.websockets.connect", AsyncMock(return_value=websocket)):
        await client.connect()
    stream = client.stream_text("hello")
    receiving = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await client.cancel()
    websocket.messages.put_nowait(b"late audio")
    with pytest.raises(StopAsyncIteration):
        await receiving
