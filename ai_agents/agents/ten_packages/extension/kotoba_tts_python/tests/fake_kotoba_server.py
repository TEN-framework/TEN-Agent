#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""In-process stand-in for the Kotoba TTS WebSocket service.

Speaks the ``/v2/tts/ws`` protocol the real app uses (``open`` ->
``session.created``, ``response.create`` -> ``audio.chunk``* ->
``response.done``, ``response.cancel`` -> ``response.done(cancelled)``),
so the extension and the real ``kotoba-sdk`` client run unchanged in tests.
Runs on its own thread with its own event loop because the extension under
test runs inside the TEN runtime.
"""
import asyncio
import base64
import json
import threading
from dataclasses import dataclass, field
from http import HTTPStatus

import websockets
from websockets.asyncio.server import serve


def pcm16_ramp(num_samples: int, start: int = 0) -> bytes:
    """Deterministic little-endian int16 samples."""
    out = bytearray()
    for i in range(num_samples):
        value = ((start + i) % 2000) - 1000
        out += int(value).to_bytes(2, "little", signed=True)
    return bytes(out)


@dataclass
class Scenario:
    """Knobs that shape the server's behaviour for one test."""

    # Audio returned for every response.create.
    chunks_per_response: int = 3
    samples_per_chunk: int = 800
    chunk_delay_s: float = 0.02
    # Reject the WebSocket handshake with this HTTP status (e.g. 401).
    handshake_status: int | None = None
    # Keys rejected for an unknown key. ``reject_mode`` "http" answers the
    # handshake with 401; "close" accepts the upgrade and then closes with
    # code 1008 "Unauthorized", which is what the fal gateway does.
    reject_keys: frozenset[str] = frozenset({"", "invalid"})
    reject_mode: str = "close"
    # Answer ``open`` with this error message instead of session.created.
    open_error: str | None = None
    # Finish the N-th response (1-based) with response.done(status=failed)
    # carrying this error code, after ``fail_after_chunks`` chunks.
    fail_response_index: int | None = None
    fail_code: str = "worker_unavailable"
    fail_after_chunks: int = 0
    # Close the socket without response.done on the N-th response, after
    # ``close_after_chunks`` chunks.
    close_response_index: int | None = None
    close_after_chunks: int = 0
    # Close the socket this long after the last response completed,
    # imitating the service's idle timeout.
    idle_close_s: float | None = None
    # Hold the first chunk of every response this long (TTFB / stall).
    first_chunk_delay_s: float = 0.0
    # Delay before answering ``open`` (slow handshake).
    handshake_delay_s: float = 0.0
    # Delay before answering ``response.cancel`` with done(cancelled).
    cancel_done_delay_s: float = 0.0
    # Send this many stray audio.chunk frames after a cancel, before
    # done(cancelled), imitating audio already in flight.
    stray_chunks_after_cancel: int = 0
    # Never answer the N-th response.create (1-based): no chunks, no done.
    hold_response_index: int | None = None
    # Append this many extra bytes to every chunk (1 = split samples).
    extra_chunk_bytes: int = 0
    # Echo this format in session.created instead of the requested one.
    negotiate_format: str | None = None


@dataclass
class Recorded:
    connections: int = 0
    opens: list[dict] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    cancels: int = 0
    responses_completed: int = 0
    responses_cancelled: int = 0


class FakeKotobaServer:
    def __init__(self, scenario: Scenario | None = None) -> None:
        self.scenario = scenario or Scenario()
        self.recorded = Recorded()
        self.port: int = 0
        self.fixed_port: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop: asyncio.Event | None = None
        self._response_counter = 0
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/v2/tts/ws"

    def start(self) -> "FakeKotobaServer":
        self._thread = threading.Thread(
            target=self._run, name="fake-kotoba-server", daemon=True
        )
        self._thread.start()
        assert self._ready.wait(5), "fake server did not start"
        return self

    def stop(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def expected_pcm(self, responses: int = 1) -> bytes:
        """Audio bytes the server emits for ``responses`` full responses."""
        chunk = pcm16_ramp(self.scenario.samples_per_chunk)
        return chunk * self.scenario.chunks_per_response * responses

    def _run(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        async with serve(
            self._handle,
            "127.0.0.1",
            self.fixed_port,
            process_request=self._process_request,
        ) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stop.wait()

    # -- protocol ----------------------------------------------------------

    def _process_request(self, connection, request):
        with self._lock:
            self.recorded.connections += 1
        status = self.scenario.handshake_status
        if status is None and self.scenario.reject_mode == "http":
            if self._key_of(request) in self.scenario.reject_keys:
                status = HTTPStatus.UNAUTHORIZED
        if status is None:
            return None
        return connection.respond(HTTPStatus(status), "rejected\n")

    @staticmethod
    def _key_of(request) -> str:
        auth = request.headers.get("Authorization", "")
        return auth.split(" ", 1)[1] if " " in auth else ""

    async def _handle(self, ws) -> None:
        if (
            self.scenario.reject_mode == "close"
            and self._key_of(ws.request) in self.scenario.reject_keys
        ):
            await ws.close(code=1008, reason="Unauthorized")
            return
        try:
            raw = await ws.recv()
            body = json.loads(raw)
            if body.get("type") != "open":
                await self._send(
                    ws, {"type": "error", "message": "invalid open message"}
                )
                await ws.close(code=1003)
                return
            self.recorded.opens.append(body)
            if self.scenario.handshake_delay_s:
                await asyncio.sleep(self.scenario.handshake_delay_s)
            if self.scenario.open_error:
                await self._send(
                    ws, {"type": "error", "message": self.scenario.open_error}
                )
                await ws.close(code=1003)
                return
            sample_rate = int(body.get("sample_rate") or 24000)
            await self._send(
                ws,
                {
                    "type": "session.created",
                    "format": (
                        self.scenario.negotiate_format
                        or str(body.get("format") or "pcm_f32").lower()
                    ),
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "language": body.get("language"),
                    "speaker_id": body.get("speaker_id"),
                    "client_id": "fake-client",
                },
            )
            await self._session_loop(ws)
        except websockets.exceptions.ConnectionClosed:
            return

    async def _session_loop(self, ws) -> None:
        active: asyncio.Task | None = None
        cancel_event = asyncio.Event()
        idle = self.scenario.idle_close_s
        loop = asyncio.get_running_loop()
        idle_since: float | None = loop.time()
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.05)
            except asyncio.TimeoutError:
                busy = active is not None and not active.done()
                if busy:
                    idle_since = None
                elif idle_since is None:
                    idle_since = loop.time()
                elif idle is not None and loop.time() - idle_since > idle:
                    await ws.close(code=1000, reason="idle")
                    return
                continue
            body = json.loads(raw)
            msg_type = body.get("type")
            if msg_type == "response.create":
                idle_since = None
                if active is not None and not active.done():
                    await self._send(
                        ws,
                        {"type": "error", "message": "response already active"},
                    )
                    continue
                text = body.get("text")
                if not isinstance(text, str) or not text:
                    await self._send(
                        ws,
                        {
                            "type": "error",
                            "message": "text must be a non-empty string",
                        },
                    )
                    continue
                self.recorded.texts.append(text)
                cancel_event = asyncio.Event()
                active = asyncio.create_task(
                    self._respond(ws, text, cancel_event)
                )
            elif msg_type == "response.cancel":
                self.recorded.cancels += 1
                if active is None or active.done():
                    await self._send(
                        ws, {"type": "error", "message": "no active response"}
                    )
                    continue
                cancel_event.set()
            else:
                await self._send(
                    ws, {"type": "error", "message": "invalid message type"}
                )

    async def _respond(
        self, ws, text: str, cancel_event: asyncio.Event
    ) -> None:
        with self._lock:
            self._response_counter += 1
            index = self._response_counter
        response_id = f"resp-{index}"
        sc = self.scenario
        await self._send(
            ws, {"type": "response.created", "response": {"id": response_id}}
        )
        fail_here = sc.fail_response_index == index
        close_here = sc.close_response_index == index
        if sc.hold_response_index == index:
            # Imitate a stalled service: wait for cancel or forever.
            await cancel_event.wait()
            await self._finish_cancelled(ws, response_id)
            return
        for i in range(sc.chunks_per_response):
            if fail_here and i >= sc.fail_after_chunks:
                await self._send(
                    ws,
                    {
                        "type": "response.done",
                        "response": {
                            "id": response_id,
                            "status": "failed",
                            "error": {
                                "code": sc.fail_code,
                                "message": sc.fail_code,
                            },
                        },
                    },
                )
                return
            if close_here and i >= sc.close_after_chunks:
                await ws.close(code=1011, reason="simulated drop")
                return
            delay = sc.chunk_delay_s + (sc.first_chunk_delay_s if i == 0 else 0)
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            if cancel_event.is_set():
                await self._finish_cancelled(ws, response_id)
                return
            chunk = pcm16_ramp(sc.samples_per_chunk)
            if sc.extra_chunk_bytes:
                chunk += bytes([0x7F]) * sc.extra_chunk_bytes
            await self._send(
                ws,
                {
                    "type": "audio.chunk",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                    "isFinal": i == sc.chunks_per_response - 1,
                    "response_id": response_id,
                },
            )
        self.recorded.responses_completed += 1
        await self._send(
            ws,
            {
                "type": "response.done",
                "response": {"id": response_id, "status": "completed"},
            },
        )

    async def _finish_cancelled(self, ws, response_id: str) -> None:
        sc = self.scenario
        self.recorded.responses_cancelled += 1
        for _ in range(sc.stray_chunks_after_cancel):
            chunk = pcm16_ramp(sc.samples_per_chunk, start=999)
            await self._send(
                ws,
                {
                    "type": "audio.chunk",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                    "isFinal": False,
                    "response_id": response_id,
                },
            )
        if sc.cancel_done_delay_s:
            await asyncio.sleep(sc.cancel_done_delay_s)
        await self._send(
            ws,
            {
                "type": "response.done",
                "response": {"id": response_id, "status": "cancelled"},
            },
        )

    @staticmethod
    async def _send(ws, payload: dict) -> None:
        await ws.send(json.dumps(payload))
