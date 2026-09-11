#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import time
import traceback
from pathlib import Path
from typing import Any

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleConnectionStatus,
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_ai_base.struct import ASRWord
from ten_runtime import AsyncTenEnv, AudioFrame
from typing_extensions import override

from .client import SpekoASRClient, SpekoRouterError
from .config import SpekoASRConfig


class SpekoASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpekoASRConfig | None = None
        self.client: SpekoASRClient | None = None
        self.audio_dumper: Dumper | None = None
        self._connect_started_at = 0.0
        self._total_audio_bytes = 0
        self._final_cursor_ms = 0
        self._turn_start_ms = 0
        self._permanent_error: SpekoRouterError | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._route: dict[str, Any] = {}

    @override
    def vendor(self) -> str:
        return "speko"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        metadata: dict[str, Any] = {
            "key": self.config.api_key,
            "api_key": self.config.api_key,
            "language": self.config.language,
            "base_url": self.config.base_url,
            "routing": self.config.routing,
        }
        if self._route:
            metadata["route"] = self._route
            metadata["model"] = self._route.get("model", "")
        return {key: value for key, value in metadata.items() if value}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        try:
            config_json, error = await ten_env.get_property_to_json("")
            if error:
                raise RuntimeError(f"Failed to read configuration: {error}")
            self.config = SpekoASRConfig.model_validate_json(config_json)
            self.config.update_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._start_dumper()
        except Exception as error:
            self.config = None
            ten_env.log_error(
                f"invalid property: {error}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(error),
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
            )

    @override
    async def start_connection(self) -> None:
        if self._permanent_error is not None:
            return
        if self.config is None:
            await self.on_disconnected(
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="Speko ASR is not configured",
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            return
        if self.client is not None:
            await self.client.close()

        self._total_audio_bytes = 0
        self._final_cursor_ms = 0
        self._turn_start_ms = 0
        self._connect_started_at = time.monotonic()
        self.client = SpekoASRClient(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            configure=self._configure_frame(),
            ready_timeout_sec=self.config.ready_timeout_sec,
            finalize_timeout_sec=self.config.finalize_timeout_sec,
            on_event=self._on_router_event,
            on_disconnect=self._on_router_disconnect,
        )
        try:
            await self.client.connect()
        except SpekoRouterError as error:
            if not error.retryable and error.code in {
                "authentication_failed",
                "insufficient_credit",
                "route_not_found",
                "capability_unsupported",
            }:
                self._permanent_error = error
            await self._report_router_error(error)
            await self.on_disconnected(
                code=self._module_error_code(error).value,
                message=error.message,
                vendor_info=self._vendor_info(error),
            )
        except Exception as error:
            self.ten_env.log_error(
                f"vendor_error: {traceback.format_exc()}",
                category=LOG_CATEGORY_VENDOR,
            )
            router_error = SpekoRouterError(
                "relay_error", str(error), retryable=True
            )
            await self._report_router_error(router_error)
            await self.on_disconnected(
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=str(error),
                vendor_info=self._vendor_info(router_error),
            )

    @override
    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_ready

    @override
    async def stop_connection(self) -> None:
        task, self._reconnect_task = self._reconnect_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        client, self.client = self.client, None
        try:
            if client is not None:
                await client.close()
        finally:
            dumper, self.audio_dumper = self.audio_dumper, None
            if dumper is not None:
                await dumper.stop()

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        self.stopped = True
        try:
            await self.stop_connection()
        finally:
            await super().on_deinit(ten_env)

    @override
    def input_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 16000

    @override
    def input_audio_channels(self) -> int:
        return self.config.channels if self.config else 1

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        if self.config is None or self.config.buffer_duration_ms == 0:
            return ASRBufferConfigModeDiscard()
        bytes_per_ms = (
            self.input_audio_sample_rate()
            * self.input_audio_channels()
            * self.input_audio_sample_width()
            // 1000
        )
        return ASRBufferConfigModeKeep(
            byte_limit=bytes_per_ms * self.config.buffer_duration_ms
        )

    @override
    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, frame: AudioFrame
    ) -> None:
        # The base consumer buffers disconnected frames without calling send_audio.
        if (
            not self.stopped
            and not self.is_connected()
            and self.connection_status != ModuleConnectionStatus.CONNECTING
            and self._permanent_error is None
            and (self.auto_connect or self._connection_requested)
            and (self._reconnect_task is None or self._reconnect_task.done())
        ):
            self._reconnect_task = asyncio.create_task(self._reconnect())
        await super().on_audio_frame(ten_env, frame)

    async def _reconnect(self) -> None:
        await self._ensure_connection()
        if not self.is_connected():
            # Coalesce incoming frames during an unsuccessful connection attempt.
            await asyncio.sleep(0.5)

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        del session_id
        if not self.is_connected() or self.client is None:
            return False
        buffer = frame.lock_buf()
        try:
            audio = bytes(buffer)
            await self.client.send_audio(audio)
            self._total_audio_bytes += len(audio)
            self.audio_timeline.add_user_audio(
                self._audio_duration_ms(len(audio))
            )
            if self.audio_dumper is not None:
                await self.audio_dumper.push_bytes(audio)
            return True
        except SpekoRouterError as error:
            await self._reset_connection(error)
            return False
        except Exception as error:
            await self._reset_connection(
                SpekoRouterError("relay_error", str(error), retryable=True)
            )
            return False
        finally:
            frame.unlock_buf(buffer)

    @override
    async def finalize(self, session_id: str | None) -> None:
        del session_id
        if not self.is_connected() or self.client is None:
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message="Speko ASR session is not connected",
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
            )
            await self.send_asr_finalize_end()
            return
        try:
            await self.client.commit()
        except asyncio.CancelledError:
            if not self.stopped:
                raise
        except SpekoRouterError as error:
            if self.is_connected():
                await self._reset_connection(error)
        except Exception as error:
            await self._reset_connection(
                SpekoRouterError("relay_error", str(error), retryable=True)
            )
        finally:
            self._turn_start_ms += self._audio_duration_ms(
                self._total_audio_bytes
            )
            self._total_audio_bytes = 0
            self._final_cursor_ms = self._turn_start_ms
            if not self.stopped:
                await self.send_asr_finalize_end()

    async def _reset_connection(self, error: SpekoRouterError) -> None:
        async with self._connection_lock:
            client, self.client = self.client, None
            try:
                if client is not None:
                    await client.close()
            finally:
                await self._on_router_disconnect(error)
            # Reconnect on the next audio frame, never replay an ambiguous send.

    async def _on_router_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "session.ready":
            self._route = dict(event.get("route", {}))
            # Audio may have ended before the handshake completed. The base
            # only drains its disconnected buffer when another frame arrives.
            # Move it ahead of queued live frames so no extra frame is needed.
            if not self.buffered_frames.empty():
                pending = []
                while not self.buffered_frames.empty():
                    pending.append(self.buffered_frames.get_nowait())
                while not self.audio_frames_queue.empty():
                    pending.append(self.audio_frames_queue.get_nowait())
                self.buffered_frames_size = 0
                for frame in pending:
                    self.audio_frames_queue.put_nowait(frame)
            connect_delay = int(
                (time.monotonic() - self._connect_started_at) * 1000
            )
            await self.on_connected()
            await self.send_connect_delay_metrics(connect_delay)
            self.ten_env.log_info(
                f"vendor_status_changed: Speko ASR ready; route={self._route}",
                category=LOG_CATEGORY_VENDOR,
            )
        elif event_type == "transcript.delta":
            await self._send_transcript(event, final=False)
        elif event_type == "transcript.final":
            await self._send_transcript(event, final=True)
        elif event_type in {"usage.updated", "session.closed"}:
            usage = dict(event.get("usage", {}))
            await self.send_vendor_metrics({"usage": usage})

    async def _on_router_disconnect(
        self, error: SpekoRouterError | None
    ) -> None:
        if error is not None:
            if not error.retryable and error.code in {
                "authentication_failed",
                "insufficient_credit",
                "route_not_found",
                "capability_unsupported",
            }:
                self._permanent_error = error
            await self._report_router_error(error)
        await self.on_disconnected(
            code=(
                self._module_error_code(error).value if error is not None else 0
            ),
            message=error.message if error is not None else "closed",
            vendor_info=(
                self._vendor_info(error) if error is not None else None
            ),
        )

    async def _send_transcript(
        self, event: dict[str, Any], *, final: bool
    ) -> None:
        segments = event.get("segments") or []
        words: list[ASRWord] = []
        if segments:
            start_ms = min(int(segment["start_ms"]) for segment in segments)
            end_ms = max(int(segment["end_ms"]) for segment in segments)
            for segment in segments:
                segment_start = int(segment["start_ms"])
                segment_end = int(segment["end_ms"])
                words.append(
                    ASRWord(
                        word=str(segment.get("text", "")),
                        start_ms=segment_start,
                        duration_ms=max(0, segment_end - segment_start),
                        stable=final,
                    )
                )
        else:
            start_ms = self._final_cursor_ms
            end_ms = self._turn_start_ms + self._audio_duration_ms(
                self._total_audio_bytes
            )

        metadata: dict[str, Any] = {
            "asr_info": {"vendor": self.vendor(), "locked": False}
        }
        if event.get("speaker") is not None:
            metadata["speaker"] = event["speaker"]

        await self.send_asr_result(
            ASRResult(
                text=str(event.get("text", "")),
                final=final,
                start_ms=start_ms,
                duration_ms=max(0, end_ms - start_ms),
                language=self.config.language if self.config else "en-US",
                words=words,
                metadata=metadata,
            )
        )
        if final:
            self._final_cursor_ms = max(self._final_cursor_ms, end_ms)

    async def _report_router_error(self, error: SpekoRouterError) -> None:
        self.ten_env.log_error(
            f"vendor_error: code={error.code}, message={error.message}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=self._module_error_code(error).value,
                message=error.message,
                vendor_info=self._vendor_info(error),
            )
        )

    def _configure_frame(self) -> dict[str, Any]:
        assert self.config is not None
        frame: dict[str, Any] = {
            "type": "session.configure",
            "audio": {
                "encoding": "pcm_s16le",
                "sample_rate_hz": self.config.sample_rate,
                "channels": self.config.channels,
            },
        }
        if self.config.routing:
            frame["routing"] = self.config.routing
        if self.config.language:
            frame["language"] = self.config.language
        if self.config.options:
            frame["options"] = self.config.options
        return frame

    async def _start_dumper(self) -> None:
        if self.config is None or not self.config.dump:
            return
        dump_path = Path(self.config.dump_path)
        if dump_path.suffix != ".pcm":
            dump_path = dump_path / "speko_asr_in.pcm"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_dumper = Dumper(str(dump_path))
        await self.audio_dumper.start()

    def _audio_duration_ms(self, byte_count: int) -> int:
        bytes_per_second = (
            self.input_audio_sample_rate()
            * self.input_audio_channels()
            * self.input_audio_sample_width()
        )
        return int(byte_count * 1000 / bytes_per_second)

    @staticmethod
    def _module_error_code(error: SpekoRouterError) -> ModuleErrorCode:
        fatal_codes = {"authentication_failed", "insufficient_credit"}
        if error.code in fatal_codes:
            return ModuleErrorCode.FATAL_ERROR
        return ModuleErrorCode.NON_FATAL_ERROR

    def _vendor_info(self, error: SpekoRouterError) -> ModuleErrorVendorInfo:
        return ModuleErrorVendorInfo(
            vendor=self.vendor(), code=error.code, message=error.message
        )
