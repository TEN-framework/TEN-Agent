#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import copy
import json
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import ValidationError
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
    ModuleType,
)
from ten_ai_base.struct import ASRWord
from ten_runtime import AsyncTenEnv, AudioFrame

from .client import IFlytekAsrClient, IFlytekAsrClientListener
from .config import IFlytekAsrConfig
from .protocol import IFlytekProtocolError, IFlytekResponse
from .reconnect_manager import ReconnectLimitReachedError, ReconnectManager

DUMP_FILE_NAME = "iflytek_asr_in.pcm"


class IFlytekConfigurationError(ValueError):
    code = "invalid_config"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason = message


class IFlytekFinalizeTimeoutError(TimeoutError):
    code = "finalize_timeout"

    def __init__(self, timeout: float) -> None:
        message = f"iFLYTEK ASR finalize timed out after {timeout:g}s"
        super().__init__(message)
        self.reason = message


class IFlytekAsrExtension(AsyncASRBaseExtension, IFlytekAsrClientListener):
    def __init__(self, name: str):
        super().__init__(name)
        self.config: IFlytekAsrConfig | None = None
        self.client: IFlytekAsrClient | None = None
        self.audio_dumper: Dumper | None = None
        self.reconnect_manager = ReconnectManager(
            base_delay=0.5,
            max_delay=8.0,
            max_attempts=5,
        )
        self._should_reconnect = True
        self._reconnect_task: asyncio.Task[None] | None = None
        self._finalize_pending = False
        self._finalize_lock = asyncio.Lock()
        self._finalize_timeout_task: asyncio.Task[None] | None = None

    @override
    def vendor(self) -> str:
        return "iflytek"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        return {"language": self.config.output_language()}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        try:
            config_json, property_error = await ten_env.get_property_to_json("")
            if property_error is not None:
                raise IFlytekConfigurationError(
                    "failed to read extension property: "
                    f"{self._error_message(property_error)}"
                )
            self.config = IFlytekAsrConfig.model_validate_json(config_json)
            self.reconnect_manager = ReconnectManager(
                base_delay=self.config.reconnect_delay,
                max_delay=self.config.reconnect_max_delay,
                max_attempts=self.config.reconnect_max_attempts,
            )
            self._log_configuration()
            self.client = IFlytekAsrClient(self.config, self)
            await self._start_audio_dumper()
        except Exception as error:
            self.config = None
            self.client = None
            message = self._error_message(error)
            ten_env.log_error(
                f"Invalid iFLYTEK ASR property: {message}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._send_framework_error(error, fatal=True)

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        await self._cancel_finalize_timeout()
        await self._stop_audio_dumper()

    @override
    async def start_connection(self) -> None:
        if self.client is None:
            await self.on_disconnected(message="client not initialized")
            return
        self._should_reconnect = True
        reconnecting = asyncio.current_task() is self._reconnect_task
        started_at = asyncio.get_running_loop().time()
        try:
            await self.client.start()
        except Exception as error:
            if reconnecting:
                raise
            message = self._error_message(error)
            self.ten_env.log_error(
                f"Failed to connect to iFLYTEK ASR: {message}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.on_disconnected(
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=message,
            )
            await self._send_framework_error(error, fatal=False)
            self._schedule_reconnect()
            return

        self.reconnect_manager.reset()
        await self._report_connect_delay(started_at)
        if self.client.is_connected():
            await self.on_connected()
        self.ten_env.log_info(
            "iFLYTEK ASR WebSocket connected",
            category=LOG_CATEGORY_VENDOR,
        )

    @override
    async def stop_connection(self) -> None:
        self._should_reconnect = False
        self._finalize_pending = False
        await self._cancel_finalize_timeout()
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None
        if self.client is not None:
            await self.client.stop()
        await self.on_disconnected(message="stopped")
        self.ten_env.log_info(
            "iFLYTEK ASR WebSocket stopped",
            category=LOG_CATEGORY_VENDOR,
        )

    @override
    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_connected()

    @override
    def input_audio_sample_rate(self) -> int:
        if self.config is None:
            raise RuntimeError("iFLYTEK ASR configuration is not initialized")
        return self.config.sample_rate

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        byte_limit = (
            self.config.buffer_max_bytes
            if self.config is not None
            else 10 * 1024 * 1024
        )
        return ASRBufferConfigModeKeep(byte_limit=byte_limit)

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        del session_id
        if self.client is None or not self.client.is_connected():
            return False

        buffer = frame.lock_buf()
        try:
            audio = bytes(buffer)
        finally:
            frame.unlock_buf(buffer)

        try:
            sent = await self.client.send_audio(audio)
        except Exception as error:
            message = self._error_message(error)
            self.ten_env.log_error(
                f"Failed to send audio to iFLYTEK ASR: {message}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._send_framework_error(error, fatal=False)
            if not self.client.is_connected():
                await self.on_disconnected(
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=message,
                )
                self._schedule_reconnect()
            return False

        if not sent:
            return False

        if self.config is not None:
            duration_ms = int(len(audio) / (self.config.sample_rate / 1000 * 2))
            self.audio_timeline.add_user_audio(duration_ms)

        if self.audio_dumper is not None:
            try:
                await self.audio_dumper.push_bytes(audio)
            except Exception as error:
                message = self._error_message(error)
                self.ten_env.log_error(
                    f"Failed to dump iFLYTEK ASR audio: {message}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                await self._send_framework_error(error, fatal=False)
        return True

    @override
    async def finalize(self, session_id: str | None) -> None:
        del session_id
        if self.client is None or not self.client.is_connected():
            self.ten_env.log_warn(
                "Cannot finalize iFLYTEK ASR: not connected",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_asr_finalize_end()
            return

        async with self._finalize_lock:
            self._finalize_pending = True

        try:
            vendor_pending = await self.client.finalize()
            if not vendor_pending:
                await self._complete_finalize()
            elif self._finalize_pending:
                self._start_finalize_timeout()
        except Exception as error:
            message = self._error_message(error)
            self.ten_env.log_error(
                f"Failed to finalize iFLYTEK ASR: {message}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._send_framework_error(error, fatal=False)
            await self._complete_finalize()

    @override
    async def on_response(self, response: IFlytekResponse) -> None:
        transcript = response.transcript
        if transcript is not None and transcript.text:
            safe_sid = self._sanitize_text(response.sid)
            self.ten_env.log_info(
                "iFLYTEK ASR result: "
                f"final={transcript.final}, chars={len(transcript.text)}, "
                f"sid={safe_sid}",
                category=LOG_CATEGORY_VENDOR,
            )
            words = [
                ASRWord(
                    word=word.word,
                    start_ms=word.start_ms,
                    duration_ms=word.duration_ms,
                    stable=word.stable,
                )
                for word in transcript.words
            ]
            result = ASRResult(
                text=transcript.text,
                final=transcript.final,
                start_ms=transcript.start_ms,
                duration_ms=transcript.duration_ms,
                language=transcript.language,
                words=words,
                metadata=self._build_result_metadata(transcript.metadata),
            )
            await self._send_result_with_metadata(result)

        if response.terminal and self._finalize_pending:
            await self._complete_finalize()

    @override
    async def on_error(self, error: Exception) -> None:
        message = self._error_message(error)
        self.ten_env.log_error(
            f"iFLYTEK ASR client error: {message}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._send_framework_error(error, fatal=False)
        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message=message,
        )

    @override
    async def on_closed(self, terminal_received: bool) -> None:
        self.ten_env.log_info(
            "iFLYTEK ASR WebSocket closed: "
            f"terminal_received={terminal_received}",
            category=LOG_CATEGORY_VENDOR,
        )
        reconnecting = self._should_reconnect and not self.stopped
        await self.on_disconnected(
            code=(ModuleErrorCode.NON_FATAL_ERROR.value if reconnecting else 0),
            message="closed",
        )
        if self._finalize_pending:
            if not terminal_received:
                self.ten_env.log_warn(
                    "iFLYTEK ASR closed before returning terminal status",
                    category=LOG_CATEGORY_VENDOR,
                )
            await self._complete_finalize()
        if reconnecting:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        client = self.client
        if client is None:
            return

        current_task = asyncio.current_task()
        assert current_task is not None
        owns_reconnect_task = self._reconnect_task is None
        if owns_reconnect_task:
            self._reconnect_task = current_task

        try:
            while self._should_reconnect and not self.stopped:
                attempt = self.reconnect_manager.current_attempts + 1
                self.ten_env.log_info(
                    "Attempting iFLYTEK ASR reconnection "
                    f"{attempt}/{self.reconnect_manager.max_attempts}",
                    category=LOG_CATEGORY_VENDOR,
                )

                async def connect() -> None:
                    await self.start_connection()

                try:
                    await self.reconnect_manager.attempt(connect)
                except ReconnectLimitReachedError as error:
                    self._should_reconnect = False
                    await self._send_framework_error(error, fatal=True)
                    return
                except Exception as error:
                    exhausted = not self.reconnect_manager.can_retry()
                    message = self._error_message(error)
                    self.ten_env.log_error(
                        f"iFLYTEK ASR reconnection failed: {message}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    await self.on_disconnected(
                        code=(
                            ModuleErrorCode.FATAL_ERROR.value
                            if exhausted
                            else ModuleErrorCode.NON_FATAL_ERROR.value
                        ),
                        message=message,
                    )
                    if exhausted:
                        self._should_reconnect = False
                        limit_error = ReconnectLimitReachedError(
                            "maximum reconnection attempts reached"
                        )
                        await self._send_framework_error(
                            limit_error, fatal=True
                        )
                        return
                    await self._send_framework_error(error, fatal=False)
                    continue

                self.ten_env.log_info(
                    "iFLYTEK ASR reconnection successful",
                    category=LOG_CATEGORY_VENDOR,
                )
                return
        finally:
            if owns_reconnect_task and self._reconnect_task is current_task:
                self._reconnect_task = None

    def _start_finalize_timeout(self) -> None:
        if self.config is None or not self._finalize_pending:
            return
        if (
            self._finalize_timeout_task is not None
            and not self._finalize_timeout_task.done()
        ):
            self._finalize_timeout_task.cancel()
        self._finalize_timeout_task = asyncio.create_task(
            self._wait_for_finalize_timeout(self.config.finalize_timeout)
        )

    async def _wait_for_finalize_timeout(self, timeout: float) -> None:
        await asyncio.sleep(timeout)
        claimed = await self._claim_finalize_completion(cancel_timeout=False)
        if not claimed:
            return
        error = IFlytekFinalizeTimeoutError(timeout)
        self.ten_env.log_error(str(error), category=LOG_CATEGORY_VENDOR)
        await self._send_framework_error(error, fatal=False)
        await self.send_asr_finalize_end()
        await self._recover_from_finalize_timeout()

    async def _recover_from_finalize_timeout(self) -> None:
        client = self.client
        if client is None:
            return

        try:
            await client.stop()
        except Exception as error:
            message = self._error_message(error)
            self.ten_env.log_error(
                "Failed to close iFLYTEK ASR after finalize timeout: "
                f"{message}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._send_framework_error(error, fatal=False)

        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message="finalize timeout",
        )
        if self._should_reconnect and not self.stopped:
            self._schedule_reconnect()

    async def _complete_finalize(self) -> bool:
        claimed = await self._claim_finalize_completion()
        if claimed:
            await self.send_asr_finalize_end()
        return claimed

    async def _claim_finalize_completion(
        self, *, cancel_timeout: bool = True
    ) -> bool:
        timeout_task: asyncio.Task[None] | None = None
        async with self._finalize_lock:
            if not self._finalize_pending:
                return False
            self._finalize_pending = False
            if cancel_timeout:
                timeout_task = self._finalize_timeout_task
            self._finalize_timeout_task = None

        if (
            timeout_task is not None
            and timeout_task is not asyncio.current_task()
        ):
            timeout_task.cancel()
            with suppress(asyncio.CancelledError):
                await timeout_task
        return True

    async def _cancel_finalize_timeout(self) -> None:
        timeout_task = self._finalize_timeout_task
        self._finalize_timeout_task = None
        if (
            timeout_task is not None
            and timeout_task is not asyncio.current_task()
        ):
            timeout_task.cancel()
            with suppress(asyncio.CancelledError):
                await timeout_task

    async def _start_audio_dumper(self) -> None:
        if self.config is None or not self.config.dump:
            return
        dump_path = Path(self.config.dump_path).expanduser()
        if dump_path.suffix.lower() != ".pcm":
            if dump_path.resolve() == Path(tempfile.gettempdir()).resolve():
                dump_path = Path(
                    tempfile.mkdtemp(prefix="iflytek_asr_", dir=dump_path)
                )
            dump_path = dump_path / DUMP_FILE_NAME
        dump_path = dump_path.resolve()
        self.audio_dumper = Dumper(str(dump_path))
        await self.audio_dumper.start()
        self.ten_env.log_info(
            f"iFLYTEK ASR audio dump enabled: {dump_path}",
            category=LOG_CATEGORY_KEY_POINT,
        )

    async def _stop_audio_dumper(self) -> None:
        if self.audio_dumper is None:
            return
        await self.audio_dumper.stop()
        self.audio_dumper = None

    async def _report_connect_delay(self, started_at: float) -> None:
        delay_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        try:
            await self.send_connect_delay_metrics(delay_ms)
        except Exception as error:
            message = self._error_message(error)
            self.ten_env.log_warn(
                f"Failed to report iFLYTEK ASR connect delay: {message}",
                category=LOG_CATEGORY_KEY_POINT,
            )

    def _log_configuration(self) -> None:
        if self.config is None:
            return
        self.ten_env.log_info(
            "config: "
            f"{json.dumps(self.config.log_summary(), ensure_ascii=False)}",
            category=LOG_CATEGORY_KEY_POINT,
        )

    def _build_result_metadata(
        self, protocol_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        metadata = copy.deepcopy(self.metadata) if self.metadata else {}
        asr_info = metadata.get("asr_info")
        if not isinstance(asr_info, dict):
            asr_info = {}
        asr_info.update({"vendor": self.vendor(), **protocol_metadata})
        metadata["asr_info"] = asr_info
        return metadata

    async def _send_result_with_metadata(self, result: ASRResult) -> None:
        original_metadata = self.metadata
        result_metadata = result.metadata
        self.metadata = result_metadata
        try:
            await self.send_asr_result(result)
        finally:
            if self.metadata is result_metadata:
                self.metadata = original_metadata

    async def _send_framework_error(
        self, error: Exception, *, fatal: bool
    ) -> None:
        code = (
            ModuleErrorCode.FATAL_ERROR.value
            if fatal
            else ModuleErrorCode.NON_FATAL_ERROR.value
        )
        vendor_code = self._sanitize_text(
            str(getattr(error, "code", "client_error"))
        )[:128]
        vendor_message = self._error_message(error)
        if isinstance(error, IFlytekProtocolError):
            vendor_code = self._sanitize_text(error.code)[:128]
        elif isinstance(error, ReconnectLimitReachedError):
            vendor_code = "reconnect_exhausted"
        elif isinstance(error, ValidationError):
            vendor_code = "invalid_config"

        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=vendor_code,
            message=vendor_message,
        )
        await self.send_asr_error(
            ModuleError(
                module=ModuleType.ASR,
                code=code,
                message=vendor_message,
            ),
            vendor_info=vendor_info,
        )

    def _error_message(self, error: object) -> str:
        if isinstance(error, ValidationError):
            details = []
            for item in error.errors(
                include_input=False,
                include_url=False,
            ):
                location = ".".join(str(part) for part in item["loc"])
                details.append(f"{location}: {item['msg']}")
            return self._sanitize_text(
                "; ".join(details) or "invalid configuration"
            )

        error_message = getattr(error, "error_message", None)
        if callable(error_message):
            return self._sanitize_text(error_message())
        reason = getattr(error, "reason", None)
        return self._sanitize_text(reason if reason else error)

    def _sanitize_text(self, message: object) -> str:
        if self.config is not None:
            return self.config.sanitize_message(message)
        return " ".join(str(message).split())[:2048]
