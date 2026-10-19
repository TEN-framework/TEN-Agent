from __future__ import annotations

import asyncio
import copy
import json
import os
import time
from contextlib import suppress
from typing import Any

from typing_extensions import override

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
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
        self._completed_finalizes: set[str] = set()
        self._buffer_flush_task: asyncio.Task[None] | None = None

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
            self._fatal = True
            await self._send_error(
                str(exc),
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

        self._connecting = True
        try:
            connected = await self.reconnect_manager.handle_reconnect(
                self._connect_once,
                should_abort=lambda: self.stopped or self._fatal,
            )
            if not connected and not self.stopped:
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
        finally:
            self._connecting = False

    async def _connect_once(self) -> None:
        if self._fatal or self.stopped:
            raise ConnectionError("StepFun connection recovery stopped")
        assert self.recognition is not None
        self._connect_started_at = time.monotonic()
        try:
            await self.recognition.start()
        except Exception as exc:
            self.ten_env.log_warn(
                f"StepFun connection attempt failed: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    @override
    async def stop_connection(self) -> None:
        if (
            self._buffer_flush_task is not None
            and self._buffer_flush_task is not asyncio.current_task()
        ):
            self._buffer_flush_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._buffer_flush_task
        self._buffer_flush_task = None
        for task in (self._recovery_task, self._input_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        self._recovery_task = None
        self._input_task = None
        if self.recognition:
            await self.recognition.shutdown()

    @override
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if data.get_name() == "asr_finalize":
            await self.audio_frames_queue.put(
                (data.clone(), asyncio.get_running_loop().time())
            )
            return
        await super().on_data(ten_env, data)

    @override
    async def _audio_frame_consumer(self) -> None:
        self._input_task = asyncio.current_task()
        while not self.stopped:
            try:
                item = await self.audio_frames_queue.get()
                if self._fatal:
                    continue
                if isinstance(item, AudioFrame):
                    await self._handle_audio_frame(self.ten_env, item)
                else:
                    data, received_at = item
                    await self._handle_finalize(data, received_at)
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

    async def _handle_finalize(self, data: Data, received_at: float) -> None:
        finalize_id, error = data.get_property_string("finalize_id")
        if error or not finalize_id:
            raise ValueError("StepFun asr_finalize requires finalize_id")
        metadata_json, metadata_error = data.get_property_to_json("metadata")
        if not metadata_error and metadata_json:
            metadata = json.loads(metadata_json)
            if not isinstance(metadata, dict):
                raise ValueError("StepFun finalize metadata must be an object")
            self.metadata = copy.deepcopy(metadata)
            self.session_id = self.metadata.get("session_id", self.session_id)

        self.finalize_id = finalize_id
        self.last_finalize_time = received_at
        done = asyncio.Event()
        self._finalize_events[finalize_id] = done
        try:
            if self.recognition is None:
                await self._finish_finalize(
                    finalize_id,
                    "StepFun recognition is unavailable",
                )
                return
            await self.recognition.commit(finalize_id, received_at)
            try:
                await asyncio.wait_for(
                    done.wait(),
                    self.config.finalize_timeout if self.config else 10.0,
                )
            except asyncio.TimeoutError:
                await self._finish_finalize(
                    finalize_id,
                    "StepFun finalize timed out",
                )
        finally:
            self._finalize_events.pop(finalize_id, None)

    async def _finish_finalize(
        self, finalize_id: str, error: str | None = None
    ):
        if finalize_id in self._completed_finalizes:
            return
        if error:
            await self._send_error(
                error,
                ModuleErrorCode.NON_FATAL_ERROR.value,
                "finalize_timeout",
            )
        self.finalize_id = finalize_id
        self._completed_finalizes.add(finalize_id)
        event = self._finalize_events.get(finalize_id)
        if event:
            event.set()
        await self.send_asr_finalize_end()

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
    async def send_audio(
        self, frame: AudioFrame, _session_id: str | None
    ) -> bool:
        if self.recognition is None:
            return False
        metadata, error = frame.get_property_to_json("metadata")
        if not error and metadata:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                self.metadata = parsed
                self.session_id = parsed.get("session_id", self.session_id)
        buf = frame.lock_buf()
        try:
            audio_data = bytes(buf)
        finally:
            frame.unlock_buf(buf)
        if not audio_data:
            return True
        if self.audio_dumper:
            await self.audio_dumper.push_bytes(audio_data)
        return await self.recognition.send_audio(audio_data)

    @override
    async def finalize(self, _session_id: str | None) -> None:
        if self.recognition:
            await self.recognition.commit(
                self.finalize_id or "",
                asyncio.get_running_loop().time(),
            )

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
                if await self.send_audio(frame, self.session_id):
                    self.sent_buffer_length += len(frame.get_buf())
                    if self.first_audio_time is None:
                        self.first_audio_time = (
                            asyncio.get_running_loop().time()
                        )
                    self.buffered_frames_size -= len(frame.get_buf())
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
            asr_result = ASRResult(
                text=text,
                final=final,
                start_ms=max(0, start_ms),
                duration_ms=max(0, duration_ms),
                language=_normalize_language(
                    str(message.get("language") or self.config.language)
                ),
                words=words,
                metadata={
                    "asr_info": {
                        "vendor": self.vendor(),
                        "model": self.config.model if self.config else "",
                        "provider_item_id": message.get("item_id", ""),
                        "finalize_id": segment.finalize_id,
                        "contains_stash": (
                            bool(message.get("stash")) if not final else False
                        ),
                    }
                },
            )
            await self.send_asr_result(asr_result)
        if final and segment.finalize_id is not None:
            await self._finish_finalize(segment.finalize_id)

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
        if self._recovery_task is None or self._recovery_task.done():
            self._recovery_task = asyncio.create_task(self.start_connection())

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


def _normalize_language(language: str) -> str:
    return {
        "en": "en-US",
        "zh": "zh-CN",
        "ja": "ja-JP",
        "ko": "ko-KR",
    }.get(language, language)
