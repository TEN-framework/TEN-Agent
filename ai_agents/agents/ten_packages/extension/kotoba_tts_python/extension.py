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
        self.ended = False


class KotobaTTSExtension(AsyncTTS2BaseExtension):
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
            )
        except Exception as exc:
            self._init_error = str(exc)
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {exc}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        request = self._request
        if request is not None:
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
            "url": self.config.base_url,
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
            await self.finish_request(
                t.request_id,
                reason=TTSAudioEndReason.ERROR,
                error=ModuleError(
                    message=f"TTS not initialized: {self._init_error}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
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
            os.makedirs(self.config.dump_path, exist_ok=True)
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
            path = os.path.join(
                self.config.dump_path, f"kotoba_tts_dump_{safe_id}.pcm"
            )
            request.recorder = PCMWriter(path)
        request.worker = asyncio.create_task(self._run_request(request))
        self._request = request
        return request

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
        except asyncio.CancelledError:
            raise
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
            sent_at = time.monotonic()
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
                    await self._emit_audio(request, chunk, sent_at)
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

    async def _emit_audio(
        self, request: _RequestState, chunk: bytes, sent_at: float
    ) -> None:
        now = time.monotonic()
        if not request.ttfb_sent:
            request.ttfb_sent = True
            await self.send_tts_ttfb_metrics(
                request_id=request.request_id,
                ttfb_ms=int((now - sent_at) * 1000),
                extra_metadata={
                    "speaker_id": self.config.speaker_id,
                    "language": self.config.language,
                },
            )
        if request.audio_started_at is None:
            request.audio_started_at = now
            await self.send_tts_audio_start(request_id=request.request_id)
        request.emitted_bytes += len(chunk)
        self.metrics_add_recv_audio_chunks(chunk)
        if request.recorder is not None:
            await request.recorder.write(chunk)
        await self.send_tts_audio_data(chunk)

    async def _end_request(
        self,
        request: _RequestState,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
    ) -> None:
        """Terminal path shared by completion and failure."""
        if not self._is_current(request) or request.ended:
            return
        request.ended = True
        self._generation += 1
        if error is not None:
            # Error first, then the terminal audio_end, so consumers learn
            # why the request ends before they see it end.
            await self.send_tts_error(request.request_id, error)
        await self._send_audio_end(request, reason)
        await self.send_usage_metrics(request.request_id)
        if self._request is request:
            self._request = None
        await self.finish_request(request.request_id, reason=reason)

    async def cancel_tts(self) -> None:
        """Flush: stop the worker, cancel the in-flight response, and
        report INTERRUPTED. The base class clears request state itself."""
        request = self._request
        if request is None or request.ended:
            return
        request.ended = True
        self._generation += 1
        await self._stop_worker(request)
        if self.client is not None:
            await self.client.cancel()
        await self._send_audio_end(request, TTSAudioEndReason.INTERRUPTED)
        if self._request is request:
            self._request = None

    async def _send_audio_end(
        self, request: _RequestState, reason: TTSAudioEndReason
    ) -> None:
        await self._close_recorder(request)
        interval_ms = 0
        if request.audio_started_at is not None:
            interval_ms = int(
                (time.monotonic() - request.audio_started_at) * 1000
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
        self._remember_completed(request.request_id)

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
            await recorder.flush()
        except Exception as exc:
            self.ten_env.log_error(
                f"failed to flush dump for {request.request_id}: {exc}"
            )
