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

# Response headers that are useful for vendor diagnostics. Everything else,
# notably Set-Cookie from the vendor or an intermediate proxy, stays out of
# production logs.
RESPONSE_HEADER_ALLOWLIST = frozenset(
    {
        "x-fishaudio-datacenter",
        "x-fishaudio-request-id",
        "x-request-id",
        "traceparent",
        "tracestate",
        "server-timing",
        "content-type",
        "date",
    }
)

CLOSE_TIMEOUT = 0.1


class FishAudioTTSClient:
    """Own one Fish Audio WebSocket connection at a time.

    A single supervisor task owns connect, retry and close. Requests submit
    protocol messages to a queue that the supervisor's send loop drains, so a
    request can never establish a competing connection. Cancelling a request
    stops the whole supervisor, including any retry backoff, and the extension
    replaces the client for the next request.
    """

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
        self._events: asyncio.Queue[tuple[bytes | None, int, str]] = (
            asyncio.Queue()
        )
        self._send_queue: asyncio.Queue[
            tuple[dict[str, object], asyncio.Future]
        ] = asyncio.Queue()
        self._state_condition = asyncio.Condition()
        self._supervisor_task: asyncio.Task | None = None
        self._channel_tasks: list[asyncio.Task] = []
        self._websocket: ClientConnection | None = None
        self._connected = False
        self._terminal_error = ""
        self._session_request_id = ""
        self._session_active = False
        self._session_first_text_flushed = False
        self._waiting_for_event = False
        self._waiting_request_id = ""
        self._is_cancelled = False
        self._is_closing = False
        self._connection_reported = False
        self._connecting_reported = False
        self._terminal_failure_reported = False
        self._consecutive_failures = 0
        self._interrupted_request_id = ""
        self._interruption_reason = ""
        self._interruption_event = EVENT_TTS_ERROR

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Constructed outside an event loop (for example by a config-only
            # unit test). get() starts the supervisor when it is first used.
            pass
        else:
            self._supervisor_task = asyncio.create_task(
                self._process_websocket()
            )

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
        captured = self._headers_to_dict(headers)
        self._response_headers = {
            name: value
            for name, value in captured.items()
            if name in RESPONSE_HEADER_ALLOWLIST
        }
        datacenter = self._response_headers.get("x-fishaudio-datacenter", "")
        trace_id = self._traceparent.split("-")[1]
        self.ten_env.log_info(
            "FishAudioTTS: WebSocket response headers: "
            f"{self._response_headers}; "
            f"x-fishaudio-datacenter={datacenter}; trace_id={trace_id}"
        )

    async def _notify_state(self) -> None:
        async with self._state_condition:
            self._state_condition.notify_all()

    async def _process_websocket(self) -> None:
        """Supervise connect, receive, reconnect and close for this client."""
        try:
            while not self._is_closing and not self._is_cancelled:
                try:
                    await self._connect_and_run()
                    # A live connection closed normally. Reconnect with the
                    # same retry budget as any other transport failure.
                    self._consecutive_failures = 0
                    await asyncio.sleep(0.2)
                except Exception as error:
                    self._log_vendor_error(error)
                    if self._is_closing or self._is_cancelled:
                        return
                    if self._session_active:
                        # The request was in flight when the transport died.
                        # Latch the failure before reconnecting so it cannot be
                        # reported as a successful completion later.
                        await self._record_interruption(
                            "Fish Audio connection dropped before the "
                            "request finished",
                            EVENT_TTS_ERROR,
                        )
                        self._session_active = False
                        self._session_request_id = ""
                    self._consecutive_failures += 1
                    self.ten_env.log_warn(
                        "FishAudioTTS: connection failed, "
                        f"attempt={self._consecutive_failures}/"
                        f"{MAX_RECONNECT_ATTEMPTS}, "
                        f"type={type(error).__name__}, "
                        f"message={str(error)}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if self._consecutive_failures >= MAX_RECONNECT_ATTEMPTS:
                        message = (
                            "Fish Audio WebSocket connection failed after "
                            f"{MAX_RECONNECT_ATTEMPTS} attempts"
                        )
                        self.ten_env.log_error(
                            message, category=LOG_CATEGORY_VENDOR
                        )
                        detail = str(error).strip()
                        self._terminal_error = (
                            f"{message}: {detail}" if detail else message
                        )
                        self._terminal_failure_reported = True
                        await self._report_connect_failure(type(error).__name__)
                        await self._notify_state()
                        return
                    await asyncio.sleep(
                        0.2 * (2 ** (self._consecutive_failures - 1))
                    )
        finally:
            await self._teardown_connection()
            await self._notify_state()

    async def _connect_and_run(self) -> None:
        self._connecting_reported = True
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
        async with connect(
            self.websocket_url,
            additional_headers=headers,
            close_timeout=CLOSE_TIMEOUT,
        ) as websocket:
            self._websocket = websocket
            await self._capture_response_headers(websocket)
            self._connection_reported = True
            self._connecting_reported = False
            self._connected = True
            self._consecutive_failures = 0
            if self.on_connection_connected is not None:
                await self.on_connection_connected()
            await self._notify_state()

            send_task = asyncio.create_task(self._send_loop(websocket))
            receive_task = asyncio.create_task(self._receive_loop(websocket))
            self._channel_tasks = [send_task, receive_task]
            failure: Exception | None = None
            try:
                done, _pending = await asyncio.wait(
                    self._channel_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    if task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        failure = error
                        if self._session_active and not self._is_cancelled:
                            # Latch before the cleanup below wakes senders with
                            # a transport error, so the request reports the
                            # provider failure instead of a generic send error.
                            await self._record_interruption(
                                "Fish Audio connection dropped before the "
                                "request finished",
                                EVENT_TTS_ERROR,
                            )
                            self._session_active = False
                            self._session_request_id = ""
                        break
            finally:
                for task in self._channel_tasks:
                    if not task.done():
                        task.cancel()
                if self._channel_tasks:
                    await asyncio.gather(
                        *self._channel_tasks, return_exceptions=True
                    )
                self._channel_tasks = []
                self._connected = False
                self._websocket = None
                self._clear_send_queue()
                await self._notify_state()

            if failure is not None:
                raise failure
            raise ConnectionError("Fish Audio WebSocket closed")

    async def _teardown_connection(self) -> None:
        for task in list(self._channel_tasks):
            if not task.done():
                task.cancel()
        if self._channel_tasks:
            await asyncio.gather(*self._channel_tasks, return_exceptions=True)
            self._channel_tasks = []
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            try:
                await asyncio.wait_for(websocket.close(), timeout=CLOSE_TIMEOUT)
            except Exception:
                pass
        self._connected = False
        if self._connection_reported and self.on_connection_disconnected:
            try:
                await self.on_connection_disconnected(code=0, message="closed")
            except Exception as error:
                self.ten_env.log_error(
                    "FishAudioTTS: failed to report disconnection: "
                    f"type={type(error).__name__}, message={str(error)}"
                )
        self._connection_reported = False
        if (
            self._connecting_reported
            and not self._terminal_failure_reported
            and (self._is_cancelled or self._is_closing)
        ):
            await self._report_connect_failure("cancelled")
        self._connecting_reported = False

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

    async def _send_loop(self, websocket: ClientConnection) -> None:
        while not self._is_closing and not self._is_cancelled:
            message, ack = await self._send_queue.get()
            try:
                payload = ormsgpack.packb(message)
                self._log_send(message, payload)
                if websocket is not self._websocket:
                    raise ConnectionError("Fish Audio WebSocket was replaced")
                if (
                    message.get("event") == "text"
                    and self.on_text_send is not None
                ):
                    # Mark TTFB immediately before the first text payload is
                    # handed to the socket. The extension callback is
                    # idempotent for subsequent chunks.
                    self.on_text_send()
                await websocket.send(payload)
            except asyncio.CancelledError:
                if not ack.done():
                    if self._is_cancelled:
                        ack.cancel()
                    else:
                        # The supervisor cancelled this send because the
                        # transport failed. Surface it as a connection error
                        # to the request instead of cancelling the caller's
                        # task.
                        ack.set_exception(
                            ConnectionError(
                                "Fish Audio WebSocket closed while sending"
                            )
                        )
                raise
            except Exception as error:
                if not ack.done():
                    ack.set_exception(error)
                raise
            else:
                if not ack.done():
                    ack.set_result(None)

    def _log_send(self, message: dict[str, object], payload: bytes) -> None:
        payload_size = len(payload)
        event = message.get("event")
        request = message.get("request")
        request_detail = f", request={request}" if request else ""
        # Log every outbound protocol event so the exact stream sent to the
        # vendor (start/text/flush/stop) can be reconstructed from the log.
        # Only event names, sizes and counts are recorded: the utterance text
        # stays out of vendor diagnostics and is logged under the transcript
        # category instead.
        self.ten_env.log_info(
            "vendor_send: "
            f"event={event}, bytes={payload_size}, "
            f"keys={sorted(message.keys())}, "
            f"text_chars={len(message.get('text') or '')}"
            f"{request_detail}",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _send(self, message: dict[str, object]) -> None:
        if self._is_cancelled:
            raise asyncio.CancelledError
        if not self._connected or self._websocket is None:
            raise ConnectionError("Fish Audio WebSocket is not connected")
        ack = asyncio.get_running_loop().create_future()
        await self._send_queue.put((message, ack))
        await ack

    async def _start_session(self, request_id: str) -> None:
        if self._session_active and self._session_request_id == request_id:
            return
        self._session_request_id = request_id
        self._session_active = True
        self._session_first_text_flushed = False
        await self._send({"event": "start", "request": self._build_request()})

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
        self._latch_interruption(self._session_request_id, reason, event)
        if self._waiting_for_event:
            self._enqueue(None, EVENT_TTS_RECONNECT)

    def _latch_interruption(
        self, request_id: str, reason: str, event: int
    ) -> None:
        """Bind a terminal failure to a request, including pre-session errors."""
        if not request_id or self._interrupted_request_id == request_id:
            return
        self._interrupted_request_id = request_id
        self._interruption_reason = reason
        self._interruption_event = event
        self.ten_env.log_warn(reason, category=LOG_CATEGORY_VENDOR)

    async def _receive_loop(self, websocket: ClientConnection) -> None:
        while not self._is_closing and not self._is_cancelled:
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
                    if self.interruption(self._session_request_id):
                        # Late audio from an interrupted session must not
                        # reach the consumer.
                        continue
                    if self.on_audio is not None:
                        await self.on_audio(audio, self._session_request_id)
                    else:
                        self._enqueue(audio, EVENT_TTS_RESPONSE)
            elif event == "finish":
                request_id = self._session_request_id
                self._session_active = False
                reason = str(data.get("reason") or "").strip()
                if reason.lower() == "error":
                    # The vendor stopped the stream because generation failed:
                    # never report this as a normal end, and force a new
                    # connection so a late frame cannot reach a later request.
                    await self._record_interruption(
                        "Fish Audio finished the stream with "
                        f"reason={reason!r}",
                        EVENT_TTS_ERROR,
                    )
                    self._session_request_id = ""
                    return
                self._enqueue(None, EVENT_TTS_END, request_id)
                self._session_request_id = ""
            elif event == "error":
                self._session_active = False
                error = str(data.get("error", "Unknown Fish Audio error"))
                _, event_type = self._error_event_text(error)
                await self._record_interruption(error, event_type)
                self._session_request_id = ""
                # The socket state after a vendor error is not trustworthy.
                # Reconnect before serving another request.
                return

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
            if event_type not in (
                EVENT_TTS_RECONNECT,
                EVENT_TTS_FLUSH,
            ):
                if owner != request_id:
                    # Event from another request: never deliver it here.
                    continue
            if event_type == EVENT_TTS_RECONNECT:
                continue
            yield payload, event_type

    async def _wait_until_connected(self) -> None:
        async with self._state_condition:
            await self._state_condition.wait_for(
                lambda: self._connected
                or self._is_cancelled
                or self._is_closing
                or bool(self._terminal_error)
            )
        if self._is_cancelled or self._is_closing:
            raise asyncio.CancelledError
        if self._terminal_error:
            raise ConnectionError(self._terminal_error)

    def _ensure_supervisor(self) -> None:
        if self._is_cancelled or self._is_closing:
            return
        if self._supervisor_task is None or self._supervisor_task.done():
            self._terminal_error = ""
            self._terminal_failure_reported = False
            self._consecutive_failures = 0
            self._connected = False
            self._supervisor_task = asyncio.create_task(
                self._process_websocket()
            )

    async def get(
        self,
        text: str,
        request_id: str = "",
        text_input_end: bool = True,
    ) -> AsyncIterator[tuple[bytes | None, int]]:
        if self._is_cancelled:
            if text_input_end:
                yield None, EVENT_TTS_FLUSH
            return
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
        self._ensure_supervisor()
        try:
            if self.on_request_start is not None:
                self.on_request_start()
            await self._wait_until_connected()
            await self._start_session(request_id)
            await self._send_text(text, is_last=text_input_end)

            if not text_input_end:
                async for event in self._drain_ready_events(request_id):
                    yield event
                return

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
                if self._is_cancelled:
                    yield None, EVENT_TTS_FLUSH
                    return
                self._waiting_for_event = True
                self._waiting_request_id = request_id
                if self._is_cancelled:
                    # Close the race between the check above and registering
                    # as a waiter: cancel() may have enqueued its sentinel
                    # while this request was not yet marked as waiting.
                    self._events.put_nowait((None, EVENT_TTS_FLUSH, ""))
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
            interruption = self.interruption(request_id)
            if interruption is not None:
                reason, event = interruption
                yield reason.encode("utf-8"), event
                return
            _, event_type = self._error_event_text(str(error))
            self._latch_interruption(request_id, str(error), event_type)
            self._session_active = False
            self._log_vendor_error(error)
            yield str(error).encode("utf-8"), event_type
        except Exception as error:
            if self._is_cancelled:
                yield None, EVENT_TTS_FLUSH
                return
            interruption = self.interruption(request_id)
            if interruption is not None:
                reason, event = interruption
                yield reason.encode("utf-8"), event
                return
            _, event_type = self._error_event_text(str(error))
            self._latch_interruption(request_id, str(error), event_type)
            self._session_active = False
            self._log_vendor_error(error)
            yield str(error).encode("utf-8"), event_type

    def _log_vendor_error(self, error: Exception) -> None:
        self.ten_env.log_error(
            "vendor_error: "
            f"type={type(error).__name__}, message={str(error)}",
            category=LOG_CATEGORY_VENDOR,
        )

    def _clear_pending_events(self) -> None:
        while True:
            try:
                self._events.get_nowait()
            except asyncio.QueueEmpty:
                return

    def _clear_send_queue(self) -> None:
        while True:
            try:
                _message, ack = self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if not ack.done():
                ack.set_exception(
                    ConnectionError("Fish Audio TTS send cancelled")
                )

    async def _stop_supervisor(self) -> None:
        task = self._supervisor_task
        self._supervisor_task = None
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._teardown_connection()

    async def cancel(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: cancel() called.")
        if self._is_cancelled:
            return
        self._is_cancelled = True
        self._clear_send_queue()
        if self._waiting_for_event:
            self._events.put_nowait((None, EVENT_TTS_FLUSH, ""))
        await self._notify_state()
        await self._stop_supervisor()
        self._clear_pending_events()
        if self._waiting_for_event:
            self._events.put_nowait((None, EVENT_TTS_FLUSH, ""))
        self._session_active = False
        self._session_request_id = ""

    async def clean(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: clean() called.")
        self._is_closing = True
        self._is_cancelled = True
        self._clear_send_queue()
        if self._waiting_for_event:
            self._events.put_nowait((None, EVENT_TTS_FLUSH, ""))
        await self._notify_state()
        await self._stop_supervisor()
        self._clear_pending_events()
        if self._waiting_for_event:
            self._events.put_nowait((None, EVENT_TTS_FLUSH, ""))
