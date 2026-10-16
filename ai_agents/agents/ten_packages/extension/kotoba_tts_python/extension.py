#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
import asyncio
import os
import re
import time
import traceback
from collections import deque

from pydantic import ValidationError
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT
from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleType,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_runtime import AsyncTenEnv

from .config import KotobaTTSConfig
from .kotoba_tts import KotobaTTSClient, KotobaTTSError, classify_error
from .segmenter import SentenceBuffer

# Marker put on a request's segment queue after its last segment.
_END_OF_REQUEST = None
# How many finished request ids to remember for late-input detection.
_COMPLETED_HISTORY = 512
# How long flush waits for a worker that is already emitting its terminal
# events before taking over. Normally the wait is well under 10 ms.
_TERMINAL_JOIN_SECONDS = 2.0


def _describe_init_error(exc: BaseException) -> str:
    """A configuration error message without any rejected input values."""
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors(include_input=False):
            loc = ".".join(str(x) for x in err.get("loc", ())) or "config"
            parts.append(f"{loc}: {err.get('type', 'invalid')}")
        return "invalid property: " + "; ".join(parts)
    if isinstance(exc, ValueError):
        # Our own validate_config() messages name fields, never values.
        return str(exc)
    return f"{type(exc).__name__}"


class _RequestState:
    """Everything owned by one TEN request id."""

    def __init__(
        self, request_id: str, generation: int, soft_limit_chars: int
    ) -> None:
        self.request_id = request_id
        self.generation = generation
        self.buffer = SentenceBuffer(soft_limit_chars)
        self.segments: asyncio.Queue[str | None] = asyncio.Queue()
        self.worker: asyncio.Task | None = None
        self.audio_started_at: float | None = None
        self.emitted_bytes = 0
        self.ttfb_sent = False
        self.recorder: PCMWriter | None = None
        # A trailing half sample held back until the next chunk completes
        # it, so only whole samples are emitted and counted.
        self.pending_bytes = b""
        # ``ended``: a terminal path has started. ``audio_end_sent``: the
        # terminal event has actually been emitted. Flush needs both.
        self.ended = False
        self.audio_end_sent = False


class KotobaTTSExtension(AsyncTTS2BaseExtension):
    # Injectable monotonic clock; tests replace it to check accounting.
    _clock = staticmethod(time.monotonic)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: KotobaTTSConfig | None = None
        self.client: KotobaTTSClient | None = None
        self._init_error: str | None = None
        self._request: _RequestState | None = None
        self._generation = 0
        self._completed_ids: set[str] = set()
        self._completed_order: deque[str] = deque(maxlen=_COMPLETED_HISTORY)

    # -- lifecycle ---------------------------------------------------------

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        try:
            config_json, _ = await ten_env.get_property_to_json("")
            config = KotobaTTSConfig.model_validate_json(config_json or "{}")
            config.update_params()
            config.validate_config()
            self.config = config
            ignored = config.ignored_params()
            if ignored:
                # Names only: an unknown key may hold a credential.
                ten_env.log_warn(f"ignoring unknown params: {ignored}")
            ten_env.log_info(
                f"config: {config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.client = KotobaTTSClient(
                config,
                ten_env,
                self.vendor(),
                on_connecting=self.on_connecting,
                on_connected=self.on_connected,
                on_disconnected=self.on_disconnected,
                clock=self._clock,
            )
        except Exception as exc:
            # Never echo rejected input: a malformed property may carry
            # the API key inside the exception text.
            self._init_error = _describe_init_error(exc)
            ten_env.log_error(f"on_init failed: {self._init_error}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {self._init_error}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        request = self._request
        if request is not None:
            if request.ended:
                # Terminal events may be mid-flight: let them land.
                await self._join_terminal_worker(request)
            else:
                await self._stop_worker(request)
            await self._close_recorder(request)
            self._request = None
        if self.client is not None:
            await self.client.close()
        await super().on_stop(ten_env)

    # -- vendor contract ---------------------------------------------------

    def vendor(self) -> str:
        return "kotoba"

    def vendor_metadata(self) -> dict:
        if self.config is None:
            return {}
        return {
            # Metadata travels on every event: never the raw endpoint.
            "url": self.config.redacted_base_url(),
            "language": self.config.language,
            "speaker_id": self.config.speaker_id,
            "sample_rate": self.config.sample_rate,
        }

    def synthesize_audio_sample_rate(self) -> int:
        if self.client is not None:
            return self.client.negotiated_sample_rate
        if self.config is not None:
            return self.config.sample_rate
        return 16000

    def synthesize_audio_channels(self) -> int:
        return 1

    def synthesize_audio_sample_width(self) -> int:
        return 2

    # -- requests ----------------------------------------------------------

    async def request_tts(self, t: TTSTextInput) -> None:
        """Buffer text; a worker task synthesizes complete sentences.

        Returns quickly: the base class awaits this call inline.
        """
        if self.client is None or self.config is None:
            await self.send_tts_error(
                t.request_id,
                ModuleError(
                    message=f"TTS not initialized: {self._init_error}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )
            # Consumers close a request on its terminal event: send one.
            await self.send_tts_audio_end(
                request_id=t.request_id,
                request_event_interval_ms=0,
                request_total_audio_duration_ms=0,
                reason=TTSAudioEndReason.ERROR,
            )
            await self.finish_request(
                t.request_id, reason=TTSAudioEndReason.ERROR
            )
            return

        if t.request_id in self._completed_ids:
            # Late input for a request that already ended (for example a
            # repeated empty request). Not an error: release the queue.
            self.ten_env.log_warn(
                f"ignoring text for finished request {t.request_id}"
            )
            await self.finish_request(t.request_id)
            return

        request = self._request
        if request is None or request.request_id != t.request_id:
            if request is not None and not request.ended:
                # The base class normally finishes a request before it
                # hands us the next one. Finalize the old one anyway so
                # it cannot stay open forever.
                self.ten_env.log_warn(
                    f"request {request.request_id} superseded by "
                    f"{t.request_id} without text_input_end"
                )
                await self._finalize_input(request)
            request = self._start_request(t.request_id)

        if t.text:
            self.metrics_add_input_characters(len(t.text))
            for segment in request.buffer.push(t.text):
                await request.segments.put(segment)
        if t.text_input_end:
            await self._finalize_input(request)

    def _start_request(self, request_id: str) -> _RequestState:
        assert self.config is not None
        self._generation += 1
        request = _RequestState(
            request_id, self._generation, self.config.segment_soft_limit_chars
        )
        if self.config.dump:
            request.recorder = self._open_recorder(request_id)
        request.worker = asyncio.create_task(self._run_request(request))
        self._request = request
        return request

    def _open_recorder(self, request_id: str) -> PCMWriter | None:
        """Create the dump writer, or ``None`` when the dump location is
        unusable. A bad ``dump_path`` must never strand the request queue."""
        assert self.config is not None
        try:
            os.makedirs(self.config.dump_path, exist_ok=True)
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
            path = os.path.join(
                self.config.dump_path, f"kotoba_tts_dump_{safe_id}.pcm"
            )
            return PCMWriter(path)
        except Exception as exc:
            self.ten_env.log_error(
                f"dump disabled for {request_id}: cannot use "
                f"dump_path {self.config.dump_path!r}: {exc}"
            )
            return None

    async def _finalize_input(self, request: _RequestState) -> None:
        rest = request.buffer.flush()
        if rest:
            await request.segments.put(rest)
        await request.segments.put(_END_OF_REQUEST)

    async def _run_request(self, request: _RequestState) -> None:
        try:
            while True:
                segment = await request.segments.get()
                if segment is _END_OF_REQUEST:
                    break
                await self._synthesize_segment(request, segment)
            await self._end_request(request, TTSAudioEndReason.REQUEST_END)
        # CancelledError is a BaseException: it passes through the handlers
        # below untouched, which is what flush relies on.
        except KotobaTTSError as err:
            await self._end_request(
                request, TTSAudioEndReason.ERROR, error=self._module_error(err)
            )
        except Exception as exc:
            self.ten_env.log_error(
                f"request {request.request_id} failed: "
                f"{traceback.format_exc()}"
            )
            await self._end_request(
                request,
                TTSAudioEndReason.ERROR,
                error=self._module_error(classify_error(exc)),
            )

    async def _synthesize_segment(
        self, request: _RequestState, segment: str
    ) -> None:
        """Send one sentence; retry once on a fresh socket when the failure
        happened before any audio for this sentence arrived."""
        assert self.client is not None
        for attempt in range(2):
            audio_in_segment = False
            await self.send_tts_request_metrics(
                request.request_id,
                segment,
                request_time_ms=int(time.time() * 1000),
            )
            stream = self.client.synthesize(segment)
            try:
                async for chunk in stream:
                    if not self._is_current(request):
                        return
                    audio_in_segment = True
                    await self._emit_audio(request, chunk)
                return
            except KotobaTTSError as err:
                if not self._is_current(request):
                    return
                if err.retryable and not audio_in_segment and attempt == 0:
                    self.ten_env.log_warn(
                        f"retrying segment after {err.code}: {err}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    continue
                raise
            finally:
                await stream.aclose()

    async def _emit_audio(self, request: _RequestState, chunk: bytes) -> None:
        assert self.client is not None and self.config is not None
        frame_bytes = (
            self.synthesize_audio_sample_width()
            * self.synthesize_audio_channels()
        )
        data = request.pending_bytes + chunk
        cut = len(data) - len(data) % frame_bytes
        request.pending_bytes = data[cut:]
        chunk = data[:cut]
        if not chunk:
            return
        connect_delay_ms = self.client.take_connect_delay_ms()
        if connect_delay_ms is not None:
            await self.metrics_connect_delay(
                connect_delay_ms, request_id=request.request_id
            )
        if not request.ttfb_sent:
            request.ttfb_sent = True
            # TTFB runs from the moment the text was handed to the socket,
            # not from connection setup (reported as connect_delay above).
            origin = self.client.last_send_at
            ttfb_ms = (
                int((self._clock() - origin) * 1000)
                if origin is not None
                else 0
            )
            await self.send_tts_ttfb_metrics(
                request_id=request.request_id,
                ttfb_ms=ttfb_ms,
                extra_metadata={
                    "speaker_id": self.config.speaker_id,
                    "language": self.config.language,
                },
            )
        if request.audio_started_at is None:
            # The event interval starts when tts_audio_start is emitted.
            request.audio_started_at = self._clock()
            await self.send_tts_audio_start(request_id=request.request_id)
        await self.send_tts_audio_data(chunk)
        # Count only audio that was handed to the runtime.
        request.emitted_bytes += len(chunk)
        self.metrics_add_recv_audio_chunks(chunk)
        if request.recorder is not None:
            try:
                await request.recorder.write(chunk)
            except Exception as exc:
                # A dump failure must not fail the request: log once and
                # stop recording this request.
                self.ten_env.log_error(
                    f"dump write failed for {request.request_id}: {exc}"
                )
                request.recorder = None

    async def _end_request(
        self,
        request: _RequestState,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
    ) -> None:
        """Terminal path shared by completion and failure.

        Order matters: the terminal events go out first, then the state
        transition, then the slow dump flush. ``cancel_tts()`` joins this
        path when a flush arrives while it runs.
        """
        if not self._is_current(request) or request.ended:
            return
        request.ended = True
        self._generation += 1
        if error is not None:
            # Error first, then the terminal audio_end, so consumers learn
            # why the request ends before they see it end.
            await self.send_tts_error(request.request_id, error)
        await self._send_audio_end(request, reason)
        await self.finish_request(request.request_id, reason=reason)
        await self._close_recorder(request)
        # Cleared last, so on_stop() can still find and join this request
        # while its recorder is being finalized.
        if self._request is request:
            self._request = None

    async def cancel_tts(self) -> None:
        """Flush: stop the worker, cancel the in-flight response, and
        report INTERRUPTED. The base class clears request state itself.

        If the worker is already emitting its terminal events, wait for it
        so that no event of the old request lands after tts_flush_end.
        """
        request = self._request
        if request is None:
            return
        if request.ended:
            await self._join_terminal_worker(request)
            if not request.audio_end_sent:
                await self._send_audio_end(
                    request, TTSAudioEndReason.INTERRUPTED
                )
            # The joined or cancelled worker may not have reached its own
            # recorder cleanup.
            await self._close_recorder(request)
            if self._request is request:
                self._request = None
            return
        request.ended = True
        self._generation += 1
        await self._stop_worker(request)
        if self.client is not None:
            await self.client.cancel()
        await self._send_audio_end(request, TTSAudioEndReason.INTERRUPTED)
        if self._request is request:
            self._request = None
        await self._close_recorder(request)

    async def _join_terminal_worker(self, request: _RequestState) -> None:
        worker = request.worker
        if worker is None or worker.done() or worker is asyncio.current_task():
            return
        try:
            await asyncio.wait_for(
                asyncio.shield(worker), _TERMINAL_JOIN_SECONDS
            )
        except asyncio.TimeoutError:
            self.ten_env.log_warn(
                f"request {request.request_id} did not finish within "
                f"{_TERMINAL_JOIN_SECONDS:g} s of flush; cancelling it"
            )
            await self._stop_worker(request)
        except Exception:
            pass

    async def _send_audio_end(
        self, request: _RequestState, reason: TTSAudioEndReason
    ) -> None:
        """Emit the single terminal audio_end and the request's usage."""
        if request.audio_end_sent:
            return
        interval_ms = 0
        if request.audio_started_at is not None:
            interval_ms = int((self._clock() - request.audio_started_at) * 1000)
        bytes_per_second = (
            self.synthesize_audio_sample_rate()
            * self.synthesize_audio_sample_width()
            * self.synthesize_audio_channels()
        )
        duration_ms = request.emitted_bytes * 1000 // bytes_per_second
        await self.send_tts_audio_end(
            request_id=request.request_id,
            request_event_interval_ms=interval_ms,
            request_total_audio_duration_ms=duration_ms,
            reason=reason,
        )
        # Set only after the event is out: a send interrupted by flush has
        # not been sent, and flush then emits INTERRUPTED itself.
        request.audio_end_sent = True
        self._remember_completed(request.request_id)
        if self.client is not None:
            # A handshake paid for by this request but never followed by
            # audio (flushed early) is still this request's metric.
            connect_delay_ms = self.client.take_connect_delay_ms()
            if connect_delay_ms is not None:
                await self.metrics_connect_delay(
                    connect_delay_ms, request_id=request.request_id
                )
        # Usage for this request only; this also resets the base counters
        # so the next request does not inherit them.
        await self.send_usage_metrics(request.request_id)

    # -- helpers -----------------------------------------------------------

    def _is_current(self, request: _RequestState) -> bool:
        return (
            self._request is request and request.generation == self._generation
        )

    def _module_error(self, err: KotobaTTSError) -> ModuleError:
        return ModuleError(
            message=str(err),
            module=ModuleType.TTS,
            code=(
                ModuleErrorCode.FATAL_ERROR
                if err.fatal
                else ModuleErrorCode.NON_FATAL_ERROR
            ),
            vendor_info=err.vendor_info(self.vendor()),
        )

    def _remember_completed(self, request_id: str) -> None:
        if len(self._completed_order) == self._completed_order.maxlen:
            oldest = self._completed_order[0]
            self._completed_ids.discard(oldest)
        self._completed_order.append(request_id)
        self._completed_ids.add(request_id)

    async def _stop_worker(self, request: _RequestState) -> None:
        worker = request.worker
        request.worker = None
        if worker is None or worker.done():
            return
        if worker is asyncio.current_task():
            return
        worker.cancel()
        try:
            await worker
        except (asyncio.CancelledError, Exception):
            pass

    async def _close_recorder(self, request: _RequestState) -> None:
        recorder, request.recorder = request.recorder, None
        if recorder is None:
            return
        try:
            # PCMWriter.flush() returns early while a background write is
            # running and leaves bytes buffered since then; repeat until
            # the buffer is empty so the dump holds every emitted frame.
            for _ in range(8):
                await recorder.flush()
                if not getattr(recorder, "buffer", None):
                    break
        except Exception as exc:
            self.ten_env.log_error(
                f"failed to flush dump for {request.request_id}: {exc}"
            )
