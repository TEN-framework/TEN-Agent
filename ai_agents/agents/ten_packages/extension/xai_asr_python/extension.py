import copy
import os
import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from typing_extensions import override

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.struct import ASRWord
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_runtime import AsyncTenEnv, AudioFrame

from .config import XAIASRConfig
from .const import (
    AUDIO_BUFFER_BYTE_LIMIT,
    DUMP_FILE_NAME,
    MODULE_NAME_ASR,
    RECONNECT_MAX_ATTEMPTS,
)
from .recognition import XAIASRRecognition, XAIASRRecognitionCallback
from .reconnect_manager import ReconnectManager


class XAIASRExtension(AsyncASRBaseExtension, XAIASRRecognitionCallback):
    def __init__(self, name: str):
        super().__init__(name)
        self.recognition: XAIASRRecognition | None = None
        self.config: XAIASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset = 0
        self.last_finalize_timestamp = 0
        self.reconnect_manager: ReconnectManager | None = None
        self._stop_requested = False
        self._close_expected = False
        self._finalize_reconnect_task: asyncio.Task | None = None
        self.connection_start_timestamp = 0
        self._init_failed = False

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        self._cancel_finalize_reconnect_task()
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    def vendor(self) -> str:
        return "xai"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        # Keep retries bounded, but use a ceiling high enough that the
        # integration guarder observes the non-fatal retry behavior before
        # terminal escalation.
        self.reconnect_manager = ReconnectManager(
            logger=ten_env, max_attempts=RECONNECT_MAX_ATTEMPTS
        )
        config_json, _ = await ten_env.get_property_to_json("")
        try:
            self.config = XAIASRConfig.model_validate_json(config_json)
            self.config.apply_defaults()
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
        except Exception as e:
            ten_env.log_error(f"Invalid xAI config: {e}")
            self._init_failed = True
            self.config = XAIASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        if self._init_failed:
            # on_init already emitted a FATAL error; do not re-emit a second
            # one for the same root cause.
            return
        assert self.config is not None
        api_key = self.config.params.get("api_key", "")
        if not api_key or str(api_key).strip() == "":
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="xAI API key is required but missing or empty",
                )
            )
            return
        self._stop_requested = False
        self._close_expected = False
        try:
            await self._connect_recognition()
        except Exception as e:
            status_code = self._extract_connection_status_code(e)
            fatal = self._is_fatal_connection_error(status_code)
            self.ten_env.log_error(f"Failed to start xAI STT connection: {e}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=(
                        ModuleErrorCode.FATAL_ERROR.value
                        if fatal
                        else ModuleErrorCode.NON_FATAL_ERROR.value
                    ),
                    message=str(e),
                ),
                ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code=(
                        str(status_code)
                        if status_code is not None
                        else "connect_failed"
                    ),
                    message=str(e),
                ),
            )
            if not fatal:
                await self._handle_reconnect()

    async def _connect_recognition(self) -> None:
        assert self.config is not None
        api_key = self.config.params.get("api_key", "")
        if self.is_connected():
            await self.stop_connection()
        self.connection_start_timestamp = int(datetime.now().timestamp() * 1000)
        self.recognition = XAIASRRecognition(
            api_key=api_key,
            audio_timeline=self.audio_timeline,
            ten_env=self.ten_env,
            config=self.config.params,
            callback=self,
        )
        await self.recognition.start(timeout=10)

    @staticmethod
    def _extract_connection_status_code(error: Exception) -> int | None:
        status_code = getattr(error, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        return None

    @staticmethod
    def _is_fatal_connection_error(error_code: int | None) -> bool:
        return error_code in {401, 403}

    @override
    async def finalize(self, _session_id: str | None) -> None:
        assert self.config is not None
        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        recognition = self.recognition
        if recognition is None or not recognition.is_connected():
            self.ten_env.log_warn(
                "asr_finalize: service not connected.",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._finalize_end()
            return

        self._close_expected = True
        try:
            await recognition.send_audio_done()
            payload = await recognition.wait_for_done(
                self.config.finalize_timeout_ms
            )
            if payload and payload.get("text"):
                await self._emit_asr_result(payload, final=True, locked=False)
            elif not recognition.done_event.is_set():
                self._close_expected = False
        except asyncio.CancelledError:
            self.ten_env.log_warn(
                "asr_finalize: wait for transcript.done was cancelled.",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self._close_expected = False
        finally:
            await self._finalize_end()

    async def _finalize_end(self) -> None:
        if self.last_finalize_timestamp != 0:
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    @override
    async def stop_connection(self) -> None:
        self._stop_requested = True
        self._cancel_finalize_reconnect_task()
        if self.recognition:
            await self.recognition.close()
            self.recognition = None

    @override
    def is_connected(self) -> bool:
        return self.recognition is not None and self.recognition.is_connected()

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=AUDIO_BUFFER_BYTE_LIMIT)

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return int(self.config.params.get("sample_rate", 16000))

    @override
    async def send_audio(
        self, frame: AudioFrame, _session_id: str | None
    ) -> bool:
        if self.recognition is None or not self.is_connected():
            return False
        buf = None
        try:
            buf = frame.lock_buf()
            audio_data = bytes(buf)
            frame.unlock_buf(buf)
            buf = None
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)
            await self.recognition.send_audio_frame(audio_data)
            return True
        except Exception as e:
            self.ten_env.log_error(f"Error sending audio to xAI STT: {e}")
            if buf is not None:
                try:
                    frame.unlock_buf(buf)
                except Exception:
                    pass
            return False

    @override
    async def on_open(self) -> None:
        connection_delay_ms = (
            int(datetime.now().timestamp() * 1000)
            - self.connection_start_timestamp
        )
        self.ten_env.log_info(
            "vendor_status_changed: on_open",
            category=LOG_CATEGORY_VENDOR,
        )
        await self.send_connect_delay_metrics(connection_delay_ms)
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()
        await self._flush_buffered_audio_frames()

    async def _flush_buffered_audio_frames(self) -> None:
        while True:
            try:
                buffered_frame = self.buffered_frames.get_nowait()
            except asyncio.QueueEmpty:
                self.buffered_frames_size = 0
                return

            metadata, _ = buffered_frame.get_property_to_json("metadata")
            if metadata:
                try:
                    metadata_json = copy.deepcopy(json.loads(metadata))
                    self.metadata = metadata_json
                    self.session_id = metadata_json.get(
                        "session_id", self.session_id
                    )
                except Exception:
                    pass

            await self.send_audio(buffered_frame, self.session_id)

    async def _emit_asr_result(
        self, message_data: dict[str, Any], final: bool, locked: bool
    ) -> None:
        assert self.config is not None
        text = message_data.get("text", "")
        # Empty-text results carry no information for downstream consumers
        # regardless of the `final` flag; finalize() already filters on
        # payload.get("text") before reaching here.
        if not text:
            return
        start_ms = int((message_data.get("start", 0) or 0) * 1000)
        duration_ms = int((message_data.get("duration", 0) or 0) * 1000)
        actual_start_ms = int(
            self.audio_timeline.get_audio_duration_before_time(start_ms)
            + self.sent_user_audio_duration_ms_before_last_reset
        )
        base_metadata = (
            copy.deepcopy(self.metadata) if self.metadata is not None else {}
        )
        session_id = base_metadata.pop("session_id", None)
        metadata: dict[str, Any] = {}
        if session_id is not None:
            metadata["session_id"] = session_id
        metadata["asr_info"] = {
            **base_metadata,
            "vendor": self.vendor(),
            "locked": locked,
        }
        words = []
        for word in message_data.get("words", []) or []:
            word_start_ms = int((word.get("start", 0) or 0) * 1000)
            word_end_ms = int((word.get("end", 0) or 0) * 1000)
            actual_word_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(
                    word_start_ms
                )
                + self.sent_user_audio_duration_ms_before_last_reset
            )
            words.append(
                ASRWord(
                    word=word.get("text", ""),
                    start_ms=actual_word_start_ms,
                    duration_ms=max(0, word_end_ms - word_start_ms),
                    stable=locked or final,
                )
            )
        asr_result = ASRResult(
            id=str(uuid4()),
            text=text,
            final=final,
            start_ms=actual_start_ms,
            duration_ms=duration_ms,
            language=self.config.normalized_language,
            words=words,
            metadata=metadata,
        )
        await self.send_asr_result(asr_result)

    @override
    async def on_partial_result(self, message_data: dict[str, Any]) -> None:
        is_final = bool(message_data.get("is_final", False))
        speech_final = bool(message_data.get("speech_final", False))
        locked = is_final and not speech_final
        await self._emit_asr_result(
            message_data,
            final=is_final and speech_final,
            locked=locked,
        )

    @override
    async def on_done(self, message_data: dict[str, Any]) -> None:
        self.ten_env.log_debug(
            f"xAI transcript.done: {message_data}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )

    @override
    async def on_error(
        self, error_msg: str, error_code: int | None = None
    ) -> None:
        self.ten_env.log_error(
            f"vendor_error: code: {error_code}, reason: {error_msg}",
            category=LOG_CATEGORY_VENDOR,
        )
        fatal = self._is_fatal_connection_error(error_code)
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=(
                    ModuleErrorCode.FATAL_ERROR.value
                    if fatal
                    else ModuleErrorCode.NON_FATAL_ERROR.value
                ),
                message=error_msg,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(error_code) if error_code else "unknown",
                message=error_msg,
            ),
        )

    @override
    async def on_close(self) -> None:
        self.ten_env.log_info("vendor_status_changed: on_close")
        self.recognition = None
        if self._stop_requested:
            return
        if self._close_expected:
            # xAI STT is a single-utterance protocol: the server closes the
            # socket after each transcript.done. Subsequent turns need a
            # fresh connection. Schedule a clean reconnect (not the
            # backoff path — this is a planned cycle, not a failure).
            # The base class buffers audio frames in the meantime and
            # flushes them from on_open.
            self._close_expected = False
            self._schedule_finalize_reconnect()
            return
        await self._handle_reconnect()

    def _schedule_finalize_reconnect(self) -> None:
        self._cancel_finalize_reconnect_task()
        self._finalize_reconnect_task = asyncio.create_task(
            self._reconnect_after_finalize()
        )
        self._finalize_reconnect_task.add_done_callback(
            self._clear_finalize_reconnect_task
        )

    def _cancel_finalize_reconnect_task(self) -> None:
        if (
            self._finalize_reconnect_task
            and not self._finalize_reconnect_task.done()
        ):
            self._finalize_reconnect_task.cancel()
        self._finalize_reconnect_task = None

    def _clear_finalize_reconnect_task(self, task: asyncio.Task) -> None:
        if self._finalize_reconnect_task is task:
            self._finalize_reconnect_task = None

    async def _reconnect_after_finalize(self) -> None:
        if self._stop_requested:
            return
        try:
            await self._connect_recognition()
        except Exception as e:
            self.ten_env.log_warn(
                f"xAI STT post-finalize reconnect failed: {e}; "
                f"falling back to reconnect manager backoff",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._handle_reconnect()

    async def _handle_reconnect(self) -> None:
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return
        while not self._stop_requested and self.reconnect_manager.can_retry():
            success = await self.reconnect_manager.handle_reconnect(
                connection_func=self._connect_recognition,
                error_handler=self.send_asr_error,
                vendor_name=self.vendor(),
                vendor_code="connect_failed",
            )

            if success:
                self.ten_env.log_debug(
                    "Reconnection attempt initiated successfully"
                )
                return

            info = self.reconnect_manager.get_attempts_info()
            self.ten_env.log_debug(
                f"Reconnection attempt failed. Status: {info}"
            )
