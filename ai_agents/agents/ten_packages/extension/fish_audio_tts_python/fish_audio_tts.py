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

# Sentence terminators used by "every_sentence" flush mode. Kept in sync with
# the elevenlabs per_sentence_flush check in conversational_agent.
SENTENCE_ENDINGS = (".", "?", "!", "。", "？", "！")


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
        self._events: asyncio.Queue[tuple[bytes | None, int, str]] = (
            asyncio.Queue()
        )
        self._send_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._session_request_id = ""
        self._session_active = False
        self._session_first_text_flushed = False
        self._context_entered = False
        self._waiting_for_event = False
        self._waiting_request_id = ""
        self._is_cancelled = False
        self._is_closing = False
        self._connection_reported = False
        self._session_stop_requested = False
        self._reconnect_attempts = 0
        self._interrupted_request_id = ""
        self._interruption_reason = ""
        self._interruption_event = EVENT_TTS_ERROR

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
                f"{normalized[name]}, {value}" if name in normalized else value
            )
        return normalized

    async def _capture_response_headers(
        self, websocket: ClientConnection
    ) -> None:
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
        # Serialize establishment: a background reconnect handshake and a new
        # request must share one connection instead of overwriting each other's
        # fields and leaving an orphaned socket behind.
        async with self._connect_lock:
            await self._connect_locked()

    async def _connect_locked(self) -> None:
        if self._websocket is not None and self._receiver_task is not None:
            if not self._receiver_task.done():
                return
            await self._reset_connection()

        self._is_closing = False
        if self.on_connection_connecting is not None:
            await self.on_connection_connecting()
        headers = self._build_headers()
        # The handshake is an outbound request too; log the endpoint and the
        # routing headers with the credential masked.
        redacted_headers = {
            name: ("<redacted>" if name.lower() == "authorization" else value)
            for name, value in headers.items()
        }
        self.ten_env.log_info(
            "vendor_send: handshake "
            f"url={self.websocket_url}, headers={redacted_headers}",
            category=LOG_CATEGORY_VENDOR,
        )
        self._connect_context = connect(
            self.websocket_url,
            additional_headers=headers,
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

    async def _report_connect_failure(self, reason: str) -> None:
        """Report a terminal handshake failure with safe diagnostics."""
        if self.on_connection_disconnected is None:
            return
        try:
            await self.on_connection_disconnected(
                code=0,
                message=f"connect failed: {reason}",
            )
        except Exception as error:
            self.ten_env.log_error(
                "FishAudioTTS: failed to report connection failure: "
                f"type={type(error).__name__}, message={str(error)}"
            )

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
        # Every attempt failed: report the terminal failure so the connection
        # state leaves ``connecting`` instead of staying there forever.
        await self._report_connect_failure(type(last_error).__name__)
        raise last_error

    async def _send(self, message: dict[str, object]) -> None:
        websocket = self._websocket
        if websocket is None:
            raise ConnectionError("Fish Audio WebSocket is not connected")
        async with self._send_lock:
            payload = ormsgpack.packb(message)
            event = message.get("event")
            request = message.get("request")
            request_detail = f", request={request}" if request else ""
            # Log every outbound protocol event so the exact stream sent to the
            # vendor (start/text/flush/stop) can be reconstructed from the log.
            # Only event names, sizes and counts are recorded: the utterance
            # text stays out of vendor diagnostics and is logged under the
            # transcript category instead.
            # Logged before the TTFB marker so measuring stays accurate.
            self.ten_env.log_info(
                "vendor_send: "
                f"event={event}, bytes={len(payload)}, "
                f"keys={sorted(message.keys())}, "
                f"text_chars={len(message.get('text') or '')}"
                f"{request_detail}",
                category=LOG_CATEGORY_VENDOR,
            )
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
        self._session_first_text_flushed = False
        self._session_stop_requested = False

    def _should_flush(self, text: str, is_last: bool) -> bool:
        """Decide whether a text chunk should be followed by a flush event.

        The protocol-level flush only nudges the server to start synthesizing
        earlier; it never waits for a receipt. Empty text never flushes, and
        the final chunk is followed by ``stop`` (which flushes server-side),
        so emitting a flush there would only add a pointless round-trip.
        """
        if not text.strip():
            return False
        if is_last:
            return False

        mode = self.config.flush_mode
        if mode == "off":
            return False
        if mode == "first_chunk":
            # Flush the first non-empty chunk so short LLM output starts
            # synthesizing without changing the server's production threshold.
            return not self._session_first_text_flushed
        if mode == "every_sentence":
            # Only look at this chunk; no cross-event buffering.
            return text.rstrip().endswith(SENTENCE_ENDINGS)
        return False

    async def _send_text(self, text: str, is_last: bool = False) -> None:
        await self._send({"event": "text", "text": text})
        if self._should_flush(text, is_last):
            await self._send({"event": "flush"})
            self._session_first_text_flushed = True

    def interruption(self, request_id: str) -> tuple[str, int] | None:
        """Return the latched interruption for ``request_id``, if any.

        The outcome is bound to the request that was in flight, so a stale
        failure can never be reported against a different request.
        """
        if request_id and request_id == self._interrupted_request_id:
            return self._interruption_reason, self._interruption_event
        return None

    def _enqueue(
        self, payload: bytes | None, event: int, owner: str = ""
    ) -> None:
        """Queue an event tagged with the request it belongs to."""
        self._events.put_nowait(
            (payload, event, owner or self._session_request_id)
        )

    async def _record_interruption(self, reason: str, event: int) -> None:
        """Latch an interruption for the in-flight request and wake a waiter.

        Latching rather than only queueing keeps the failure attached to its
        request even when nothing was waiting on the event queue at the moment
        the connection broke.
        """
        if not self._session_request_id:
            return
        self._interrupted_request_id = self._session_request_id
        self._interruption_reason = reason
        self._interruption_event = event
        self.ten_env.log_warn(reason, category=LOG_CATEGORY_VENDOR)
        if self._waiting_for_event:
            self._enqueue(None, EVENT_TTS_RECONNECT)

    async def _receive_loop(self, websocket: ClientConnection) -> None:
        try:
            while not self._is_closing:
                if websocket is not self._websocket:
                    # Superseded by a newer connection: publish nothing.
                    return
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
                        if (
                            self.interruption(self._session_request_id)
                            is not None
                        ):
                            # Late audio from an interrupted session must not
                            # reach the consumer.
                            continue
                        if self.on_audio is not None:
                            await self.on_audio(audio, self._session_request_id)
                        else:
                            self._enqueue(audio, EVENT_TTS_RESPONSE)
                elif event == "finish":
                    self._session_active = False
                    reason = str(data.get("reason") or "").strip()
                    if reason.lower() == "error":
                        # The vendor stopped the stream because generation
                        # failed: never report this as a normal end.
                        await self._record_interruption(
                            "Fish Audio finished the stream with "
                            f"reason={reason!r}",
                            EVENT_TTS_ERROR,
                        )
                    else:
                        self._enqueue(None, EVENT_TTS_END)
                elif event == "error":
                    self._session_active = False
                    error = str(data.get("error", "Unknown Fish Audio error"))
                    _, event_type = self._error_event_text(error)
                    await self._record_interruption(error, event_type)
        except Exception as error:
            if websocket is not self._websocket:
                # A superseded connection failed; it owns no request state, so
                # it must not latch a failure or trigger another reconnect.
                return
            if not self._is_closing:
                self.ten_env.log_warn(
                    "FishAudioTTS: WebSocket receive failed; "
                    f"starting reconnect, attempt={self._reconnect_attempts + 1}, "
                    f"type={type(error).__name__}, message={str(error)}"
                )
                if self._session_active and not self._is_cancelled:
                    # The session was in flight, so this request did not
                    # finish. Latch the failure before reconnecting: it must be
                    # reported for this request even if nothing is waiting.
                    await self._record_interruption(
                        "Fish Audio connection dropped before the request "
                        "finished",
                        EVENT_TTS_ERROR,
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
        """Re-establish the transport after a receive failure.

        Already accepted text is never resent: the vendor session dies with the
        socket and the protocol carries no acknowledgement, so replaying a
        buffered utterance would duplicate audible speech. An interrupted
        request is failed instead, and the next request reconnects on demand.
        """
        while not self._is_closing and not self._is_cancelled:
            self._reconnect_attempts += 1
            if self._reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
                message = (
                    "Fish Audio WebSocket reconnect exhausted after "
                    f"{MAX_RECONNECT_ATTEMPTS} attempts"
                )
                self.ten_env.log_error(message, category=LOG_CATEGORY_VENDOR)
                # Every retry re-entered ``connecting``; report the terminal
                # failure so the status does not stay there forever.
                await self._report_connect_failure("reconnect exhausted")
                if self._waiting_for_event and not self._interrupted_request_id:
                    self._enqueue(
                        message.encode("utf-8"),
                        EVENT_TTS_ERROR,
                        self._waiting_request_id,
                    )
                return

            await asyncio.sleep(0.2 * (2 ** (self._reconnect_attempts - 1)))
            try:
                async with self._connect_lock:
                    await self._reset_connection(notify=False)
                    await self._connect_locked()
                self._reconnect_attempts = 0
                self.ten_env.log_info("FishAudioTTS: WebSocket reconnected")
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

    async def _drain_ready_events(
        self, request_id: str
    ) -> AsyncIterator[tuple[bytes | None, int]]:
        while True:
            try:
                payload, event_type, owner = self._events.get_nowait()
            except asyncio.QueueEmpty:
                return
            if event_type not in (EVENT_TTS_RECONNECT, EVENT_TTS_FLUSH):
                if owner != request_id:
                    # Event from another request: never deliver it here.
                    continue
            if event_type == EVENT_TTS_RECONNECT:
                continue
            yield payload, event_type

    async def get(
        self,
        text: str,
        request_id: str = "",
        text_input_end: bool = True,
    ) -> AsyncIterator[tuple[bytes | None, int]]:
        self._is_cancelled = False
        interrupted = self.interruption(request_id)
        if interrupted is not None:
            # The request already failed: never open another vendor session or
            # submit more text for it.
            self.ten_env.log_debug(
                "FishAudioTTS: dropping text for interrupted request "
                f"{request_id}"
            )
            if text_input_end:
                reason, event = interrupted
                yield reason.encode("utf-8"), event
            return
        try:
            if self.on_request_start is not None:
                self.on_request_start()
            await self._ensure_connection_with_retry()
            await self._start_session(request_id)
            await self._send_text(text, is_last=text_input_end)

            if not text_input_end:
                async for event in self._drain_ready_events(request_id):
                    yield event
                return

            self._session_stop_requested = True
            await self._send({"event": "stop"})
            while True:
                interruption = self.interruption(request_id)
                if interruption is not None:
                    # The session broke before the vendor concluded this
                    # request, so report the latched failure instead of waiting
                    # for a terminal event that will never arrive.
                    reason, event = interruption
                    yield reason.encode("utf-8"), event
                    return
                self._waiting_for_event = True
                self._waiting_request_id = request_id
                try:
                    payload, event_type, owner = await self._events.get()
                finally:
                    self._waiting_for_event = False
                    self._waiting_request_id = ""
                if event_type not in (
                    EVENT_TTS_RECONNECT,
                    EVENT_TTS_FLUSH,
                ):
                    if owner != request_id:
                        # Terminal event from an earlier, abandoned session.
                        continue
                if event_type == EVENT_TTS_RECONNECT:
                    continue
                yield payload, event_type
                if event_type in (
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
            self.ten_env.log_info(
                "vendor_send: close", category=LOG_CATEGORY_VENDOR
            )
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
        if (
            notify
            and self._connection_reported
            and self.on_connection_disconnected
        ):
            await self.on_connection_disconnected(code=0, message="closed")
        self._context_entered = False
        self._connection_reported = False
        self._session_active = False
        self._session_request_id = ""
        self._session_first_text_flushed = False

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
            self._enqueue(None, EVENT_TTS_FLUSH)
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
