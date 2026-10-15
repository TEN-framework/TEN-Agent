import asyncio
import copy
import json
import os
from typing import Any, Dict

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

from .config import OrukRealtimeASRConfig
from .const import DUMP_FILE_NAME, MODEL, MODULE_NAME_ASR, SAMPLE_RATE
from .recognition import OrukRealtimeConnection, OrukRealtimeCallback

AUDIO_DRAIN_TIMEOUT_SECONDS = 10.0
IO_TIMEOUT_SECONDS = 10.0


class _FinalizeBoundary:
    def __init__(self):
        self.ready = asyncio.Event()
        self.release = asyncio.Event()


class _TurnCallback:
    """Ignore late events from a socket replaced by a later turn."""

    def __init__(self, extension, generation):
        self.extension = extension
        self.generation = generation

    def __getattr__(self, name):
        async def dispatch(*args, **kwargs):
            target = self.extension
            if not target.accepts_callback(self.generation, name):
                return
            await getattr(target, name)(*args, **kwargs)

        return dispatch


class OrukRealtimeASRExtension(AsyncASRBaseExtension, OrukRealtimeCallback):
    """Oruk realtime (streaming WebSocket) ASR for TEN.

    Streams PCM16 to Oruk's realtime API, surfacing interim transcript deltas and
    a final transcript per turn plus optional phrase-emotion estimates. The Oruk
    socket commits one turn per connection, so the extension opens a fresh
    connection for each turn and reconnects after the server closes.

    Phrase-emotion estimates describe vocal expression only; they are not
    verified assessments of a person's internal state.
    """

    def accepts_callback(self, generation: int, event: str) -> bool:
        return (
            generation == self._generation
            and not self.stopped
            and (not self._fatal or event == "on_close")
        )

    def __init__(self, name: str):
        super().__init__(name)
        self.config: OrukRealtimeASRConfig | None = None
        self.connection: OrukRealtimeConnection | None = None
        self.audio_dumper: Dumper | None = None
        self._reconnect_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._io_lock = asyncio.Lock()
        self._finalize_lock = asyncio.Lock()
        self._finalize_request_lock = asyncio.Lock()
        self._finalize_boundaries: set[_FinalizeBoundary] = set()
        self._reconnect_task = None
        self._generation = 0
        self._fatal = False
        self._init_failed = False
        self._finalize_pending = False
        self._turn_done = asyncio.Event()
        self._connect_started = 0.0
        self._ready_event = asyncio.Event()
        self._flushing = False
        # Per-turn state.
        self._phrases: list[dict[str, Any]] = []
        self._final_sent = False
        self._turn_bytes = 0
        self._emitted_ms = 0

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
            # Mark receipt before waiting for an earlier finalize request.
            # The base consumes audio separately from control messages.
            boundary = None
            queue = getattr(self, "audio_frames_queue", None)
            if queue is not None and not (
                self.stopped or self._fatal or self._init_failed
            ):
                boundary = _FinalizeBoundary()
                self._finalize_boundaries.add(boundary)
                queue.put_nowait(boundary)
            try:
                async with self._finalize_request_lock:
                    if boundary is not None and not (
                        self.stopped or self._fatal or self._init_failed
                    ):
                        try:
                            await asyncio.wait_for(
                                boundary.ready.wait(),
                                timeout=AUDIO_DRAIN_TIMEOUT_SECONDS,
                            )
                        except asyncio.TimeoutError:
                            await self.on_error(
                                "Oruk audio drain timed out",
                                "drain_timeout",
                                True,
                            )
                    self._capture_metadata(data)
                    await super().on_data(ten_env, data)
            finally:
                if boundary is not None:
                    boundary.release.set()
                    self._finalize_boundaries.discard(boundary)
            return
        await super().on_data(ten_env, data)

    async def _handle_audio_frame(self, ten_env, audio_frame):
        if isinstance(audio_frame, _FinalizeBoundary):
            audio_frame.ready.set()
            # Hold later frames until the final result/ack has used this turn's
            # metadata; future audio can then enter the next socket's buffer.
            await audio_frame.release.wait()
            return
        await super()._handle_audio_frame(ten_env, audio_frame)

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
        fields = {
            "key": self.config.api_key,
            "url": self.config.url,
            "model": MODEL,
        }
        # The base class redacts sensitive fields before reporting.
        return {k: v for k, v in fields.items() if v}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        config_json, _ = await ten_env.get_property_to_json("")
        try:
            self.config = OrukRealtimeASRConfig.model_validate_json(config_json)
            self.config.validate_config()
            ten_env.log_info(
                f"config: {self.config.to_json(sensitive_handling=True)}",
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
            self.config = OrukRealtimeASRConfig.model_validate_json("{}")
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
        await self.stop_connection()
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    async def start_connection(self) -> None:
        if self._init_failed or self._fatal or self.stopped:
            await self.on_disconnected(code=0, message="connection disabled")
            return
        async with self._connect_lock:
            if self._init_failed or self._fatal or self.stopped:
                await self.on_disconnected(
                    code=0, message="connection disabled"
                )
                return
            if self.is_connected():
                await self.on_connected()
                return
            assert self.config is not None
            await self._close_current()
            self._generation += 1
            generation = self._generation
            self._reset_turn()
            self._ready_event.clear()
            self._flushing = True
            self._turn_done.clear()
            self._connect_started = asyncio.get_running_loop().time()
            connection = OrukRealtimeConnection(
                api_key=self.config.api_key,
                url=self.config.url,
                language=self.config.language,
                phrase_emotions=self.config.phrase_emotions,
                diarize=self.config.diarize,
                sample_rate=self.config.sample_rate,
                callback=_TurnCallback(self, generation),
                ten_env=self.ten_env,
            )
            self.connection = connection
            try:
                await connection.start(request_id=self.uuid)
                if self.stopped or generation != self._generation:
                    await connection.close()
                    if self.connection is connection:
                        self.connection = None
            except asyncio.CancelledError:
                await connection.close()
                if self.connection is connection:
                    self.connection = None
                raise
            except Exception as exc:
                await connection.close()
                if self.connection is connection:
                    self.connection = None
                if self.stopped or generation != self._generation:
                    return
                status = getattr(exc, "status", None)
                await self.on_error(
                    "Oruk connection failed",
                    str(status or "connect_failed"),
                    status in {401, 403},
                )
                await self.on_disconnected(code=0, message="connect failed")
                self._schedule_reconnect()

    @override
    def is_connected(self) -> bool:
        return (
            not self._fatal
            and not self._flushing
            and not self.stopped
            and self.connection is not None
            and self.connection.is_connected()
        )

    async def _close_current(self) -> None:
        self._ready_event.set()
        self._generation += 1
        async with self._io_lock:
            connection, self.connection = self.connection, None
        if connection is not None:
            await connection.close()

    @override
    async def stop_connection(self) -> None:
        for boundary in self._finalize_boundaries:
            boundary.ready.set()
            boundary.release.set()
        task, self._reconnect_task = self._reconnect_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._close_current()
        await self._finish_finalize()

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.sample_rate

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        # Hold audio while the next turn's socket is (re)connecting.
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    async def send_audio(
        self, frame: AudioFrame, _session_id: str | None
    ) -> bool:
        async with self._io_lock:
            connection = self.connection
            if connection is None or not connection.is_connected():
                return False
            self._capture_metadata(frame, _session_id)
            buf = frame.lock_buf()
            try:
                audio_data = bytes(buf)
                await asyncio.wait_for(
                    connection.send_pcm(audio_data), timeout=IO_TIMEOUT_SECONDS
                )
                self._turn_bytes += len(audio_data)
                self.audio_timeline.add_user_audio(
                    len(audio_data) / 2 / self.config.sample_rate * 1000
                )
                if self.audio_dumper:
                    try:
                        await asyncio.wait_for(
                            self.audio_dumper.push_bytes(audio_data),
                            timeout=IO_TIMEOUT_SECONDS,
                        )
                    except Exception:
                        self.ten_env.log_error("Audio diagnostic dump failed")
                return True
            except Exception:
                await self.on_error(
                    "Oruk audio send failed", "send_failed", False
                )
                return False
            finally:
                frame.unlock_buf(buf)

    @override
    async def finalize(self, _session_id: str | None) -> None:
        async with self._finalize_lock:
            callback_owned = False
            generation = None
            requested_generation = self._generation
            turn_done = self._turn_done
            buffered_turn = not self.buffered_frames.empty() or self._flushing
            try:
                # Queue consumption can leave earlier audio in the disconnected
                # buffer. Wait for on_open to flush it, then select that socket
                # generation, rather than abandoning the request on reconnect.
                connection = await asyncio.wait_for(
                    self._connection_for_finalize(), timeout=IO_TIMEOUT_SECONDS
                )
                if connection is None:
                    return
                if (
                    self._generation != requested_generation
                    and not buffered_turn
                ):
                    return
                async with self._io_lock:
                    if (
                        self.connection is not connection
                        or not self.is_connected()
                    ):
                        raise asyncio.TimeoutError
                    generation = self._generation
                    turn_done = self._turn_done
                    # Previous-socket callbacks cannot acknowledge this request
                    # while it is still waiting for the next ready connection.
                    self._finalize_pending = True
                    callback_owned = True
                    await asyncio.wait_for(
                        connection.commit(), timeout=IO_TIMEOUT_SECONDS
                    )
                await asyncio.wait_for(
                    turn_done.wait(), timeout=IO_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                if generation is not None and generation != self._generation:
                    return
                await self.on_error(
                    "Oruk finalization timed out", "finalize_timeout", False
                )
                # The boundary prevents later-turn audio entering this buffer.
                # A failed turn must not be replayed as part of the next one.
                while not self.buffered_frames.empty():
                    self.buffered_frames.get_nowait()
                self.buffered_frames_size = 0
                await self._close_current()
                await self.on_disconnected(code=0, message="finalize timeout")
                self._schedule_reconnect()
            finally:
                if callback_owned:
                    await self._finish_finalize(turn_done)
                else:
                    await self.send_asr_finalize_end()

    async def _connection_for_finalize(self):
        while not self.is_connected():
            if self.stopped or self._fatal or self._init_failed:
                return None
            if self.connection is None:
                if self.buffered_frames.empty():
                    return None
                self._schedule_reconnect()
            self._ready_event.clear()
            await self._ready_event.wait()
        return self.connection

    async def _finish_finalize(self, turn_done=None) -> None:
        (turn_done if turn_done is not None else self._turn_done).set()
        if self._finalize_pending:
            self._finalize_pending = False
            await self.send_asr_finalize_end()

    # ---- Vendor callbacks (OrukRealtimeCallback) ----

    @override
    async def on_open(self) -> None:
        self.ten_env.log_info(
            "Oruk realtime connection opened", category=LOG_CATEGORY_VENDOR
        )
        await self.on_connected()
        await self._flush_buffered_audio()
        self._flushing = False
        self._ready_event.set()
        await self.send_connect_delay_metrics(
            int(
                (asyncio.get_running_loop().time() - self._connect_started)
                * 1000
            )
        )

    @override
    async def on_interim(self, text: str) -> None:
        await self.send_asr_result(
            ASRResult(
                text=text,
                final=False,
                start_ms=self._emitted_ms,
                duration_ms=self._turn_duration_ms(),
                language=self.config.asr_result_language if self.config else "",
                words=[],
                metadata=self._build_metadata(),
            )
        )

    @override
    async def on_final(self, text: str) -> None:
        if self._final_sent:
            return
        self._final_sent = True
        duration_ms = self._turn_duration_ms()
        if not text.strip():
            self._emitted_ms += duration_ms
            await self._finish_finalize()
            return
        await self.send_asr_result(
            ASRResult(
                text=text,
                final=True,
                start_ms=self._emitted_ms,
                duration_ms=duration_ms,
                language=self.config.asr_result_language if self.config else "",
                words=[],
                metadata=self._build_metadata(with_phrases=True),
            )
        )
        self._emitted_ms += duration_ms
        await self._finish_finalize()

    @override
    async def on_phrase_emotion(self, event: dict[str, Any]) -> None:
        self._phrases.append(event)
        # Emotions that arrive after the final transcript are reported as vendor
        # metrics so they are not lost while keeping the text result immutable.
        if self._final_sent:
            await self.send_vendor_metrics({"phrase_emotion": event})

    @override
    async def on_usage(self, usage: dict[str, Any]) -> None:
        await self.send_vendor_metrics({"usage": usage})

    @override
    async def on_error(
        self, message: str, code: str | None, fatal: bool
    ) -> None:
        if fatal:
            self._fatal = True
        self.ten_env.log_error(
            f"vendor_error: code={code}",
            category=LOG_CATEGORY_VENDOR,
        )
        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=str(code) if code else "unknown",
            message=message,
        )
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=(
                    ModuleErrorCode.FATAL_ERROR.value
                    if fatal
                    else ModuleErrorCode.NON_FATAL_ERROR.value
                ),
                message=message,
            ),
            vendor_info,
        )
        if fatal:
            await self._close_current()
            await self._finish_finalize()
            await self.on_disconnected(code=0, message="fatal vendor error")

    @override
    async def on_close(self, code: int, message: str) -> None:
        # Transport cleanup precedes callback delivery in the client.
        self.connection = None
        self._ready_event.set()
        if not self._final_sent:
            self._emitted_ms += self._turn_duration_ms()
        await self._finish_finalize()
        await self.on_disconnected(code=code, message=message)
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self.stopped or self._fatal or self._init_failed:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reopen())

    async def _reopen(self) -> None:
        async with self._reconnect_lock:
            for attempt in range(5):
                if self.stopped or self._fatal or self.is_connected():
                    return
                if attempt:
                    await asyncio.sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
                await self.start_connection()
                if self.is_connected():
                    return
            if not self.stopped and not self._fatal:
                await self.on_error(
                    "Oruk reconnect retry limit reached", "retry_limit", True
                )

    # ---- helpers ----

    def _reset_turn(self) -> None:
        # A waiting finalize retains the completed turn's event even when the
        # next connection opens before its coroutine resumes.
        self._turn_done = asyncio.Event()
        self._phrases = []
        self._final_sent = False
        self._turn_bytes = 0

    def _turn_duration_ms(self) -> int:
        rate = self.config.sample_rate if self.config else SAMPLE_RATE
        return int(self._turn_bytes / 2 / rate * 1000)

    def _build_metadata(self, with_phrases: bool = False) -> Dict[str, Any]:
        base_metadata = copy.deepcopy(self.metadata) if self.metadata else {}
        session_id = base_metadata.pop("session_id", None)
        asr_info = base_metadata
        asr_info["vendor"] = self.vendor()
        asr_info["model"] = MODEL
        if with_phrases and self._phrases:
            asr_info["phrases"] = copy.deepcopy(self._phrases)

        metadata: Dict[str, Any] = {}
        if session_id is not None:
            metadata["session_id"] = session_id
        metadata["asr_info"] = asr_info
        return metadata
