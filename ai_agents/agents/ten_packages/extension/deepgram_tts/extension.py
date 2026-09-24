#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from datetime import datetime
import os
import traceback

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleErrorVendorInfo,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from .config import DeepgramTTSConfig

from .deepgram_tts import (
    EVENT_TTS_END,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    EVENT_TTS_ERROR,
    DeepgramTTSClient,
    DeepgramTTSConnectionException,
)
from ten_runtime import AsyncTenEnv


class DeepgramTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: DeepgramTTSConfig | None = None
        self.client: DeepgramTTSClient | None = None
        self.current_request_id: str | None = None
        self.current_turn_id: int = -1
        self.sent_ts: datetime | None = None
        self.current_request_finished: bool = False
        self.total_audio_bytes: int = 0
        self._is_stopped: bool = False
        self.recorder_map: dict[str, PCMWriter] = {}
        self._audio_start_sent: bool = False

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json_str, _ = await self.ten_env.get_property_to_json("")

            if not config_json_str or config_json_str.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. "
                    "Required parameter 'api_key' is missing."
                )

            self.config = DeepgramTTSConfig.model_validate_json(config_json_str)
            self.config.update_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if not self.config.api_key:
                raise ValueError("API key is required")

            self.client = self._create_client(ten_env)
            await self.client.start()
            ten_env.log_debug("DeepgramTTS client initialized successfully")
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
        ten_env.log_debug("Extension stopping, rejecting new requests")

        if self.client:
            await self.client.stop()
            self.client = None

        for request_id, recorder in list(self.recorder_map.items()):
            try:
                await recorder.flush()
                ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: " f"{request_id}"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for "
                    f"request_id {request_id}: {e}"
                )

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def cancel_tts(self) -> None:
        self.current_request_finished = True
        if self.current_request_id:
            self.ten_env.log_debug(
                f"Cancelling request {self.current_request_id}"
            )
            if self.client:
                await self.client.cancel()
            await self._finalize_request(TTSAudioEndReason.INTERRUPTED)
        else:
            self.ten_env.log_warn("No current request, skipping cancel.")

    def vendor(self) -> str:
        return "deepgram"

    def synthesize_audio_sample_rate(self) -> int:
        if self.config is None:
            return 24000
        return self.config.sample_rate

    def _create_client(self, ten_env: AsyncTenEnv) -> DeepgramTTSClient:
        return DeepgramTTSClient(
            config=self.config,
            ten_env=ten_env,
        )

    async def _ensure_client(self) -> None:
        """Ensure client is connected, reconnecting if needed."""
        if self.client is None:
            self.ten_env.log_debug(
                "TTS client is not initialized, reconnecting..."
            )
            self.client = self._create_client(self.ten_env)
            await self.client.start()
            self.ten_env.log_debug("TTS client reconnected successfully.")

    async def _reconnect_client(self) -> None:
        """Destroy current client and reconnect immediately."""
        if self.client:
            await self.client.stop()
            self.client = None
        try:
            self.client = self._create_client(self.ten_env)
            await self.client.start()
            self.ten_env.log_debug("Client reconnected after error.")
        except Exception as e:
            self.ten_env.log_error(f"Immediate reconnect failed: {e}")
            self.client = None

    async def _finalize_request(
        self,
        reason: TTSAudioEndReason,
        error: ModuleError | None = None,
    ) -> None:
        """Send audio end, flush recorder, finish request."""
        if not self._audio_start_sent:
            await self.send_tts_audio_start(
                request_id=self.current_request_id,
            )
            self._audio_start_sent = True

        request_event_interval = self._current_request_interval_ms()
        duration_ms = self._calculate_audio_duration_ms()

        await self.send_tts_audio_end(
            request_id=self.current_request_id,
            request_event_interval_ms=request_event_interval,
            request_total_audio_duration_ms=duration_ms,
            reason=reason,
        )

        if self.current_request_id in self.recorder_map:
            await self.recorder_map[self.current_request_id].flush()

        await self.finish_request(
            request_id=self.current_request_id,
            reason=reason,
            error=error,
        )

        self.sent_ts = None
        self.ten_env.log_debug(
            f"Finalized request, reason: {reason}, "
            f"interval: {request_event_interval}ms, "
            f"duration: {duration_ms}ms"
        )

    async def request_tts(self, t: TTSTextInput) -> None:
        """Handle TTS requests."""
        try:
            self.ten_env.log_info(
                f"Requesting TTS for text: {t.text}, "
                f"text_input_end: {t.text_input_end} "
                f"request ID: {t.request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            await self._ensure_client()

            if t.request_id != self.current_request_id:
                self.ten_env.log_debug(
                    f"New TTS request with ID: {t.request_id}"
                )
                if self.client:
                    if self.current_request_id is not None:
                        await self.client.discard_pending()
                    self.client.reset_ttfb()
                self.current_request_id = t.request_id
                self.current_request_finished = False
                self.total_audio_bytes = 0
                self.sent_ts = None
                self._audio_start_sent = False
                if t.metadata is not None:
                    self.session_id = t.metadata.get("session_id", "")
                    self.current_turn_id = t.metadata.get("turn_id", -1)
                await self._setup_recorder(t.request_id)
            elif self.current_request_finished:
                self.ten_env.log_error(
                    f"Received a message for a finished "
                    f"request_id '{t.request_id}' with "
                    f"text_input_end=False."
                )
                return

            if t.text_input_end:
                self.ten_env.log_debug(
                    f"KEYPOINT finish session for "
                    f"request ID: {t.request_id}"
                )
                self.current_request_finished = True

            prepared_text = t.text.strip()
            text_to_send = (
                prepared_text if self.config.per_sentence_flush else t.text
            )

            if self._is_stopped:
                self.ten_env.log_debug(
                    f"TTS is stopped, skipping " f"request_id: {t.request_id}"
                )
                return

            has_text = (
                prepared_text != ""
                if self.config.per_sentence_flush
                else t.text != ""
            )
            if has_text or (
                t.text_input_end and not self.config.per_sentence_flush
            ):
                await self._process_tts_text(text_to_send, t)
            elif t.text_input_end:
                await self._finalize_request(TTSAudioEndReason.REQUEST_END)

        except DeepgramTTSConnectionException as e:
            await self._handle_connection_error(e)

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: "
                f"{traceback.format_exc()}. text: {t.text}"
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            await self._finalize_request(TTSAudioEndReason.ERROR, error=error)
            if isinstance(e, ConnectionRefusedError):
                await self._reconnect_client()

    async def _process_tts_text(self, text: str, t: TTSTextInput) -> None:
        """Process non-empty text through the TTS pipeline."""
        self.ten_env.log_debug(
            f"send_text_to_tts_server: {text} "
            f"of request_id: {t.request_id}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )
        if not t.text_input_end and not self.config.per_sentence_flush:
            data = self.client.get(text, flush=False)
        else:
            data = self.client.get(text)

        chunk_count = 0
        if self.sent_ts is None:
            self.sent_ts = datetime.now()

        async for data_msg, event_status in data:
            self.ten_env.log_debug(f"Received event_status: {event_status}")
            if event_status == EVENT_TTS_RESPONSE:
                if (
                    data_msg is not None
                    and isinstance(data_msg, bytes)
                    and len(data_msg) > 0
                ):
                    chunk_count += 1
                    self.total_audio_bytes += len(data_msg)
                    self.ten_env.log_info(
                        f"Received audio chunk "
                        f"#{chunk_count}, "
                        f"size: {len(data_msg)} bytes"
                    )
                    await self._write_dump(data_msg)
                    await self.send_tts_audio_data(data_msg)
                else:
                    self.ten_env.log_debug("Empty payload, ignoring")

            elif event_status == EVENT_TTS_TTFB_METRIC:
                if data_msg is not None and isinstance(data_msg, int):
                    # Overwrite sent_ts to audio-start time so that
                    # _current_request_interval_ms() measures streaming
                    # duration (first audio → last audio), not total
                    # request time. This matches the HTTP base class.
                    self.sent_ts = datetime.now()
                    ttfb = data_msg
                    await self.send_tts_audio_start(
                        request_id=self.current_request_id,
                    )
                    self._audio_start_sent = True
                    await self.send_tts_ttfb_metrics(
                        request_id=self.current_request_id,
                        ttfb_ms=ttfb,
                        extra_metadata={
                            "model": self.config.model,
                        },
                    )
                    self.ten_env.log_debug(
                        f"Sent TTS audio start and " f"TTFB metrics: {ttfb}ms"
                    )

            elif event_status == EVENT_TTS_END:
                if t.text_input_end:
                    self.ten_env.log_info(
                        f"Received final TTS_END event from Deepgram TTS "
                        f"for request_id: {t.request_id}"
                    )
                    await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                else:
                    self.ten_env.log_debug(
                        f"Received intermediate TTS_END event from "
                        f"Deepgram TTS for request_id: {t.request_id}"
                    )
                break

            elif event_status == EVENT_TTS_ERROR:
                error_msg = (
                    data_msg.decode("utf-8")
                    if isinstance(data_msg, bytes)
                    else str(data_msg)
                )
                self.ten_env.log_error(f"TTS_ERROR from Deepgram: {error_msg}")
                error = ModuleError(
                    message=error_msg,
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
                if t.text_input_end:
                    # Final chunk: surface error and
                    # finalize the request
                    await self._finalize_request(
                        TTSAudioEndReason.ERROR,
                        error=error,
                    )
                else:
                    # Non-final chunk: log only. The base
                    # class will send subsequent chunks for
                    # this request_id; errors on partial
                    # streaming are transient.
                    self.ten_env.log_warn(
                        f"Transient TTS error on non-final "
                        f"chunk for {t.request_id}: "
                        f"{error_msg}"
                    )
                break

        self.ten_env.log_debug(
            f"TTS processing completed, " f"total chunks: {chunk_count}"
        )

    async def _handle_connection_error(
        self, e: DeepgramTTSConnectionException
    ) -> None:
        """Handle Deepgram connection errors.

        Sends exactly one error event via _finalize_request.
        """
        self.ten_env.log_error(f"DeepgramTTSConnectionException: {e.body}")
        if e.status_code == 401:
            code = ModuleErrorCode.FATAL_ERROR
        else:
            code = ModuleErrorCode.NON_FATAL_ERROR

        error = ModuleError(
            message=e.body,
            module=ModuleType.TTS,
            code=code,
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(e.status_code),
                message=e.body,
            ),
        )
        await self._finalize_request(TTSAudioEndReason.ERROR, error=error)

    async def _setup_recorder(self, request_id: str) -> None:
        """Set up PCMWriter for a new request."""
        if not (self.config and self.config.dump):
            return
        # Clean up old PCMWriters
        for old_rid in [
            rid for rid in self.recorder_map.keys() if rid != request_id
        ]:
            try:
                await self.recorder_map[old_rid].flush()
                del self.recorder_map[old_rid]
                self.ten_env.log_debug(
                    f"Cleaned up old PCMWriter for " f"request_id: {old_rid}"
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Error cleaning up PCMWriter for "
                    f"request_id {old_rid}: {e}"
                )

        if request_id not in self.recorder_map:
            dump_file_path = os.path.join(
                self.config.dump_path,
                f"deepgram_dump_{request_id}.pcm",
            )
            self.recorder_map[request_id] = PCMWriter(dump_file_path)
            self.ten_env.log_debug(
                f"Created PCMWriter for request_id: "
                f"{request_id}, file: {dump_file_path}"
            )

    async def _write_dump(self, data: bytes) -> None:
        """Write audio data to dump file if enabled."""
        if (
            self.config
            and self.config.dump
            and self.current_request_id
            and self.current_request_id in self.recorder_map
        ):
            try:
                await self.recorder_map[self.current_request_id].write(data)
            except Exception as e:
                self.ten_env.log_error(f"Dump write failed: {e}")

    def _current_request_interval_ms(self) -> int:
        if not self.sent_ts:
            return 0
        return int((datetime.now() - self.sent_ts).total_seconds() * 1000)

    def _calculate_audio_duration_ms(self) -> int:
        if self.config is None:
            return 0
        bytes_per_sample = 2  # 16-bit PCM
        channels = 1  # Mono
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)
