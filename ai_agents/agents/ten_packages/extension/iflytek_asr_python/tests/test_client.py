import asyncio
import json
from collections.abc import AsyncIterator

import websockets

from iflytek_asr_python.client import IFlytekAsrClient
from iflytek_asr_python.config import IFlytekAsrConfig
from iflytek_asr_python.protocol import IFlytekResponse


class FakeWebSocket(AsyncIterator[str]):
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.closed = False

    def __aiter__(self) -> "FakeWebSocket":
        return self

    async def __anext__(self) -> str:
        message = await self.incoming.get()
        if message is None:
            raise StopAsyncIteration
        return message

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True
        await self.incoming.put(None)


class Listener:
    def __init__(self) -> None:
        self.responses: list[IFlytekResponse] = []
        self.errors: list[Exception] = []
        self.closed: list[bool] = []
        self.closed_event = asyncio.Event()

    async def on_response(self, response: IFlytekResponse) -> None:
        self.responses.append(response)

    async def on_error(self, error: Exception) -> None:
        self.errors.append(error)

    async def on_closed(self, terminal_received: bool) -> None:
        self.closed.append(terminal_received)
        self.closed_event.set()


def create_config() -> IFlytekAsrConfig:
    return IFlytekAsrConfig(
        params={
            "url": "ws://127.0.0.1:9990/tuling/ast/v3",
            "biz_id": "tenant-1",
            "trace_id_prefix": "test",
        }
    )


def test_client_sends_first_intermediate_and_finalize_frames() -> None:
    asyncio.run(_test_client_sends_first_intermediate_and_finalize_frames())


async def _test_client_sends_first_intermediate_and_finalize_frames() -> None:
    config = create_config()
    websocket = FakeWebSocket()
    listener = Listener()

    async def connect(_url: str, **_kwargs: object) -> FakeWebSocket:
        return websocket

    client = IFlytekAsrClient(config, listener, connect=connect)

    await client.start()
    assert client.is_connected()
    assert await client.send_audio(b"\x01\x02") is True
    assert await client.send_audio(b"\x03\x04") is True
    assert await client.finalize() is True

    messages = [json.loads(message) for message in websocket.sent]
    assert [message["header"]["status"] for message in messages] == [0, 1, 2]

    await client.stop()
    assert client.is_connected() is False


def test_client_dispatches_terminal_response_and_closes() -> None:
    asyncio.run(_test_client_dispatches_terminal_response_and_closes())


async def _test_client_dispatches_terminal_response_and_closes() -> None:
    config = create_config()
    websocket = FakeWebSocket()
    listener = Listener()

    async def connect(_url: str, **_kwargs: object) -> FakeWebSocket:
        return websocket

    client = IFlytekAsrClient(config, listener, connect=connect)
    await client.start()

    await websocket.incoming.put(
        json.dumps({"header": {"code": 0, "status": 2}, "payload": {}})
    )
    await asyncio.wait_for(listener.closed_event.wait(), timeout=1)

    assert len(listener.responses) == 1
    assert listener.responses[0].terminal is True
    assert listener.errors == []
    assert listener.closed == [True]
    assert websocket.closed is True
    assert client.is_connected() is False


def test_client_works_with_real_websockets_transport() -> None:
    asyncio.run(_test_client_works_with_real_websockets_transport())


async def _test_client_works_with_real_websockets_transport() -> None:
    received: list[dict[str, object]] = []

    async def handler(websocket: object) -> None:
        for _ in range(2):
            message = await websocket.recv()  # type: ignore[attr-defined]
            received.append(json.loads(message))
        await websocket.send(  # type: ignore[attr-defined]
            json.dumps({"header": {"code": 0, "status": 2}, "payload": {}})
        )

    server = await websockets.serve(handler, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        config = IFlytekAsrConfig(
            params={
                "url": f"ws://127.0.0.1:{port}/tuling/ast/v3",
                "biz_id": "tenant-1",
            }
        )
        listener = Listener()
        client = IFlytekAsrClient(config, listener)

        await client.start()
        assert await client.send_audio(b"\x01\x02") is True
        assert await client.finalize() is True
        await asyncio.wait_for(listener.closed_event.wait(), timeout=1)

        assert [message["header"]["status"] for message in received] == [
            0,
            2,
        ]
        assert listener.errors == []
        assert listener.closed == [True]
    finally:
        server.close()
        await server.wait_closed()


def test_stale_websocket_close_does_not_close_active_connection() -> None:
    asyncio.run(_test_stale_websocket_close_does_not_close_active_connection())


async def _test_stale_websocket_close_does_not_close_active_connection() -> (
    None
):
    config = create_config()
    stale_websocket = FakeWebSocket()
    active_websocket = FakeWebSocket()
    listener = Listener()

    async def connect(_url: str, **_kwargs: object) -> FakeWebSocket:
        return stale_websocket

    client = IFlytekAsrClient(config, listener, connect=connect)
    await client.start()
    stale_receive_task = client._receive_task
    assert stale_receive_task is not None

    active_receive_task = asyncio.create_task(asyncio.Event().wait())
    client._websocket = active_websocket
    client._receive_task = active_receive_task
    await stale_websocket.incoming.put(None)
    await stale_receive_task

    assert client._websocket is active_websocket
    assert client._receive_task is active_receive_task
    assert listener.closed == []

    active_receive_task.cancel()
    try:
        await active_receive_task
    except asyncio.CancelledError:
        pass
    await active_websocket.close()
