"""Provider-boundary contract tests for the Fish Audio TTS extension."""

import asyncio
import json
import threading
import time

import ormsgpack
import pytest
import websockets
from pytest_ten import TenTestContext, ten_test
from ten_runtime import Data


class MockFishServer:
    """A small Fish Audio live endpoint that records the wire protocol."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.port: int | None = None
        self.connections: list[dict] = []
        self.delay_audio = False
        self.audio_delay = 0.3
        self.error_on_text = ""

    @property
    def base_url(self) -> str:
        assert self.port is not None
        return f"ws://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()
        assert self._ready.wait(timeout=2.0), "mock server did not start"

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)

    def connection(self, index: int) -> dict:
        with self._lock:
            record = self.connections[index]
            return {
                "messages": list(record["messages"]),
                "headers": dict(record["headers"]),
                "path": record["path"],
            }

    def connection_count(self) -> int:
        with self._lock:
            return len(self.connections)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(self._start_server())
        assert self._server.sockets is not None
        self.port = self._server.sockets[0].getsockname()[1]
        self._ready.set()
        self._loop.run_forever()
        self._server.close()
        self._loop.run_until_complete(self._server.wait_closed())
        self._loop.close()

    async def _start_server(self):
        return await websockets.serve(self._handler, "127.0.0.1", 0)

    async def _handler(self, websocket) -> None:
        request = websocket.request
        record = {
            "messages": [],
            "headers": dict(request.headers),
            "path": request.path,
        }
        with self._lock:
            self.connections.append(record)
        try:
            async for raw in websocket:
                message = ormsgpack.unpackb(raw)
                with self._lock:
                    record["messages"].append(message)
                event = message.get("event")
                if event == "text":
                    if self.delay_audio:
                        await asyncio.sleep(self.audio_delay)
                    if self.error_on_text:
                        await websocket.send(
                            ormsgpack.packb(
                                {
                                    "event": "error",
                                    "error": self.error_on_text,
                                }
                            )
                        )
                        return
                    await websocket.send(
                        ormsgpack.packb(
                            {
                                "event": "audio",
                                "audio": b"\x00\x00" * 160,
                            }
                        )
                    )
                elif event == "stop":
                    await websocket.send(
                        ormsgpack.packb({"event": "finish", "reason": "stop"})
                    )
        except Exception:
            # The extension closes the socket on flush/cancel.
            return


@pytest.fixture()
def server():
    mock = MockFishServer()
    mock.start()
    try:
        yield mock
    finally:
        mock.stop()


def config(server: MockFishServer, **params) -> str:
    merged = {
        "api_key": "mock-key",
        "base_url": server.base_url,
        "sample_rate": 16000,
        "format": "pcm",
        **params,
    }
    return json.dumps({"params": merged})


def payload(data) -> dict:
    value, error = data.get_property_to_json("")
    assert error is None
    return json.loads(value)


async def send_text(
    ctx: TenTestContext,
    request_id: str,
    text: str,
    text_input_end: bool = True,
) -> None:
    data = Data.create("tts_text_input")
    data.set_property_from_json(
        "",
        json.dumps(
            {
                "request_id": request_id,
                "text": text,
                "text_input_end": text_input_end,
            }
        ),
    )
    await ctx.send_data(data)


async def send_flush(ctx: TenTestContext) -> None:
    data = Data.create("tts_flush")
    data.set_property_from_json("", json.dumps({"flush_id": "flush-test"}))
    await ctx.send_data(data)


async def wait_until(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


async def expect_audio(ctx: TenTestContext) -> None:
    frame = await ctx.expect_audio_frame(timeout=1.0)
    buf = frame.lock_buf()
    try:
        assert len(bytes(buf)) > 0
    finally:
        frame.unlock_buf(buf)


async def expect_matching(
    ctx: TenTestContext,
    name: str,
    predicate,
    timeout: float = 1.0,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                f"no matching {name} message within {timeout}s"
            )
        value = payload(await ctx.expect_data(name, timeout=remaining))
        if predicate(value):
            return value


async def wait_for_connected(ctx: TenTestContext) -> None:
    await expect_matching(
        ctx,
        "connection_status_changed",
        lambda item: item["current"] == "connected",
        timeout=2.0,
    )


@pytest.mark.api
def test_api_protocol_sequence_and_ttfb(server):
    @ten_test("fish_audio_tts_python", config(server), timeout=2.0)
    async def scenario(ctx: TenTestContext):
        await wait_for_connected(ctx)
        await send_text(ctx, "req-1", "Hello", text_input_end=False)
        await send_text(ctx, "req-1", " world", text_input_end=True)

        metrics = await expect_matching(
            ctx,
            "metrics",
            lambda item: "ttfb" in item.get("metrics", {}),
            timeout=1.0,
        )
        assert metrics["metrics"]["ttfb"] >= 0
        await expect_audio(ctx)

        end = await expect_matching(
            ctx,
            "tts_audio_end",
            lambda item: item["request_id"] == "req-1",
            timeout=1.0,
        )
        assert end["reason"] == 1

        assert await wait_until(lambda: server.connection_count() == 1, 1.0)
        record = server.connection(0)
        assert record["path"] == "/v1/tts/live/with-timestamp"
        assert record["headers"]["model"] == "speech-1.5"
        assert record["headers"]["traceparent"].startswith("00-")
        assert [m["event"] for m in record["messages"]] == [
            "start",
            "text",
            "flush",
            "text",
            "stop",
        ]
        assert record["messages"][0]["request"]["chunk_length"] == 200
        assert record["messages"][1]["text"] == "Hello"
        assert record["messages"][3]["text"] == " world"

    scenario()


@pytest.mark.api
def test_api_flush_reconnects_without_replaying_text(server):
    @ten_test("fish_audio_tts_python", config(server), timeout=3.0)
    async def scenario(ctx: TenTestContext):
        await wait_for_connected(ctx)
        await send_text(ctx, "req-1", "first", text_input_end=False)
        await expect_audio(ctx)
        assert await wait_until(lambda: server.connection_count() == 1, 1.0)

        await send_flush(ctx)
        assert await wait_until(lambda: server.connection_count() == 2, 2.0)
        interrupted = await expect_matching(
            ctx,
            "tts_audio_end",
            lambda item: item["request_id"] == "req-1",
            timeout=1.0,
        )
        assert interrupted["reason"] == 2

        await send_text(ctx, "req-2", "second", text_input_end=True)
        await expect_audio(ctx)
        second_end = await expect_matching(
            ctx,
            "tts_audio_end",
            lambda item: item["request_id"] == "req-2",
            timeout=1.0,
        )
        assert second_end["reason"] == 1

        first = server.connection(0)["messages"]
        second = server.connection(1)["messages"]
        assert [m["text"] for m in first if m["event"] == "text"] == ["first"]
        assert [m["text"] for m in second if m["event"] == "text"] == ["second"]

    scenario()


@pytest.mark.api
def test_api_flush_before_audio_reports_interrupted(server):
    server.delay_audio = True

    @ten_test("fish_audio_tts_python", config(server), timeout=2.0)
    async def scenario(ctx: TenTestContext):
        await wait_for_connected(ctx)
        await send_text(ctx, "req-1", "cancel me", text_input_end=False)
        await expect_audio(ctx)
        await send_flush(ctx)

        end = await expect_matching(
            ctx,
            "tts_audio_end",
            lambda item: item["request_id"] == "req-1",
            timeout=1.0,
        )
        assert end["reason"] == 2
        assert end["request_event_interval_ms"] >= 0
        assert end["request_total_audio_duration_ms"] >= 0

    scenario()


@pytest.mark.api
def test_api_vendor_error_reports_error_end(server):
    server.error_on_text = "401 Unauthorized"

    @ten_test("fish_audio_tts_python", config(server), timeout=2.0)
    async def scenario(ctx: TenTestContext):
        await wait_for_connected(ctx)
        await send_text(ctx, "req-1", "fail", text_input_end=True)

        error = await expect_matching(
            ctx,
            "error",
            lambda item: item["id"] == "req-1",
            timeout=1.0,
        )
        assert error["code"] == -1000
        assert "401" in error["message"]

        end = await expect_matching(
            ctx,
            "tts_audio_end",
            lambda item: item["request_id"] == "req-1",
            timeout=1.0,
        )
        assert end["reason"] == 3

    scenario()
