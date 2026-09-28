from datetime import datetime
import os
import traceback

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_TRANSCRIPTS
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

from .config import XAITTSConfig
from .xai_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    XAITTSClient,
    XAITTSConnectionException,
)


# Per xAI TTS docs: a single request accepts at most 15000 characters.
MAX_REQUEST_TEXT_CHARS = 15000


class XAITTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: XAITTSConfig | None = None
        self.client: XAITTSClient | None = None
        self.current_request_id: str | None = None
        self.current_turn_id = -1
        self.sent_ts: datetime | None = None
        self.current_request_finished = False
        self.total_audio_bytes = 0
        self._is_stopped = False
        self.recorder_map: dict[str, PCMWriter] = {}
        self._audio_start_sent = False
        self._request_text_length = 0
        self._audio_start_timestamp_ms = 0
        self._first_audio_chunk_ts: datetime | None = None
        self._last_audio_chunk_ts: datetime | None = None

    @staticmethod
    def _contains_spoken_content(text: str) -> bool:
        return any(char.isalnum() for char in text)

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json_str, _ = await self.ten_env.get_property_to_json("")
            if not config_json_str or config_json_str.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. Required api_key is missing."
                )
            self.config = XAITTSConfig.model_validate_json(config_json_str)
            self.config.update_params()
            self.config.validate_config()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.client = self._create_client(ten_env)
            await self.client.start()
        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        self._is_stopped = True
        if self.client:
            await self.client.stop()
            self.client = None
        for recorder in list(self.recorder_map.values()):
            try:
                await recorder.flush()
            except Exception as e:
                ten_env.log_error(f"Error flushing PCMWriter: {e}")
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)

    async def cancel_tts(self) -> None:
        self.current_request_finished = True
        self._request_text_length = 0
        if self.current_request_id:
            if self.client:
                await self.client.cancel()
            await self._finalize_request(TTSAudioEndReason.INTERRUPTED)

    def vendor(self) -> str:
        return "xai"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 24000

    def synthesize_audio_channels(self) -> int:
        return 1

    def synthesize_audio_sample_width(self) -> int:
        return 2

    def _create_client(self, ten_env: AsyncTenEnv) -> XAITTSClient:
        return XAITTSClient(config=self.config, ten_env=ten_env)

    async def _reconnect_client(self) -> None:
        if self.client:
            await self.client.stop()
            self.client = None
        self.client = self._create_client(self.ten_env)
        await self.client.start()

    async def _finalize_request(
        self, reason: TTSAudioEndReason, error: ModuleError | None = None
    ) -> None:
        if not self._audio_start_sent:
            await self.send_tts_audio_start(request_id=self.current_request_id)
            self._audio_start_sent = True
        request_event_interval = self._calculate_request_event_interval_ms()
        duration_ms = self._calculate_audio_duration_ms()
        await self.send_tts_audio_end(
            request_id=self.current_request_id,
            request_event_interval_ms=request_event_interval,
            request_total_audio_duration_ms=duration_ms,
            reason=reason,
        )
        await self.send_usage_metrics(self.current_request_id or "")
        recorder = (
            self.recorder_map.pop(self.current_request_id, None)
            if self.current_request_id
            else None
        )
        if recorder is not None:
            try:
                await recorder.flush()
            except Exception as e:
                self.ten_env.log_error(f"Error flushing PCMWriter: {e}")
        await self.finish_request(
            request_id=self.current_request_id,
            reason=reason,
            error=error,
        )
        self.sent_ts = None
        self._audio_start_timestamp_ms = 0
        self._first_audio_chunk_ts = None
        self._last_audio_chunk_ts = None

    def _calculate_audio_duration_ms(self) -> int:
        bytes_per_sample = self.synthesize_audio_sample_width()
        channels = self.synthesize_audio_channels()
        if bytes_per_sample <= 0 or channels <= 0:
            return 0
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)

    def _calculate_request_event_interval_ms(self) -> int:
        if (
            self._first_audio_chunk_ts is None
            or self._last_audio_chunk_ts is None
        ):
            return 0
        return int(
            (
                self._last_audio_chunk_ts - self._first_audio_chunk_ts
            ).total_seconds()
            * 1000
        )

    async def request_tts(self, t: TTSTextInput) -> None:
        try:
            await self._ensure_client()

            if t.request_id != self.current_request_id:
                if self.client:
                    self.client.reset_ttfb()
                self.current_request_id = t.request_id
                self.current_request_finished = False
                self.total_audio_bytes = 0
                self.sent_ts = None
                self._audio_start_sent = False
                self._request_text_length = 0
                self._audio_start_timestamp_ms = 0
                self._first_audio_chunk_ts = None
                self._last_audio_chunk_ts = None
                if t.metadata is not None:
                    self.session_id = t.metadata.get("session_id", "")
                    self.current_turn_id = t.metadata.get("turn_id", -1)
                await self._setup_recorder(t.request_id)
            elif self.current_request_finished:
                self.ten_env.log_error(
                    f"Received text for finished request_id '{t.request_id}'"
                )
                return

            prepared_text = t.text.strip()
            if (
                t.text_input_end
                and prepared_text
                and self._request_text_length == 0
                and not self._contains_spoken_content(prepared_text)
            ):
                error = ModuleError(
                    message="xAI TTS input must contain spoken text",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
                await self.send_tts_error(
                    request_id=t.request_id,
                    error=error,
                )
                await self.finish_request(
                    request_id=t.request_id,
                    reason=TTSAudioEndReason.ERROR,
                    error=error,
                )
                self.current_request_finished = True
                self._request_text_length = 0
                self.total_audio_bytes = 0
                self.sent_ts = None
                self._audio_start_sent = False
                self._first_audio_chunk_ts = None
                self._last_audio_chunk_ts = None
                return
            if prepared_text:
                if (
                    self._request_text_length + len(prepared_text)
                    > MAX_REQUEST_TEXT_CHARS
                ):
                    raise ValueError(
                        f"xAI TTS text exceeds "
                        f"{MAX_REQUEST_TEXT_CHARS} characters"
                    )
                self._request_text_length += len(prepared_text)
                self.metrics_add_input_characters(len(prepared_text))
                self.metrics_add_output_characters(len(prepared_text))

            if self._is_stopped:
                return

            if t.text_input_end:
                self.current_request_finished = True

            if not prepared_text:
                if t.text_input_end:
                    await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                return

            await self._process_tts_text(prepared_text, t)
        except XAITTSConnectionException as e:
            await self._handle_connection_error(e, t.text_input_end)
        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}. text: {t.text}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            if t.text_input_end:
                await self._finalize_request(
                    TTSAudioEndReason.ERROR, error=error
                )
            else:
                await self.send_tts_error(
                    request_id=t.request_id,
                    error=error,
                )
            await self._reconnect_client()

    async def _process_tts_text(self, text: str, t: TTSTextInput) -> None:
        if self.sent_ts is None:
            self.sent_ts = datetime.now()

        async for data_msg, event_status in self.client.get(text):
            self.ten_env.log_debug(f"Received event_status: {event_status}")
            if event_status == EVENT_TTS_RESPONSE:
                if data_msg and isinstance(data_msg, bytes):
                    now = datetime.now()
                    if self._first_audio_chunk_ts is None:
                        self._first_audio_chunk_ts = now
                    self._last_audio_chunk_ts = now
                    chunk_timestamp_ms = (
                        self._get_next_audio_chunk_timestamp_ms()
                    )
                    self.metrics_add_recv_audio_chunks(data_msg)
                    self.total_audio_bytes += len(data_msg)
                    await self._write_dump(data_msg)
                    await self.send_tts_audio_data(
                        data_msg, timestamp=chunk_timestamp_ms
                    )
            elif event_status == EVENT_TTS_TTFB_METRIC:
                if isinstance(data_msg, int):
                    await self.send_tts_audio_start(
                        request_id=self.current_request_id
                    )
                    self._audio_start_sent = True
                    await self.send_tts_ttfb_metrics(
                        request_id=self.current_request_id,
                        ttfb_ms=data_msg,
                        extra_metadata={
                            "voice_id": self.config.voice_id,
                            "codec": self.config.codec,
                        },
                    )
            elif event_status == EVENT_TTS_END:
                if t.text_input_end:
                    await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                break
            elif event_status == EVENT_TTS_ERROR:
                error_message = (
                    data_msg.decode("utf-8", errors="ignore")
                    if isinstance(data_msg, bytes)
                    else "Unknown xAI TTS error"
                )
                error = ModuleError(
                    message=error_message,
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
                if t.text_input_end:
                    await self._finalize_request(
                        TTSAudioEndReason.ERROR, error=error
                    )
                else:
                    self.ten_env.log_warn(
                        f"Transient TTS error on non-final chunk for "
                        f"{t.request_id}: {error_message}"
                    )
                break

    def _get_next_audio_chunk_timestamp_ms(self) -> int:
        if self._audio_start_timestamp_ms <= 0:
            self._audio_start_timestamp_ms = int(
                datetime.now().timestamp() * 1000
            )
        return (
            self._audio_start_timestamp_ms + self._calculate_audio_duration_ms()
        )

    async def _handle_connection_error(
        self, e: XAITTSConnectionException, text_input_end: bool
    ) -> None:
        error_code = (
            ModuleErrorCode.FATAL_ERROR
            if e.status_code in {401, 403}
            else ModuleErrorCode.NON_FATAL_ERROR
        )
        error = ModuleError(
            message=str(e),
            module=ModuleType.TTS,
            code=error_code,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(e.status_code),
                message=e.body,
            ),
        )
        if text_input_end:
            await self._finalize_request(TTSAudioEndReason.ERROR, error=error)
        else:
            await self.send_tts_error(
                request_id=self.current_request_id or "",
                error=error,
            )

    async def _setup_recorder(self, request_id: str) -> None:
        if self.config and self.config.dump:
            dump_path = os.path.join(
                self.config.dump_path, f"{request_id}_xai_tts_out.pcm"
            )
            os.makedirs(os.path.dirname(dump_path), exist_ok=True)
            self.recorder_map[request_id] = PCMWriter(dump_path)

    async def _write_dump(self, data_msg: bytes) -> None:
        if self.current_request_id in self.recorder_map:
            await self.recorder_map[self.current_request_id].write(data_msg)

    async def _ensure_client(self) -> None:
        if self.client is None:
            self.client = self._create_client(self.ten_env)
            await self.client.start()
            return

        if self.client.is_connected():
            return

        await self._reconnect_client()
