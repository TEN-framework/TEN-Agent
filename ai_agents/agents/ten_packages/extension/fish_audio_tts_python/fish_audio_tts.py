import asyncio
import secrets
from collections.abc import AsyncIterator, Callable

import ormsgpack
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_runtime import AsyncTenEnv
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import FishAudioTTSConfig

EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_INVALID_KEY_ERROR = 4
EVENT_TTS_FLUSH = 5
EVENT_TTS_RECONNECT = 6
MAX_RECONNECT_ATTEMPTS = 3


class FishAudioTTSClient:
    def __init__(
        self,
        config: FishAudioTTSConfig,
        ten_env: AsyncTenEnv,
        on_request_start: Callable[[], None] | None = None,
        on_connection_connecting: Callable[[], object] | None = None,
        on_connection_connected: Callable[[], object] | None = None,
        on_connection_disconnected: Callable[..., object] | None = None,
        on_audio: Callable[[bytes, str], object] | None = None,
        on_text_send: Callable[[], None] | None = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.on_request_start = on_request_start
        self.on_text_send = on_text_send
        self.on_connection_connecting = on_connection_connecting
        self.on_connection_connected = on_connection_connected
        self.on_connection_disconnected = on_connection_disconnected
        self.on_audio = on_audio
        self._traceparent = ""
        self._response_headers: dict[str, str] = {}
        self._connect_context = None
        self._websocket: ClientConnection | None = None
        self._connect_task: asyncio.Task | None = None
        self._receiver_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._events: asyncio.Queue[tuple[bytes | None, int]] = asyncio.Queue()
        self._send_lock = asyncio.Lock()
        self._session_request_id = ""
        self._session_active = False
        self._session_texts: list[str] = []
        self._session_first_text_flushed = False
        self._session_audio_seen = False
        self._replay_request_id = ""
        self._replay_texts: list[str] = []
        self._context_entered = False
        self._waiting_for_event = False
        self._is_cancelled = False
        self._is_closing = False
        self._connection_reported = False
        self._session_stop_requested = False
        self._reconnect_attempts = 0

    @property
    def websocket_url(self) -> str:
        base_url = self.config.base_url.strip()
        if not base_url:
            base_url = "wss://api.fish.audio"
        elif base_url.startswith("https://"):
            base_url = "wss://" + base_url.removeprefix("https://")
        elif base_url.startswith("http://"):
            base_url = "ws://" + base_url.removeprefix("http://")
        return f"{base_url.rstrip('/')}/v1/tts/live/with-timestamp"

    @property
    def session_active(self) -> bool:
        return self._session_active

    @staticmethod
    def _new_traceparent() -> str:
        return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"

    def _build_headers(self) -> dict[str, str]:
        self._traceparent = self._new_traceparent()
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "model": self.config.backend,
            "traceparent": self._traceparent,
        }

    def _build_request(self) -> dict[str, object]:
        request: dict[str, object] = {"text": ""}
        request.update(self.config.params)
        request["text"] = ""
        request.setdefault("chunk_length", 200)
        return request

    @staticmethod
    def _headers_to_dict(headers) -> dict[str, str]:
        raw_items = getattr(headers, "raw_items", None)
        items = raw_items() if callable(raw_items) else headers.items()
        normalized: dict[str, str] = {}
        for name, value in items:
            name = name.lower()
            normalized[name] = (
                f"{normalized[name]}, {value}"
                if name in normalized
                else value
            )
        return normalized

    async def _capture_response_headers(self, websocket: ClientConnection) -> None:
        response = getattr(websocket, "response", None)
        headers = getattr(response, "headers", None)
        if headers is None:
            headers = getattr(websocket, "response_headers", {})
        self._response_headers = self._headers_to_dict(headers)
        datacenter = self._response_headers.get("x-fishaudio-datacenter", "")
        trace_id = self._traceparent.split("-")[1]
        self.ten_env.log_info(
            "FishAudioTTS: WebSocket response headers: "
            f"{self._response_headers}; "
            f"x-fishaudio-datacenter={datacenter}; trace_id={trace_id}"
        )

    async def _ensure_connection(self) -> None:
        if self._websocket is not None and self._receiver_task is not None:
            if not self._receiver_task.done():
                return
            if self._session_active and not self._session_audio_seen:
                self._replay_request_id = self._session_request_id
                self._replay_texts = list(self._session_texts)
            await self._reset_connection()

        self._is_closing = False
        if self.on_connection_connecting is not None:
            await self.on_connection_connecting()
        self._connect_context = connect(
            self.websocket_url,
            additional_headers=self._build_headers(),
        )
        self._connect_task = asyncio.create_task(
            self._connect_context.__aenter__()
        )
        try:
            self._websocket = await self._connect_task
            self._context_entered = True
            self._connect_task = None
            await self._capture_response_headers(self._websocket)
            self._connection_reported = True
            if self.on_connection_connected is not None:
                await self.on_connection_connected()
            self._receiver_task = asyncio.create_task(
                self._receive_loop(self._websocket)
            )
        except BaseException:
            self._connect_task = None
            await self._reset_connection()
            raise

    async def _ensure_connection_with_retry(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            try:
                await self._ensure_connection()
                return
            except Exception as error:
                last_error = error
                self.ten_env.log_warn(
                    "FishAudioTTS: WebSocket connect failed, "
                    f"attempt={attempt}/{MAX_RECONNECT_ATTEMPTS}, "
                    f"type={type(error).__name__}, message={str(error)}"
                )
                if attempt < MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(0.2 * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error

    async def _send(self, message: dict[str, object]) -> None:
        websocket = self._websocket
        if websocket is None:
            raise ConnectionError("Fish Audio WebSocket is not connected")
        async with self._send_lock:
            payload = ormsgpack.packb(message)
            if message.get("event") == "text" and self.on_text_send is not None:
                # Mark TTFB immediately before the first text payload is sent.
                # The extension callback is idempotent for subsequent chunks.
                self.on_text_send()
            await websocket.send(payload)

    async def _start_session(self, request_id: str) -> None:
        if self._session_active and self._session_request_id == request_id:
            return
        await self._send({"event": "start", "request": self._build_request()})
        self._session_request_id = request_id
        self._session_active = True
        self._session_texts = []
        self._session_first_text_flushed = False
        self._session_audio_seen = False
        self._session_stop_requested = False

    async def _send_text(self, text: str) -> None:
        await self._send({"event": "text", "text": text})
        if text.strip() and not self._session_first_text_flushed:
            # Flush the first non-empty chunk so short LLM output starts
            # synthesizing without changing the server's production threshold.
            await self._send({"event": "flush"})
            self._session_first_text_flushed = True

    async def _receive_loop(self, websocket: ClientConnection) -> None:
        try:
            while not self._is_closing:
                message = await websocket.recv()
                if isinstance(message, str):
                    raise RuntimeError(
                        "Fish Audio returned a text WebSocket message"
                    )
                data = ormsgpack.unpackb(message)
                event = data.get("event")
                if event == "audio":
                    audio = data.get("audio")
                    if isinstance(audio, bytes) and audio:
                        self._session_audio_seen = True
                        if self.on_audio is not None:
                            await self.on_audio(audio, self._session_request_id)
                        else:
                            await self._events.put((audio, EVENT_TTS_RESPONSE))
                elif event == "finish":
                    self._session_active = False
                    await self._events.put((None, EVENT_TTS_END))
                elif event == "error":
                    self._session_active = False
                    error = str(data.get("error", "Unknown Fish Audio error"))
                    await self._events.put(self._error_event_text(error))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._is_closing:
                self.ten_env.log_warn(
                    "FishAudioTTS: WebSocket receive failed; "
                    f"starting reconnect, attempt={self._reconnect_attempts + 1}, "
                    f"type={type(error).__name__}, message={str(error)}"
                )
                self._schedule_reconnect()
            if self._connection_reported and self.on_connection_disconnected:
                await self.on_connection_disconnected(
                    code=1000,
                    message=str(error),
                )
                self._connection_reported = False

    def _schedule_reconnect(self) -> None:
        if self._is_closing or self._is_cancelled:
            return
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        request_id = self._session_request_id
        texts = list(self._session_texts)
        stop_requested = self._session_stop_requested
        while not self._is_closing and not self._is_cancelled:
            self._reconnect_attempts += 1
            if self._reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
                message = (
                    "Fish Audio WebSocket reconnect exhausted after "
                    f"{MAX_RECONNECT_ATTEMPTS} attempts"
                )
                self.ten_env.log_error(message, category=LOG_CATEGORY_VENDOR)
                if self._waiting_for_event:
                    await self._events.put(
                        (message.encode("utf-8"), EVENT_TTS_ERROR)
                    )
                return

            await asyncio.sleep(0.2 * (2 ** (self._reconnect_attempts - 1)))
            try:
                await self._reset_connection(notify=False)
                await self._ensure_connection()
                await self._start_session(request_id)
                for replay_text in texts:
                    await self._send_text(replay_text)
                self._session_texts = texts
                if stop_requested:
                    await self._send({"event": "stop"})
                self._reconnect_attempts = 0
                self.ten_env.log_info(
                    f"FishAudioTTS: WebSocket reconnected, replayed={len(texts)}"
                )
                return
            except Exception as error:
                self.ten_env.log_warn(
                    "FishAudioTTS: reconnect attempt failed, "
                    f"attempt={self._reconnect_attempts}, "
                    f"type={type(error).__name__}, message={str(error)}"
                )

    @staticmethod
    def _error_event_text(error_message: str) -> tuple[bytes, int]:
        event = (
            EVENT_TTS_INVALID_KEY_ERROR
            if (
                "401" in error_message
                or "403" in error_message
                or "402" in error_message
                or "Unauthorized" in error_message
                or "Forbidden" in error_message
                or "Payment Required" in error_message
            )
            else EVENT_TTS_ERROR
        )
        return error_message.encode("utf-8"), event

    async def _drain_ready_events(self) -> AsyncIterator[tuple[bytes | None, int]]:
        while True:
            try:
                yield self._events.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def get(
        self,
        text: str,
        request_id: str = "",
        text_input_end: bool = True,
    ) -> AsyncIterator[tuple[bytes | None, int]]:
        self._is_cancelled = False
        try:
            if self.on_request_start is not None:
                self.on_request_start()
            await self._ensure_connection_with_retry()
            await self._start_session(request_id)
            if self._replay_request_id == request_id:
                for replay_text in self._replay_texts:
                    await self._send_text(replay_text)
                self._replay_request_id = ""
                self._replay_texts = []
            await self._send_text(text)
            self._session_texts.append(text)

            if not text_input_end:
                async for event in self._drain_ready_events():
                    yield event
                return

            self._session_stop_requested = True
            await self._send({"event": "stop"})
            while True:
                self._waiting_for_event = True
                try:
                    event_data = await self._events.get()
                finally:
                    self._waiting_for_event = False
                if event_data[1] == EVENT_TTS_RECONNECT:
                    continue
                yield event_data
                if event_data[1] in (
                    EVENT_TTS_END,
                    EVENT_TTS_ERROR,
                    EVENT_TTS_INVALID_KEY_ERROR,
                    EVENT_TTS_FLUSH,
                ):
                    return
        except asyncio.CancelledError:
            if self._is_cancelled:
                yield None, EVENT_TTS_FLUSH
                return
            raise
        except (ConnectionClosed, WebSocketException, OSError) as error:
            if self._is_cancelled:
                yield None, EVENT_TTS_FLUSH
                return
            self._log_vendor_error(error)
            yield self._error_event_text(str(error))
        except Exception as error:
            if self._is_cancelled:
                yield None, EVENT_TTS_FLUSH
                return
            self._log_vendor_error(error)
            yield self._error_event_text(str(error))

    def _log_vendor_error(self, error: Exception) -> None:
        self.ten_env.log_error(
            "vendor_error: "
            f"type={type(error).__name__}, message={str(error)}",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _reset_connection(self, notify: bool = True) -> None:
        reconnect_task = self._reconnect_task
        if (
            reconnect_task is not None
            and reconnect_task is not asyncio.current_task()
            and not reconnect_task.done()
        ):
            reconnect_task.cancel()
            await asyncio.gather(reconnect_task, return_exceptions=True)
        if reconnect_task is self._reconnect_task:
            self._reconnect_task = None

        connect_task = self._connect_task
        self._connect_task = None
        if connect_task is not None and not connect_task.done():
            connect_task.cancel()
            await asyncio.gather(connect_task, return_exceptions=True)

        receiver_task = self._receiver_task
        self._receiver_task = None
        if (
            receiver_task is not None
            and receiver_task is not asyncio.current_task()
            and not receiver_task.done()
        ):
            receiver_task.cancel()
            await asyncio.gather(receiver_task, return_exceptions=True)

        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

        context = self._connect_context
        self._connect_context = None
        if context is not None and self._context_entered:
            try:
                await context.__aexit__(None, None, None)
            except Exception:
                pass
        if notify and self._connection_reported and self.on_connection_disconnected:
            await self.on_connection_disconnected(code=0, message="closed")
        self._context_entered = False
        self._connection_reported = False
        self._session_active = False
        self._session_request_id = ""
        self._session_texts = []
        self._session_first_text_flushed = False
        self._session_audio_seen = False

    def _clear_pending_events(self) -> None:
        while True:
            try:
                self._events.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def cancel(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: cancel() called.")
        self._is_cancelled = True
        self._clear_pending_events()
        if self._waiting_for_event:
            await self._events.put((None, EVENT_TTS_FLUSH))
        if self._connect_task is not None and not self._connect_task.done():
            self._connect_task.cancel()
            await asyncio.gather(self._connect_task, return_exceptions=True)
            self._connect_task = None
        await self._reset_connection()
        if not self._waiting_for_event:
            self._clear_pending_events()

    async def clean(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: clean() called.")
        self._is_closing = True
        self._is_cancelled = True
        await self._reset_connection()
