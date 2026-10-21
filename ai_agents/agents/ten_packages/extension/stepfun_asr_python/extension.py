from __future__ import annotations

import asyncio
import copy
import json
import os
import time
from collections import OrderedDict
from contextlib import suppress
from typing import Any

from typing_extensions import override
from websockets.exceptions import InvalidStatus

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
    PROPERTY_KEY_METADATA,
    PROPERTY_KEY_SESSION_ID,
)
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_ai_base.struct import ASRWord
from ten_runtime import AsyncTenEnv, AudioFrame, Data

from .config import StepFunASRConfig
from .const import DUMP_FILE_NAME, MODULE_NAME_ASR
from .recognition import (
    StepFunASRRecognition,
    StepFunASRRecognitionCallback,
    TranscriptSegment,
)
from .reconnect_manager import ReconnectManager


_MAX_COMPLETED_FINALIZES = 256


class StepFunASRExtension(AsyncASRBaseExtension, StepFunASRRecognitionCallback):
    """TEN adapter for StepAudio 2.5 real-time WebSocket recognition."""

    def __init__(self, name: str):
        super().__init__(name)
        self.config: StepFunASRConfig | None = None
        self.recognition: StepFunASRRecognition | None = None
        self.audio_dumper: Dumper | None = None
        self.reconnect_manager = ReconnectManager()
        self._recovery_task: asyncio.Task[None] | None = None
        self._input_task: asyncio.Task[None] | None = None
        self._connecting = False
        self._fatal = False
        self._fatal_error_sent = False
        self._connect_started_at: float | None = None
        self._finalize_events: dict[str, asyncio.Event] = {}
        self._completed_finalizes: OrderedDict[str, None] = OrderedDict()
        self._finalize_contexts: dict[str, dict[str, Any]] = {}
        self._finalize_times: dict[str, float] = {}
        # Finalize ids whose metadata was omitted and must be resolved after
        # preceding audio (and buffered frames) at the queue boundary.
        self._finalize_inherit_metadata: set[str] = set()
        self._buffer_flush_task: asyncio.Task[None] | None = None
        self._reconnect_pending = False
        self._finalize_locks: dict[str, asyncio.Lock] = {}
        self._connect_attempt = 0
        self._connect_task: asyncio.Task[None] | None = None
        self._result_context_lock = asyncio.Lock()
        # Metadata from audio frames dropped while _fatal skips journaling.
        self._fatal_discarded_frame_metadata: dict[str, Any] | None = None

    @staticmethod
    def _metadata_with_session(
        metadata: dict[str, Any] | None,
        session_id: str | None,
    ) -> dict[str, Any]:
        merged = copy.deepcopy(metadata) if metadata else {}
        if session_id is not None and "session_id" not in merged:
            merged["session_id"] = session_id
        return merged

    @staticmethod
    def _metadata_from_audio_frame(frame: AudioFrame) -> dict[str, Any] | None:
        metadata_json, error = frame.get_property_to_json("metadata")
        if error or not metadata_json:
            return None
        parsed = json.loads(metadata_json)
        if isinstance(parsed, dict) and parsed:
            return copy.deepcopy(parsed)
        return None

    @staticmethod
    def _sanitize_config_error(exc: Exception) -> str:
        """Drop Pydantic input_value dumps that may embed credentials."""
        errors = getattr(exc, "errors", None)
        if callable(errors):
            try:
                errors()
            except Exception:
                pass
            return "StepFun configuration is invalid"
        message = str(exc)
        lowered = message.lower()
        if any(
            key in lowered
            for key in ("api_key", "input_value", "password", "secret", "token")
        ):
            return "StepFun configuration is invalid"
        return message

    @override
    def vendor(self) -> str:
        return "stepfun"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        return {
            "url": self.config.url,
            "model": self.config.model,
            "language": self.config.language,
            "sample_rate": self.config.sample_rate,
            "api_key": self.config.api_key,
        }

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        config_json, error = await ten_env.get_property_to_json("")
        try:
            if error:
                raise ValueError(f"cannot read StepFun properties: {error}")
            self.config = StepFunASRConfig.model_validate_json(config_json)
            self.config.validate_config()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.reconnect_manager = ReconnectManager(
                self.config.reconnect_max_attempts,
                self.config.reconnect_base_delay,
            )
            self.recognition = StepFunASRRecognition(
                self.config,
                ten_env,
                self,
            )
            if self.config.dump:
                self.audio_dumper = Dumper(
                    os.path.join(self.config.dump_path, DUMP_FILE_NAME)
                )
                await self.audio_dumper.start()
        except Exception as exc:
            self.config = None
            self.recognition = None
            self._fatal = True
            await self._send_error(
                self._sanitize_config_error(exc),
                ModuleErrorCode.FATAL_ERROR.value,
                "invalid_config",
                once=True,
            )

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await self.stop_connection()
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None
        await super().on_deinit(ten_env)

    @override
    async def start_connection(self) -> None:
        if self.stopped or self._fatal:
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="StepFun connection disabled",
            )
            return
        if self.config is None or self.recognition is None:
            self._fatal = True
            await self._send_error(
                "StepFun ASR is not initialized",
                ModuleErrorCode.FATAL_ERROR.value,
                "not_initialized",
                once=True,
            )
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="StepFun ASR is not initialized",
            )
            return
        if not self.config.api_key:
            self._fatal = True
            await self._send_error(
                "StepFun API key is required",
                ModuleErrorCode.FATAL_ERROR.value,
                "auth",
                once=True,
            )
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="StepFun API key is required",
            )
            return
        if self._connecting:
            # Wait for the in-flight attempt instead of returning immediately —
            # otherwise recovery with delay=0 busy-spins on this early return.
            active = self._connect_task
            if (
                active is not None
                and active is not asyncio.current_task()
                and not active.done()
            ):
                with suppress(BaseException):
                    await active
            return

        self._connecting = True
        attempt = self._connect_attempt
        current = asyncio.current_task()
        if current is not None:
            self._connect_task = current
        try:
            await self._connect_once(attempt=attempt)
            if self.stopped or attempt != self._connect_attempt:
                if self.recognition:
                    await self.recognition.shutdown()
                return
            if self.is_connected():
                self.reconnect_manager.mark_connection_successful()
            elif self.recognition and self.recognition.normal_close:
                await self._handle_connect_failure(
                    ConnectionError("StepFun connection closed normally"),
                    report_error=False,
                )
            else:
                raise ConnectionError("StepFun connection ended before ready")
        except Exception as exc:
            if self.stopped or attempt != self._connect_attempt:
                return
            await self._handle_connect_failure(exc)
        finally:
            self._connecting = False
            if self._connect_task is current:
                self._connect_task = None

    async def _connect_once(self, *, attempt: int | None = None) -> None:
        if self._fatal or self.stopped:
            raise ConnectionError("StepFun connection recovery stopped")
        if attempt is not None and attempt != self._connect_attempt:
            raise ConnectionError("StepFun connection attempt invalidated")
        assert self.recognition is not None
        self._connect_started_at = time.monotonic()
        await self.recognition.start()
        if self.stopped or (
            attempt is not None and attempt != self._connect_attempt
        ):
            await self.recognition.shutdown()
            raise ConnectionError("StepFun connection attempt invalidated")

    async def _handle_connect_failure(
        self,
        exc: Exception,
        *,
        report_error: bool = True,
    ) -> None:
        # Structured handshake/vendor errors already latched fatal via on_error;
        # do not emit a second contradictory NON_FATAL ConnectionError.
        if self._fatal:
            return
        fatal, vendor_code, message = self._classify_connect_error(exc)
        self.ten_env.log_warn(
            f"StepFun connection attempt failed: {message}",
            category=LOG_CATEGORY_VENDOR,
        )
        if fatal:
            self._fatal = True
            await self._send_error(
                message,
                ModuleErrorCode.FATAL_ERROR.value,
                vendor_code,
                once=True,
            )
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=message,
                vendor_info=ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code=vendor_code,
                    message=message,
                ),
            )
            return

        if report_error:
            await self._send_error(
                message,
                ModuleErrorCode.NON_FATAL_ERROR.value,
                vendor_code,
            )
        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message=message,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=vendor_code,
                message=message,
            ),
        )
        self.reconnect_manager.record_failed_attempt()
        if self.stopped or self._fatal:
            return
        if not self.reconnect_manager.can_retry():
            self._fatal = True
            await self._send_error(
                "StepFun reconnect attempts exhausted; transcription is incomplete",
                ModuleErrorCode.FATAL_ERROR.value,
                "reconnect_exhausted",
                once=True,
            )
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="StepFun reconnect attempts exhausted",
            )
            return
        # When already inside the recovery task, the retry loop continues after
        # start_connection() returns — do not schedule a nested successor.
        if asyncio.current_task() is self._recovery_task:
            return
        self._schedule_reconnect()

    def _classify_connect_error(self, exc: Exception) -> tuple[bool, str, str]:
        message = str(exc)
        status = _extract_http_status(exc)
        if status in {401, 403}:
            return True, str(status), message
        lower = message.lower()
        if "401" in message or "403" in message or "unauthorized" in lower:
            code = (
                "401" if "401" in message or "unauthorized" in lower else "403"
            )
            return True, code, message
        if status is not None:
            return False, str(status), message
        return False, type(exc).__name__, message

    def _schedule_reconnect(self) -> None:
        if self.stopped or self._fatal:
            return
        if self._recovery_task is not None and not self._recovery_task.done():
            self._reconnect_pending = True
            return
        self._reconnect_pending = False
        task = asyncio.create_task(self._reconnect_loop())
        self._recovery_task = task

        def _clear(done_task: asyncio.Task[None]) -> None:
            if self._recovery_task is not done_task:
                return
            self._recovery_task = None
            pending = self._reconnect_pending
            self._reconnect_pending = False
            if (
                pending
                and not self.stopped
                and not self._fatal
                and not self.is_connected()
            ):
                self._schedule_reconnect()

        task.add_done_callback(_clear)

    async def _reconnect_loop(self) -> None:
        """Own consecutive reconnect attempts until success, fatal, or budget."""
        while not self.stopped and not self._fatal:
            delay = self.reconnect_manager.next_delay()
            if delay:
                await asyncio.sleep(delay)
            if self.stopped or self._fatal:
                return
            active = self._connect_task
            if (
                active is not None
                and active is not asyncio.current_task()
                and not active.done()
            ):
                # Defer until the original attempt finishes; do not spin.
                with suppress(BaseException):
                    await active
                if self.is_connected() or self.stopped or self._fatal:
                    return
                continue
            # Re-enter through the public hook so connecting is reported again.
            await self.start_connection()
            if self.is_connected() or self._fatal:
                return
            if not self.reconnect_manager.can_retry():
                return
            # Another failed attempt was recorded; continue the same owner.

    @override
    async def stop_connection(self) -> None:
        self._connect_attempt += 1
        if (
            self._buffer_flush_task is not None
            and self._buffer_flush_task is not asyncio.current_task()
        ):
            self._buffer_flush_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._buffer_flush_task
        self._buffer_flush_task = None
        for task in (
            self._recovery_task,
            self._input_task,
            self._connect_task,
        ):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        self._recovery_task = None
        self._input_task = None
        self._connect_task = None
        if self.recognition:
            await self.recognition.shutdown()

    @override
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if data.get_name() != "asr_finalize":
            await super().on_data(ten_env, data)
            return

        # Capture finalize fields and enqueue the boundary in input order
        # before waiting on result-output serialization. Holding the result
        # lock first would let later audio overtake the finalize tuple.
        finalize_id, finalize_error = data.get_property_string("finalize_id")
        if finalize_error:
            ten_env.log_error(
                f"asr_finalize: failed to get finalize_id: {finalize_error}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            return

        # Finalize metadata is optional. Do not snapshot self.metadata here —
        # it can lag behind audio still waiting on audio_frames_queue. When
        # omitted, resolve inheritance at the queue boundary after prior frames.
        provided: dict[str, Any] | None = None
        metadata_json, metadata_error = data.get_property_to_json("metadata")
        if not metadata_error and metadata_json:
            parsed = json.loads(metadata_json)
            if not isinstance(parsed, dict):
                raise ValueError("StepFun finalize metadata must be an object")
            if parsed:
                provided = copy.deepcopy(parsed)

        inherit_metadata = provided is None
        context = copy.deepcopy(provided) if provided is not None else {}
        received_at = asyncio.get_running_loop().time()
        self._enqueue_finalize_boundary(
            finalize_id,
            received_at,
            context,
            inherit_metadata=inherit_metadata,
        )

        # Install mutable context only after the boundary is queued, and only
        # while no in-flight result is emitting metrics from these fields.
        # Inherited metadata is installed later in _handle_finalize.
        async with self._result_context_lock:
            if provided is not None:
                self.metadata = copy.deepcopy(provided)
                self.session_id = self.metadata.get(
                    "session_id", self.session_id
                )
            self.finalize_id = finalize_id
            self.last_finalize_time = received_at

        # Required base hook (§4.1). Base finalize() waits on the pre-queued
        # boundary instead of enqueuing a second time.
        await super().on_data(ten_env, data)

    @override
    async def _audio_frame_consumer(self) -> None:
        self._input_task = asyncio.current_task()
        while not self.stopped:
            try:
                item = await self.audio_frames_queue.get()
                if isinstance(item, AudioFrame):
                    if self._fatal:
                        parsed = self._metadata_from_audio_frame(item)
                        if parsed is not None:
                            self._fatal_discarded_frame_metadata = parsed
                        continue
                    await self._handle_audio_frame(self.ten_env, item)
                    continue
                finalize_id, received_at, metadata = item
                if self._fatal:
                    emit_metadata = await self._resolve_finalize_emit_context(
                        finalize_id, metadata
                    )
                    await self._finish_finalize(
                        finalize_id,
                        "StepFun ASR is in a fatal error state",
                        metadata=emit_metadata,
                    )
                    continue
                await self._handle_finalize(finalize_id, received_at, metadata)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._fatal = True
                await self._send_error(
                    str(exc),
                    ModuleErrorCode.FATAL_ERROR.value,
                    "input_processing",
                    once=True,
                )

    def _enqueue_finalize_boundary(
        self,
        finalize_id: str,
        received_at: float,
        metadata: dict[str, Any],
        *,
        inherit_metadata: bool = False,
    ) -> None:
        """Queue a finalize tuple once, preserving input order vs audio.

        Empty-string finalize_id is a valid echoed id and must still get a
        boundary plus exactly one asr_finalize_end.
        """
        if finalize_id in self._finalize_events:
            return
        context = copy.deepcopy(metadata)
        self._finalize_contexts[finalize_id] = context
        self._finalize_times[finalize_id] = received_at
        self._finalize_events[finalize_id] = asyncio.Event()
        if inherit_metadata:
            self._finalize_inherit_metadata.add(finalize_id)
        else:
            self._finalize_inherit_metadata.discard(finalize_id)
        self.audio_frames_queue.put_nowait((finalize_id, received_at, context))

    def _resolve_finalize_metadata(
        self,
        finalize_id: str,
        metadata: dict[str, Any],
        *,
        use_journal_context: bool = True,
    ) -> dict[str, Any]:
        """Resolve finalize metadata after preceding audio has been consumed."""
        inherit = finalize_id in self._finalize_inherit_metadata
        if not inherit and metadata:
            resolved = copy.deepcopy(metadata)
            known_session = resolved.get("session_id", self.session_id)
            if known_session is None and self.recognition is not None:
                known_session = (
                    self.recognition._current.session_id  # pylint: disable=protected-access
                )
            return self._metadata_with_session(resolved, known_session)

        resolved = copy.deepcopy(self.metadata) if self.metadata else {}
        if use_journal_context and self.recognition is not None:
            current = self.recognition._current  # pylint: disable=protected-access
            if current.metadata:
                resolved = copy.deepcopy(current.metadata)
            elif current.session_id is not None:
                resolved = {**resolved, "session_id": current.session_id}
        if not inherit and metadata:
            resolved.update(copy.deepcopy(metadata))
        return resolved

    def _metadata_from_audio_queue_before_finalize(
        self, finalize_id: str
    ) -> dict[str, Any] | None:
        """Read frame metadata queued before a finalize tuple (no dequeuing).

        Returns None when the finalize tuple is not present (already dequeued).
        """
        inherited: dict[str, Any] = {}
        found = False
        for item in self.audio_frames_queue._queue:  # noqa: SLF001 pylint: disable=protected-access
            if isinstance(item, AudioFrame):
                parsed = self._metadata_from_audio_frame(item)
                if parsed is not None:
                    inherited = parsed
                continue
            queued_id, _, _queued_meta = item
            if queued_id == finalize_id:
                found = True
                break
        if not found:
            return None
        return inherited

    async def _resolve_finalize_emit_context(
        self,
        finalize_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve omitted finalize metadata for emit-only fallback paths."""
        async with self._result_context_lock:
            previous_metadata = self.metadata
            previous_session_id = self.session_id
            try:
                queued = self._metadata_from_audio_queue_before_finalize(
                    finalize_id
                )
                if queued is None:
                    source = (
                        copy.deepcopy(self._fatal_discarded_frame_metadata)
                        if self._fatal_discarded_frame_metadata
                        else {}
                    )
                elif queued:
                    source = queued
                elif self._fatal_discarded_frame_metadata:
                    source = copy.deepcopy(self._fatal_discarded_frame_metadata)
                else:
                    source = {}
                if source:
                    self.metadata = copy.deepcopy(source)
                    self.session_id = source.get("session_id", self.session_id)
                return self._resolve_finalize_metadata(
                    finalize_id,
                    metadata,
                    use_journal_context=False,
                )
            finally:
                self.metadata = previous_metadata
                self.session_id = previous_session_id

    @override
    async def finalize(self, _session_id: str | None) -> None:
        # Preserve "" — do not coerce with `or`, which would drop a valid empty id.
        finalize_id = self.finalize_id if self.finalize_id is not None else ""
        received_at = self._finalize_times.get(finalize_id)
        if received_at is None:
            received_at = (
                self.last_finalize_time
                if self.last_finalize_time is not None
                else asyncio.get_running_loop().time()
            )
        # Fallback path only; on_data normally pre-queues with inherit flags.
        metadata = copy.deepcopy(self.metadata) if self.metadata else {}
        self._enqueue_finalize_boundary(
            finalize_id,
            received_at,
            metadata,
            inherit_metadata=not metadata,
        )
        done = self._finalize_events.get(finalize_id)
        if done is None:
            return
        try:
            timeout = self.config.finalize_timeout if self.config else 10.0
            loop = asyncio.get_running_loop()
            elapsed = loop.time() - received_at
            remaining = timeout - elapsed
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.wait_for(done.wait(), remaining)
        except asyncio.TimeoutError:
            queued = self._finalize_contexts.get(finalize_id, metadata)
            emit_metadata = await self._resolve_finalize_emit_context(
                finalize_id, queued if queued is not None else {}
            )
            await self._finish_finalize(
                finalize_id,
                "StepFun finalize timed out",
                metadata=emit_metadata,
                timed_out=True,
            )
        finally:
            self._finalize_events.pop(finalize_id, None)
            self._finalize_times.pop(finalize_id, None)

    async def _handle_finalize(
        self,
        finalize_id: str,
        received_at: float,
        metadata: dict[str, Any],
    ) -> None:
        if finalize_id in self._completed_finalizes:
            # Timeout already completed this id; still seal/discard its audio
            # so the next turn does not inherit the open span.
            if (
                self.recognition is not None
                and self.recognition.is_finalize_timed_out(finalize_id)
            ):
                try:
                    resolved = await self._prepare_finalize_context(
                        finalize_id,
                        metadata,
                        register_context=False,
                    )
                    recognition = self.recognition
                    session_id = resolved.get("session_id", self.session_id)
                    if recognition is not None:
                        await recognition.commit(
                            finalize_id,
                            received_at,
                            metadata=resolved,
                            session_id=session_id,
                        )
                finally:
                    self._finalize_contexts.pop(finalize_id, None)
            return

        async with self._result_context_lock:
            self.finalize_id = finalize_id
            self.last_finalize_time = received_at
        resolved = await self._prepare_finalize_context(finalize_id, metadata)
        recognition = self.recognition
        session_id = resolved.get("session_id", self.session_id)

        if recognition is None:
            await self._finish_finalize(
                finalize_id,
                "StepFun recognition is unavailable",
                metadata=resolved,
            )
            return

        await recognition.commit(
            finalize_id,
            received_at,
            metadata=resolved,
            session_id=session_id,
        )

    async def _prepare_finalize_context(
        self,
        finalize_id: str,
        metadata: dict[str, Any],
        *,
        register_context: bool = True,
    ) -> dict[str, Any]:
        """Absorb buffered audio, then resolve omitted finalize metadata."""
        async with self._result_context_lock:
            provisional = (
                copy.deepcopy(metadata)
                if metadata
                else (copy.deepcopy(self.metadata) if self.metadata else {})
            )
            session_for_absorb = provisional.get("session_id", self.session_id)
        await self._absorb_buffered_frames(
            metadata=provisional,
            session_id=session_for_absorb,
        )
        async with self._result_context_lock:
            resolved = self._resolve_finalize_metadata(finalize_id, metadata)
            self.metadata = copy.deepcopy(resolved)
            self.session_id = resolved.get("session_id", self.session_id)
            if register_context:
                self._finalize_contexts[finalize_id] = copy.deepcopy(resolved)
            self._finalize_inherit_metadata.discard(finalize_id)
            return resolved

    async def _absorb_buffered_frames(
        self,
        *,
        metadata: dict[str, Any],
        session_id: str | None,
    ) -> None:
        """Move base-class buffered frames into the transport journal."""
        while True:
            try:
                frame = self.buffered_frames.get_nowait()
            except asyncio.QueueEmpty:
                self.buffered_frames_size = 0
                return
            if await self._consume_buffered_frame(
                frame,
                metadata=metadata,
                session_id=session_id,
            ):
                continue
            self.buffered_frames.put_nowait(frame)
            return

    async def _consume_buffered_frame(
        self,
        frame: AudioFrame,
        *,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Journal a buffered frame; True means the frame must not be requeued."""
        if self.recognition is None:
            return False
        frame_len = len(frame.get_buf())
        tail_before = self.recognition.journal_tail
        await self.send_audio(frame, session_id, fallback_metadata=metadata)
        if self.recognition.journal_tail > tail_before:
            self.buffered_frames_size = max(
                0, self.buffered_frames_size - frame_len
            )
            return True
        return False

    async def _finish_finalize(
        self,
        finalize_id: str,
        error: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        timed_out: bool = False,
    ):
        lock = self._finalize_locks.setdefault(finalize_id, asyncio.Lock())
        async with lock:
            # Claim completion before any await so timeout/final races cannot
            # emit asr_finalize_end twice for the same finalize_id.
            if finalize_id in self._completed_finalizes:
                return
            self._remember_completed_finalize(finalize_id)
            finalize_time = self._finalize_times.get(finalize_id)
            if timed_out and self.recognition is not None:
                self.recognition.mark_finalize_timed_out(finalize_id)
            if error:
                await self._send_error(
                    error,
                    ModuleErrorCode.NON_FATAL_ERROR.value,
                    "finalize_timeout" if timed_out else "finalize_error",
                )

            context = metadata
            if context is None:
                context = self._finalize_contexts.get(finalize_id)
            if finalize_id in self._finalize_inherit_metadata or not context:
                context = await self._resolve_finalize_emit_context(
                    finalize_id, context if context is not None else {}
                )
            elif context is None:
                context = copy.deepcopy(self.metadata) if self.metadata else {}
            emit_metadata = copy.deepcopy(context) if context else {}
            emit_metadata = self._metadata_with_session(
                emit_metadata,
                emit_metadata.get("session_id", self.session_id),
            )
            async with self._result_context_lock:
                previous_finalize_id = self.finalize_id
                previous_metadata = self.metadata
                try:
                    self.finalize_id = finalize_id
                    self.metadata = emit_metadata
                    event = self._finalize_events.get(finalize_id)
                    if event:
                        event.set()
                    await self.send_asr_finalize_end()
                finally:
                    if self.metadata is emit_metadata:
                        self.metadata = previous_metadata
                    if self.finalize_id == finalize_id:
                        self.finalize_id = previous_finalize_id
                        if (
                            finalize_time is None
                            or self.last_finalize_time == finalize_time
                        ):
                            self.last_finalize_time = None

            self._finalize_contexts.pop(finalize_id, None)
            self._finalize_inherit_metadata.discard(finalize_id)
            self._finalize_locks.pop(finalize_id, None)
            self._fatal_discarded_frame_metadata = None

    def _remember_completed_finalize(self, finalize_id: str) -> None:
        self._completed_finalizes[finalize_id] = None
        while len(self._completed_finalizes) > _MAX_COMPLETED_FINALIZES:
            self._completed_finalizes.popitem(last=False)

    async def _check_complete(self, data: Data) -> None:
        check_id, error = data.get_property_string("check_id")
        if error:
            raise ValueError("StepFun completion check requires check_id")
        complete = (
            self.recognition is not None
            and self.recognition.recovery_complete()
        )
        response = Data.create("asr_check_complete_end")
        response.set_property_from_json(
            "",
            json.dumps({"check_id": check_id, "complete": complete}),
        )
        await self.ten_env.send_data(response)

    @override
    async def _handle_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        frame_buf = audio_frame.get_buf()
        if not frame_buf:
            ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        if not self._safe_is_connected():
            if self.auto_connect or self._connection_requested:
                ten_env.log_debug("send_frame: service not connected.")
            buffer_strategy = self.buffer_strategy()
            if isinstance(buffer_strategy, ASRBufferConfigModeKeep):
                byte_limit = buffer_strategy.byte_limit
                while self.buffered_frames_size + len(frame_buf) > byte_limit:
                    if self.buffered_frames.empty():
                        break
                    discard_frame = await self.buffered_frames.get()
                    discarded_len = len(discard_frame.get_buf())
                    self.buffered_frames_size -= discarded_len
                    self.audio_timeline.add_dropped_audio(discarded_len)
                self.buffered_frames.put_nowait(audio_frame)
                self.buffered_frames_size += len(frame_buf)
            else:
                self.audio_timeline.add_dropped_audio(len(frame_buf))
            return

        async with self._result_context_lock:
            metadata, _ = audio_frame.get_property_to_json(
                PROPERTY_KEY_METADATA
            )
            if metadata:
                try:
                    metadata_json = json.loads(metadata)
                    self.metadata = metadata_json
                    self.session_id = metadata_json.get(
                        PROPERTY_KEY_SESSION_ID, self.session_id
                    )
                except json.JSONDecodeError as exc:
                    ten_env.log_warn(
                        f"send_frame: invalid metadata json - {exc}"
                    )

        if self.buffered_frames.qsize() > 0:
            ten_env.log_debug(
                f"send_frame: flushing {self.buffered_frames.qsize()} buffered frames."
            )
            while True:
                try:
                    buffered_frame = self.buffered_frames.get_nowait()
                    await self.send_audio(buffered_frame, self.session_id)
                except asyncio.QueueEmpty:
                    break
            self.buffered_frames_size = 0

        success = await self.send_audio(audio_frame, self.session_id)
        if success:
            self.sent_buffer_length += len(frame_buf)
            if self.first_audio_time is None:
                self.first_audio_time = asyncio.get_running_loop().time()

    @override
    async def send_audio(
        self,
        frame: AudioFrame,
        _session_id: str | None,
        *,
        fallback_metadata: dict[str, Any] | None = None,
    ) -> bool:
        if self.recognition is None:
            return False
        async with self._result_context_lock:
            metadata_json, error = frame.get_property_to_json("metadata")
            parsed = None
            if not error and metadata_json:
                parsed = json.loads(metadata_json)
                if isinstance(parsed, dict):
                    self.metadata = copy.deepcopy(parsed)
                    self.session_id = parsed.get("session_id", _session_id)
            if not isinstance(parsed, dict) and fallback_metadata is not None:
                self.metadata = copy.deepcopy(fallback_metadata)
                self.session_id = _session_id
            metadata_for_vendor = (
                copy.deepcopy(self.metadata)
                if self.metadata is not None
                else None
            )
            session_for_vendor = self.session_id
        buf = frame.lock_buf()
        try:
            audio_data = bytes(buf)
        finally:
            frame.unlock_buf(buf)
        if not audio_data:
            return True
        # Journal before dump so finalize cannot observe a frame that left the
        # base buffer but is not yet in the recovery journal.
        delivered = await self.recognition.send_audio(
            audio_data,
            metadata=metadata_for_vendor,
            session_id=session_for_vendor,
        )
        if self.audio_dumper:
            await self.audio_dumper.push_bytes(audio_data)
        return delivered

    @override
    def is_connected(self) -> bool:
        return bool(self.recognition and self.recognition.is_connected())

    @override
    def input_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 16000

    @override
    def input_audio_channels(self) -> int:
        return self.config.channels if self.config else 1

    @override
    def input_audio_sample_width(self) -> int:
        return self.config.bits // 8 if self.config else 2

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=10 * 1024 * 1024)

    async def on_open(self) -> None:
        if self.stopped or self._fatal:
            if self.recognition:
                await self.recognition.shutdown()
            return
        self.reconnect_manager.mark_connection_successful()
        await self.on_connected()
        if self._connect_started_at is not None:
            await self.send_connect_delay_metrics(
                max(
                    1, int((time.monotonic() - self._connect_started_at) * 1000)
                )
            )
        self.ten_env.log_info(
            "vendor_status_changed: StepFun connection opened",
            category=LOG_CATEGORY_VENDOR,
        )
        ready = Data.create("asr_ready")
        ready.set_property_from_json(
            "",
            json.dumps(
                {
                    "vendor": self.vendor(),
                    "model": self.config.model if self.config else "",
                }
            ),
        )
        await self.ten_env.send_data(ready)
        if self.buffered_frames.qsize() > 0:
            self._buffer_flush_task = asyncio.create_task(
                self._flush_buffered_frames()
            )

    async def _flush_buffered_frames(self) -> None:
        """Flush frames held by the base class during a connection outage."""
        try:
            while True:
                try:
                    frame = self.buffered_frames.get_nowait()
                except asyncio.QueueEmpty:
                    self.buffered_frames_size = 0
                    return
                if await self._consume_buffered_frame(frame):
                    continue
                self.buffered_frames.put_nowait(frame)
                return
        except Exception as exc:
            self.ten_env.log_error(
                f"StepFun buffered audio flush failed: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )

    async def on_audio_sent(self, total_bytes: int) -> None:
        if self.recognition is None:
            return
        duration_ms = total_bytes * 1000 // self.recognition.bytes_per_second
        current = self.audio_timeline.total_user_audio_duration
        self.audio_timeline.add_user_audio(max(0, duration_ms - current))
        self.sent_buffer_length = total_bytes
        if self.first_audio_time is None:
            self.first_audio_time = asyncio.get_running_loop().time()

    async def on_result(
        self,
        message: dict[str, Any],
        segment: TranscriptSegment,
    ) -> None:
        final = str(message.get("type") or "").endswith(".completed")
        text = (
            str(message.get("transcript") or "")
            if final
            else str(message.get("text") or "")
            + str(message.get("stash") or "")
        )
        if text:
            words = self._build_words(message, final)
            if words:
                start_ms = words[0].start_ms
                end_ms = words[-1].start_ms + words[-1].duration_ms
            else:
                start_ms = self._timeline_ms(segment.start)
                end_ms = self._timeline_ms(segment.end or segment.start)
            duration_ms = max(0, int(end_ms) - start_ms)
            # Serialize against finalize/input so awaited metrics helpers cannot
            # observe another turn's mutable metadata/finalize timestamp.
            async with self._result_context_lock:
                previous_metadata = self.metadata
                previous_session = self.session_id
                previous_finalize_time = self.last_finalize_time
                previous_finalize_id = self.finalize_id
                try:
                    if segment.metadata:
                        self.metadata = self._metadata_with_session(
                            segment.metadata,
                            segment.session_id,
                        )
                    elif segment.session_id is not None:
                        # Server-VAD spans may only have session_id stamped.
                        # Empty metadata dict must not block this fallback.
                        self.metadata = {"session_id": segment.session_id}
                    if segment.session_id is not None:
                        self.session_id = segment.session_id
                    if segment.finalize_id is not None:
                        self.finalize_id = segment.finalize_id
                    if segment.timed_out:
                        # Timed-out segments must not consume the next turn's TTLW.
                        self.last_finalize_time = None
                    elif final and segment.finalize_time is not None:
                        self.last_finalize_time = segment.finalize_time
                    elif final:
                        # Automatic VAD finals must not consume another turn's
                        # finalize timestamp.
                        self.last_finalize_time = None
                    if segment.result_id is None:
                        segment.result_id = self._get_uuid()
                    self.uuid = segment.result_id
                    asr_result = ASRResult(
                        text=text,
                        final=final,
                        start_ms=max(0, start_ms),
                        duration_ms=max(0, duration_ms),
                        language=_normalize_language(
                            str(
                                message.get("language")
                                or (
                                    self.config.language
                                    if self.config
                                    else "en"
                                )
                            )
                        ),
                        words=words,
                        metadata={
                            "asr_info": {
                                "vendor": self.vendor(),
                                "model": (
                                    self.config.model if self.config else ""
                                ),
                                "provider_item_id": message.get("item_id", ""),
                                "finalize_id": segment.finalize_id,
                                "contains_stash": (
                                    bool(message.get("stash"))
                                    if not final
                                    else False
                                ),
                            }
                        },
                    )
                    await self.send_asr_result(asr_result)
                finally:
                    self.metadata = previous_metadata
                    self.session_id = previous_session
                    self.finalize_id = previous_finalize_id
                    # Keep an active turn's consumed TTLW timestamp cleared, but
                    # restore a newer turn when publishing an older late result.
                    if (
                        final
                        and not segment.timed_out
                        and segment.finalize_id is not None
                        and previous_finalize_id == segment.finalize_id
                    ):
                        pass
                    else:
                        self.last_finalize_time = previous_finalize_time
        if final and segment.finalize_id is not None and not segment.timed_out:
            await self._finish_finalize(
                segment.finalize_id,
                metadata=segment.metadata,
            )

    def _timeline_ms(self, byte_offset: int) -> int:
        if self.recognition is None:
            return 0
        provider_ms = int(
            byte_offset * 1000 / self.recognition.bytes_per_second
        )
        available_ms = (
            self.audio_timeline.total_user_audio_duration
            + self.audio_timeline.total_silence_audio_duration
        )
        if provider_ms > available_ms:
            return (
                provider_ms + self.audio_timeline.total_dropped_audio_duration
            )
        return self.audio_timeline.get_audio_duration_before_time(provider_ms)

    def _build_words(
        self, message: dict[str, Any], stable: bool
    ) -> list[ASRWord]:
        offset = float(message.get("audio_offset_ms") or 0)
        result = []
        for word in message.get("words") or []:
            provider_start_ms = int(
                offset + float(word.get("start") or 0) * 1000
            )
            provider_end_ms = int(offset + float(word.get("end") or 0) * 1000)
            start_ms = self._provider_time_to_timeline(provider_start_ms)
            end_ms = self._provider_time_to_timeline(provider_end_ms)
            result.append(
                ASRWord(
                    word=str(word.get("word") or ""),
                    start_ms=max(0, start_ms),
                    duration_ms=max(0, end_ms - start_ms),
                    stable=stable,
                )
            )
        return result

    def _provider_time_to_timeline(self, provider_ms: int) -> int:
        available_ms = (
            self.audio_timeline.total_user_audio_duration
            + self.audio_timeline.total_silence_audio_duration
        )
        if provider_ms > available_ms:
            return (
                provider_ms + self.audio_timeline.total_dropped_audio_duration
            )
        return self.audio_timeline.get_audio_duration_before_time(provider_ms)

    async def on_error(
        self,
        message: str,
        error_type: str = "",
        error_code: str = "",
    ) -> None:
        fatal = error_type in {
            "auth",
            "invalid_request_error",
            "invalid_value",
            "missing_param",
            "risk_blocked",
            "invalid_response",
        } or error_code in {"401", "403"}
        if fatal:
            self._fatal = True
        code = (
            ModuleErrorCode.FATAL_ERROR.value
            if fatal
            else ModuleErrorCode.NON_FATAL_ERROR.value
        )
        await self._send_error(
            message,
            code,
            error_code or error_type or "unknown",
            once=fatal,
        )
        if fatal:
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=message,
            )

    async def on_close(self) -> None:
        if self.stopped or self._fatal:
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value if self._fatal else 0,
                message="StepFun connection closed",
            )
            return
        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message="StepFun connection closed",
        )
        self._schedule_reconnect()

    async def _send_error(
        self,
        message: str,
        code: int,
        vendor_code: str,
        *,
        once: bool = False,
    ) -> None:
        if once and self._fatal_error_sent:
            return
        if once:
            self._fatal_error_sent = True
        await self.send_asr_error(
            ModuleError(module=MODULE_NAME_ASR, code=code, message=message),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(vendor_code),
                message=message,
            ),
        )


def _extract_http_status(exc: Exception) -> int | None:
    if isinstance(exc, InvalidStatus):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return int(status) if status is not None else None
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return int(status)
    status = getattr(exc, "status_code", None)
    return int(status) if status is not None else None


def _normalize_language(language: str) -> str:
    return {
        "en": "en-US",
        "zh": "zh-CN",
        "ja": "ja-JP",
        "ko": "ko-KR",
    }.get(language, language)
