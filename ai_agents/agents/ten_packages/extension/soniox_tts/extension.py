from __future__ import annotations

import asyncio
import os
import re
import traceback
import uuid
from time import monotonic

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

from .config import SonioxTTSConfig
from .soniox_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    SonioxTTSClient,
    SonioxTTSConnectionException,
    SonioxTTSError,
)


class SonioxTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SonioxTTSConfig | None = None
        self.client: SonioxTTSClient | None = None
        self.current_request_id: str | None = None
        self.current_stream_id: str | None = None
        self.current_turn_id = -1
        self.current_request_finished = False
        self._stream_task: asyncio.Task | None = None
        self._is_stopped = False
        self._terminal_sent = False
        self._audio_start_sent = False
        self._audio_start_monotonic: float | None = None
        self._audio_alignment_buffer = b""
        self.total_audio_bytes = 0
        self.recorder_map: dict[str, PCMWriter] = {}
        self.leftover_bytes = b""
        self.session_id: str | None = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json, _ = await ten_env.get_property_to_json("")
            if not config_json or config_json.strip() == "{}":
                raise ValueError("Configuration is empty")

            self.config = SonioxTTSConfig.model_validate_json(config_json)
            self.config.update_params()
            self.config.validate_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            self.client = self._create_client(ten_env)
            ten_env.log_debug("Soniox TTS client initialized successfully")
        except Exception as exc:
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
        self._is_stopped = True
        await self._cancel_stream_task()
        if self.client:
            await self.client.stop()
            self.client = None

        for request_id, recorder in list(self.recorder_map.items()):
            try:
                await recorder.flush()
            except Exception as exc:
                ten_env.log_error(
                    "Error flushing PCMWriter for "
                    f"request_id {request_id}: {exc}"
                )

        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)

    async def cancel_tts(self) -> None:
        await self._cancel_stream_task()
        if self.client:
            await self.client.cancel()
        if self.current_request_id and not self._terminal_sent:
            await self._finalize_request(TTSAudioEndReason.INTERRUPTED)

    def vendor(self) -> str:
        return "soniox"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 24000

    def synthesize_audio_channels(self) -> int:
        return 1

    def synthesize_audio_sample_width(self) -> int:
        return 2

    def _create_client(self, ten_env: AsyncTenEnv) -> SonioxTTSClient:
        if self.config is None:
            raise RuntimeError("Soniox TTS configuration is unavailable")
        return SonioxTTSClient(self.config, ten_env)

    async def _ensure_client(self) -> None:
        if self.client is None:
            self.client = self._create_client(self.ten_env)
            await self.client.start()

    async def request_tts(self, t: TTSTextInput) -> None:
        request_id = t.request_id
        try:
            if self._is_stopped:
                return

            if request_id != self.current_request_id:
                await self._start_request(t)
            elif self._terminal_sent:
                return

            if not t.text.strip() and not t.text_input_end:
                return

            if (
                not t.text.strip()
                and t.text_input_end
                and self.current_stream_id is None
            ):
                await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                return

            self.metrics_add_input_characters(len(t.text))
            await self._ensure_client()

            if self.current_stream_id is None:
                self.current_stream_id = f"ten-{uuid.uuid4().hex}"
                await self.client.start_stream(self.current_stream_id)
                self._stream_task = asyncio.create_task(
                    self._consume_stream(request_id, self.current_stream_id)
                )

            await self.client.send_text(t.text, t.text_input_end)
            if t.text_input_end and self._stream_task:
                await self._stream_task
        except SonioxTTSConnectionException as exc:
            await self._cancel_stream_task()
            await self._finalize_request(
                TTSAudioEndReason.ERROR,
                self._connection_error(exc),
            )
        except Exception as exc:
            await self._cancel_stream_task()
            self.ten_env.log_error(
                f"Soniox TTS request failed: {traceback.format_exc()}"
            )
            await self._finalize_request(
                TTSAudioEndReason.ERROR,
                ModuleError(
                    message=str(exc),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def _start_request(self, t: TTSTextInput) -> None:
        self.current_request_id = t.request_id
        self.current_request_finished = False
        self.current_stream_id = None
        self._terminal_sent = False
        self._audio_start_sent = False
        self._audio_start_monotonic = None
        self._audio_alignment_buffer = b""
        self.total_audio_bytes = 0
        self.leftover_bytes = b""
        if t.metadata:
            self.session_id = t.metadata.get("session_id", "")
            self.current_turn_id = t.metadata.get("turn_id", -1)
        await self._setup_recorder(t.request_id)
        if t.text_input_end:
            self.current_request_finished = True

    async def _consume_stream(self, request_id: str, stream_id: str) -> None:
        if self.client is None:
            return
        try:
            async for payload, event in self.client.iter_events(stream_id):
                if request_id != self.current_request_id or self._terminal_sent:
                    return

                if event == EVENT_TTS_TTFB_METRIC:
                    if isinstance(payload, int) and not self._audio_start_sent:
                        await self.send_tts_audio_start(request_id=request_id)
                        self._audio_start_sent = True
                        self._audio_start_monotonic = monotonic()
                        await self.send_tts_ttfb_metrics(
                            request_id=request_id,
                            ttfb_ms=payload,
                            extra_metadata={
                                "model": self.config.model,
                                "voice": self.config.voice,
                            },
                        )
                elif event == EVENT_TTS_RESPONSE:
                    if isinstance(payload, bytes) and payload:
                        await self._emit_audio(payload)
                        await asyncio.sleep(0)
                elif event == EVENT_TTS_END:
                    await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                    return
                elif event == EVENT_TTS_ERROR:
                    if (
                        isinstance(payload, SonioxTTSError)
                        and payload.error_type == "request_timeout"
                        and not self.client.text_end_sent
                    ):
                        if self.client:
                            await self.client.stop()
                        await self._finalize_request(
                            TTSAudioEndReason.REQUEST_END
                        )
                        return
                    error = self._vendor_error(payload)
                    if self.client:
                        await self.client.stop()
                    await self._finalize_request(
                        TTSAudioEndReason.ERROR,
                        error,
                    )
                    return
            if (
                request_id == self.current_request_id
                and not self._terminal_sent
            ):
                await self._finalize_request(
                    TTSAudioEndReason.ERROR,
                    ModuleError(
                        message="Soniox TTS stream ended without termination",
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )
        except Exception as exc:
            await self._finalize_request(
                TTSAudioEndReason.ERROR,
                ModuleError(
                    message=str(exc),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def _emit_audio(self, audio: bytes) -> None:
        frame_width = (
            self.synthesize_audio_channels()
            * self.synthesize_audio_sample_width()
        )
        combined = self._audio_alignment_buffer + audio
        valid_length = len(combined) - len(combined) % frame_width
        self._audio_alignment_buffer = combined[valid_length:]
        if valid_length == 0:
            return

        emitted = combined[:valid_length]
        if not self._audio_start_sent and self.current_request_id:
            await self.send_tts_audio_start(request_id=self.current_request_id)
            self._audio_start_sent = True
            self._audio_start_monotonic = monotonic()
        self.total_audio_bytes += len(emitted)
        self.metrics_add_recv_audio_chunks(emitted)
        await self._write_dump(emitted)
        await self.send_tts_audio_data(emitted)

    async def _finalize_request(
        self,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
    ) -> None:
        request_id = self.current_request_id
        if not request_id or self._terminal_sent:
            return
        self._terminal_sent = True
        self.current_stream_id = None
        self._audio_alignment_buffer = b""
        interval_ms = 0
        if self._audio_start_monotonic is not None:
            interval_ms = int(
                (monotonic() - self._audio_start_monotonic) * 1000
            )

        await self.send_tts_audio_end(
            request_id=request_id,
            request_event_interval_ms=interval_ms,
            request_total_audio_duration_ms=self._audio_duration_ms(),
            reason=reason,
        )
        recorder = self.recorder_map.get(request_id)
        if recorder:
            await recorder.flush()
        await self.finish_request(request_id, reason=reason, error=error)

    def _audio_duration_ms(self) -> int:
        bytes_per_second = (
            self.synthesize_audio_sample_rate()
            * self.synthesize_audio_channels()
            * self.synthesize_audio_sample_width()
        )
        return int(self.total_audio_bytes * 1000 / bytes_per_second)

    def _connection_error(
        self, exc: SonioxTTSConnectionException
    ) -> ModuleError:
        code = (
            ModuleErrorCode.FATAL_ERROR
            if exc.status_code in (401, 403)
            else ModuleErrorCode.NON_FATAL_ERROR
        )
        return ModuleError(
            message=exc.body,
            module=ModuleType.TTS,
            code=code,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(exc.status_code),
                message=exc.body,
            ),
        )

    def _vendor_error(self, payload: object) -> ModuleError:
        if isinstance(payload, SonioxTTSError):
            code = (
                ModuleErrorCode.FATAL_ERROR
                if payload.error_code in (401, 403)
                else ModuleErrorCode.NON_FATAL_ERROR
            )
            return ModuleError(
                message=payload.message,
                module=ModuleType.TTS,
                code=code,
                vendor_info=ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code=str(payload.error_code or payload.error_type),
                    message=payload.message,
                ),
            )
        return ModuleError(
            message=str(payload),
            module=ModuleType.TTS,
            code=ModuleErrorCode.NON_FATAL_ERROR,
            vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
        )

    async def _cancel_stream_task(self) -> None:
        task = self._stream_task
        self._stream_task = None
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _setup_recorder(self, request_id: str) -> None:
        if not self.config or not self.config.dump:
            return
        dump_path = self.config.dump_path or "/tmp"
        os.makedirs(dump_path, exist_ok=True)
        for old_request_id in list(self.recorder_map):
            if old_request_id == request_id:
                continue
            try:
                await self.recorder_map[old_request_id].flush()
            finally:
                del self.recorder_map[old_request_id]

        if request_id not in self.recorder_map:
            safe_request_id = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
            path = os.path.join(
                dump_path,
                f"soniox_dump_{safe_request_id}.pcm",
            )
            self.recorder_map[request_id] = PCMWriter(path)

    async def _write_dump(self, audio: bytes) -> None:
        if (
            not self.config
            or not self.config.dump
            or not self.current_request_id
        ):
            return
        recorder = self.recorder_map.get(self.current_request_id)
        if recorder:
            await recorder.write(audio)
