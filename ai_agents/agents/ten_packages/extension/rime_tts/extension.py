#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime
import os
import time
import traceback

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleErrorVendorInfo,
    ModuleVendorException,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT
from .config import RimeTTSConfig

from .rime_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    RimeTTSClient,
)
from ten_runtime import AsyncTenEnv


class RimeTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: RimeTTSConfig = None
        self.client: RimeTTSClient = None
        self.current_request_id: str = None
        self.current_turn_id: int = -1
        self.stop_event: asyncio.Event = None
        self.msg_polling_task: asyncio.Task = None
        self.recorder: PCMWriter = None
        self.sent_tts: bool = False
        self.request_start_ts: datetime | None = None
        self.total_audio_bytes: int = 0
        self.response_msgs = asyncio.Queue[tuple[int, bytes | int]]()
        self.recorder_map: dict[str, PCMWriter] = {}
        self.last_completed_request_id: str | None = None
        self.last_completed_has_reset_synthesizer = True
        self.current_request_finished: bool = True

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_debug("on_init")

            config_json, _ = await self.ten_env.get_property_to_json("")
            if not config_json or config_json.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. Required parameter 'key' is missing."
                )

            self.config = RimeTTSConfig.model_validate_json(config_json)
            self.config.update_params()

            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if not self.config.api_key:
                raise ValueError("API key is required")

            # Create client (connection management will be handled automatically)
            self.client = RimeTTSClient(
                self.config,
                self.ten_env,
                self.vendor(),
                self.response_msgs,
                self.on_connecting,
                self.on_connected,
                self.on_disconnected,
            )
            self.msg_polling_task = asyncio.create_task(self._loop())
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
        if self.client:
            await self.client.close()

        if self.msg_polling_task:
            self.msg_polling_task.cancel()
            try:
                await self.msg_polling_task
            except asyncio.CancelledError:
                ten_env.log_debug("Message polling task cancelled.")

        for request_id, recorder in self.recorder_map.items():
            try:
                await recorder.flush()
                ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except asyncio.CancelledError:
                # CancelledError is expected during shutdown, just log and continue
                ten_env.log_debug(
                    f"PCMWriter flush cancelled for request_id: {request_id} (normal during shutdown)"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    def vendor(self) -> str:
        return "rime"

    def vendor_metadata(self) -> dict:
        if self.config is None:
            return {}

        metadata = {
            "key": self.config.api_key,
            "url": self.config.base_url,
            "model": self.config.params.get("modelId", ""),
            "lang": self.config.params.get("lang", ""),
            "api_key": self.config.api_key,
        }
        return {key: value for key, value in metadata.items() if value}

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sampling_rate

    def synthesize_audio_channels(self) -> int:
        """Return number of audio channels"""
        return 1  # Mono

    def synthesize_audio_sample_width(self) -> int:
        """Return sample width in bytes"""
        return 2  # 16-bit PCM

    async def _loop(self) -> None:
        while True:
            try:
                event, data = await self.client.response_msgs.get()

                if event == EVENT_TTS_RESPONSE:  # Audio data event
                    if data is not None and isinstance(data, bytes):
                        self.ten_env.log_debug(
                            f"Received audio data for request ID: {self.current_request_id}, audio_data_len: {len(data)}"
                        )

                        if (
                            self.config.dump
                            and self.current_request_id
                            and self.current_request_id in self.recorder_map
                        ):
                            asyncio.create_task(
                                self.recorder_map[
                                    self.current_request_id
                                ].write(data)
                            )
                        # Accumulate audio bytes instead of duration to avoid precision loss
                        self.total_audio_bytes += len(data)
                        # Track audio metrics
                        self.metrics_add_recv_audio_chunks(data)
                        await self.send_tts_audio_data(data)
                    else:
                        self.ten_env.log_debug(
                            "Received empty payload for TTS response"
                        )
                elif event == EVENT_TTS_TTFB_METRIC:
                    if data is not None and isinstance(data, int):
                        self.request_start_ts = datetime.now()
                        ttfb = data
                        await self.send_tts_audio_start(
                            request_id=self.current_request_id,
                        )
                        extra_metadata = {
                            "speaker": self.config.params.get("speaker", ""),
                            "modelId": self.config.params.get("modelId", ""),
                        }
                        await self.send_tts_ttfb_metrics(
                            request_id=self.current_request_id,
                            ttfb_ms=ttfb,
                            extra_metadata=extra_metadata,
                        )

                        self.ten_env.log_debug(
                            f"Sent TTS audio start and TTFB metrics: {ttfb}ms"
                        )
                elif event == EVENT_TTS_END:
                    self.ten_env.log_debug(
                        f"Session finished for request ID: {self.current_request_id}"
                    )
                    await self._handle_tts_audio_end()
                    if self.stop_event:
                        self.stop_event.set()
                        self.stop_event = None
                elif event == EVENT_TTS_ERROR:
                    error_msg = (
                        data.decode() if isinstance(data, bytes) else str(data)
                    )
                    self.ten_env.log_error(
                        f"TTS error for request ID {self.current_request_id}: {error_msg}"
                    )
                    error = ModuleError(
                        message=error_msg,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    )
                    if self.current_request_finished:
                        await self._handle_tts_audio_end(
                            reason=TTSAudioEndReason.ERROR, error=error
                        )
                    else:
                        await self.send_tts_error(
                            request_id=self.current_request_id or "",
                            error=error,
                        )
                    if self.stop_event:
                        self.stop_event.set()
                        self.stop_event = None

            except Exception:
                self.ten_env.log_error(
                    f"Error in _loop: {traceback.format_exc()}"
                )
                if self.stop_event:
                    self.stop_event.set()
                    self.stop_event = None

    async def _handle_tts_audio_end(
        self,
        reason: TTSAudioEndReason = TTSAudioEndReason.REQUEST_END,
        error: ModuleError | None = None,
    ) -> None:
        """Centralized method for properly ending a TTS request."""
        if self.request_start_ts is not None:
            request_event_interval = int(
                (datetime.now() - self.request_start_ts).total_seconds() * 1000
            )

            # Flush PCMWriter for current request to ensure dump file is written
            if (
                self.config.dump
                and self.current_request_id
                and self.current_request_id in self.recorder_map
            ):
                try:
                    await self.recorder_map[self.current_request_id].flush()
                    self.ten_env.log_debug(
                        f"Flushed PCMWriter for request_id: {self.current_request_id}"
                    )
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error flushing PCMWriter for request_id {self.current_request_id}: {e}"
                    )

            # Calculate audio duration from total bytes (like google_tts)
            request_total_audio_duration_ms = (
                self._calculate_audio_duration_ms()
            )

            # Send TTS audio end event
            await self.send_tts_audio_end(
                request_id=self.current_request_id,
                request_event_interval_ms=request_event_interval,
                request_total_audio_duration_ms=request_total_audio_duration_ms,
                reason=reason,
            )

            self.ten_env.log_debug(
                f"Sent TTS audio end for request ID: {self.current_request_id}, "
                f"interval: {request_event_interval}ms, duration: {request_total_audio_duration_ms}ms, "
                f"reason: {reason}"
            )

            # Send usage metrics
            await self.send_usage_metrics(self.current_request_id)

            # Finish request to complete state transition
            await self.finish_request(
                request_id=self.current_request_id,
                reason=reason,
                error=error,
            )

            # Clear current request
            self.current_request_id = None

    async def request_tts(self, t: TTSTextInput) -> None:
        """
        Override this method to handle TTS requests.
        This is called when the TTS request is made.
        """
        try:
            self.ten_env.log_info(
                f"Requesting TTS for text: {t.text}, text_input_end: {t.text_input_end} request ID: {t.request_id}",
            )

            self.ten_env.log_debug(
                f"current_request_id: {self.current_request_id}, new request_id: {t.request_id}"
            )
            if self.client is None:
                self.client = RimeTTSClient(
                    self.config, self.ten_env, self.vendor(), self.response_msgs
                )
                self.ten_env.log_debug("TTS client reinitialized successfully.")

            if (
                self.last_completed_request_id
                and t.request_id == self.last_completed_request_id
            ):
                error_msg = f"Request ID {t.request_id} has already been completed (last completed: {self.last_completed_request_id})"
                self.ten_env.log_warn(error_msg)
                await self.send_tts_error(
                    request_id=t.request_id,
                    error=ModuleError(
                        message=error_msg,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )
                return
            if t.request_id != self.current_request_id:
                self.ten_env.log_debug(
                    f"New TTS request with ID: {t.request_id}"
                )
                if not self.last_completed_has_reset_synthesizer:
                    await self.client.reset_synthesizer()
                self.last_completed_has_reset_synthesizer = False

                self.current_request_id = t.request_id
                self.current_request_finished = False
                if t.metadata is not None:
                    self.current_turn_id = t.metadata.get("turn_id", -1)
                self.request_start_ts = datetime.now()
                self.total_audio_bytes = 0
                self.sent_tts = False

                if self.config.dump:
                    old_request_ids = [
                        rid
                        for rid in self.recorder_map.keys()
                        if rid != t.request_id
                    ]
                    for old_rid in old_request_ids:
                        try:
                            await self.recorder_map[old_rid].flush()
                            del self.recorder_map[old_rid]
                            self.ten_env.log_debug(
                                f"Cleaned up old PCMWriter for request_id: {old_rid}"
                            )
                        except Exception as e:
                            self.ten_env.log_error(
                                f"Error cleaning up PCMWriter for request_id {old_rid}: {e}"
                            )

                    # 创建新的 PCMWriter
                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"rime_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_debug(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )

            self.sent_tts = True
            # Track character metrics
            self.metrics_add_output_characters(len(t.text))
            if t.text:
                await self.send_tts_request_metrics(
                    request_id=t.request_id,
                    request_time_ms=int(time.time() * 1000),
                    request_text=t.text,
                )
            await self.client.send_text(t)
            if t.text_input_end:
                self.current_request_finished = True
                self.ten_env.log_debug(
                    f"text_input_end received for request ID: {t.request_id}"
                )

                if (
                    self.request_start_ts
                    and t.text.strip() == ""
                    and not self.sent_tts
                ):
                    # Empty text with text_input_end - finish immediately
                    await self._handle_tts_audio_end()
                    self.ten_env.log_debug(
                        f"Sent TTS audio end event, text is empty for request ID: {t.request_id}"
                    )

                self.last_completed_request_id = t.request_id
                self.ten_env.log_info(
                    f"Updated last completed request_id to: {t.request_id}"
                )

                if self.sent_tts:
                    self.stop_event = asyncio.Event()
                    await self.stop_event.wait()
                    # session finished, connection will be re-established for next request
                    if not self.last_completed_has_reset_synthesizer:
                        await self.client.reset_synthesizer()
                        self.last_completed_has_reset_synthesizer = True
                else:
                    self.ten_env.log_debug("Skipping stop_event")

        except ModuleVendorException as e:
            self.sent_tts = False
            self.ten_env.log_error(
                f"ModuleVendorException in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=e.error,
            )
            if self.current_request_finished or t.text_input_end:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )
        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            if self.current_request_finished or t.text_input_end:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )

    async def cancel_tts(self) -> None:
        if self.current_request_id:
            self.ten_env.log_debug(
                f"Current request {self.current_request_id} is being cancelled. Sending INTERRUPTED."
            )
            if self.client:
                self.client.cancel()
                self.last_completed_has_reset_synthesizer = True

            # If there's a waiting stop_event, set it to release request_tts waiting
            if self.stop_event:
                self.stop_event.set()
                self.stop_event = None

            await self._handle_tts_audio_end(TTSAudioEndReason.INTERRUPTED)
            self.current_request_finished = True
        else:
            self.ten_env.log_warn(
                "No current request found, skipping TTS cancellation."
            )

    def _calculate_audio_duration_ms(self) -> int:
        """
        Calculate audio duration in milliseconds from total_audio_bytes.
        This method calculates duration once from total bytes to avoid precision loss
        from multiple accumulations (like google_tts implementation).
        """
        if self.config is None or self.total_audio_bytes == 0:
            return 0

        bytes_per_sample = self.synthesize_audio_sample_width()
        channels = self.synthesize_audio_channels()
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)
