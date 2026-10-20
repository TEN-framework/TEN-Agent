#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
import asyncio
import hashlib
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

from .aio import cancel_and_wait, wait_done
from .config import KotobaTTSConfig
from .kotoba_tts import KotobaTTSClient, KotobaTTSError, classify_error
from .segmenter import SentenceBuffer

# Marker put on a request's segment queue after its last segment.
_END_OF_REQUEST = None
# How many finished request ids to remember for late-input detection.
_COMPLETED_HISTORY = 512
# How long flush and shutdown wait for a worker that is already in its
# terminal path before taking it over. A latency bound only: whatever the
# worker did not complete, the caller completes (see ``_finalize()``).
_TERMINAL_JOIN_SECONDS = 2.0


def dump_file_name(request_id: str) -> str:
    """Dump file name for a request id: a sanitized form of the id for
    readability plus a hash of the raw id, so ids that sanitize to the same
    text (``a/b`` and ``a_b``) never share a file."""
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:8]
    return f"kotoba_tts_dump_{safe_id}_{digest}.pcm"


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
        # A handshake time taken from the client but not yet reported.
        # Kept here so a send interrupted by flush is repeated, not lost.
        self.pending_connect_delay_ms: int | None = None
        # Terminal progress. ``ended``: a terminal path has started. Each
        # ``*_sent`` flag is set right after its event has gone out, so a
        # second caller of ``_finalize()`` repeats only what was cut off.
        self.ended = False
        self.error_sent = False
        self.audio_end_sent = False
        self.usage_sent = False
        self.finished = False
        # Set once every event is out and the request no longer owns the
        # extension; only the dump flush may still be running.
        self.settled = asyncio.Event()
        # Flush and shutdown may finalize concurrently; one at a time.
        self.finalize_lock = asyncio.Lock()
        # The dump close, run as its own task once the events are out so
        # that flush never waits on disk I/O. Joined by on_stop.
        self.cleanup: asyncio.Task | None = None


class KotobaTTSExtension(AsyncTTS2BaseExtension):
    # Injectable monotonic clock; tests replace it to check accounting.
    _clock = staticmethod(time.monotonic)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: KotobaTTSConfig | None = None
        self.client: KotobaTTSClient | None = None
        self._init_error: str | None = None
        self._request: _RequestState | None = None
        # Requests whose terminal path has started and whose dump is not
        # closed yet. ``_request`` may already point at the next request.
        self._finishing: set[_RequestState] = set()
        # Set first thing in on_stop(): no request may start after that.
        self._stopping = False
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
        # The base class's input loop keeps running until its own on_stop;
        # refuse new requests first, so a request released by a finishing
        # one during the waits below cannot start behind our back.
        self._stopping = True
        while True:
            requests = list(self._finishing)
            current = self._request
            if current is not None and current not in self._finishing:
                requests.append(current)
            if not requests:
                break
            for request in requests:
                if request.ended:
                    # Terminal events or the dump close may be mid-flight:
                    # let them land, bounded, then complete what is left.
                    await self._join_bounded(request, request.worker, "stop")
                    await self._finalize(
                        request, TTSAudioEndReason.INTERRUPTED, finish=False
                    )
                    await self._join_bounded(
                        request, request.cleanup, "dump close"
                    )
                else:
                    # A request that never reached its end gets no terminal
                    # events on shutdown (the base class emits none
                    # either); only its worker is stopped and its dump
                    # closed.
                    await self._stop_worker(request)
                    request.ended = True
                # Shutdown is the one caller that must wait for the file:
                # whatever the dump task did not finish is closed here.
                await self._close_recorder(request)
                self._finishing.discard(request)
                if self._request is request:
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
        if t.request_id in self._completed_ids:
            # Late input for a request that already ended (for example a
            # repeated empty request, or more deltas after an init-failed
            # request was reported). Not an error: release the queue.
            self.ten_env.log_warn(
                f"ignoring text for finished request {t.request_id}"
            )
            await self.finish_request(t.request_id)
            return

        if self._stopping:
            # Shutdown has begun: nothing may start now. The base class is
            # about to flush its queue and clear request state itself.
            self.ten_env.log_warn(
                f"ignoring text for {t.request_id}: extension is stopping"
            )
            return

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
            # Consumers close a request on its terminal event: send one,
            # and only one; further deltas of this id take the branch above.
            await self.send_tts_audio_end(
                request_id=t.request_id,
                request_event_interval_ms=0,
                request_total_audio_duration_ms=0,
                reason=TTSAudioEndReason.ERROR,
            )
            self._remember_completed(t.request_id)
            await self.finish_request(
                t.request_id, reason=TTSAudioEndReason.ERROR
            )
            return

        request = self._request
        if request is None or request.request_id != t.request_id:
            if request is not None and not request.ended:
                # The base class finishes a request before it hands us the
                # next one, so this is unexpected. Interrupt the old one
                # so it cannot stay open forever.
                self.ten_env.log_warn(
                    f"request {request.request_id} superseded by "
                    f"{t.request_id} without text_input_end"
                )
                await self._interrupt(request)
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
            path = os.path.join(
                self.config.dump_path, dump_file_name(request_id)
            )
            # PCMWriter appends: start this request's file empty so a
            # stale file from an earlier run never receives new audio.
            with open(path, "wb"):
                pass
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
        ttfb_ms: int | None = None
        if not request.ttfb_sent:
            request.ttfb_sent = True
            # TTFB runs from the moment the text was handed to the socket,
            # not from connection setup (reported as connect_delay below).
            # Read before any await: the metric sends take time that is
            # not part of the time to first byte.
            origin = self.client.last_send_at
            ttfb_ms = (
                int((self._clock() - origin) * 1000)
                if origin is not None
                else 0
            )
        await self._report_connect_delay(request)
        if ttfb_ms is not None:
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
        """Worker entry to the terminal path, for completion and failure."""
        if not self._is_current(request) or request.ended:
            return
        self._generation += 1
        await self._finalize(request, reason, error)

    async def cancel_tts(self) -> None:
        """Flush: stop the worker, cancel the in-flight response, and
        report INTERRUPTED. The base class clears request state itself.

        If the worker is already emitting its terminal events, wait for
        them so that no event of the old request lands after
        tts_flush_end; if they do not land in time, take over.
        """
        request = self._request
        if request is None:
            return
        if not request.ended:
            await self._interrupt(request)
            return
        if await self._wait_settled(request):
            return
        await self._finalize(
            request, TTSAudioEndReason.INTERRUPTED, finish=False
        )

    async def _interrupt(self, request: _RequestState) -> None:
        """Stop a request that is still synthesizing and end it as
        INTERRUPTED. ``finish_request()`` is not called: the base class
        owns the state transition on flush."""
        request.ended = True
        self._generation += 1
        await self._stop_worker(request)
        if self.client is not None:
            await self.client.cancel()
        await self._finalize(
            request, TTSAudioEndReason.INTERRUPTED, finish=False
        )

    async def _finalize(
        self,
        request: _RequestState,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
        *,
        finish: bool = True,
    ) -> None:
        """The single terminal sequence: error, audio_end, usage, state
        transition, release of the extension, dump flush.

        Idempotent: every step records its completion on the request right
        after its await returns, so a caller that takes over after the
        worker was cancelled mid-way repeats only the steps that did not
        complete. ``finish`` is False when the base class performs the
        state transition itself (flush, shutdown).
        """
        request.ended = True
        self._finishing.add(request)
        async with request.finalize_lock:
            if error is not None and not request.error_sent:
                # Error first, then the terminal audio_end, so consumers
                # learn why the request ends before they see it end.
                await self.send_tts_error(request.request_id, error)
                request.error_sent = True
            if not request.audio_end_sent:
                interval_ms = 0
                if request.audio_started_at is not None:
                    interval_ms = int(
                        (self._clock() - request.audio_started_at) * 1000
                    )
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
                request.audio_end_sent = True
                self._remember_completed(request.request_id)
            if not request.usage_sent:
                # A handshake paid for by this request but never followed
                # by audio (flushed early) is still this request's metric.
                await self._report_connect_delay(request)
                # Usage for this request only; this also resets the base
                # counters so the next request does not inherit them.
                await self.send_usage_metrics(request.request_id)
                request.usage_sent = True
            if finish and not request.finished:
                await self.finish_request(request.request_id, reason=reason)
                request.finished = True
            # Every event is out: the extension is free for the next
            # request, and the caller (flush included) is not made to wait
            # for disk I/O. The dump closes in its own task; the request
            # stays in _finishing until that task is through, so on_stop
            # can still join it.
            if self._request is request:
                self._request = None
            request.settled.set()
            if request.recorder is not None and request.cleanup is None:
                request.cleanup = asyncio.create_task(self._close_dump(request))
        if request.recorder is None:
            self._finishing.discard(request)

    async def _close_dump(self, request: _RequestState) -> None:
        await self._close_recorder(request)
        self._finishing.discard(request)

    async def _report_connect_delay(self, request: _RequestState) -> None:
        """Report the handshake time of a new connection under this
        request, once. The value is parked on the request before the send
        so an interrupted send is repeated by the next caller."""
        if request.pending_connect_delay_ms is None and self.client is not None:
            request.pending_connect_delay_ms = (
                self.client.take_connect_delay_ms()
            )
        if request.pending_connect_delay_ms is None:
            return
        await self.metrics_connect_delay(
            request.pending_connect_delay_ms, request_id=request.request_id
        )
        request.pending_connect_delay_ms = None

    async def _wait_settled(self, request: _RequestState) -> bool:
        """Flush found the worker inside its terminal events: wait for them
        to land. Returns False when they did not land in time, in which
        case the worker has been cancelled and the caller takes over."""
        try:
            await asyncio.wait_for(
                request.settled.wait(), _TERMINAL_JOIN_SECONDS
            )
            return True
        except asyncio.TimeoutError:
            self.ten_env.log_warn(
                f"request {request.request_id} did not finish within "
                f"{_TERMINAL_JOIN_SECONDS:g} s of flush; cancelling it"
            )
            await self._stop_worker(request)
            return False

    async def _join_bounded(
        self, request: _RequestState, task: asyncio.Task | None, what: str
    ) -> None:
        """Shutdown found a request's worker or dump close in flight: wait
        for it, bounded. The task may end in any way, including being
        cancelled by a concurrent flush takeover: that is a completed join.
        On timeout cancel it; the caller completes the rest."""
        if task is None or task.done() or task is asyncio.current_task():
            return
        if await wait_done(task, _TERMINAL_JOIN_SECONDS):
            return
        self.ten_env.log_warn(
            f"request {request.request_id}: {what} did not finish "
            f"within {_TERMINAL_JOIN_SECONDS:g} s of stop; cancelling it"
        )
        await cancel_and_wait(task)
        if task is request.worker:
            request.worker = None

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
        await cancel_and_wait(worker)

    async def _close_recorder(self, request: _RequestState) -> None:
        recorder = request.recorder
        if recorder is None:
            return
        try:
            # PCMWriter.flush() returns early while a background write is
            # running and leaves bytes buffered since then; repeat until
            # the buffer is empty so the dump holds every emitted frame.
            # Shielded: cancelling the caller must not cancel the writer's
            # own task, which has already taken the bytes out of the buffer.
            for _ in range(8):
                await asyncio.shield(recorder.flush())
                if not getattr(recorder, "buffer", None):
                    break
        except Exception as exc:
            self.ten_env.log_error(
                f"failed to flush dump for {request.request_id}: {exc}"
            )
        # Detached only once the flush is through: a close interrupted by
        # cancellation leaves the recorder for the caller that takes over.
        request.recorder = None
