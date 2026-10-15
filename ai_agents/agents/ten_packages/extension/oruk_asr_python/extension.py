import asyncio
import copy
import json
import os
from contextvars import ContextVar
from typing import Any, Dict

import numpy as np
from typing_extensions import override

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)

from .config import OrukASRConfig
from .const import DUMP_FILE_NAME, MODULE_NAME_ASR, ORUKEET_MODEL
from .recognizer import OrukeetRecognizer

MAX_UTTERANCE_BYTES = 10 * 1024 * 1024
FINALIZE_TIMEOUT_SECONDS = 30.0


class _FinalizeBoundary:
    def __init__(self):
        self.ready = asyncio.Event()
        self.release = asyncio.Event()


class OrukASRExtension(AsyncASRBaseExtension):
    """Local Orukeet ASR for TEN.

    Orukeet (NVIDIA Parakeet TDT 0.6B v3 + Gabor kernels) runs on CPU via
    onnx-asr. There is no network connection: "connecting" means loading the
    INT8 ONNX model once. Audio is buffered per utterance and transcribed when
    the framework finalizes the turn (typically on a VAD stop / asr_finalize),
    so this extension emits final results only, with automatic language
    detection. It needs no API key and never uploads audio.
    """

    def __init__(self, name: str):
        self._live_metadata = None
        self._live_session_id = None
        self._finalize_context = ContextVar("oruk_local_finalize", default=None)
        super().__init__(name)
        self.config: OrukASRConfig | None = None
        self.recognizer: OrukeetRecognizer | None = None
        self.audio_dumper: Dumper | None = None
        self._connected = False
        self._init_failed = False
        self._finalize_request_lock = asyncio.Lock()
        self._audio_lock = asyncio.Lock()
        self._active_boundary = None
        self._pending_boundaries = set()
        self._inference_task = None
        self._utterance_overflow = False
        self._ready_event = asyncio.Event()
        self._loading = False
        self._flushing = False
        # Current utterance PCM16 bytes and the stream offset where it began.
        self._utterance = bytearray()
        self._utterance_start_ms = 0

    @property
    def metadata(self):
        context = self._finalize_context.get()
        return context[0] if context is not None else self._live_metadata

    @metadata.setter
    def metadata(self, value):
        self._live_metadata = value

    @property
    def session_id(self):
        context = self._finalize_context.get()
        return context[1] if context is not None else self._live_session_id

    @session_id.setter
    def session_id(self, value):
        self._live_session_id = value

    def _capture_metadata(self, message, session_id=None):
        try:
            raw, _ = message.get_property_to_json("metadata")
            value = json.loads(raw) if raw else None
            if isinstance(value, dict):
                self.metadata = copy.deepcopy(value)
                self.session_id = value.get("session_id", self.session_id)
            if session_id is not None and self.metadata is None:
                self.metadata = {"session_id": session_id}
                self.session_id = session_id
        except (ValueError, TypeError, AttributeError):
            pass

    @override
    async def on_audio_frame(self, ten_env, audio_frame):
        if self.metadata is None:
            self._capture_metadata(audio_frame)
        await super().on_audio_frame(ten_env, audio_frame)

    @override
    async def on_data(self, ten_env, data):
        if data.get_name() == "asr_finalize":
            # Place the boundary at receipt, even when an earlier request is
            # still recognizing. Otherwise a later turn can overtake this one.
            boundary = None
            queue = getattr(self, "audio_frames_queue", None)
            if queue is not None and not (self.stopped or self._init_failed):
                boundary = _FinalizeBoundary()
                self._pending_boundaries.add(boundary)
                queue.put_nowait(boundary)
            try:
                # The base owns one mutable finalize_id. Serialize its use,
                # while each request retains its own queue boundary.
                async with self._finalize_request_lock:
                    self._active_boundary = boundary
                    if boundary is not None and not (
                        self.stopped or self._init_failed
                    ):
                        try:
                            await asyncio.wait_for(
                                boundary.ready.wait(),
                                timeout=FINALIZE_TIMEOUT_SECONDS,
                            )
                        except asyncio.TimeoutError:
                            await self._fail_session(
                                "Orukeet audio drain timed out", "drain_timeout"
                            )
                    # Cold-start audio is held in the base's startup buffer;
                    # loading must finish draining it before metadata is frozen.
                    await self._wait_until_ready()
                    # A request without metadata inherits the last frame that
                    # was actually drained, never a later turn's queued frame.
                    self._capture_metadata(data)
                    token = self._finalize_context.set(
                        (copy.deepcopy(self.metadata), self.session_id)
                    )
                    try:
                        await super().on_data(ten_env, data)
                    finally:
                        self._finalize_context.reset(token)
            finally:
                if boundary is not None:
                    boundary.release.set()
                    self._pending_boundaries.discard(boundary)
                if self._active_boundary is boundary:
                    self._active_boundary = None
            return
        await super().on_data(ten_env, data)

    async def _handle_audio_frame(self, ten_env, audio_frame):
        # The base consumes this queue in order. A boundary pauses it until
        # finalize has snapshotted all earlier frames, including pending dumps.
        if isinstance(audio_frame, _FinalizeBoundary):
            audio_frame.ready.set()
            await audio_frame.release.wait()
            return
        await super()._handle_audio_frame(ten_env, audio_frame)

    def _release_boundary(self):
        if self._active_boundary is not None:
            self._active_boundary.release.set()

    async def _fail_session(self, message, code):
        self._init_failed = True
        self._connected = False
        if self.recognizer is not None:
            recognizer, self.recognizer = self.recognizer, None
            recognizer.close()
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=message,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(), code=code, message=message
            ),
        )
        await self.on_disconnected(code=0, message=message)

    async def _flush_buffered_audio(self):
        while not self.stopped:
            try:
                frame = self.buffered_frames.get_nowait()
            except asyncio.QueueEmpty:
                self.buffered_frames_size = 0
                return
            if not await self.send_audio(frame, self.session_id):
                pending = [frame]
                while not self.buffered_frames.empty():
                    pending.append(self.buffered_frames.get_nowait())
                for queued in pending:
                    self.buffered_frames.put_nowait(queued)
                self.buffered_frames_size = sum(
                    len(x.get_buf()) for x in pending
                )
                raise ConnectionError("Buffered audio could not be sent")
            self.sent_buffer_length += len(frame.get_buf())
            if self.first_audio_time is None:
                self.first_audio_time = asyncio.get_running_loop().time()

    @override
    def vendor(self) -> str:
        return "oruk"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        # No credentials or URLs: the local model is fixed to Orukeet.
        return {"model": ORUKEET_MODEL}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        config_json, _ = await ten_env.get_property_to_json("")
        try:
            self.config = OrukASRConfig.model_validate_json(config_json)
            self.config.validate_config()
            ten_env.log_info(
                f"config: {self.config.to_json()}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
                await self.audio_dumper.start()
        except Exception:
            ten_env.log_error("Invalid Oruk ASR configuration")
            self._init_failed = True
            self.config = OrukASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="Invalid Oruk ASR configuration",
                ),
                ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code="invalid_config",
                    message="Invalid Oruk ASR configuration",
                ),
            )

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    async def start_connection(self) -> None:
        """Load the local model once. The base emits CONNECTING before this runs."""
        if self._init_failed or self.stopped:
            await self.on_disconnected(code=0, message="connection disabled")
            return
        assert self.config is not None
        self.ten_env.log_info(
            "Loading Orukeet model (CPU, INT8 ONNX)",
            category=LOG_CATEGORY_VENDOR,
        )
        self._loading = True
        self._ready_event.clear()
        began = asyncio.get_running_loop().time()
        try:
            if self.recognizer is None:
                self.recognizer = OrukeetRecognizer(
                    cache_dir=self.config.cache_dir,
                    local_files_only=self.config.local_files_only,
                )
            await asyncio.to_thread(self.recognizer.prewarm)
            if self.stopped or self._init_failed:
                await self.on_disconnected(
                    code=0, message="connection disabled"
                )
                return
            self._flushing = True
            self._connected = True
            self._utterance.clear()
            self._utterance_start_ms = int(
                self.audio_timeline.get_total_user_audio_duration()
            )
            await self.on_connected()
            await self._flush_buffered_audio()
            self._flushing = False
            await self.send_connect_delay_metrics(
                int((asyncio.get_running_loop().time() - began) * 1000)
            )
            self.ten_env.log_info(
                "Orukeet model ready", category=LOG_CATEGORY_VENDOR
            )
        except Exception as e:
            if self.stopped or self._init_failed:
                await self.on_disconnected(
                    code=0, message="connection disabled"
                )
                return
            self.ten_env.log_error(f"Failed to load Orukeet model: {e}")
            error = ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=str(e),
            )
            await self.send_asr_error(
                error,
                ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code="model_load_failed",
                    message=error.message,
                ),
            )
            self._init_failed = True
            await self.on_disconnected(code=error.code, message=error.message)
        finally:
            self._loading = False
            self._ready_event.set()

    @override
    def is_connected(self) -> bool:
        return (
            self._connected
            and not self._flushing
            and self.recognizer is not None
            and self.recognizer.loaded
        )

    @override
    async def stop_connection(self) -> None:
        self._ready_event.set()
        for boundary in self._pending_boundaries:
            boundary.ready.set()
            boundary.release.set()
        self._connected = False
        self._utterance.clear()
        task, self._inference_task = self._inference_task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.recognizer is not None:
            recognizer = self.recognizer
            self.recognizer = None
            recognizer.close()

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.sample_rate

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        # Keep audio that arrives before the model finishes loading.
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    async def send_audio(
        self, frame: AudioFrame, _session_id: str | None
    ) -> bool:
        async with self._audio_lock:
            return await self._buffer_audio(frame, _session_id)

    async def _buffer_audio(self, frame, session_id):
        if self.stopped or self._init_failed or self._utterance_overflow:
            return False
        self._capture_metadata(frame, session_id)
        buf = frame.lock_buf()
        try:
            audio_data = bytes(buf)
            if len(self._utterance) + len(audio_data) > MAX_UTTERANCE_BYTES:
                self._utterance.clear()
                self._utterance_overflow = True
                message = "Orukeet utterance exceeded the 10 MiB audio limit"
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=message,
                    ),
                    ModuleErrorVendorInfo(
                        vendor=self.vendor(),
                        code="utterance_too_long",
                        message=message,
                    ),
                )
                return False
            if self.audio_dumper:
                try:
                    await self.audio_dumper.push_bytes(audio_data)
                except Exception:
                    self.ten_env.log_error("Audio diagnostic dump failed")
            if self.stopped or self._init_failed:
                return False
            if not self._utterance:
                self._utterance_start_ms = int(
                    self.audio_timeline.get_total_user_audio_duration()
                )
            self._utterance.extend(audio_data)
            self.audio_timeline.add_user_audio(
                len(audio_data) / 2 / self.config.sample_rate * 1000
            )
            return True
        except Exception as e:
            self.ten_env.log_error(f"Error buffering audio for Orukeet: {e}")
            return False
        finally:
            frame.unlock_buf(buf)

    @override
    async def finalize(self, _session_id: str | None) -> None:
        """Transcribe the buffered utterance and emit a single final result."""
        assert self.config is not None
        if self.stopped or self._init_failed:
            await self.send_asr_finalize_end()
            return
        await self._wait_until_ready()
        if self.stopped or self._init_failed:
            await self.send_asr_finalize_end()
            return

        # TEN's result, metrics and finalize helpers all read self.metadata.
        # Keep their view task-local while the audio consumer accepts the next
        # turn, without replacing or restoring that consumer's live metadata.
        token = self._finalize_context.set(
            (copy.deepcopy(self.metadata), self.session_id)
        )
        try:
            await self._finalize_utterance()
        finally:
            self._finalize_context.reset(token)

    async def _wait_until_ready(self):
        if self._loading and not (self.stopped or self._init_failed):
            try:
                await asyncio.wait_for(
                    self._ready_event.wait(), timeout=FINALIZE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                await self._fail_session(
                    "Orukeet model readiness timed out", "readiness_timeout"
                )

    async def _finalize_utterance(self) -> None:
        try:
            try:
                await asyncio.wait_for(
                    self._audio_lock.acquire(),
                    timeout=FINALIZE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                await self._fail_session(
                    "Orukeet audio drain timed out", "drain_timeout"
                )
                return
            try:
                if self.recognizer is None:
                    # With explicit connection control, finalize may precede
                    # trigger_connect. Drop this boundary's startup audio;
                    # replaying it on a later connection would mix turns.
                    while not self.buffered_frames.empty():
                        frame = self.buffered_frames.get_nowait()
                        self.audio_timeline.add_dropped_audio(
                            len(frame.get_buf())
                        )
                        self.dropped_audio_frames += 1
                    self.buffered_frames_size = 0
                pcm = bytes(self._utterance)
                if len(pcm) % 2:
                    pcm = pcm[:-1]
                self._utterance.clear()
                overflow = self._utterance_overflow
                self._utterance_overflow = False
                sample_rate = self.config.sample_rate
                duration_ms = int(len(pcm) / 2 / sample_rate * 1000)
                start_ms = self._utterance_start_ms
                self._utterance_start_ms += duration_ms
            finally:
                self._audio_lock.release()
                self._release_boundary()
            if overflow or not pcm or self.recognizer is None:
                return
            try:
                samples = (
                    np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )
                task = asyncio.create_task(
                    asyncio.to_thread(
                        self.recognizer.recognize, samples, sample_rate
                    )
                )
                self._inference_task = task
                text = await asyncio.wait_for(
                    task, timeout=FINALIZE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                await self._fail_session(
                    "Orukeet recognition timed out", "recognition_timeout"
                )
                return
            except asyncio.CancelledError:
                if self.stopped:
                    return
                raise
            except Exception as e:
                if self.stopped:
                    return
                self.ten_env.log_error(f"Orukeet recognition failed: {e}")
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=str(e),
                    ),
                    ModuleErrorVendorInfo(
                        vendor=self.vendor(),
                        code="recognition_failed",
                        message=str(e),
                    ),
                )
                return
            finally:
                self._inference_task = None

            if self.stopped:
                return

            if text:
                metadata = self._build_metadata()
                # The base shallow-merges self.metadata over result.metadata.
                # Give it the enriched view only during result/metric emission;
                # the finalize acknowledgement still echoes the request exactly.
                token = self._finalize_context.set((metadata, self.session_id))
                try:
                    await self.send_asr_result(
                        ASRResult(
                            text=text,
                            final=True,
                            start_ms=start_ms,
                            duration_ms=duration_ms,
                            language=self.config.asr_result_language,
                            words=[],
                            metadata=metadata,
                        )
                    )
                finally:
                    self._finalize_context.reset(token)

        finally:
            self._release_boundary()
            await self.send_asr_finalize_end()

    def _build_metadata(self) -> Dict[str, Any]:
        """Preserve caller fields, with authoritative generated ASR details."""
        metadata = copy.deepcopy(self.metadata) if self.metadata else {}
        supplied = metadata.get("asr_info")
        asr_info = supplied if isinstance(supplied, dict) else {}
        asr_info.update(vendor=self.vendor(), model=ORUKEET_MODEL)
        metadata["asr_info"] = asr_info
        return metadata
