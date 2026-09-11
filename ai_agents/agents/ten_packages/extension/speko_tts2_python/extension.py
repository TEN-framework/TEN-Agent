#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import os
import time
from typing import Any

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
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

from .client import (
    SpekoRouterError,
    SpekoTTSClient,
    SpekoTTSEventType,
)
from .config import SpekoTTS2Config


class SpekoTTS2Extension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpekoTTS2Config | None = None
        self.client: SpekoTTSClient | None = None
        self.current_request_id: str | None = None
        self._route: dict[str, Any] = {}
        self._router_usage: dict[str, Any] = {}
        self._audio_start_sent = False
        self._first_audio_at: float | None = None
        self._total_audio_bytes = 0
        self._finalized = False
        self._audio_end_sent = False
        self._cancelled = False
        self._stopped = False
        self._permanent_error: SpekoRouterError | None = None
        self._recorders: dict[str, PCMWriter] = {}

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        try:
            config_json, error = await ten_env.get_property_to_json("")
            if error:
                raise RuntimeError(f"Failed to read configuration: {error}")
            self.config = SpekoTTS2Config.model_validate_json(config_json)
            self.config.update_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
        except Exception as error:
            self.config = None
            ten_env.log_error(
                f"invalid property: {error}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(error),
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        self._stopped = True
        task = self.current_task
        await self._cancel_current_task()
        if task is not None and task is not asyncio.current_task():
            await asyncio.gather(task, return_exceptions=True)
        try:
            await self._close_client()
        finally:
            try:
                for request_id in list(self._recorders):
                    await self._flush_recorder(request_id)
            finally:
                await super().on_stop(ten_env)

    def vendor(self) -> str:
        return "speko"

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

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 24000

    def synthesize_audio_channels(self) -> int:
        return self.config.channels if self.config else 1

    async def request_tts(self, text_input: TTSTextInput) -> None:
        # TEN flush cancels current_task; keep network work in that child task
        # so interruption cannot leave a stream reading a closed client.
        task = asyncio.create_task(self._request_tts(text_input))
        self.current_task = task
        try:
            await task
        finally:
            if self.current_task is task:
                self.current_task = None

    async def _request_tts(self, text_input: TTSTextInput) -> None:
        if self.config is None or self._stopped:
            return

        try:
            if text_input.request_id != self.current_request_id:
                await self._begin_request(text_input)
            if self._finalized:
                self.ten_env.log_warn(
                    "Ignoring text for a completed Speko TTS request"
                )
                return

            if self._permanent_error is not None:
                raise self._permanent_error
            text = text_input.text
            if text:
                await self._stream_text(text, text_input.request_id)

            if text_input.text_input_end:
                await self._finalize_request(TTSAudioEndReason.REQUEST_END)
        except SpekoRouterError as error:
            if self._cancelled or self._stopped:
                return
            await self._handle_router_error(error, text_input.text_input_end)
        except Exception as error:
            if self._cancelled or self._stopped:
                return
            await self._handle_router_error(
                SpekoRouterError("relay_error", str(error), retryable=True),
                text_input.text_input_end,
            )

    async def cancel_tts(self) -> None:
        request_id = self.current_request_id
        if request_id is None or self._audio_end_sent or self._cancelled:
            return
        self._finalized = True
        self._cancelled = True
        client, self.client = self.client, None
        try:
            if client is not None:
                await client.cancel()
        except asyncio.CancelledError:
            if not self._stopped:
                raise
        except Exception as error:
            router_error = (
                error
                if isinstance(error, SpekoRouterError)
                else SpekoRouterError("relay_error", str(error), retryable=True)
            )
            await self.send_tts_error(
                request_id, self._make_module_error(router_error)
            )
        finally:
            try:
                if not self._stopped:
                    await self.on_disconnected(code=0, message="cancelled")
                    await self._ensure_audio_start()
                    self._audio_end_sent = True
                    await self.send_tts_audio_end(
                        request_id=request_id,
                        request_event_interval_ms=self._request_interval_ms(),
                        request_total_audio_duration_ms=self._audio_duration_ms(),
                        reason=TTSAudioEndReason.INTERRUPTED,
                    )
            finally:
                await self._flush_recorder(request_id)

    async def _begin_request(self, text_input: TTSTextInput) -> None:
        if self.client is not None:
            await self._close_client()
        self.current_request_id = text_input.request_id
        self._route = {}
        self._router_usage = {}
        self._audio_start_sent = False
        self._first_audio_at = None
        self._total_audio_bytes = 0
        self._finalized = False
        self._audio_end_sent = False
        self._cancelled = False
        await self._setup_recorder(text_input.request_id)

    async def _ensure_client(self) -> SpekoTTSClient:
        if self.client is not None and self.client.is_ready:
            return self.client
        if self.config is None:
            raise RuntimeError("Speko TTS is not configured")

        await self.on_connecting()
        connected_at = time.monotonic()
        client = SpekoTTSClient(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            configure=self._configure_frame(),
            ready_timeout_sec=self.config.ready_timeout_sec,
            receive_timeout_sec=self.config.receive_timeout_sec,
        )
        await client.connect()
        self.client = client
        self._route = client.route
        await self.on_connected()
        await self.metrics_connect_delay(
            int((time.monotonic() - connected_at) * 1000),
            extra_metadata={"route": self._route},
            request_id=self.current_request_id or "",
        )
        self.ten_env.log_info(
            f"vendor_status_changed: Speko TTS ready; route={self._route}",
            category=LOG_CATEGORY_VENDOR,
        )
        return client

    async def _stream_text(self, text: str, request_id: str) -> None:
        client = await self._ensure_client()
        self.metrics_add_output_characters(len(text))
        async for event in client.stream_text(text):
            if self._cancelled or self._stopped:
                return
            if event.type == SpekoTTSEventType.TTFB:
                if not self._audio_start_sent:
                    await self._ensure_audio_start()
                    await self.send_tts_ttfb_metrics(
                        request_id=request_id,
                        ttfb_ms=int(event.value or 0),
                        extra_metadata={"route": self._route},
                    )
            elif event.type == SpekoTTSEventType.AUDIO:
                audio = event.value
                if not isinstance(audio, bytes) or not audio:
                    continue
                await self._ensure_audio_start()
                if self._first_audio_at is None:
                    self._first_audio_at = time.monotonic()
                self._total_audio_bytes += len(audio)
                self.metrics_add_recv_audio_chunks(audio)
                await self._write_dump(request_id, audio)
                await self.send_tts_audio_data(audio)
            elif event.type == SpekoTTSEventType.USAGE:
                if isinstance(event.value, dict):
                    self._router_usage = event.value

    async def _finalize_request(
        self,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
    ) -> None:
        request_id = self.current_request_id
        if request_id is None or self._finalized:
            return
        self._finalized = True
        cancelled = False
        try:
            try:
                await self._close_client()
            except Exception as close_error:
                if self._cancelled or self._stopped:
                    return
                router_error = (
                    close_error
                    if isinstance(close_error, SpekoRouterError)
                    else SpekoRouterError(
                        "relay_error", str(close_error), retryable=True
                    )
                )
                reason = TTSAudioEndReason.ERROR
                error = self._make_module_error(router_error)
                await self.on_disconnected(
                    code=error.code,
                    message=error.message,
                    vendor_info=error.vendor_info,
                )
            if self._cancelled:
                return
            await self._ensure_audio_start()
            self._audio_end_sent = True
            await self.send_tts_audio_end(
                request_id=request_id,
                request_event_interval_ms=self._request_interval_ms(),
                request_total_audio_duration_ms=self._audio_duration_ms(),
                reason=reason,
                extra_metadata={"router_usage": self._router_usage},
            )
            await self.send_usage_metrics(
                request_id,
                extra_metadata={"router_usage": self._router_usage},
            )
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            # Flush owns interruption state; do not finish a cancelled request
            # as a successful request while cancel_tts is emitting its end.
            if not cancelled and not self._cancelled:
                try:
                    await self._flush_recorder(request_id)
                finally:
                    await self.finish_request(
                        request_id, reason=reason, error=error
                    )

    def _make_module_error(self, error: SpekoRouterError) -> ModuleError:
        if not error.retryable and error.code in {
            "authentication_failed",
            "insufficient_credit",
            "route_not_found",
            "capability_unsupported",
        }:
            self._permanent_error = error
        return ModuleError(
            module=ModuleType.TTS,
            code=self._module_error_code(error).value,
            message=error.message,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(), code=error.code, message=error.message
            ),
        )

    async def _handle_router_error(
        self, error: SpekoRouterError, final_input: bool
    ) -> None:
        module_error = self._make_module_error(error)
        await self.on_disconnected(
            code=module_error.code,
            message=error.message,
            vendor_info=module_error.vendor_info,
        )
        if self._finalized:
            await self.send_tts_error(self.current_request_id, module_error)
        elif final_input:
            await self._finalize_request(
                TTSAudioEndReason.ERROR, error=module_error
            )
        else:
            # The remaining chunks still belong to the same TEN request.
            client, self.client = self.client, None
            try:
                if client is not None:
                    await client.close(drain=False)
            finally:
                await self.send_tts_error(self.current_request_id, module_error)

    async def _ensure_audio_start(self) -> None:
        if self._audio_start_sent or self.current_request_id is None:
            return
        await self.send_tts_audio_start(
            request_id=self.current_request_id,
            extra_metadata={"route": self._route},
        )
        self._audio_start_sent = True

    async def _close_client(self) -> None:
        if self.client is None:
            return
        client, self.client = self.client, None
        request_id = self.current_request_id
        try:
            await client.close()
        finally:
            if self.current_request_id == request_id:
                self._router_usage = client.usage or self._router_usage
        if self.current_request_id == request_id and self.client is None:
            await self.on_disconnected(code=0, message="closed")

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
        if self.config.voice:
            frame["voice"] = self.config.voice
        return frame

    async def _setup_recorder(self, request_id: str) -> None:
        if self.config is None or not self.config.dump:
            return
        os.makedirs(self.config.dump_path, exist_ok=True)
        path = os.path.join(
            self.config.dump_path, f"speko_tts_{request_id}.pcm"
        )
        self._recorders[request_id] = PCMWriter(path)

    async def _write_dump(self, request_id: str, audio: bytes) -> None:
        recorder = self._recorders.get(request_id)
        if recorder is not None:
            await recorder.write(audio)

    async def _flush_recorder(self, request_id: str) -> None:
        recorder = self._recorders.pop(request_id, None)
        if recorder is not None:
            await recorder.flush()

    def _request_interval_ms(self) -> int:
        if self._first_audio_at is None:
            return 0
        return int((time.monotonic() - self._first_audio_at) * 1000)

    def _audio_duration_ms(self) -> int:
        bytes_per_second = (
            self.synthesize_audio_sample_rate()
            * self.synthesize_audio_channels()
            * self.synthesize_audio_sample_width()
        )
        return int(self._total_audio_bytes * 1000 / bytes_per_second)

    @staticmethod
    def _module_error_code(error: SpekoRouterError) -> ModuleErrorCode:
        fatal_codes = {"authentication_failed", "insufficient_credit"}
        if error.code in fatal_codes:
            return ModuleErrorCode.FATAL_ERROR
        return ModuleErrorCode.NON_FATAL_ERROR
