#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from contextlib import suppress
from datetime import datetime
import os
import traceback

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.helper import generate_file_name, PCMWriter
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

from .config import CosyTTSConfig
from .cosy_tts import (
    MESSAGE_TYPE_CMD_COMPLETE,
    MESSAGE_TYPE_CMD_ERROR,
    MESSAGE_TYPE_PCM,
    CosyTTSClient,
    CosyTTSProviderError,
    ProviderCompletion,
    ProviderError,
)

_FATAL_VENDOR_ERROR_CODES = {
    "Arrearage",
    "Forbidden",
    "InvalidApiKey",
    "InvalidParameter",
    "ModelNotFound",
    "Request voice is invalid!",
    "Unauthorized",
}


class CosyTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name
        self.client: CosyTTSClient | None = None
        self.client_start_task: asyncio.Task[int] | None = None
        self.config: CosyTTSConfig | None = None
        self.current_request_id: str | None = None
        self.first_chunk_ts: datetime | None = None
        self.total_audio_bytes = 0
        self.request_text_characters = 0
        self.first_chunk = True
        self.audio_processor_task: asyncio.Task[None] | None = None
        self.recorder_map: dict[str, PCMWriter] = {}
        self._finish_lock = asyncio.Lock()
        self._provider_task_id = ""
        self._provider_request_uuid = ""
        self._connect_delay_ms = 0
        self._connect_delay_reported = False

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json, error = await ten_env.get_property_to_json("")
            if error:
                raise RuntimeError(f"Failed to read Cosy TTS config: {error}")
            self.config = CosyTTSConfig.model_validate_json(config_json)
            self.config.update_params()
            self.config.validate_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            self.client = CosyTTSClient(self.config, ten_env, self.vendor())
            self.client_start_task = asyncio.create_task(self.client.start())
            self.audio_processor_task = asyncio.create_task(
                self._process_audio_data()
            )
        except Exception as exc:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=self._module_error(
                    ProviderError(type(exc).__name__, str(exc)),
                    ModuleErrorCode.FATAL_ERROR,
                ),
                extra_metadata=self._base_metadata(),
            )

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.audio_processor_task is not None:
            self.audio_processor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.audio_processor_task
            self.audio_processor_task = None

        if self.client_start_task is not None:
            try:
                self._connect_delay_ms = await self.client_start_task
            except Exception as exc:
                ten_env.log_error(f"Cosy TTS client startup failed: {exc}")
            self.client_start_task = None

        if self.client is not None:
            await self.client.stop()
            self.client = None
        await self._cleanup_all_pcm_writers()
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def cancel_tts(self) -> None:
        request_id = self.current_request_id
        if self.client is not None:
            await self.client.cancel()
        if request_id is not None:
            # The base flush flow owns request-state cleanup and must not receive a
            # second finish_request() call from the provider extension.
            await self._finish_request_once(
                request_id,
                TTSAudioEndReason.INTERRUPTED,
                finish_base_request=False,
            )

    async def request_tts(self, t: TTSTextInput) -> None:
        try:
            if self.current_request_id is None:
                await self._begin_request(t.request_id)
            elif self.current_request_id != t.request_id:
                raise RuntimeError(
                    "Cosy TTS request overlap, "
                    f"active: {self.current_request_id}, new: {t.request_id}",
                )

            if self.client is None:
                await self._finish_request_once(
                    t.request_id,
                    TTSAudioEndReason.ERROR,
                    error=self._module_error(
                        ProviderError(
                            "ClientNotInitialized",
                            "TTS client is not initialized",
                        ),
                        ModuleErrorCode.FATAL_ERROR,
                    ),
                )
                return

            if (
                self.audio_processor_task is None
                or self.audio_processor_task.done()
            ):
                self.audio_processor_task = asyncio.create_task(
                    self._process_audio_data(),
                )

            self.ten_env.log_info(
                "KEYPOINT Requesting Cosy TTS, "
                f"request_id: {t.request_id}, text_length: {len(t.text)}, "
                f"text_input_end: {t.text_input_end}",
            )

            text = t.text.strip()
            if text:
                await self._ensure_client_ready(t.request_id)
                if len(text) > 20000:
                    raise ValueError(
                        "Cosy TTS text chunk exceeds 20000 characters"
                    )
                self.request_text_characters += len(t.text)
                if self.request_text_characters > 200000:
                    raise ValueError("Cosy TTS task exceeds 200000 characters")
                self.metrics_add_output_characters(len(t.text))
                await self.client.synthesize_audio(t.text, t.request_id)
            elif not t.text_input_end:
                self.ten_env.log_debug(
                    f"Skipped empty Cosy TTS chunk, request_id: {t.request_id}",
                )

            if t.text_input_end:
                if self.request_text_characters == 0:
                    await self._finish_request_once(
                        t.request_id,
                        TTSAudioEndReason.REQUEST_END,
                    )
                    return
                await self.client.complete(t.request_id)
        except CosyTTSProviderError as exc:
            await self._finish_provider_error(t.request_id, exc.error)
        except Exception as exc:
            self.ten_env.log_error(
                "Cosy TTS request failed, "
                f"request_id: {t.request_id}, error: {traceback.format_exc()}",
            )
            await self._finish_request_once(
                t.request_id,
                TTSAudioEndReason.ERROR,
                error=self._module_error(
                    ProviderError(type(exc).__name__, str(exc)),
                    ModuleErrorCode.FATAL_ERROR,
                ),
            )
            if self.client is not None:
                await self.client.cancel()

    async def _process_audio_data(self) -> None:
        while True:
            try:
                client = self.client
                if client is None:
                    return
                item = await client.get_audio_data()
                if item.request_id != self.current_request_id:
                    self.ten_env.log_warn(
                        "Discarded stale Cosy TTS callback, "
                        f"active_request_id: {self.current_request_id}, "
                        f"callback_request_id: {item.request_id}, task_id: {item.task_id}",
                    )
                    continue

                if item.message_type == MESSAGE_TYPE_PCM:
                    if isinstance(item.payload, bytes) and item.payload:
                        await self._handle_audio_chunk(
                            item.payload, item.task_id, item.ttfb_ms
                        )
                    continue

                if item.message_type == MESSAGE_TYPE_CMD_ERROR:
                    if isinstance(item.payload, ProviderError):
                        await self._finish_provider_error(
                            item.request_id, item.payload
                        )
                    continue

                if item.message_type == MESSAGE_TYPE_CMD_COMPLETE:
                    if isinstance(item.payload, ProviderCompletion):
                        self._provider_task_id = item.payload.task_id
                        self._provider_request_uuid = item.payload.request_uuid
                        self.metrics_add_input_characters(
                            item.payload.billed_characters,
                        )
                    await self._finish_request_once(
                        item.request_id,
                        TTSAudioEndReason.REQUEST_END,
                    )
            except Exception as exc:
                self.ten_env.log_error(
                    f"Cosy TTS audio consumer failed: {traceback.format_exc()}",
                )
                request_id = self.current_request_id
                if request_id is not None:
                    await self._finish_request_once(
                        request_id,
                        TTSAudioEndReason.ERROR,
                        error=self._module_error(
                            ProviderError(type(exc).__name__, str(exc)),
                            ModuleErrorCode.NON_FATAL_ERROR,
                        ),
                    )
                return

    async def _handle_audio_chunk(
        self,
        audio_chunk: bytes,
        task_id: str,
        ttfb_ms: int | None,
    ) -> None:
        request_id = self.current_request_id
        config = self.config
        if request_id is None or config is None:
            return

        self.metrics_add_recv_audio_chunks(audio_chunk)
        self.total_audio_bytes += len(audio_chunk)
        if self.first_chunk:
            self.first_chunk = False
            self.first_chunk_ts = datetime.now()
            self._provider_task_id = task_id
            await self.send_tts_audio_start(request_id)
            if ttfb_ms is not None:
                await self.send_tts_ttfb_metrics(
                    request_id=request_id,
                    ttfb_ms=ttfb_ms,
                    extra_metadata=self._provider_metadata(),
                )

        recorder = self.recorder_map.get(request_id)
        if recorder is not None:
            await recorder.write(audio_chunk)
        await self.send_tts_audio_data(audio_chunk)
        self.ten_env.log_debug(
            f"Received {len(audio_chunk)} Cosy TTS bytes, request_id: {request_id}",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _begin_request(self, request_id: str) -> None:
        self.current_request_id = request_id
        self.first_chunk_ts = None
        self.total_audio_bytes = 0
        self.request_text_characters = 0
        self.first_chunk = True
        self._provider_task_id = ""
        self._provider_request_uuid = ""

        await self._create_pcm_writer(request_id)

    async def _ensure_client_ready(self, request_id: str) -> None:
        if self.client_start_task is not None:
            if self.client_start_task.done():
                self._connect_delay_ms = await self.client_start_task
                self.ten_env.log_debug(
                    "Cosy TTS connection pool already ready, "
                    f"request_id: {request_id}, "
                    f"connect_delay_ms: {self._connect_delay_ms}",
                )
            else:
                wait_started = asyncio.get_running_loop().time()
                self.ten_env.log_info(
                    "Waiting for Cosy TTS connection pool, "
                    f"request_id: {request_id}",
                )
                self._connect_delay_ms = await self.client_start_task
                wait_ms = int(
                    (asyncio.get_running_loop().time() - wait_started) * 1000
                )
                self.ten_env.log_info(
                    "Cosy TTS connection pool ready for request, "
                    f"request_id: {request_id}, wait_ms: {wait_ms}, "
                    f"connect_delay_ms: {self._connect_delay_ms}",
                )
        if not self._connect_delay_reported:
            await self.metrics_connect_delay(
                self._connect_delay_ms,
                request_id=request_id,
                extra_metadata=self._base_metadata(),
            )
            self._connect_delay_reported = True

    async def _finish_provider_error(
        self,
        request_id: str,
        provider_error: ProviderError,
    ) -> None:
        if self.client is not None:
            await self.client.cancel()
        error_code = (
            ModuleErrorCode.FATAL_ERROR
            if provider_error.code in _FATAL_VENDOR_ERROR_CODES
            else ModuleErrorCode.NON_FATAL_ERROR
        )
        await self._finish_request_once(
            request_id,
            TTSAudioEndReason.ERROR,
            error=self._module_error(provider_error, error_code),
            provider_error=provider_error,
        )

    async def _finish_request_once(
        self,
        request_id: str,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
        provider_error: ProviderError | None = None,
        finish_base_request: bool = True,
    ) -> None:
        async with self._finish_lock:
            if self.current_request_id != request_id:
                return

            if provider_error is not None:
                self._provider_task_id = provider_error.task_id
                self._provider_request_uuid = provider_error.request_uuid
            metadata = self._provider_metadata()
            request_event_interval_ms = (
                int(
                    (datetime.now() - self.first_chunk_ts).total_seconds()
                    * 1000
                )
                if self.first_chunk_ts is not None
                else 0
            )
            audio_duration_ms = self._calculate_audio_duration(
                self.total_audio_bytes
            )
            await self._flush_pcm_writer(request_id)
            await self.send_tts_audio_end(
                request_id=request_id,
                request_event_interval_ms=request_event_interval_ms,
                request_total_audio_duration_ms=audio_duration_ms,
                reason=reason,
                extra_metadata=metadata,
            )
            await self.send_usage_metrics(request_id, extra_metadata=metadata)
            if error is not None:
                await self.send_tts_error(
                    request_id,
                    error,
                    extra_metadata=metadata,
                )

            self.current_request_id = None
            self.first_chunk_ts = None
            self.total_audio_bytes = 0
            self.request_text_characters = 0
            self.first_chunk = True
            if finish_base_request:
                await self.finish_request(request_id, reason=reason)

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config is not None else 16000

    def vendor(self) -> str:
        return "cosy"

    def _calculate_audio_duration(self, bytes_length: int) -> int:
        sample_rate = self.synthesize_audio_sample_rate()
        return int(bytes_length / (sample_rate * 2) * 1000)

    def _base_metadata(self) -> dict[str, str]:
        config = self.config
        return {
            "model": config.model if config is not None else "",
            "voice": config.voice if config is not None else "",
        }

    def _provider_metadata(self) -> dict[str, str]:
        metadata = self._base_metadata()
        if self._provider_task_id:
            metadata["vendor_task_id"] = self._provider_task_id
        if self._provider_request_uuid:
            metadata["vendor_request_uuid"] = self._provider_request_uuid
        return metadata

    def _module_error(
        self,
        provider_error: ProviderError,
        code: ModuleErrorCode,
    ) -> ModuleError:
        return ModuleError(
            message=provider_error.message,
            module=ModuleType.TTS,
            code=code.value,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=provider_error.code,
                message=provider_error.message,
            ),
        )

    async def _create_pcm_writer(self, request_id: str) -> None:
        config = self.config
        if config is None or not config.dump:
            return
        await self._cleanup_all_pcm_writers(except_request_id=request_id)
        if request_id not in self.recorder_map:
            path = os.path.join(
                config.dump_path,
                generate_file_name(f"{self.name}_out_{request_id}"),
            )
            self.recorder_map[request_id] = PCMWriter(path)

    async def _flush_pcm_writer(self, request_id: str) -> None:
        recorder = self.recorder_map.pop(request_id, None)
        if recorder is not None:
            await recorder.flush()

    async def _cleanup_all_pcm_writers(
        self,
        except_request_id: str | None = None,
    ) -> None:
        request_ids = [
            request_id
            for request_id in self.recorder_map
            if request_id != except_request_id
        ]
        for request_id in request_ids:
            recorder = self.recorder_map.pop(request_id)
            try:
                await recorder.flush()
            except Exception as exc:
                self.ten_env.log_error(
                    f"Failed to flush Cosy TTS dump for {request_id}: {exc}",
                )
