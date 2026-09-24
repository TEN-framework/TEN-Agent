import asyncio
import base64
import json
import time
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .config import CartesiaTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTSTextInput, TTSWord

CARTESIA_API_VERSION = "2025-04-16"
CARTESIA_DEFAULT_WS_BASE_URL = "wss://api.cartesia.ai"
MAX_RETRY_TIMES = 5
PCM_QUEUE_STOP_SENTINEL = (None, "", 0)
WORDS_QUEUE_STOP_SENTINEL = ([], "", "", False)


class CartesiaTTSConnectionException(Exception):
    """Exception raised when Cartesia TTS connection fails"""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"Cartesia TTS connection failed (code: {status_code}): {body}"
        )


class CartesiaTTSClient:
    _NO_SPACE_BEFORE = set(".,!?;:%)]}，。！？；：、％》」』】")
    _NO_SPACE_AFTER = set("([{<“‘「『【")

    def __init__(
        self,
        config: CartesiaTTSConfig,
        ten_env: AsyncTenEnv,
        error_callback: Callable[[str, str], Awaitable[None]] | None = None,
        fatal_error_callback: Callable[[str], Awaitable[None]] | None = None,
        ttfb_metrics_callback: (
            Callable[[str, int], Awaitable[None]] | None
        ) = None,
        latency_metrics_callback: (
            Callable[[int], Awaitable[None]] | None
        ) = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.error_callback = error_callback
        self.fatal_error_callback = fatal_error_callback
        self.ttfb_metrics_callback = ttfb_metrics_callback
        self.latency_metrics_callback = latency_metrics_callback

        # Queues for full-duplex communication
        self.text_queue: asyncio.Queue[TTSTextInput | None] = asyncio.Queue()
        self.pcm_queue: asyncio.Queue[tuple[bytes | None, str, int]] = (
            asyncio.Queue()
        )
        self.words_queue: asyncio.Queue[
            tuple[list[TTSWord], str, str, bool]
        ] = asyncio.Queue()

        # Connection state
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._closing = False
        self._connection_task: asyncio.Task | None = None
        self._channel_tasks: list[asyncio.Task] = []

        # Pending inputs for reconnection
        self._pending_inputs: list[TTSTextInput] = []
        self._pending_input_ids: set[int] = set()

        # TTFB tracking: context_id -> request_start_time
        self._request_start_times: dict[str, float] = {}
        self._ttfb_sent: set[str] = set()

        # Current request tracking
        self._cur_request_id: str = ""

        # Per-context audio timestamp tracking
        self._base_start_ms: float = 0.0
        self._all_samples: float = 0.0

        # Per-context word timestamp tracking: context_id -> last word end ms
        # Used to insert space words between consecutive word groups
        self._last_word_end_ms: dict[str, int] = {}

        # Reconnection state
        self._connect_failures: int = 0

    @staticmethod
    def _is_cjk(char: str) -> bool:
        """Return True if the character belongs to a common CJK block."""
        code = ord(char)
        return (
            0x3400 <= code <= 0x4DBF
            or 0x4E00 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
            or 0x3040 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
        )

    @classmethod
    def _should_insert_space(cls, previous: str, current: str) -> bool:
        """Decide whether two adjacent tokens should be separated by a space."""
        if not previous or not current:
            return False
        if previous[-1].isspace() or current[0].isspace():
            return False
        if previous[-1] in cls._NO_SPACE_AFTER:
            return False
        if current[0] in cls._NO_SPACE_BEFORE:
            return False
        if cls._is_cjk(previous[-1]) or cls._is_cjk(current[0]):
            return False
        if unicodedata.category(current[0]).startswith("P"):
            return False
        return True

    def _get_ws_url(self) -> str:
        """Build the WebSocket URL with query parameters."""
        base = self.config.base_url.strip()
        if not base:
            base = CARTESIA_DEFAULT_WS_BASE_URL
        base = base.rstrip("/")
        if base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        elif base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif not base.startswith("wss://") and not base.startswith("ws://"):
            base = "wss://" + base
        return (
            f"{base}/tts/websocket" f"?cartesia_version={CARTESIA_API_VERSION}"
        )

    async def start(self) -> None:
        """Start the client: establish connection and launch background tasks."""
        self._closing = False
        if not self._session:
            self._session = aiohttp.ClientSession()
        self._connection_task = asyncio.create_task(self._connection_loop())
        self.ten_env.log_debug(
            "vendor_status: client starting",
            category=LOG_CATEGORY_VENDOR,
        )

    async def stop(self) -> None:
        """Stop the client: close connection and cancel all tasks."""
        self._closing = True
        self.ten_env.log_debug(
            "vendor_status: client stopping",
            category=LOG_CATEGORY_VENDOR,
        )

        # Signal text_queue to stop
        await self.text_queue.put(None)

        # Cancel channel tasks
        for task in self._channel_tasks:
            task.cancel()
        self._channel_tasks.clear()

        # Cancel connection task
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

        # Unblock any consumers waiting on pcm_queue / words_queue.
        await self.pcm_queue.put(PCM_QUEUE_STOP_SENTINEL)
        await self.words_queue.put(WORDS_QUEUE_STOP_SENTINEL)

        # Close WebSocket and session
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def cancel(self, request_id: str) -> None:
        """Cancel a specific context by sending cancel message."""
        self.ten_env.log_debug(
            f"vendor_status: cancelling context: {request_id}",
            category=LOG_CATEGORY_VENDOR,
        )
        if self._ws and not self._ws.closed and request_id:
            try:
                cancel_payload = {"context_id": request_id, "cancel": True}
                await self._ws.send_json(cancel_payload)
                self.ten_env.log_debug(
                    f"vendor_status: sent cancel for context: {request_id}",
                    category=LOG_CATEGORY_VENDOR,
                )
            except Exception as e:
                self.ten_env.log_warn(
                    f"vendor_error: error sending cancel: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )
        # Clear TTFB tracking for this context
        self._request_start_times.pop(request_id, None)
        self._ttfb_sent.discard(request_id)
        self._last_word_end_ms.pop(request_id, None)

    async def text_to_speech(self, t: TTSTextInput) -> None:
        """Put a text input into the send queue."""
        await self.text_queue.put(t)

    async def get_audio(self) -> tuple[bytes | None, str, int]:
        """Get next audio chunk from pcm_queue. Returns (data, request_id, timestamp_ms)."""
        return await self.pcm_queue.get()

    async def get_words(self) -> tuple[list[TTSWord], str, str, bool]:
        """Get next word timestamps from words_queue. Returns (words, request_id, text, is_final)."""
        return await self.words_queue.get()

    async def send_audio_end_signal(self, request_id: str) -> None:
        """Send end-of-audio signal to pcm_queue."""
        await self.pcm_queue.put((None, request_id, 0))

    async def set_current_request_id(self, request_id: str) -> None:
        self._cur_request_id = request_id

    # ── Connection loop with auto-reconnect ──────────────────────────

    async def _connection_loop(self) -> None:
        """
        Top-level loop that maintains the WebSocket connection.
        On disconnect, retries with exponential backoff.
        """
        min_delay = 0.1
        max_delay = 3.0

        while not self._closing:
            try:
                connection_start = time.time()
                await self._connect()
                connection_ms = int((time.time() - connection_start) * 1000)

                if self.latency_metrics_callback:
                    await self.latency_metrics_callback(connection_ms)

                self.ten_env.log_debug(
                    f"vendor_status: connected in {connection_ms}ms",
                    category=LOG_CATEGORY_VENDOR,
                )
                self._connect_failures = 0

                if self._closing:
                    return

                # Launch send and receive tasks
                self._channel_tasks = [
                    asyncio.create_task(self._send_text_loop()),
                    asyncio.create_task(self._receive_loop()),
                ]

                # Wait for either task to finish (usually means error/disconnect)
                done, pending = await asyncio.wait(
                    self._channel_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                self._channel_tasks.clear()

                # Check for exceptions
                for task in done:
                    exc = task.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        self.ten_env.log_warn(
                            f"Channel task exception: {exc}",
                            category=LOG_CATEGORY_VENDOR,
                        )

            except CartesiaTTSConnectionException as e:
                # Fatal auth error — don't retry
                self.ten_env.log_error(
                    f"Fatal connection error: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )
                if self.fatal_error_callback:
                    await self.fatal_error_callback(str(e))
                return

            except asyncio.CancelledError:
                return

            except Exception as e:
                self.ten_env.log_warn(
                    f"vendor_status: connection error: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )

            finally:
                # Close current ws
                if self._ws and not self._ws.closed:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass
                self._ws = None

            if self._closing:
                return

            # Exponential backoff
            self._connect_failures += 1
            if self._connect_failures > MAX_RETRY_TIMES:
                self.ten_env.log_error(
                    f"Max retries ({MAX_RETRY_TIMES}) exceeded, stopping reconnect",
                    category=LOG_CATEGORY_VENDOR,
                )
                if self.error_callback:
                    await self.error_callback(
                        self._cur_request_id,
                        f"WebSocket reconnect failed after {MAX_RETRY_TIMES} attempts",
                    )
                return

            delay = min(
                min_delay * (2 ** (self._connect_failures - 1)), max_delay
            )
            self.ten_env.log_debug(
                f"vendor_status: reconnecting in {delay:.1f}s "
                f"(attempt {self._connect_failures}/{MAX_RETRY_TIMES})",
                category=LOG_CATEGORY_VENDOR,
            )
            await asyncio.sleep(delay)

    async def _connect(self) -> None:
        """Establish WebSocket connection. Raises CartesiaTTSConnectionException on auth failure."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        url = self._get_ws_url()
        headers = {"X-Api-Key": self.config.api_key}
        try:
            self._ws = await self._session.ws_connect(url, headers=headers)
        except aiohttp.WSServerHandshakeError as e:
            if e.status == 401:
                raise CartesiaTTSConnectionException(
                    status_code=401, body=str(e)
                ) from e
            raise
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg and "Unauthorized" in error_msg:
                raise CartesiaTTSConnectionException(
                    status_code=401, body=error_msg
                ) from e
            raise

    # ── Send loop ──────────────────────────────────────────────────

    async def _send_text_loop(self) -> None:
        """Read from text_queue and send to WebSocket."""
        if not self._ws or self._ws.closed:
            raise RuntimeError("WebSocket is not connected for send loop")

        # Re-send any pending inputs from before reconnect
        pending_inputs = self._pending_inputs
        self._pending_inputs = []
        self._pending_input_ids.clear()
        for t in pending_inputs:
            if self._closing:
                return
            await self._send_one_text(t)

        try:
            while not self._closing:
                t = await self.text_queue.get()
                if t is None:
                    # Shutdown signal
                    return
                await self._send_one_text(t)
        except asyncio.CancelledError:
            return
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: send_text error: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    async def _send_one_text(self, t: TTSTextInput) -> None:
        """Send a single text input to the WebSocket."""
        if not self._ws or self._ws.closed:
            # Buffer for retry after reconnect
            self._buffer_pending_input(t)
            return

        context_id = t.request_id

        # Empty text with text_input_end — close the context.
        # Cartesia requires a transcript field, so send a empty string.
        if not t.text.strip() and t.text_input_end:
            close_payload = self._build_request_payload("", context_id)
            close_payload["continue"] = False
            self.ten_env.log_debug(
                f"send_context_end (empty text): context_id={context_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            try:
                await self._ws.send_json(close_payload)
            except Exception:
                self._pending_inputs.append(t)
                raise
            return

        # Skip non-end empty text entirely
        if not t.text.strip():
            return

        payload = self._build_request_payload(t.text, context_id)

        # Track request start time for TTFB
        if context_id not in self._request_start_times:
            self._request_start_times[context_id] = time.time()

        if t.text_input_end:
            # For the final text, set continue=False to signal end of context
            payload["continue"] = False

        self.ten_env.log_debug(
            f"send_text_to_tts_server: context_id={context_id}, "
            f"text={t.text[:80]}, text_input_end={t.text_input_end}",
            category=LOG_CATEGORY_VENDOR,
        )

        try:
            await self._ws.send_json(payload)
        except Exception:
            # Buffer for retry
            self._buffer_pending_input(t)
            raise

    def _build_request_payload(self, text: str, context_id: str) -> dict:
        """Build the JSON payload for a TTS generation request."""
        params = dict(self.config.params)
        params.pop("api_key", None)
        params.pop("base_url", None)

        payload: dict[str, Any] = {
            "transcript": text,
            "context_id": context_id,
            "continue": True,
        }

        # Extract known keys from params
        for key in (
            "model_id",
            "voice",
            "language",
            "output_format",
            "generation_config",
            "duration",
        ):
            if key in params:
                payload[key] = params.pop(key)

        # Set add_timestamps based on config.enable_words
        payload["add_timestamps"] = self.config.enable_words

        # Remaining params go directly into payload
        for key, value in params.items():
            if key not in payload:
                payload[key] = value

        return payload

    # ── Receive loop ─────────────────────────────────────────────────

    async def _receive_loop(self) -> None:
        """Read messages from WebSocket and dispatch to queues."""
        if not self._ws or self._ws.closed:
            raise RuntimeError("WebSocket is not connected for receive loop")

        try:
            async for msg in self._ws:
                if self._closing:
                    return

                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_ws_message(json.loads(msg.data))

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    error_msg = (
                        f"vendor_error: WebSocket error: {self._ws.exception()}"
                    )
                    self.ten_env.log_error(
                        error_msg,
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if self.error_callback:
                        await self.error_callback(
                            self._cur_request_id, error_msg
                        )
                    return

                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                ):
                    self.ten_env.log_warn(
                        "vendor_status: WebSocket closed by server",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    return

        except asyncio.CancelledError:
            return
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: receive_loop error: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    async def _handle_ws_message(self, data: dict) -> None:
        """Dispatch a single WebSocket JSON message."""
        resp_type = data.get("type", "")
        context_id = data.get("context_id", "")

        # Initialize base_start_ms on the first response (chunk or timestamps)
        # for the current context, so both audio and word timestamps share
        # the same time base.
        if resp_type in ("chunk", "timestamps") and self._base_start_ms == 0.0:
            self._base_start_ms = time.time() * 1000
            self._all_samples = 0.0

        if resp_type == "chunk":
            audio_b64 = data.get("data", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)

                # TTFB calculation
                if context_id and context_id not in self._ttfb_sent:
                    start_time = self._request_start_times.get(context_id)
                    if start_time:
                        ttfb_ms = int((time.time() - start_time) * 1000)
                        self._ttfb_sent.add(context_id)
                        self.ten_env.log_debug(
                            f"vendor_status: TTFB for {context_id}: {ttfb_ms}ms",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        if self.ttfb_metrics_callback:
                            await self.ttfb_metrics_callback(
                                context_id, ttfb_ms
                            )

                sample_rate = (
                    self.config.sample_rate
                    if self.config.sample_rate
                    else 16000
                )
                cur_pcm_start_ms = int(
                    self._base_start_ms + self._all_samples / sample_rate
                )
                # Accumulate samples (16-bit PCM mono: 2 bytes per sample)
                self._all_samples += float(len(audio_bytes)) / 2 * 1000

                self.ten_env.log_debug(
                    f"receive_audio: context={context_id}, "
                    f"len={len(audio_bytes)}, "
                    f"pcm_start_ms={cur_pcm_start_ms}, "
                    f"base_ms={int(self._base_start_ms)}, "
                    f"all_samples={self._all_samples:.0f}",
                    category=LOG_CATEGORY_VENDOR,
                )
                await self.pcm_queue.put(
                    (audio_bytes, context_id, cur_pcm_start_ms)
                )

        elif resp_type == "done":
            self.ten_env.log_debug(
                f"receive_done: context_id={context_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            self._base_start_ms = 0.0
            self._all_samples = 0.0
            self._last_word_end_ms.pop(context_id, None)
            await self.words_queue.put(([], context_id, "", True))
            await self.pcm_queue.put((None, context_id, 0))

        elif resp_type == "flush_done":
            self.ten_env.log_debug(
                f"receive_flush_done: context_id={context_id}",
                category=LOG_CATEGORY_VENDOR,
            )

        elif resp_type == "timestamps":
            await self._handle_timestamps(data, context_id)

        elif resp_type == "error":
            error_msg = data.get("message", "Unknown error")
            status_code = data.get("status_code", 0)
            self.ten_env.log_error(
                f"vendor_error: context_id={context_id} "
                f"status={status_code}, message={error_msg}",
                category=LOG_CATEGORY_VENDOR,
            )
            if self.error_callback:
                await self.error_callback(context_id, error_msg)

        else:
            self.ten_env.log_debug(
                f"receive_unknown: context_id={context_id}, type={resp_type}",
                category=LOG_CATEGORY_VENDOR,
            )

    async def _handle_timestamps(self, data: dict, context_id: str) -> None:
        """Parse word timestamps and put into words_queue."""
        ts_data = data.get("word_timestamps", data)
        raw_words = ts_data.get("words", [])
        raw_starts = ts_data.get("start", [])
        raw_ends = ts_data.get("end", [])

        if not raw_words:
            self.ten_env.log_debug(
                f"receive_timestamps: context_id={context_id}, empty",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        self.ten_env.log_debug(
            f"receive_timestamps: context_id={context_id}, "
            f"words={raw_words}, start={raw_starts}, end={raw_ends}",
            category=LOG_CATEGORY_VENDOR,
        )

        # Use the same base_start_ms as audio frames for alignment
        base_ms = self._base_start_ms

        words: list[TTSWord] = []
        text_parts: list[str] = []

        # If this context already received words, prepend a space word
        # so concatenated subtitles have proper spacing between groups.
        if context_id in self._last_word_end_ms:
            space_start_ms = self._last_word_end_ms[context_id]
            words.append(
                TTSWord(word=" ", start_ms=space_start_ms, duration_ms=0)
            )
            text_parts.append(" ")

        for i, word_text in enumerate(raw_words):
            start_s = raw_starts[i] if i < len(raw_starts) else 0.0
            end_s = raw_ends[i] if i < len(raw_ends) else start_s
            start_ms = int(base_ms + start_s * 1000)
            duration_ms = int((end_s - start_s) * 1000)
            if i == 0:
                self.ten_env.log_debug(
                    f"receive_timestamps: context_id={context_id}, "
                    f"first_word_start_ms={start_ms}, "
                    f"raw_start_s={start_s}, base_ms={int(base_ms)}, "
                    f"cur_all_samples={self._all_samples:.0f}",
                    category=LOG_CATEGORY_VENDOR,
                )
            if text_parts and self._should_insert_space(
                text_parts[-1], word_text
            ):
                words.append(
                    TTSWord(word=" ", start_ms=start_ms, duration_ms=0)
                )
                text_parts.append(" ")
            words.append(
                TTSWord(
                    word=word_text,
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                )
            )
            text_parts.append(word_text)

        # Track last word end for next group
        last = words[-1]
        self._last_word_end_ms[context_id] = last.start_ms + last.duration_ms

        text = "".join(text_parts)
        self.ten_env.log_debug(
            f"receive_words: context_id={context_id}, "
            f"{len(words)} words, text={text[:80]}",
            category=LOG_CATEGORY_VENDOR,
        )
        # is_final=False here; the extension will determine finality
        await self.words_queue.put((words, context_id, text, False))

    def _buffer_pending_input(self, t: TTSTextInput) -> None:
        """Buffer one TTSTextInput once to avoid duplicate replay on reconnect."""
        input_id = id(t)
        if input_id in self._pending_input_ids:
            return
        self._pending_input_ids.add(input_id)
        self._pending_inputs.append(t)
